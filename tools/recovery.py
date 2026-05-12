"""Audited phase-machine recovery for feature folders.

This module owns the *audited* force-override path for the state machine.
``tools.state.start_phase(..., force=True)`` exists as the bare primitive
that bypasses :class:`tools.state.PhasePreconditionError`; recovery
adds an append-only ADR entry to the feature's ``decisions.md`` so the
override survives in the audit trail.

Reach for :func:`recover_force_start_phase` from:

  * Long-lived recovery scripts (operator manually rewinds a stuck feature).
  * The eventual ``/forge:recover`` slash command.
  * Any context where the override needs to be discoverable months later.

For one-shot test fixtures that simply want to land at a specific phase
without ceremony, call ``start_phase(..., force=True)`` directly — there
is no operator to consult and no audit trail to maintain.
"""

from __future__ import annotations

from datetime import date as _date
from pathlib import Path
from typing import Any

from tools.state import StateError, start_phase

_RECOVERY_HEADING = "Forced phase start"


class RecoveryError(RuntimeError):
    """Raised when the recovery preconditions are not met."""


def recover_force_start_phase(
    feature_dir: Path,
    phase: str,
    reason: str,
    *,
    today: _date | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Force-start ``phase`` and append an audited ADR to ``decisions.md``.

    Composes the two halves of an auditable bypass:

      1. Append a dated ADR block to ``<feature_dir>/decisions.md``
         identifying the forced phase, the operator-supplied reason,
         and the date. Append is in-place; no atomic-replace dance
         since ``decisions.md`` is human-authored and append-only by
         convention.
      2. Call :func:`tools.state.start_phase` with ``force=True``.

    Args:
        feature_dir: ``.forge/features/<id>/`` directory.
        phase: Phase to force-start. Must be a member of
            :data:`tools.state.VALID_LIFECYCLE_PHASES`; the underlying
            ``start_phase`` enforces this.
        reason: Non-empty operator rationale. Lands verbatim in the ADR.
        today: Optional date stamp for the ADR heading. Defaults to
            :func:`datetime.date.today`.
        schema_path: Optional override forwarded to ``start_phase`` for
            schema validation on read+write.

    Returns:
        The updated state payload returned by ``start_phase``.

    Raises:
        RecoveryError: ``reason`` is empty / whitespace-only, or
            ``feature_dir`` does not contain a ``state.json``.
        StateError: ``start_phase`` refused the underlying transition
            for reasons unrelated to the precondition (unknown phase,
            tier mismatch, schema failure).
    """
    if not reason or not reason.strip():
        raise RecoveryError("recover_force_start_phase: reason must be non-empty")

    state_path = feature_dir / "state.json"
    if not state_path.is_file():
        raise RecoveryError(f"recover_force_start_phase: no state.json under {feature_dir!s}")

    decisions_path = feature_dir / "decisions.md"
    stamp = (today or _date.today()).isoformat()
    entry = (
        f"\n## {stamp} — {_RECOVERY_HEADING}: {phase}\n\n"
        f"**Context:** Phase-machine precondition bypassed via "
        f"`tools.recovery.recover_force_start_phase`.\n\n"
        f"**Decision:** Force-start phase `{phase}`.\n\n"
        f"**Rationale:** {reason.strip()}\n"
    )
    _append_decision(decisions_path, entry)

    try:
        return start_phase(state_path, phase, schema_path=schema_path, force=True)
    except StateError:
        raise


def _append_decision(path: Path, entry: str) -> None:
    """Append ``entry`` to ``path``. Creates the file if absent.

    ``decisions.md`` is a human-authored append-only log; an atomic
    rename here would interleave badly with concurrent operator edits.
    The append is best-effort: a partial write surfaces the underlying
    OSError to the caller rather than being silenced.
    """
    if path.exists():
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry)
    else:
        path.write_text(entry.lstrip("\n"), encoding="utf-8")
