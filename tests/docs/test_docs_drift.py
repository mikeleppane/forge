"""Drift tests: user-facing docs must agree with canonical project state."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_NUMBER_WORDS = {
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
}


def _phases_from_schema() -> list[str]:
    schema = json.loads((REPO_ROOT / "schemas" / "state.schema.json").read_text(encoding="utf-8"))
    enum = schema["properties"]["phases"]["propertyNames"]["enum"]
    assert isinstance(enum, list) and enum, "state.schema.json phases enum shape changed"
    return list(enum)


def _commands_on_disk() -> set[str]:
    return {p.stem for p in (REPO_ROOT / "commands").glob("*.md")}


def _skills_on_disk() -> set[str]:
    return {p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")}


def _extract_phase_list_constants() -> dict[str, list[str]]:
    """Parse tools/state.py via ast and return canonical phase-list tuples.

    Stdlib-only so the docs-drift suite stays free of the heavier ``tools.state``
    import chain (which transitively pulls ``jsonschema``).
    """
    text = (REPO_ROOT / "tools" / "state.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    constants: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        name = node.target.id
        if not name.startswith("_PHASE_LIST_") or not isinstance(node.value, ast.Tuple):
            continue
        phases: list[str] = []
        for elt in node.value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                phases.append(elt.value)
            elif isinstance(elt, ast.Starred) and isinstance(elt.value, ast.Name):
                phases.extend(constants.get(elt.value.id, []))
        constants[name] = phases
    return constants


def _tier_phase_counts() -> dict[str, int]:
    """Per-tier ``routing.phase_list`` cardinality at the default seed.

    Operator-facing docs (README, ``commands/do.md``) report counts that match
    what ``/forge:do`` actually seeds today. The default template does not
    seed ``flow_version: 3`` (``tools/routing.py``), so the full-tier default
    is the pre-v3 list (11 phases). Migrating a feature to ``flow_version: 3``
    adds ``qa`` to that list — but that's a per-feature opt-in, not the
    template default the docs describe.
    """
    consts = _extract_phase_list_constants()
    for key in ("_PHASE_LIST_FOCUSED", "_PHASE_LIST_STANDARD", "_PHASE_LIST_FULL_PRE_V3"):
        assert key in consts, f"could not extract {key} from tools/state.py"
    return {
        "focused": len(consts["_PHASE_LIST_FOCUSED"]),
        "standard": len(consts["_PHASE_LIST_STANDARD"]),
        "full": len(consts["_PHASE_LIST_FULL_PRE_V3"]),
    }


def _full_v3_phase_order() -> list[str]:
    return _extract_phase_list_constants()["_PHASE_LIST_FULL_V3"]


def _lifecycle_block() -> str:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(
        r"^## Lifecycle\b.*?```text\s*(.*?)```",
        readme,
        re.DOTALL | re.MULTILINE,
    )
    assert m, "Lifecycle code block not found in README.md"
    return m.group(1).strip()


def test_readme_lifecycle_order_matches_full_v3() -> None:
    """README lifecycle code block lists every phase in canonical order."""
    block = _lifecycle_block()
    found = [tok for tok in re.split(r"\s*→\s*|\s+", block) if tok]
    canonical = _full_v3_phase_order()
    assert found == canonical, (
        f"README lifecycle order drift — found: {found}, canonical: {canonical}"
    )


def test_readme_lifecycle_membership_matches_schema() -> None:
    """README lifecycle code block tokens are exactly the schema's phase enum."""
    found = set(re.findall(r"\b([a-z][a-z-]+)\b", _lifecycle_block()))
    expected = set(_phases_from_schema())
    missing = expected - found
    extra = found - expected
    assert not missing and not extra, (
        f"README lifecycle phase drift - missing: {sorted(missing)}, extra: {sorted(extra)}"
    )


def test_readme_tier_counts_match_state_module() -> None:
    """README tier counts agree with canonical phase lists in tools/state.py."""
    counts = _tier_phase_counts()
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for tier in ("focused", "standard", "full"):
        m = re.search(rf"\b{tier}(?:\s+tier)?\s+runs\s+(\w+)", readme, re.IGNORECASE)
        assert m, f"README missing tier-count phrase for {tier!r}"
        word = m.group(1).lower()
        assert word in _NUMBER_WORDS, (
            f"README tier {tier!r}: unrecognised count word {word!r}; "
            "extend _NUMBER_WORDS or use a recognised one"
        )
        assert _NUMBER_WORDS[word] == counts[tier], (
            f"README tier {tier!r}: prose says {word!r} ({_NUMBER_WORDS[word]}), "
            f"tools/state.py canonical = {counts[tier]}"
        )


def test_readme_command_references_match_commands_dir() -> None:
    """README mentions every command on disk; every /forge:X in README exists on disk."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    mentioned = set(re.findall(r"/forge:([a-z][a-z-]+)", readme))
    on_disk = _commands_on_disk()
    phantom = mentioned - on_disk
    missing = on_disk - mentioned
    assert not phantom, f"README references commands not on disk: {sorted(phantom)}"
    assert not missing, f"commands/ entries missing from README: {sorted(missing)}"


def test_agents_md_command_references_exist() -> None:
    """Every /forge:X in AGENTS.md resolves to a command on disk."""
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    mentioned = set(re.findall(r"/forge:([a-z][a-z-]+)", agents))
    on_disk = _commands_on_disk()
    phantom = mentioned - on_disk
    assert not phantom, f"AGENTS.md references commands not on disk: {sorted(phantom)}"


def test_agents_md_skill_citations_match_skills_dir() -> None:
    """AGENTS.md cites every skill on disk; every backticked forge-* name exists on disk.

    Uses backtick-bounded matching so non-skill ``forge-*`` tokens (e.g. asset
    filenames, package extras) don't get mistaken for skill citations.
    """
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    cited = set(re.findall(r"`(forge-[a-z-]+)`", agents))
    on_disk = _skills_on_disk()
    phantom = cited - on_disk
    missing = on_disk - cited
    assert not phantom, f"AGENTS.md cites skills not on disk: {sorted(phantom)}"
    assert not missing, f"skills/ entries missing from AGENTS.md: {sorted(missing)}"


def test_readme_skill_references_exist() -> None:
    """Every backticked forge-* skill name in README resolves to a skill dir on disk.

    Backtick-bounded so asset paths like ``images/forge-logo.png`` and package
    extras like ``forge-tools[dev]`` don't trip the drift check.
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    cited = set(re.findall(r"`(forge-[a-z-]+)`", readme))
    on_disk = _skills_on_disk()
    phantom = cited - on_disk
    assert not phantom, f"README references skills not on disk: {sorted(phantom)}"
