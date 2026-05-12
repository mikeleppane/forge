"""Bash CLI entry point for the ``/forge:do`` post-confirm seed step.

This module wraps :func:`tools.routing.seed_routed_feature` in an argparse
surface so the ``forge-do`` skill's STOP block collapses to a single,
mechanical Bash invocation instead of a multi-line Python heredoc that
agents consistently skim past. The CLI is a thin shell — all tier
proposal, user-confirm dialogue, Constitution preflight, and capability
scan UI live in the skill body; this surface only owns the deterministic
seed step that the skill's body has been pointing at the whole time.

Surface (verbatim from ``forge-do --help``):

    forge-do --idea TEXT --tier {focused,standard,full} --rationale TEXT
             [--proposed-tier {focused,standard,full}]
             [--constitution-present | --no-constitution-present]
             [--research]
             [--repo-root PATH]
             [--feature-slug SLUG]

Exit codes:

  * 0 — seed succeeded.
  * 1 — helper-level refusal (already-exists, schema-invalid, malformed
    slug, focused+research, idea cap exceeded). The underlying message
    lands on stderr.
  * 2 — argparse usage error (argparse's default).

Unexpected exceptions propagate with their traceback intact — those are
real bugs the operator should see, not user errors to swallow.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from tools.archive import ArchiveError
from tools.routing import seed_routed_feature
from tools.state import StateError

# The dispatch literal printed after a successful seed. Mapping is locked:
# ``spec`` → forge-spec; ``refine`` → forge-refine; ``research`` →
# forge-research. The skill's STOP block points at this CLI as the single
# source of truth, so the mapping is duplicated nowhere else in the
# operator-facing flow.
_NEXT_COMMAND_FOR_PHASE: dict[str, str] = {
    "spec": "/forge:spec",
    "refine": "/forge:refine",
    "research": "/forge:research",
}

# Tier set surfaced by ``--tier`` and ``--proposed-tier``. Mirrors
# :data:`tools.state.VALID_TIERS` but pinned here so argparse refuses
# bogus tier values BEFORE any seed work begins (exit 2, not exit 1).
_VALID_TIERS: tuple[str, ...] = ("focused", "standard", "full")

_SECRETS_WARNING: str = (
    "sensitive content (tokens, passwords) discouraged — text is persisted to "
    "state.json.routing.idea verbatim"
)

_FOCUSED_PLUS_RESEARCH_HINT: str = (
    'research escalates to standard tier; use /forge:do --standard --research "<idea>"'
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the ``forge-do`` argparse surface."""
    parser = argparse.ArgumentParser(
        prog="forge-do",
        description=(
            "Seed a FORGE feature folder + routing block in one mechanical step. "
            "Wraps tools.routing.seed_routed_feature so the /forge:do skill's "
            "STOP block can collapse to a single Bash invocation."
        ),
    )
    parser.add_argument(
        "--idea",
        required=True,
        help="Free-text feature idea. Persisted verbatim into state.json.routing.idea.",
    )
    parser.add_argument(
        "--tier",
        required=True,
        choices=_VALID_TIERS,
        help="Final tier resolved by the skill (override flag wins over LLM proposal).",
    )
    parser.add_argument(
        "--rationale",
        required=True,
        help="One-sentence rationale for the resolved tier.",
    )
    parser.add_argument(
        "--proposed-tier",
        choices=_VALID_TIERS,
        default=None,
        help=(
            "Tier the LLM originally proposed. Defaults to --tier when omitted, "
            "so the no-override path stays clean."
        ),
    )
    parser.add_argument(
        "--constitution-present",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Set when .forge/CONSTITUTION.md exists at routing time. "
            "Default: --no-constitution-present."
        ),
    )
    parser.add_argument(
        "--research",
        action="store_true",
        help=(
            "Opt the feature into the research phase (standard tier only; "
            "full tier always runs research; focused tier refuses)."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root containing .forge/. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--feature-slug",
        default=None,
        help=(
            "Optional disambiguating slug for the suffix-disambig branch "
            "(e.g. <canonical>-v2). When omitted, the slug is derived from --idea."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``forge-do`` CLI end to end.

    Args:
        argv: Optional argv override (argparse reads from ``sys.argv[1:]``
            when omitted).

    Returns:
        Exit code: 0 on a successful seed, 1 on a helper-level refusal.
        Argparse itself raises ``SystemExit(2)`` on usage errors before
        this function returns.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Print the secrets warning to stderr BEFORE any disk activity so the
    # operator sees the verbatim caveat even if the seed then refuses on
    # a downstream guard.
    print(_SECRETS_WARNING, file=sys.stderr)

    # Locally refuse focused+research with the same wording the helper
    # uses so the operator sees a clean exit-1 error message instead of
    # the Python ValueError traceback that a bare helper call would
    # surface. The helper still mirrors this refusal as a defence in
    # depth; we never reach it on this branch.
    if args.tier == "focused" and args.research:
        print(_FOCUSED_PLUS_RESEARCH_HINT, file=sys.stderr)
        return 1

    proposed_tier: str = args.proposed_tier if args.proposed_tier is not None else args.tier
    repo_root: Path = args.repo_root if args.repo_root is not None else Path.cwd()

    try:
        folder = seed_routed_feature(
            repo_root,
            idea=args.idea,
            final_tier=args.tier,
            proposed_tier=proposed_tier,
            rationale=args.rationale,
            constitution_present=args.constitution_present,
            feature_slug=args.feature_slug,
            research_opt_in=args.research,
        )
    except (ArchiveError, StateError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Resolve the dispatch literal from the seeded state.json. Reading
    # ``current_phase`` back out of the seeded payload (instead of
    # re-deriving it from --tier and --research) keeps this CLI as the
    # single source of truth aligned with the helper's seed decisions —
    # if the helper ever shifts the (tier, research) → phase mapping, the
    # CLI does not need an update.
    state_payload = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    current_phase: str = state_payload["current_phase"]
    next_command = _NEXT_COMMAND_FOR_PHASE[current_phase]
    feature_id = folder.name

    print(f"seeded: {folder}")
    print(f"Next: {next_command} --feature {feature_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
