"""Finding dataclass + severity vocabulary. Internal package surface (M3 §5.3.6)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Severity = Literal["BLOCK", "HIGH", "MEDIUM", "LOW", "WARN", "INFO"]
EXIT_NONZERO_SEVERITIES: frozenset[Severity] = frozenset({"BLOCK", "HIGH"})


class ValidationError(RuntimeError):
    """Raised when validator setup fails (not when findings are produced)."""


@dataclass(frozen=True)
class Finding:
    """A single validator finding.

    Attributes:
        severity: see module-level Severity literal. Exit-affecting values are
            in `EXIT_NONZERO_SEVERITIES`; the rest are advisory.
        target: Which validator produced the finding.
        file: Repo-relative path to the file that triggered the finding.
        message: Human-readable description.
        fix_hint: Optional, imperative one-liner naming the recovery action
            (and any disambiguating identifier) so the operator does not need
            to read the validator source. ``None`` when no concrete hint
            applies; CLI rendering omits the key in that case so existing
            JSON fixtures retain their dict shape.
    """

    severity: Severity
    target: str
    file: Path
    message: str
    fix_hint: str | None = None


def _finding_to_dict(finding: Finding) -> dict[str, str]:
    payload: dict[str, str] = {
        "severity": finding.severity,
        "target": finding.target,
        "file": str(finding.file),
        "message": finding.message,
    }
    if finding.fix_hint is not None:
        payload["fix_hint"] = finding.fix_hint
    return payload
