---
name: validate
description: Run the IDD structural validator across artifacts and surface findings. Use when the user asks to validate, check, or audit Constitution / delta / spec / repo health structure.
---

# /idd:validate

Run `python -m tools.validate` and report findings. Read-only.

## Behavior

1. Parse args: required `--target` (see list below), optional positional `path`, optional `--repo-root <path>`, optional `--check-registries`.
2. Invoke the `idd-validate` skill (see `skills/idd-validate/SKILL.md`).
3. Skill runs `python -m tools.validate` and prints findings.
4. Exit code mirrors the underlying validator: `0` (no BLOCK / HIGH), `1` (any BLOCK or HIGH), `2` (usage error).

## Targets

### Per-file (positional `path` = artifact)

- `spec` — NR placement + frontmatter schema (SPEC.md).
- `plan` — frontmatter schema (PLAN.md).
- `delta` — frontmatter + `## Affects` / `## Delta` + op-marker presence (proposal.md).
- `scenarios` — P2b: Scenarios↔Acceptance Criteria coverage (SPEC.md).
- `anchors` — P2b: `# Codebase Anchors` module-resolve (SPEC.md). Resolves relative to `--repo-root`.
- `spec-semantic` — umbrella for `scenarios` + `anchors` over the same SPEC.md.
- `plan-tasks` — P2b: slice↔acceptance + slice file collisions; reads paired SPEC.md next to PLAN.md.
- `verified-deps` — P2b: `## Verified Dependencies` table shape on PLAN.md. Shape-only by default; see `--check-registries`.

### Per-folder (positional `path` = feature folder)

- `deviations` — P2b: cross-references `state.json` `deviations[]` against `decisions.md`.

### Repo-wide (no positional path; uses `--repo-root`)

- `constitution` — Constitution structural check (defaults to `<repo-root>/.idd/CONSTITUTION.md` if no path supplied).
- `ship` — P2a slice: capability-uniqueness only. Full ship-gate (Constitution acknowledge gate) lands in **P5**.
- `health` — D-HEALTH layout scan over `.idd/`.
- `all` — fan-out across the entire `.idd/` tree:
  1. `validate_health(repo_root)` — single layout pass.
  2. `validate_capability_uniqueness(repo_root)` — same call as `--target ship`.
  3. `validate_constitution` over `.idd/CONSTITUTION.md` if present.
  4. For each `.idd/changes/<change>/proposal.md`: `validate_delta`.
  5. For each `.idd/features/<feature>/`: `validate_deviations` + (if SPEC.md) `validate_negative_requirements`, `validate_frontmatter(kind=spec)`, `validate_scenarios`, `validate_anchors` + (if PLAN.md) `validate_frontmatter(kind=plan)`, `validate_plan_tasks` (when SPEC.md is also present), `validate_verified_deps`.

> `ship` is preserved for back-compat; `all` is the recommended entry point in M3+.

## Flags

- `--repo-root <path>` (default: cwd). Repo root for repo-wide targets and for resolving `anchors` paths.
- `--check-registries` (default: `False`). Forwarded to `validate_verified_deps`. **Offline by default**: pass `--check-registries` for live registry probes (requires `npm` and/or `pip` on PATH). Only meaningful for `verified-deps` and `all`; ignored elsewhere.

## Examples

- Run repo health check: `python -m tools.validate --target health`
- Validate a SPEC's scenarios: `python -m tools.validate --target scenarios .idd/features/<id>/SPEC.md`
- Validate a feature folder's deviations: `python -m tools.validate --target deviations .idd/features/<id>`
- Run every check across the .idd/ tree: `python -m tools.validate --target all`
- Run all + live registry probes: `python -m tools.validate --target all --check-registries`

## Failure modes

- Unknown `--target` → exit 2 with usage message.
- Per-file target without a positional path, or path is not an existing file → exit 1 with `BLOCK` finding.
- Per-folder target (`deviations`) without a positional path, or path is not a directory → exit 1 with `BLOCK` finding.
- Positional `path` supplied with a repo-wide target → `WARN` finding noting the path was ignored.
- `--repo-root` pointing at a non-directory → exit 1 with `BLOCK` finding.
- Malformed artifact → BLOCK finding listing the structural defect.

All errors surface verbatim from the underlying validator. No partial writes — read-only.
