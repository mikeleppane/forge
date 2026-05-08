---
name: refine
description: Socratic vague-idea collapse before /forge:spec. Use when /forge:do (full tier) routes here, or when the user invokes /forge:refine directly to refine a vague idea into a single-feature paragraph.
argument-hint: "[--feature <id>] [<idea>]"
model: sonnet
---

# /forge:refine

Pre-spec phase for full-tier features. Collapses a vague idea (seeded by
`/forge:do --full`) into a single-feature, measurable refined paragraph through
a Socratic loop capped at 5 rounds. Writes the result to
`state.json.refined_idea` and transitions `current_phase` from `refine` to
`spec`.

## Args

- `--feature <id>` — target feature folder under `.forge/features/<id>/`.
  Optional; when omitted, the single-active rule resolves the unique
  unshipped feature.
- `[<idea>]` — optional positional. CLI fallback for the idea text when
  `state.json.routing.idea` is absent. Until `/forge:do --full` ships in
  M3 P6.2, this is the documented direct-invocation path.

## Behavior

1. Resolves the active feature; guards `current_phase == "refine"`.
2. Resolves the idea source. Precedence: `state.json.routing.idea` (when
   seeded by `/forge:do --full`) wins and the CLI `<idea>` is ignored. When
   `routing.idea` is absent AND the user passed CLI `<idea>`, seeds the
   routing block via `tools.state.record_routing_decision` with
   `final_tier="full"` before round 1. When both are absent, aborts with
   `"/forge:refine needs an idea — pass one as an argument: /forge:refine \"<idea text>\""`.
3. Runs a Socratic loop, max 5 rounds, calling
   `tools.state.increment_refine_attempts` after each user reply.
4. Persists the converged paragraph via `tools.state.record_refined_idea`; on
   round-cap in auto mode, logs a deviation to `decisions.md` and
   `state.json.deviations`.
5. Transitions phase to `spec` via `complete_phase` + `start_phase`, then
   prints `next: /forge:spec`.

## Bootstrap caveat (until M3 P6.2)

`/forge:refine` does NOT create the feature folder — that's `/forge:spec`'s
job. Until `/forge:do --full` ships in P6.2, the feature folder +
`state.json` at `current_phase == "refine"` must already exist before
`/forge:refine` can run.

## See also

- `skills/forge-refine/SKILL.md` — full lifecycle.
- `tools.state.increment_refine_attempts` — round counter.
- `/forge:spec` — next phase; consumes `refined_idea` as Intent draft.
