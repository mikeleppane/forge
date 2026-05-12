"""Shared feature-folder layout constants (M3 §5.3.6 D-HEALTH)."""

from __future__ import annotations

STATE_FILENAME = "state.json"
SPEC_FILENAME = "SPEC.md"
PLAN_FILENAME = "PLAN.md"
DECISIONS_FILENAME = "decisions.md"

TEMPLATED_FEATURE_FILES: frozenset[str] = frozenset(
    {
        "state.json",
        "SPEC.md",
        "PLAN.md",
        "UNDERSTANDING.md",
        "REVIEW.md",
        "REVIEW.plan.md",
        "REVIEW.code.md",
        "VERIFICATION.md",
        "decisions.md",
    }
)

# Files that may appear in a never-advanced orphan feature folder.
# Used by both cleanup_orphan_feature (tools/archive.py) and the health
# orphan-detection check (tools/validate/health.py) so the two predicates stay
# in lock-step.
#
# ``state.json.lock`` is the advisory lockfile owned by
# ``tools.state.state_lock``. A seed write briefly holds it; once the writer
# closes the file handle, the inode remains as a zero-byte sidecar. The orphan
# allowlist must include it so a feature that has only been seeded (and never
# advanced) still passes the orphan-conditions predicate.
_ORPHAN_FEATURE_FILES: frozenset[str] = frozenset(
    {
        "state.json",
        "state.json.lock",
        "SPEC.md",
        "decisions.md",
    }
)

# Phases that mark a never-advanced seed feature.  Shared between
# tools/archive.py::_orphan_conditions_met and
# tools/validate/health.py::_check_feature_payload so a future change to one
# predicate cannot silently desync the other.  Includes BOTH the refine-tier
# seed and the focused/standard /forge:do pre-seed.
_ORPHAN_SEED_PHASES: frozenset[str] = frozenset({"refine", "spec"})
