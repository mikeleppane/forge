---
name: review
description: Run the review phase against the active feature — layered self-review, heavy on-demand subagent review, and a convergence loop on HIGH+ findings. Targets PLAN.md before execute or code after execute. Use after /forge:crucible (plan target) or /forge:execute (code target).
---

# /forge:review

Run the FORGE review phase against the active feature.

## Behavior

1. Determine active feature (same rules as /forge:plan).
2. Parse args:
   - `--target plan` (default after crucible) — review PLAN.md. Output: `.forge/features/<id>/REVIEW.plan.md`.
   - `--target code` (default after execute) — review the diff plus PLAN.md mapping. Output: `.forge/features/<id>/REVIEW.code.md`.
   - `--cross-ai` — dispatch the active target to a second-opinion CLI in manual mode. Builds the prompt, runs redaction, writes the prompt to `.forge/features/<id>/cross-ai/<target>-<ts>-prompt.md`, and prints the disclosure plus run instructions. The skill never invokes an external CLI; the operator runs it by hand and pastes the response back later.
   - `--cross-ai-paste <path>` — paste-back companion to `--cross-ai`. Reads the response file at `<path>`, parses findings, merges them into `REVIEW.<target>.md`, and re-enters the convergence loop.
3. Read `state.json`. For target=plan: require `phases.crucible.status == "done"`. For target=code: require `phases.execute.status == "done"`.
4. **Enter or resume the review phase.** If `phases.review.status != "in_progress"`, call `tools.state.start_phase(path, "review")`. If review is already `in_progress` (typical for the second pass — `target=code` after the first `target=plan` pass left review open), skip `start_phase` so `phases.review.targets_done` from the first pass survives. `start_phase` itself preserves `targets_done` and `current_target` across review restarts as a safety net.
5. Invoke the `forge-review` skill with the resolved target. The skill writes `REVIEW.<target>.md` (never plain `REVIEW.md`); the dual-pass standard-tier flow keeps two separate audit trails.
6. On completion, print: `REVIEW.<target>.md` path, findings by severity, convergence cycles run, final status (resolved | escalated).

## Failure modes

- `tier == "focused"` → abort: "Review is standard-tier+. Focused tier verifies directly via /forge:verify after /forge:execute."
- Convergence loop fails to drive HIGH+ findings to zero in 3 cycles → halt, surface remaining findings to user, status=escalated.

## Constitution preflight

When `.forge/CONSTITUTION.md` is present, the skill calls `tools.constitution.load_and_filter` before its primary work and passes filtered `articles[]` into every subagent dispatch budget. No-op when absent.

The heavy subagent pass is mandatory when `target=code` AND `len(articles) > 0`; otherwise self-review may miss Constitution violations and the §5.3.9 ship gate would see nothing.

## Cross-AI manual mode

`--cross-ai` triggers Step 4a in `forge-review`: build prompt, redact, write prompt to disk under `.forge/features/<id>/cross-ai/`, render disclosure, halt the cross-ai branch. The in-house heavy pass still runs in the same cycle. The skill never invokes external CLIs — the operator runs the second-opinion CLI by hand against the written prompt.

`--cross-ai-paste <path>` triggers Step 4b: read the response file, parse the findings table, merge findings into `REVIEW.<target>.md`, re-enter the convergence loop.

**Configuration.** Read from a `cross_ai.*` block in `.forge/config.json`, validated against `schemas/cross-ai-config.schema.json`. Default `mode: "manual"`. Minimal shape:

```json
{
  "cross_ai": {
    "mode": "manual",
    "allowed_clis": ["codex", "gemini"],
    "redaction": { "deny_globs": [], "deny_regex": [], "fatal_regex": [], "allow_globs": [] }
  }
}
```

**Redaction.** Applied automatically before the disclosure renders. `deny_globs` exclude entire files from prompt context; `deny_regex` scrub matched substrings from the prompt body; `fatal_regex` matches REFUSE the dispatch and surface the offending matches to the operator. `allow_globs` reinstate paths that would otherwise be denied.

**Cost.** The disclosure carries a cost estimate plus a `cost_warn_triggered` flag derived from `cross_ai.cost_warn_threshold_usd` (default $0.50). In manual mode the warning is advisory — the operator reviews the prompt before sending. The auto-mode `APPROVE-COST` enforcement is out of scope here.
