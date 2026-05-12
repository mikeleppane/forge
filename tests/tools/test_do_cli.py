"""Tests for the ``forge-do`` Bash CLI surface (``tools.do_cli``).

The CLI is a thin shell over :func:`tools.routing.seed_routed_feature` so
agent callers of ``/forge:do`` can replace the multi-line Python heredoc
in the skill's STOP block with a single, mechanical Bash invocation:

    forge-do --idea "<idea>" --tier <focused|standard|full> \\
             --rationale "<one_sentence>" [--proposed-tier ...] \\
             [--constitution-present] [--research]

These tests pin down the CLI's exit codes, dispatch-literal rendering,
secrets warning, and the focused+``--research`` refusal path.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from tools.do_cli import main

# Slug shape required for the seeded folder: ``YYYY-MM-DD-<slug>``.
# The CLI MUST NOT improvise the slug; ``slug_from_idea`` is the only
# producer, so the folder name always matches this pattern.
_FEATURE_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]{2,}$")


def _read_state(folder: Path) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    return payload


def _seeded_folder(tmp_path: Path) -> Path:
    """Return the single seeded feature folder under ``tmp_path``."""
    features_dir = tmp_path / ".forge" / "features"
    assert features_dir.is_dir(), "seed must create .forge/features/"
    children = list(features_dir.iterdir())
    assert len(children) == 1, f"expected exactly one seeded feature, got {children}"
    return children[0]


def test_do_cli_seeds_focused_tier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Focused tier seed: exit 0, folder exists, state validates."""
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--idea",
            "test idea",
            "--tier",
            "focused",
            "--rationale",
            "test rationale",
        ]
    )

    assert rc == 0
    folder = _seeded_folder(tmp_path)
    payload = _read_state(folder)
    assert payload["tier"] == "focused"
    assert payload["current_phase"] == "spec"


def test_do_cli_seeds_full_tier_with_research_default_off(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full tier seeds ``current_phase='refine'`` even without --research."""
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--idea",
            "build a payment processor",
            "--tier",
            "full",
            "--rationale",
            "multi-capability architectural feature",
        ]
    )

    assert rc == 0
    folder = _seeded_folder(tmp_path)
    payload = _read_state(folder)
    assert payload["tier"] == "full"
    assert payload["current_phase"] == "refine"


def test_do_cli_seeds_standard_tier_with_research_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Standard + --research seeds ``current_phase='research'``."""
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--idea",
            "evaluate auth providers",
            "--tier",
            "standard",
            "--rationale",
            "needs comparative research first",
            "--research",
        ]
    )

    assert rc == 0
    folder = _seeded_folder(tmp_path)
    payload = _read_state(folder)
    assert payload["tier"] == "standard"
    assert payload["current_phase"] == "research"


def test_do_cli_refuses_focused_plus_research(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--tier focused --research`` exits 1 BEFORE any disk mutation."""
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--idea",
            "small focused thing",
            "--tier",
            "focused",
            "--rationale",
            "single capability",
            "--research",
        ]
    )

    assert rc == 1
    captured = capsys.readouterr()
    assert "escalates to standard tier" in captured.err
    # No seed must have happened.
    assert not (tmp_path / ".forge" / "features").exists()


def test_do_cli_seeded_path_is_canonical_yyyy_mm_dd_slug(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The seeded folder name must match ``YYYY-MM-DD-<slug>`` exactly."""
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--idea",
            "add caching layer",
            "--tier",
            "focused",
            "--rationale",
            "perf improvement",
        ]
    )

    assert rc == 0
    folder = _seeded_folder(tmp_path)
    assert _FEATURE_ID_RE.match(folder.name), f"folder name {folder.name!r} not canonical"


def test_do_cli_next_dispatch_literal_for_focused_tier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Focused tier prints ``Next: /forge:spec --feature <id>``."""
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--idea",
            "add caching layer",
            "--tier",
            "focused",
            "--rationale",
            "perf improvement",
        ]
    )

    assert rc == 0
    folder = _seeded_folder(tmp_path)
    captured = capsys.readouterr()
    assert f"Next: /forge:spec --feature {folder.name}" in captured.out


def test_do_cli_next_dispatch_literal_for_full_tier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Full tier prints ``Next: /forge:refine --feature <id>``."""
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--idea",
            "build payment processor",
            "--tier",
            "full",
            "--rationale",
            "multi-capability architectural feature",
        ]
    )

    assert rc == 0
    folder = _seeded_folder(tmp_path)
    captured = capsys.readouterr()
    assert f"Next: /forge:refine --feature {folder.name}" in captured.out


def test_do_cli_emits_secrets_warning_to_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The secrets warning lands on stderr before any disk write."""
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "--idea",
            "add caching layer",
            "--tier",
            "focused",
            "--rationale",
            "perf improvement",
        ]
    )

    assert rc == 0
    captured = capsys.readouterr()
    assert (
        "sensitive content (tokens, passwords) discouraged — text is persisted to "
        "state.json.routing.idea verbatim"
    ) in captured.err


def test_do_cli_helper_refusal_exits_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pre-existing feature folder triggers helper refusal → exit 1."""
    monkeypatch.chdir(tmp_path)

    # Seed once successfully.
    rc1 = main(
        [
            "--idea",
            "add caching layer",
            "--tier",
            "focused",
            "--rationale",
            "perf improvement",
        ]
    )
    assert rc1 == 0
    capsys.readouterr()  # clear captured streams

    # Same idea + same date → collision on the second call.
    rc2 = main(
        [
            "--idea",
            "add caching layer",
            "--tier",
            "focused",
            "--rationale",
            "perf improvement",
        ]
    )
    captured = capsys.readouterr()

    assert rc2 == 1
    assert "feature folder already exists" in captured.err
