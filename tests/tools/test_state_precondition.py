"""Regression tests for the start_phase lifecycle precondition guard."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tools import state
from tools.routing import seed_routed_feature

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "state.schema.json"


def _state_path(folder: Path) -> Path:
    return folder / "state.json"


def _seed_focused(repo: Path) -> Path:
    return seed_routed_feature(
        repo,
        idea="precondition probe",
        final_tier="focused",
        today=date(2026, 5, 12),
    )


def _seed_standard(repo: Path) -> Path:
    return seed_routed_feature(
        repo,
        idea="precondition probe standard",
        final_tier="standard",
        today=date(2026, 5, 12),
    )


def _mark_done(sp: Path, *phases: str) -> None:
    """Directly stamp phases as ``done`` so the test can bypass the exit gates.

    ``complete_phase`` enforces SPEC-semantic / plan / TDD evidence gates
    against the live artifacts; this helper short-circuits that for tests
    that only care about the phase-machine state and not the artifact
    contents.
    """
    payload: dict[str, Any] = state.read_state(sp, schema_path=SCHEMA_PATH)
    for phase in phases:
        payload["phases"][phase] = {
            "status": "done",
            "started_at": "2026-05-12T00:00:00Z",
            "completed_at": "2026-05-12T00:00:01Z",
        }
    state.write_state(sp, payload, schema_path=SCHEMA_PATH)


def test_phase_precondition_error_is_state_error_subclass() -> None:
    """PhasePreconditionError must remain catchable as StateError for back-compat."""
    assert issubclass(state.PhasePreconditionError, state.StateError)


def test_start_phase_refuses_when_prior_phase_not_done(tmp_path: Path) -> None:
    folder = _seed_focused(tmp_path)
    sp = _state_path(folder)

    # Seed lands at spec/in_progress. Jumping to execute must refuse.
    with pytest.raises(state.PhasePreconditionError, match="prior phase 'spec'"):
        state.start_phase(sp, "execute", schema_path=SCHEMA_PATH)


def test_start_phase_refuses_when_target_already_done(tmp_path: Path) -> None:
    folder = _seed_focused(tmp_path)
    sp = _state_path(folder)
    _mark_done(sp, "spec", "execute")
    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    payload["current_phase"] = "execute"
    state.write_state(sp, payload, schema_path=SCHEMA_PATH)

    # execute is now done; re-entering without force must refuse.
    with pytest.raises(state.PhasePreconditionError, match="already done"):
        state.start_phase(sp, "execute", schema_path=SCHEMA_PATH)


def test_start_phase_idempotent_on_in_progress(tmp_path: Path) -> None:
    """Re-entering a phase whose status is in_progress is a no-op success."""
    folder = _seed_focused(tmp_path)
    sp = _state_path(folder)

    # spec is in_progress from the seed; re-entering must succeed without
    # raising PhasePreconditionError.
    result = state.start_phase(sp, "spec", schema_path=SCHEMA_PATH)
    assert result["phases"]["spec"]["status"] == "in_progress"


def test_start_phase_idempotent_on_pending(tmp_path: Path) -> None:
    """A phase block in 'pending' state may be promoted to in_progress."""
    folder = _seed_focused(tmp_path)
    sp = _state_path(folder)

    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    payload["phases"]["spec"] = {"status": "pending"}
    state.write_state(sp, payload, schema_path=SCHEMA_PATH)

    result = state.start_phase(sp, "spec", schema_path=SCHEMA_PATH)
    assert result["phases"]["spec"]["status"] == "in_progress"


def test_start_phase_force_bypasses_prior_check(tmp_path: Path) -> None:
    folder = _seed_focused(tmp_path)
    sp = _state_path(folder)

    result = state.start_phase(sp, "execute", schema_path=SCHEMA_PATH, force=True)
    assert result["current_phase"] == "execute"
    assert result["phases"]["execute"]["status"] == "in_progress"


def test_start_phase_force_does_not_touch_decisions(tmp_path: Path) -> None:
    """Bare force=True is silent; only tools.recovery writes the audit entry."""
    folder = _seed_focused(tmp_path)
    sp = _state_path(folder)
    decisions = folder / "decisions.md"
    pre = decisions.read_text(encoding="utf-8") if decisions.exists() else ""

    state.start_phase(sp, "execute", schema_path=SCHEMA_PATH, force=True)

    post = decisions.read_text(encoding="utf-8") if decisions.exists() else ""
    assert post == pre, (
        "start_phase(force=True) must not append to decisions.md; "
        "the audit trail is owned by tools.recovery"
    )


def test_start_phase_review_to_execute_pivot_after_plan_target(tmp_path: Path) -> None:
    """Standard-tier execute may start while review is in_progress with plan done."""
    folder = _seed_standard(tmp_path)
    sp = _state_path(folder)

    # Stamp the lifecycle up to "review in_progress with plan target done".
    _mark_done(sp, "spec", "scenarios", "plan", "crucible")
    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    payload["current_phase"] = "review"
    payload["phases"]["review"] = {
        "status": "in_progress",
        "started_at": "2026-05-12T00:00:00Z",
        "current_target": "plan",
        "targets_done": ["plan"],
    }
    state.write_state(sp, payload, schema_path=SCHEMA_PATH)

    # Pivot to execute. Review is still in_progress with targets_done=['plan'].
    state.start_phase(sp, "execute", schema_path=SCHEMA_PATH)

    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    assert payload["current_phase"] == "execute"
    assert payload["phases"]["review"]["status"] == "in_progress"


def test_start_phase_review_to_execute_pivot_refused_without_plan_target(
    tmp_path: Path,
) -> None:
    """Pivoting from review to execute without plan target done must refuse."""
    folder = _seed_standard(tmp_path)
    sp = _state_path(folder)

    _mark_done(sp, "spec", "scenarios", "plan", "crucible")
    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    payload["current_phase"] = "review"
    payload["phases"]["review"] = {
        "status": "in_progress",
        "started_at": "2026-05-12T00:00:00Z",
        "targets_done": [],
    }
    state.write_state(sp, payload, schema_path=SCHEMA_PATH)

    with pytest.raises(state.PhasePreconditionError, match="prior phase 'review'"):
        state.start_phase(sp, "execute", schema_path=SCHEMA_PATH)


def test_start_phase_skipped_phase_is_transparent(tmp_path: Path) -> None:
    """A phase listed in state.skipped does not block the next slot."""
    folder = _seed_focused(tmp_path)
    sp = _state_path(folder)

    # spec done; execute marked skipped; verify must accept without prior-block.
    _mark_done(sp, "spec")
    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    payload["current_phase"] = "spec"
    payload["skipped"] = [{"phase": "execute", "reason": "synthetic skip for unit test"}]
    state.write_state(sp, payload, schema_path=SCHEMA_PATH)

    state.start_phase(sp, "verify", schema_path=SCHEMA_PATH)
    payload = state.read_state(sp, schema_path=SCHEMA_PATH)
    assert payload["current_phase"] == "verify"
