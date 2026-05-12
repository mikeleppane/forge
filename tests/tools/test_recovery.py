"""Regression tests for tools.recovery — audited force-override."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tools import state
from tools.recovery import RecoveryError, recover_force_start_phase
from tools.routing import seed_routed_feature

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "state.schema.json"


def _seed(tmp_path: Path) -> Path:
    return seed_routed_feature(
        tmp_path,
        idea="recovery probe",
        final_tier="focused",
        today=date(2026, 5, 12),
    )


def test_recovery_appends_decisions_entry(tmp_path: Path) -> None:
    folder = _seed(tmp_path)
    decisions = folder / "decisions.md"
    pre = decisions.read_text(encoding="utf-8") if decisions.exists() else ""

    recover_force_start_phase(
        folder,
        phase="execute",
        reason="manual rewind after a botched merge",
        today=date(2026, 5, 12),
        schema_path=SCHEMA_PATH,
    )

    post = decisions.read_text(encoding="utf-8")
    appended = post[len(pre) :]
    assert "Forced phase start: execute" in appended
    assert "manual rewind after a botched merge" in appended
    assert "2026-05-12" in appended


def test_recovery_advances_phase(tmp_path: Path) -> None:
    folder = _seed(tmp_path)

    payload = recover_force_start_phase(
        folder,
        phase="verify",
        reason="reproduce a verify-only flake",
        schema_path=SCHEMA_PATH,
    )
    assert payload["current_phase"] == "verify"
    assert payload["phases"]["verify"]["status"] == "in_progress"


def test_recovery_refuses_empty_reason(tmp_path: Path) -> None:
    folder = _seed(tmp_path)

    with pytest.raises(RecoveryError, match="reason must be non-empty"):
        recover_force_start_phase(folder, phase="execute", reason="", schema_path=SCHEMA_PATH)


def test_recovery_refuses_whitespace_only_reason(tmp_path: Path) -> None:
    folder = _seed(tmp_path)

    with pytest.raises(RecoveryError, match="reason must be non-empty"):
        recover_force_start_phase(
            folder, phase="execute", reason="   \n\t  ", schema_path=SCHEMA_PATH
        )


def test_recovery_refuses_missing_state_json(tmp_path: Path) -> None:
    bogus = tmp_path / "no-state-here"
    bogus.mkdir()

    with pytest.raises(RecoveryError, match=r"no state\.json"):
        recover_force_start_phase(
            bogus, phase="execute", reason="should never run", schema_path=SCHEMA_PATH
        )


def test_recovery_appends_one_entry_per_call(tmp_path: Path) -> None:
    folder = _seed(tmp_path)

    for n in range(3):
        recover_force_start_phase(
            folder,
            phase="execute",
            reason=f"iteration {n}",
            today=date(2026, 5, 12),
            schema_path=SCHEMA_PATH,
        )
        # Each call lands on a "done" execute slot via complete_phase so the
        # next iteration's precondition (target already done) is overridden
        # by force=True. That overrides land cleanly is the property tested.
        state.complete_phase(folder / "state.json", "execute", schema_path=SCHEMA_PATH)

    decisions_text = (folder / "decisions.md").read_text(encoding="utf-8")
    assert decisions_text.count("Forced phase start: execute") == 3
    for n in range(3):
        assert f"iteration {n}" in decisions_text


def test_recovery_strips_reason_whitespace_in_audit_entry(tmp_path: Path) -> None:
    folder = _seed(tmp_path)

    recover_force_start_phase(
        folder,
        phase="execute",
        reason="   trim me   ",
        today=date(2026, 5, 12),
        schema_path=SCHEMA_PATH,
    )

    decisions = (folder / "decisions.md").read_text(encoding="utf-8")
    assert "**Rationale:** trim me\n" in decisions
