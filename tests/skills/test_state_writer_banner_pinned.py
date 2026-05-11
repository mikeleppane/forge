"""Contract test: every skill that mutates state.json carries the SAME banner.

Five skills currently mutate ``state.json``: ``forge-do``, ``forge-spec``,
``forge-execute``, ``forge-refine``, ``forge-domain``. Each prepends a
hook-protection banner pointing agents at the ``tools.state.*`` helpers
and naming the ``hooks/check_state_writer.py`` PreToolUse hook that
refuses direct ``Write`` / ``Edit`` / ``MultiEdit``.

The banner text is byte-identical across all five so a future drift
("I'll just clarify this one helper name in forge-execute…") is caught
by this test instead of silently breaking the grep-once invariant the
original banner commit promised.

If you legitimately need to evolve the banner, edit ``_CANONICAL_BANNER``
below and update every skill in lock-step. Anything else is drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SKILLS_WITH_STATE_MUTATION = (
    "forge-do",
    "forge-spec",
    "forge-execute",
    "forge-refine",
    "forge-domain",
)

_CANONICAL_BANNER = """\
> **`state.json` is hook-protected.** Mutate it only through the
> `tools.state.*` helpers — `complete_phase`, `start_phase`,
> `record_routing_decision`, `record_refined_idea`, `record_commit`,
> `append_deviation`, `set_execute_current_slice`. The PreToolUse hook
> at `hooks/check_state_writer.py` refuses direct `Write` / `Edit` /
> `MultiEdit` on `.forge/features/<id>/state.json` and surfaces a
> permission-deny with guidance toward the correct helper.
"""


@pytest.mark.parametrize("skill_name", _SKILLS_WITH_STATE_MUTATION)
def test_skill_carries_canonical_state_writer_banner(repo_root: Path, skill_name: str) -> None:
    """Each state-mutating skill must contain the byte-identical banner block."""
    skill_path = repo_root / "skills" / skill_name / "SKILL.md"
    body = skill_path.read_text(encoding="utf-8")

    assert _CANONICAL_BANNER.strip() in body, (
        f"skills/{skill_name}/SKILL.md is missing or has drifted from the canonical "
        f"state-writer banner. Restore the banner exactly, or — if the banner is "
        f"changing intentionally — update _CANONICAL_BANNER in this test and every "
        f"other skill in lock-step."
    )
