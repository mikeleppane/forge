"""Tests for tools.validate.Finding dataclass and module skeleton."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import validate
from tools.validate._finding import _finding_to_dict


def test_finding_is_frozen() -> None:
    finding = validate.Finding(
        severity="BLOCK",
        target="constitution",
        file=Path(".forge/CONSTITUTION.md"),
        message="missing frontmatter",
    )
    with pytest.raises(AttributeError):
        finding.severity = "WARN"  # type: ignore[misc]


def test_finding_fields_round_trip() -> None:
    finding = validate.Finding(
        severity="WARN",
        target="constitution",
        file=Path(".forge/CONSTITUTION.md"),
        message="article count near cap",
    )
    assert finding.severity == "WARN"
    assert finding.target == "constitution"
    assert finding.file == Path(".forge/CONSTITUTION.md")
    assert finding.message == "article count near cap"


def test_validate_error_is_runtime_error() -> None:
    err = validate.ValidationError("boom")
    assert isinstance(err, RuntimeError)


def test_finding_fix_hint_defaults_to_none() -> None:
    """Constructing a Finding without fix_hint leaves the field as None
    so existing call sites in validators stay backward compatible."""
    finding = validate.Finding(
        severity="BLOCK",
        target="constitution",
        file=Path(".forge/CONSTITUTION.md"),
        message="missing frontmatter",
    )
    assert finding.fix_hint is None


def test_finding_fix_hint_round_trips_through_dict() -> None:
    """When fix_hint is set, _finding_to_dict surfaces it under the
    `fix_hint` key so the CLI JSON payload carries it to the operator."""
    finding = validate.Finding(
        severity="BLOCK",
        target="tdd_evidence",
        file=Path(".forge/features/x/state.json"),
        message="tdd_evidence:missing_test_pair — AC-1 needs a test pair",
        fix_hint="Author a test commit for AC-1 before the impl commit.",
    )
    payload = _finding_to_dict(finding)
    assert payload["fix_hint"] == (
        "Author a test commit for AC-1 before the impl commit."
    )


def test_finding_dict_omits_fix_hint_when_none() -> None:
    """When fix_hint is None, _finding_to_dict omits the key so existing
    test fixtures comparing dicts verbatim do not have to grow a new key."""
    finding = validate.Finding(
        severity="WARN",
        target="constitution",
        file=Path(".forge/CONSTITUTION.md"),
        message="article count near cap",
    )
    payload = _finding_to_dict(finding)
    assert "fix_hint" not in payload
