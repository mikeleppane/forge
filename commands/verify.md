---
name: verify
description: Run the three-layer verify phase against the active feature. Use after /idd:execute reports done. Produces VERIFICATION.md by combining code-audit (always), scenario execution (when .feature files exist), and conversational UAT for the rest. Updates state.json.
---

# /idd:verify

Run the IDD verify phase. Wraps the `idd-verify` skill.

## Behavior

1. Determine active feature: `--feature <id>` flag, otherwise the most recently modified `.idd/features/*/state.json`.
2. Validate `phases.execute.status == "done"`. Abort otherwise.
3. Invoke the `idd-verify` skill.
4. On completion, print: total verified count (EVIDENCED or PASS), list of FAILs (if any), skipped-phase warnings, path to VERIFICATION.md.
5. If all criteria are EVIDENCED or PASS and no FAIL/PENDING remain, transition `current_phase` to `ship` (standard/full) or `done` (focused). For focused tier, this calls `tools.state.finish_feature(path)`.

## Failure modes

- Layer 1 audit subagent dispatch blocked by `PreToolUse` hook → surface reason; refine the dispatch.
- Layer 1 audit subagent returns `status: blocked` → halt, surface blocker.
- Layer 2 BDD command fails to run (binary not found, etc.) → log as Skipped phase warning, fall through to Layer 3.
- Layer 3 UAT cancelled by user → leave criteria as PENDING, do not transition state.
