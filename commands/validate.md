---
name: validate
description: Run the FORGE structural validator across artifacts and surface findings. Use when the user asks to validate, check, or audit Constitution / delta / spec / repo health structure.
---

# /forge:validate

Run `python -m tools.validate` and report findings. Read-only.

## Behavior

1. Parse args: required `--target` (see list below), optional positional `path`, optional `--repo-root <path>`, optional `--check-registries`.
2. Invoke the `forge-validate` skill (see `skills/forge-validate/SKILL.md`).
3. Skill runs `python -m tools.validate` and prints findings.
4. Exit code mirrors the underlying validator: `0` (no BLOCK / HIGH), `1` (any BLOCK or HIGH), `2` (usage error).

## Targets

### Per-file (positional `path` = artifact)

- `spec` — NR placement + frontmatter schema (SPEC.md).
- `plan` — frontmatter schema (PLAN.md).
- `delta` — frontmatter + `## Affects` / `## Delta` + op-marker presence (proposal.md).
- `scenarios` — Scenarios↔Acceptance Criteria coverage (SPEC.md).
- `anchors` — `# Codebase Anchors` module-resolve (SPEC.md). Resolves relative to `--repo-root`.
- `spec-semantic` — umbrella for `scenarios` + `anchors` over the same SPEC.md.
- `plan-tasks` — slice↔acceptance + slice file collisions; reads paired SPEC.md next to PLAN.md.
- `verified-deps` — `## Verified Dependencies` table shape on PLAN.md. Shape-only by default; see `--check-registries`.
- `domain_glossary` — full-tier `# Domain` glossary table check on SPEC.md.
- `qa_shape` — post-merge QA artifact shape check on the feature's QA log.
- `research` — RESEARCH.md grounding-mode + citations shape check.
- `review-lesson-tags` — REVIEW.md cross-feature trap tag lineage check.

### Per-folder (positional `path` = feature folder)

- `deviations` — cross-references `state.json` `deviations[]` against `decisions.md`.
- `tdd_evidence` — TDD pairing audit across the feature's commits (slice ↔ test pair). Honors `--commit` and `--diff-file`; see Flags.

### Repo-wide (no positional path; uses `--repo-root`)

- `constitution` — Constitution structural check (defaults to `<repo-root>/.forge/CONSTITUTION.md` if no path supplied).
- `config` — `.forge/config.json` schema + cross-AI block shape check.
- `conventions` — `.forge/conventions.json` schema + rule shape check (strict; the dispatch hook owns the permissive runtime path).
- `git-conventions` — Conventional Commits + scope audit on recent git history per `.forge/git-conventions.json`.
- `lessons` — `.forge/intel/lessons.md` parse check (cross-feature trap memory). Optional artifact; absent file passes silently.
- `ship` — capability-uniqueness check + Constitution ship-gate parser smoke (full gate runs in `/forge:ship`).
- `health` — layout scan over `.forge/`.
- `all` — fan-out across the entire `.forge/` tree:
  1. `validate_health(repo_root)` — single layout pass.
  2. `validate_capability_uniqueness(repo_root)` — same call as `--target ship`.
  3. `validate_constitution` over `.forge/CONSTITUTION.md` if present.
  4. `validate_lessons(repo_root)` — same call as `--target lessons`; no-op when the file is absent.
  5. For each `.forge/changes/<change>/proposal.md`: `validate_delta`.
  6. For each `.forge/features/<feature>/`: `validate_deviations` + (if SPEC.md) `validate_negative_requirements`, `validate_frontmatter(kind=spec)`, `validate_scenarios`, `validate_anchors` + (if PLAN.md) `validate_frontmatter(kind=plan)`, `validate_plan_tasks` (when SPEC.md is also present), `validate_verified_deps`.

> `ship` is preserved for back-compat; `all` is the recommended entry point in M3+.

## Flags

- `--repo-root <path>` (default: cwd). Repo root for repo-wide targets and for resolving `anchors` paths.
- `--check-registries` (default: `False`). Forwarded to `validate_verified_deps`. **Offline by default**: pass `--check-registries` for live registry probes (requires `npm` and/or `pip` on PATH). Only meaningful for `verified-deps` and `all`; ignored elsewhere.
- `--commit <sha>` (default: unset). Scopes `tdd_evidence` to a single commit so a pre-push hook can audit just the work about to land. Ignored by other targets.
- `--diff-file <path>` (default: unset). Reads the working-tree diff from `<path>` instead of shelling out to `git diff`, letting `tdd_evidence` audit an arbitrary diff payload (CI artifact replay, offline review). Ignored by other targets.

## Environment

- `FORGE_REPO_ROOT` — When set to an absolute path, overrides the default repo-root resolution for tooling that walks up from an awkward cwd (WSL mounts, Codespaces sub-shells, sandboxed runners). Empty / unset = use the default `_locate_repo_root` walk. Honored by every consumer of `tools._repo_root.discover_repo_root` including the dispatch-brief hook and `python -m tools.validate --target conventions`.

## Examples

- Run repo health check: `python -m tools.validate --target health`
- Validate a SPEC's scenarios: `python -m tools.validate --target scenarios .forge/features/<id>/SPEC.md`
- Validate a feature folder's deviations: `python -m tools.validate --target deviations .forge/features/<id>`
- Run every check across the .forge/ tree: `python -m tools.validate --target all`
- Run all + live registry probes: `python -m tools.validate --target all --check-registries`

## Failure modes

- Unknown `--target` → exit 2 with usage message.
- Per-file target without a positional path, or path is not an existing file → exit 1 with `BLOCK` finding.
- Per-folder target (`deviations`) without a positional path, or path is not a directory → exit 1 with `BLOCK` finding.
- Positional `path` supplied with a repo-wide target → `WARN` finding noting the path was ignored.
- `--repo-root` pointing at a non-directory → exit 1 with `BLOCK` finding.
- Malformed artifact → BLOCK finding listing the structural defect.

All errors surface verbatim from the underlying validator. No partial writes — read-only.
