---
name: change
description: Author a delta proposal against a canonical capability spec. Use when /forge:spec routes to delta or when the user invokes /forge:change directly.
argument-hint: "[--capability <slug>] [<description>]"
model: sonnet
---

# /forge:change

Author a structured delta proposal against an existing canonical capability spec.
The resulting `proposal.md` captures which sections change, the exact block-grammar
ops (ADD / REMOVE / MODIFY), and a rationale paragraph.  Once approved, the proposal
is merged into the canonical spec via `/forge:ship --change <change_id>`.

## Args

- `--capability <slug>` — target capability slug (must already exist as
  `.forge/specs/<slug>/SPEC.md`). Optional; if omitted, prompts.
- `<description>` — short free-text description of the change. Used to
  derive `change_id`. Optional; if omitted, prompts.

## Behavior

1. Validates the capability exists via `tools.archive.scan_existing_capabilities`.
2. Computes `change_id` from today's date + a slug derived from `<description>`.
3. Seeds `.forge/changes/<change_id>/proposal.md` from `templates/changes/proposal.md`.
4. Guides the user through `## Affects`, `## Delta`, and `## Rationale` sections.
5. Runs `python -m tools.validate --target delta` and, on zero findings, flips
   `status: draft -> approved`.

See `skills/forge-change/SKILL.md` for the full step-by-step lifecycle.

## See also

- `skills/forge-change/SKILL.md`
- `tools.archive.merge_delta_proposal` (merge-time helper)
- `/forge:ship --change <change_id>` (merges the approved proposal)
