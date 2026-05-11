"""Contract tests for the /forge:spec next-step prose surfaces.

The /forge:spec command's "next step" output must NOT tell the user to
run a downstream phase that will refuse because spec.status is still
in_progress. Two surfaces ship that prose:

- ``commands/spec.md`` step 6 — the command's behavior contract.
- ``skills/forge-spec/SKILL.md`` step 7 — the skill's self-review gate.

Both surfaces must:

1. Branch on phases.spec.status. The in-progress branch tells the user
   to re-run /forge:spec; the done branch surfaces the next phase via
   tools.state.next_phase_command.
2. Never instruct the user to run /forge:execute (or any other
   downstream phase command) from a state where spec.status is still
   in_progress.
"""

from __future__ import annotations

from pathlib import Path


def test_command_spec_branches_next_step_on_phase_status(repo_root: Path) -> None:
    """commands/spec.md step 6 must surface both status branches by name."""
    body = (repo_root / "commands" / "spec.md").read_text(encoding="utf-8")

    assert 'phases.spec.status == "done"' in body, (
        "commands/spec.md must branch the next-step prose on the done status"
    )
    assert 'phases.spec.status == "in_progress"' in body, (
        "commands/spec.md must branch the next-step prose on the in_progress status"
    )
    assert "Re-run /forge:spec --feature" in body, (
        "commands/spec.md must instruct the user to re-run /forge:spec when "
        "spec.status is still in_progress"
    )
    assert "next_phase_command" in body, (
        "commands/spec.md must resolve the done-branch next step via "
        "tools.state.next_phase_command rather than hard-coding /forge:execute"
    )


def test_skill_forge_spec_block_handling_surfaces_re_run(repo_root: Path) -> None:
    """forge-spec SKILL step 7 must describe the BLOCK-handling exit shape."""
    body = (repo_root / "skills" / "forge-spec" / "SKILL.md").read_text(encoding="utf-8")

    assert "When the gate blocks phase exit" in body, (
        "skills/forge-spec/SKILL.md step 7 must describe what to print when "
        "BLOCK/HIGH findings hold the gate"
    )
    assert "Re-run /forge:spec --feature" in body, (
        "skills/forge-spec/SKILL.md must instruct the user to re-run /forge:spec "
        "when the self-review gate blocks phase exit"
    )
    assert "Do NOT call `complete_phase" in body, (
        "skills/forge-spec/SKILL.md must explicitly forbid calling complete_phase "
        "on the blocked-exit branch"
    )
