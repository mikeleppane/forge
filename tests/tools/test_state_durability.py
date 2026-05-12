"""Regression tests for state.json atomicity, locking, and concurrency.

Pins the durability contract:
- ``write_state`` routes exclusively through ``_atomic_write_json``
  (tempfile + ``fsync`` + ``os.replace`` + parent-directory ``fsync``).
- A mid-write fault leaves ``state.json`` byte-identical to its pre-call
  snapshot and removes the partial tempfile.
- ``state_lock`` is non-re-entrant and refuses on native Win32.
- Concurrent processes calling ``record_commit`` each land their entry;
  no commit is silently dropped.
- The on-disk module source contains no direct ``Path.write_text`` call
  against a ``state.json`` payload outside ``_atomic_write_json``.
"""

from __future__ import annotations

import contextlib
import multiprocessing as mp
import os
import re
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from tools import state
from tools.routing import seed_routed_feature

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "state.schema.json"


def _state_path(folder: Path) -> Path:
    return folder / "state.json"


def _seed_feature(repo: Path, idea: str = "durability probe") -> Path:
    return seed_routed_feature(
        repo,
        idea=idea,
        final_tier="focused",
        today=date(2026, 5, 12),
    )


def test_write_state_routes_through_atomic_helper(tmp_path: Path) -> None:
    folder = _seed_feature(tmp_path)
    sp = _state_path(folder)

    pre_bytes = sp.read_bytes()
    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    payload["routing"] = {**payload["routing"], "rationale": "atomic round-trip"}

    with patch.object(state, "_atomic_write_json", wraps=state._atomic_write_json) as spy:
        state.write_state(sp, payload, schema_path=SCHEMA_PATH)

    spy.assert_called_once()
    assert sp.read_bytes() != pre_bytes


def test_module_source_has_no_direct_state_write_text(tmp_path: Path) -> None:
    source = (REPO_ROOT / "tools" / "state.py").read_text(encoding="utf-8")
    # Any ``path.write_text`` call against a JSON-shaped payload from
    # tools.state outside the atomic helper would re-introduce the
    # non-atomic write that this bundle replaces.
    bad_pattern = re.compile(r"\bpath\.write_text\(json\.dumps")
    assert bad_pattern.search(source) is None, (
        "tools.state must not call path.write_text(json.dumps(...)) directly — "
        "route through _atomic_write_json instead."
    )


def test_mid_write_fsync_failure_leaves_state_untouched(tmp_path: Path) -> None:
    folder = _seed_feature(tmp_path)
    sp = _state_path(folder)
    pre_bytes = sp.read_bytes()

    real_fsync = os.fsync
    fsync_calls = {"count": 0}

    def flaky_fsync(fd: int) -> None:
        fsync_calls["count"] += 1
        if fsync_calls["count"] == 1:
            raise OSError("simulated disk-full mid-write")
        real_fsync(fd)

    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    payload["routing"] = {**payload["routing"], "rationale": "should not land"}

    with patch.object(os, "fsync", new=flaky_fsync), pytest.raises(OSError, match="simulated"):
        state.write_state(sp, payload, schema_path=SCHEMA_PATH)

    assert sp.read_bytes() == pre_bytes
    leftover = [p.name for p in folder.iterdir() if p.name.startswith(".state-")]
    assert leftover == [], f"tempfile leaked after mid-write failure: {leftover}"


def test_atomic_write_cleans_up_tempfile_on_replace_failure(tmp_path: Path) -> None:
    folder = _seed_feature(tmp_path)
    sp = _state_path(folder)
    pre_bytes = sp.read_bytes()

    def broken_replace(self: Path, target: str | Path) -> None:
        raise OSError("simulated cross-device rename")

    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    payload["routing"] = {**payload["routing"], "rationale": "should not land"}

    with patch.object(Path, "replace", new=broken_replace), pytest.raises(OSError):
        state.write_state(sp, payload, schema_path=SCHEMA_PATH)

    assert sp.read_bytes() == pre_bytes
    leftover = [p.name for p in folder.iterdir() if p.name.startswith(".state-")]
    assert leftover == []


def test_state_lock_is_non_reentrant(tmp_path: Path) -> None:
    folder = _seed_feature(tmp_path)
    sp = _state_path(folder)

    with (
        state.state_lock(sp),
        pytest.raises(RuntimeError, match="non-re-entrant"),
        state.state_lock(sp),
    ):
        pytest.fail("nested state_lock acquisition should have raised")


def test_state_lock_refuses_on_native_win32(tmp_path: Path) -> None:
    folder = _seed_feature(tmp_path)
    sp = _state_path(folder)

    with (
        patch("tools.state.sys.platform", "win32"),
        pytest.raises(state.LockingNotSupportedError, match="WSL"),
        state.state_lock(sp),
    ):
        pytest.fail("state_lock should refuse on native win32")


def test_locking_not_supported_error_subclasses_state_error() -> None:
    assert issubclass(state.LockingNotSupportedError, state.StateError)


def test_record_commit_docstring_describes_locked_atomic_contract() -> None:
    doc = state.record_commit.__doc__ or ""
    assert "state_lock" in doc, "record_commit docstring must reference state_lock"
    assert "_atomic_write_json" in doc, "record_commit docstring must reference _atomic_write_json"


def _record_commit_worker(state_path_str: str, sha: str) -> None:
    """Module-level worker for the multiprocess concurrency test."""
    state.record_commit(
        Path(state_path_str),
        sha=sha,
        phase="spec",
        subject=f"slot {sha}",
        schema_path=SCHEMA_PATH,
    )


@pytest.mark.smoke
def test_concurrent_record_commit_lands_every_entry(tmp_path: Path) -> None:
    folder = _seed_feature(tmp_path)
    sp = _state_path(folder)

    shas = [f"abc{i:04x}1234567" for i in range(8)]
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=_record_commit_worker, args=(str(sp), sha)) for sha in shas]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0, f"worker exited {p.exitcode}"

    payload: dict[str, Any] = state.read_state(sp, schema_path=SCHEMA_PATH)
    landed = {entry["sha"] for entry in payload["commits"]}
    assert landed == set(shas)
    assert len(payload["commits"]) == len(shas)


def test_state_lock_releases_on_exception(tmp_path: Path) -> None:
    folder = _seed_feature(tmp_path)
    sp = _state_path(folder)

    with contextlib.suppress(ZeroDivisionError), state.state_lock(sp):
        raise ZeroDivisionError

    # If the lock leaked, this second acquisition would raise RuntimeError.
    with state.state_lock(sp):
        pass
