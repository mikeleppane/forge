"""Regression: forge-spec capability-scan integration parity.

Asserts:
1. SKILL.md contains scan_existing_capabilities token.
2. SKILL.md contains slug_from_idea token.
3. SKILL.md contains route-to-change prompt token (/forge:change + (y/n)).
4. commands/spec.md describes capability scan first + slug_from_idea token.
5. Scan step appears before feature folder creation step in SKILL.md (positional).
6. Scan step appears before constitution preflight in SKILL.md (positional).
7. Scan is NOT gated on tier — no "full tier only" / "tier == full" guards.
8. SKILL.md body guards the prompt when existing is empty (if existing: guard).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO / "skills" / "forge-spec" / "SKILL.md"
COMMAND_PATH = REPO / "commands" / "spec.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. SKILL.md contains scan_existing_capabilities token
# ---------------------------------------------------------------------------


def test_skill_contains_scan_existing_capabilities_token() -> None:
    text = _read(SKILL_PATH)
    assert "tools.archive.scan_existing_capabilities" in text, (
        "SKILL.md must contain the literal 'tools.archive.scan_existing_capabilities'"
    )


# ---------------------------------------------------------------------------
# 2. SKILL.md contains slug_from_idea token
# ---------------------------------------------------------------------------


def test_skill_contains_slug_from_idea_token() -> None:
    text = _read(SKILL_PATH)
    assert "tools.archive.slug_from_idea" in text, (
        "SKILL.md must contain the literal 'tools.archive.slug_from_idea'"
    )


# ---------------------------------------------------------------------------
# 3. SKILL.md contains route-to-change prompt token
# ---------------------------------------------------------------------------


def test_skill_contains_route_to_change_prompt_token() -> None:
    text = _read(SKILL_PATH)
    assert "/forge:change" in text, "SKILL.md must contain '/forge:change' (route-to-change prompt)"
    assert "(y/n)" in text, "SKILL.md must contain '(y/n)' (route-to-change confirmation prompt)"


# ---------------------------------------------------------------------------
# 4. commands/spec.md describes capability scan first + slug_from_idea
# ---------------------------------------------------------------------------


def test_command_spec_describes_capability_scan_first() -> None:
    text = _read(COMMAND_PATH)
    assert re.search(r"capability scan", text, re.IGNORECASE), (
        "commands/spec.md must mention 'capability scan' (case-insensitive)"
    )
    assert "slug_from_idea" in text, "commands/spec.md must contain the literal 'slug_from_idea'"
    # The scan must be mentioned before the feature folder creation step.
    # Use 'templates/feature/state.json' as the feature-folder-creation anchor
    # (it only appears in the create-folder step, not in the intro description).
    scan_idx = text.lower().find("capability scan")
    folder_idx = text.find("templates/feature/state.json")
    assert scan_idx != -1, "commands/spec.md must mention 'capability scan'"
    assert folder_idx != -1, (
        "commands/spec.md must mention 'templates/feature/state.json' "
        "(feature folder creation step anchor)"
    )
    assert scan_idx < folder_idx, (
        "In commands/spec.md, 'capability scan' must appear before "
        "'templates/feature/state.json' (scan runs before feature folder creation)"
    )


# ---------------------------------------------------------------------------
# 5. Scan step appears before feature folder creation in SKILL.md (positional)
# ---------------------------------------------------------------------------


def test_scan_step_appears_before_feature_folder_creation() -> None:
    text = _read(SKILL_PATH)
    scan_idx = text.find("scan_existing_capabilities")
    # Use 'templates/feature/state.json' as the feature-folder-creation anchor:
    # it only appears in the create-folder step (step 4), not in the Goal section.
    # Variable is a path literal, not a secret — noqa S105 not needed; rename avoids FP.
    folder_creation_anchor = "templates/feature/state.json"
    folder_idx = text.find(folder_creation_anchor)
    assert scan_idx != -1, "SKILL.md must contain 'scan_existing_capabilities'"
    assert folder_idx != -1, (
        f"SKILL.md must contain '{folder_creation_anchor}' (feature folder creation anchor)"
    )
    assert scan_idx < folder_idx, (
        f"In SKILL.md, 'scan_existing_capabilities' (pos {scan_idx}) must appear "
        f"BEFORE '{folder_creation_anchor}' (pos {folder_idx})"
    )


# ---------------------------------------------------------------------------
# 6. Scan step appears before constitution preflight in SKILL.md (positional)
# ---------------------------------------------------------------------------


def test_scan_step_appears_before_constitution_preflight() -> None:
    text = _read(SKILL_PATH)
    scan_idx = text.find("scan_existing_capabilities")
    preflight_idx = text.find("tools.constitution.load_and_filter")
    assert scan_idx != -1, "SKILL.md must contain 'scan_existing_capabilities'"
    assert preflight_idx != -1, (
        "SKILL.md must contain 'tools.constitution.load_and_filter' (constitution preflight)"
    )
    assert scan_idx < preflight_idx, (
        f"In SKILL.md, 'scan_existing_capabilities' (pos {scan_idx}) must appear "
        f"BEFORE 'tools.constitution.load_and_filter' (pos {preflight_idx})"
    )


# ---------------------------------------------------------------------------
# 7. Scan is NOT gated on tier
# ---------------------------------------------------------------------------


def test_scan_is_not_tier_gated() -> None:
    text = _read(SKILL_PATH)
    forbidden: list[str] = [
        'tier == "full"',
        "tier == 'full'",
        "full tier only",
        "if tier in",
        "if full_tier",
        "full_tier only",
    ]
    for phrase in forbidden:
        assert phrase not in text, (
            f"SKILL.md must NOT contain tier-gate phrase: {phrase!r}. "
            "Capability scan must run for ALL tiers."
        )


# ---------------------------------------------------------------------------
# 8. Prompt is suppressed when existing is empty (guard expression present)
# ---------------------------------------------------------------------------


def test_prompt_suppressed_when_no_capabilities() -> None:
    text = _read(SKILL_PATH)
    # Acceptable guard patterns (any one is sufficient)
    guard_patterns = [
        r"if existing:",
        r"if existing and slug in existing",
        r"len\(existing\) > 0",
        r"if not existing:",
        r"if existing is\s+\S",  # e.g. "if existing is non-empty"
        r"non-empty AND",  # prose guard: "If `existing` is non-empty AND slug in existing"
        r"non.empty.*slug in existing",
    ]
    matched = any(re.search(p, text) for p in guard_patterns)
    assert matched, (
        "SKILL.md must contain a guard expression that suppresses the "
        "route-to-change prompt when `existing` is empty. "
        "Acceptable patterns: 'if existing:', 'if existing and slug in existing', "
        "'len(existing) > 0', 'if not existing:', or prose 'non-empty AND slug in existing'."
    )
