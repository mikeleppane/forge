---
name: forge-change
description: Author a delta proposal against a canonical capability spec. Use when /forge:spec capability scan routes to delta or when the user invokes /forge:change directly.
model: sonnet
---

# FORGE Change

## When this skill applies

User invoked `/forge:change` (with or without `--capability` and/or a description
argument), or `/forge:spec` routed here after detecting a capability collision.

## Inputs

- `--capability <slug>` — target capability slug (must exist as `.forge/specs/<slug>/SPEC.md`).
  Prompted if omitted.
- `<change_description>` — short free-text description of the change. Used to derive
  `change_id`. Prompted if omitted.

## Steps

1. **Validate canonical exists.**
   Read CLI args (`--capability <slug>`, `<change_description>`).
   Call `tools.archive.scan_existing_capabilities(repo_root)` and verify `<slug>` is
   in the returned list.  If it is not, abort with:
   > "Capability `<slug>` has no canonical SPEC.md; use `/forge:spec` first."

2. **Compute `change_id`.**
   `change_id = f"{today}-{tools.archive.slug_from_idea(change_description)}"`.
   Print the computed id and confirm with the user before proceeding.

3. **Seed proposal.md.**
   Create `.forge/changes/<change_id>/` and copy
   `templates/changes/proposal.md` into `proposal.md`.  Substitute the
   placeholder `id`, `affects_capability`, and `created` frontmatter fields with
   the actual values; keep `status: draft`.

4. **Interactive authoring.**
   Walk the user through each of the three required sections:

   - `## Affects` — which sections of the canonical SPEC.md are touched (e.g.
     `sections [Intent, Scope]`).
   - `## Delta` — one or more block-grammar operations per the op-format defined
     in `tools/delta_merge.py`'s module docstring:
     `+ ADD: <label>`, `- REMOVE: <label>`, `~ MODIFY: <label>`.
   - `## Rationale` — one paragraph covering motivation, alternatives considered,
     and visible impact on the capability's consumers.

5. **Validate + approve.**
   Run `python -m tools.validate --target delta .forge/changes/<change_id>/proposal.md`.
   On exit 0 with zero findings, ask the user to confirm.  On confirmation, flip
   frontmatter `status: draft -> approved`.

   The merge happens later via `/forge:ship --change <change_id>`, which delegates
   to `tools.archive.merge_delta_proposal`.  The `_mark_change_merged_hook` factory
   (also in `tools.archive`) provides the approval flip that completes the
   validator + approval lifecycle inside the transactional merge.

   Do NOT call `tools.archive.merge_delta_proposal` from this skill.

## Done

`.forge/changes/<change_id>/proposal.md` exists with `status: approved`.
The merge-time consumer `tools.archive.merge_delta_proposal` is invoked by
`/forge:ship --change <change_id>` in a separate session.
