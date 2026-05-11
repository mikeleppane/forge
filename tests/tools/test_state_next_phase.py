"""Tests for next_phase_command static dispatch in tools.state."""

from __future__ import annotations

from typing import Any

import pytest

from tools import state


def _state(tier: str, phase: str, **review_extra: object) -> dict[str, Any]:
    review_block: dict[str, Any] = {"status": "in_progress"}
    review_block.update(review_extra)
    phases: dict[str, Any] = (
        {phase: review_block} if phase == "review" else {phase: {"status": "in_progress"}}
    )
    return {
        "feature_id": "2026-05-04-demo",
        "tier": tier,
        "current_phase": phase,
        "phases": phases,
        "skipped": [],
        "deviations": [],
        "commits": [],
    }


@pytest.mark.parametrize(
    "phase,expected",
    [
        ("spec", "/forge:execute"),
        ("execute", "/forge:verify"),
        ("verify", None),
    ],
)
def test_next_phase_focused_tier(phase: str, expected: str | None) -> None:
    assert state.next_phase_command(_state("focused", phase)) == expected


@pytest.mark.parametrize(
    "phase,expected",
    [
        # 'refine' is full-tier only; standard tier never enters refine
        # so it is intentionally absent from the standard-tier next map
        # (deep-M-A2). See test_standard_next_does_not_route_through_refine.
        ("spec", "/forge:scenarios"),
        ("scenarios", "/forge:plan"),
        ("plan", "/forge:crucible"),
        ("crucible", "/forge:review --target plan"),
        ("execute", "/forge:review --target code"),
        ("verify", "/forge:ship"),
        ("ship", "/forge:qa --against merged"),
        ("qa", None),
    ],
)
def test_next_phase_standard_tier(phase: str, expected: str | None) -> None:
    assert state.next_phase_command(_state("standard", phase)) == expected


@pytest.mark.parametrize(
    "tier",
    ["standard", "full"],
)
def test_next_phase_ship_routes_to_qa(tier: str) -> None:
    """Standard and full tiers both end in qa: ``ship → /forge:qa --against merged``,
    ``qa → None``. Focused tier finishes earlier (at verify) and never reaches ship."""
    assert state.next_phase_command(_state(tier, "ship")) == "/forge:qa --against merged"
    assert state.next_phase_command(_state(tier, "qa")) is None


def test_next_phase_standard_tier_refine_returns_none() -> None:
    """Refine is full-tier only; querying it on standard-tier yields no next.

    Pinning this explicitly makes the deep-M-A2 cleanup self-evident in the
    test surface: the misroute that previously claimed standard tier could
    advance refine -> /forge:spec is gone.
    """
    assert state.next_phase_command(_state("standard", "refine")) is None


def test_next_phase_full_tier_inserts_domain_after_spec() -> None:
    assert state.next_phase_command(_state("full", "spec")) == "/forge:domain"


def test_next_phase_full_tier_domain_routes_to_scenarios() -> None:
    assert state.next_phase_command(_state("full", "domain")) == "/forge:scenarios"


def test_next_phase_review_routes_to_plan_when_no_targets_done() -> None:
    payload = _state("standard", "review", targets_done=[], current_target="plan")
    assert state.next_phase_command(payload) == "/forge:review --target plan"


def test_next_phase_review_routes_to_execute_when_plan_done() -> None:
    payload = _state("standard", "review", targets_done=["plan"], current_target="plan")
    assert state.next_phase_command(payload) == "/forge:execute"


def test_next_phase_review_routes_to_verify_when_both_done() -> None:
    payload = _state("standard", "review", targets_done=["plan", "code"], current_target="code")
    assert state.next_phase_command(payload) == "/forge:verify"


def test_next_phase_unknown_tier_returns_none() -> None:
    payload = _state("focused", "spec")
    payload["tier"] = "exotic"
    assert state.next_phase_command(payload) is None


# ---------------------------------------------------------------------------
# current_phase_command — slash literal for the phase the feature is in NOW
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phase,expected",
    [
        ("refine", "/forge:refine"),
        ("research", "/forge:research"),
        ("spec", "/forge:spec"),
        ("domain", "/forge:domain"),
        ("scenarios", "/forge:scenarios"),
        ("plan", "/forge:plan"),
        ("crucible", "/forge:crucible"),
        ("execute", "/forge:execute"),
        ("verify", "/forge:verify"),
        ("ship", "/forge:ship"),
    ],
)
def test_current_phase_command_returns_slash_for_current_phase(phase: str, expected: str) -> None:
    """After ``start_phase(P)``, ``current_phase`` equals P; the helper
    returns the slash that runs P — not the slash for the phase after P.

    Regression guard: ``commands/spec.md`` used to print
    ``next_phase_command(payload)`` here, which returned the phase *after*
    the just-opened phase and told users to skip ahead.
    """
    assert state.current_phase_command(_state("full", phase)) == expected


def test_current_phase_command_qa_carries_against_merged_flag() -> None:
    assert state.current_phase_command(_state("full", "qa")) == "/forge:qa --against merged"


def test_current_phase_command_review_delegates_to_review_resolver() -> None:
    payload = _state("standard", "review", targets_done=[], current_target="plan")
    assert state.current_phase_command(payload) == "/forge:review --target plan"

    payload_after_plan = _state("standard", "review", targets_done=["plan"], current_target="plan")
    # After plan-review closes, the lifecycle leaves review for execute; the
    # resolver mirrors that ping-pong.
    assert state.current_phase_command(payload_after_plan) == "/forge:execute"


def test_current_phase_command_returns_none_for_done_state() -> None:
    payload = _state("focused", "verify")
    payload["current_phase"] = "done"
    assert state.current_phase_command(payload) is None


def test_current_phase_command_returns_none_for_non_string_phase() -> None:
    payload = _state("focused", "spec")
    payload["current_phase"] = 42
    assert state.current_phase_command(payload) is None


def test_current_phase_command_returns_none_for_unknown_phase() -> None:
    payload = _state("focused", "spec")
    payload["current_phase"] = "fictional-phase"
    assert state.current_phase_command(payload) is None
