"""Documentation drift detector.

Locks AGENTS.md and commands/validate.md against the on-disk reality:

  * Every directory under ``skills/`` must appear in the AGENTS.md skills
    table at least once. Undocumented skills FAIL.
  * Every ``commands/<name>.md`` must appear in the AGENTS.md commands
    table under ``/forge:<name>``. Undocumented commands FAIL.
  * Every ``--target`` choice exposed by ``tools.validate`` CLI must be
    documented in ``commands/validate.md``. Undocumented targets FAIL.

The direction is one-way: documented-but-unimplemented entries are
permitted (a row in the AGENTS.md table for a future skill is fine).
The detector only fails when code ships ahead of docs.
"""

from __future__ import annotations

import re
from pathlib import Path

from tools.validate.cli import _TARGET_CHOICES

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_MD = REPO_ROOT / "AGENTS.md"
VALIDATE_MD = REPO_ROOT / "commands" / "validate.md"
SKILLS_DIR = REPO_ROOT / "skills"
COMMANDS_DIR = REPO_ROOT / "commands"


def _skills_on_disk() -> set[str]:
    return {p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()}


def _commands_on_disk() -> set[str]:
    return {p.stem for p in COMMANDS_DIR.glob("*.md")}


def _agents_text() -> str:
    return AGENTS_MD.read_text(encoding="utf-8")


def _validate_md_text() -> str:
    return VALIDATE_MD.read_text(encoding="utf-8")


def _validate_cli_targets() -> set[str]:
    """Pull the ``--target`` argparse choices from the validate CLI module.

    ``_TARGET_CHOICES`` is the canonical source of truth for the CLI's
    accepted values; importing the tuple directly is more reliable than
    instantiating the argparse parser (which the CLI builds inline).
    """
    return set(_TARGET_CHOICES)


def test_every_skill_dir_appears_in_agents_md_skills_table() -> None:
    agents = _agents_text()
    missing = sorted(skill for skill in _skills_on_disk() if f"`{skill}`" not in agents)
    assert missing == [], (
        f"AGENTS.md skills table is missing rows for: {missing}. "
        "Add a row under '## Skills' so non-Claude tools that read AGENTS.md "
        "can discover these skills."
    )


def test_every_command_md_appears_in_agents_md_commands_table() -> None:
    agents = _agents_text()
    missing = sorted(name for name in _commands_on_disk() if f"`/forge:{name}`" not in agents)
    assert missing == [], (
        f"AGENTS.md commands table is missing rows for slash commands: "
        f"{[f'/forge:{n}' for n in missing]}. "
        "Add a row under '## Commands' so non-Claude tools discover them."
    )


def test_every_validate_cli_target_is_documented() -> None:
    cli_targets = _validate_cli_targets()
    documented = _validate_md_text()
    # Each target token appears verbatim somewhere in the markdown (within
    # backticks, an inline list, or a heading). We search for the
    # token-as-backtick-literal to avoid false positives on phrases like
    # "all the targets".
    missing = [target for target in sorted(cli_targets) if f"`{target}`" not in documented]
    assert missing == [], (
        f"commands/validate.md is missing entries for --target choices: {missing}. "
        "Each CLI choice must be documented as `<target>` in the markdown."
    )


def test_agents_md_skills_table_is_well_formed() -> None:
    """Defence-in-depth: every row under '## Skills' parses as a markdown table row."""
    agents = _agents_text()
    skills_section_match = re.search(r"## Skills.*?(?=^## )", agents, re.DOTALL | re.MULTILINE)
    assert skills_section_match is not None, "AGENTS.md must contain a '## Skills' section"
    section = skills_section_match.group(0)
    table_rows = [line for line in section.splitlines() if line.strip().startswith("|")]
    # Header + separator + at least one row.
    assert len(table_rows) >= 3, "AGENTS.md skills table is structurally empty"
