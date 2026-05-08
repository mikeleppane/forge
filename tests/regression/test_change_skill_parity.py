"""Regression: forge-change skill + /forge:change command shape parity.

Asserts:
1. skills/forge-change/SKILL.md exists.
2. SKILL.md frontmatter contains name, description, and model: sonnet lines.
3. SKILL.md body references tools.archive.merge_delta_proposal.
4. SKILL.md body contains the four logical lifecycle phases:
   - validate canonical
   - compute change_id
   - seed proposal.md
   - validator + approval  (approval flip step)
5. commands/change.md exists.
6. commands/change.md frontmatter contains description and argument-hint lines.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO / "skills" / "forge-change" / "SKILL.md"
COMMAND_PATH = REPO / "commands" / "change.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Skill file exists
# ---------------------------------------------------------------------------


def test_forge_change_skill_exists() -> None:
    assert SKILL_PATH.exists(), f"Expected {SKILL_PATH} to exist"


# ---------------------------------------------------------------------------
# 2. Skill frontmatter tokens
# ---------------------------------------------------------------------------


def test_forge_change_skill_frontmatter_name() -> None:
    text = _read(SKILL_PATH)
    assert "name: forge-change" in text, "SKILL.md frontmatter must contain 'name: forge-change'"


def test_forge_change_skill_frontmatter_description() -> None:
    text = _read(SKILL_PATH)
    assert "description:" in text, "SKILL.md frontmatter must contain 'description:' line"


def test_forge_change_skill_frontmatter_model_sonnet() -> None:
    text = _read(SKILL_PATH)
    assert "model: sonnet" in text, "SKILL.md frontmatter must contain 'model: sonnet'"


# ---------------------------------------------------------------------------
# 3. Body references merge_delta_proposal
# ---------------------------------------------------------------------------


def test_forge_change_skill_references_merge_delta_proposal() -> None:
    text = _read(SKILL_PATH)
    assert "tools.archive.merge_delta_proposal" in text, (
        "SKILL.md must reference tools.archive.merge_delta_proposal"
    )


# ---------------------------------------------------------------------------
# 4. Body contains four lifecycle phases (case-insensitive)
# ---------------------------------------------------------------------------


def test_forge_change_skill_lifecycle_validate_canonical() -> None:
    text = _read(SKILL_PATH)
    assert re.search(r"validate canonical", text, re.IGNORECASE), (
        "SKILL.md must contain 'validate canonical' lifecycle phase"
    )


def test_forge_change_skill_lifecycle_compute_change_id() -> None:
    text = _read(SKILL_PATH)
    assert re.search(r"compute.{0,5}change_id", text, re.IGNORECASE), (
        "SKILL.md must contain 'compute change_id' lifecycle phase"
    )


def test_forge_change_skill_lifecycle_seed_proposal() -> None:
    text = _read(SKILL_PATH)
    assert re.search(r"seed proposal", text, re.IGNORECASE), (
        "SKILL.md must contain 'seed proposal' lifecycle phase"
    )


def test_forge_change_skill_lifecycle_validator_approval() -> None:
    text = _read(SKILL_PATH)
    assert re.search(r"validator.*approval|approval.*flip|validate.*approv", text, re.IGNORECASE), (
        "SKILL.md must contain validator + approval flip lifecycle phase"
    )


# ---------------------------------------------------------------------------
# 5. Command file exists
# ---------------------------------------------------------------------------


def test_forge_change_command_exists() -> None:
    assert COMMAND_PATH.exists(), f"Expected {COMMAND_PATH} to exist"


# ---------------------------------------------------------------------------
# 6. Command frontmatter tokens
# ---------------------------------------------------------------------------


def test_forge_change_command_frontmatter_description() -> None:
    text = _read(COMMAND_PATH)
    assert "description:" in text, "commands/change.md frontmatter must contain 'description:' line"


def test_forge_change_command_frontmatter_argument_hint() -> None:
    text = _read(COMMAND_PATH)
    assert "argument-hint:" in text, (
        "commands/change.md frontmatter must contain 'argument-hint:' line"
    )
