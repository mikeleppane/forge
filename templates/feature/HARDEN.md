---
feature_id: <YYYY-MM-DD-slug>
shipped_at: <ISO-8601 timestamp recorded by /forge:ship>
hardened_at: <ISO-8601 timestamp recorded when /forge:harden completes>
confidence: <high|partial|low>
flow_version: 3
---

# Hardening Record

> Post-ship confidence record. Produced by `/forge:harden` against the merged artifact. Each section
> reports a status (`pass | fail | skipped | partial`), the findings that drove the status, and an
> evidence pointer (file path, command transcript, or commit sha) the reviewer can re-check.
> The aggregate `confidence` field at the top of this file is computed from the per-section statuses
> per the rule at the bottom of this document. Do not edit `confidence` by hand.

# Contract

> Re-runs the SPEC.md `# Scenarios` against the merged artifact (CLI subprocess for tools, pytest
> markers for libraries). Confirms the shipped contract still matches the spec.

- **Status:** <pass | fail | partial>
- **Scenarios run:** <count>
- **Scenarios passed:** <count>
- **Findings:**
  - <one bullet per failure: scenario id + observed deviation>
- **Evidence:** <path to scenario transcript, or commit sha tested against>

# UAT Replay

> Replays the conversational UAT prompts recorded in VERIFICATION.md. Interactive by default;
> non-interactive mode reads recorded transcripts.

- **Status:** <pass | fail | skipped | partial>
- **Mode:** <interactive | non-interactive>
- **Prompts replayed:** <count>
- **Prompts confirmed:** <count>
- **Findings:**
  - <one bullet per disconfirmation: prompt id + user-reported deviation>
- **Evidence:** <transcript path, or VERIFICATION.md section reference>

# Adversarial

> One subagent dispatched to break the feature. Capped at 5 minutes walltime and 50 attempted-breakage
> scenarios. Records every attempt and outcome regardless of whether it surfaces a real issue.

- **Status:** <pass | fail | partial>
- **Walltime budget:** <minutes spent / 5 max>
- **Attempts:** <count / 50 max>
- **Breakages found:** <count>
- **Findings:**
  - <one bullet per surfaced breakage: severity + scenario + reproducer>
- **Evidence:** <subagent return-payload path, decisions.md ref, or sha of recorded transcript>

# Soak

> Optional long-running run when the feature exposes a daemon, server, or other long-running entrypoint
> (detected via `pyproject.toml` scripts or `package.json` bin entries). Skipped silently for libraries.

- **Status:** <pass | fail | skipped>
- **Duration:** <minutes run, or "n/a" when skipped>
- **Detected entrypoint:** <command / module, or "none — library">
- **Resource trend:** <RSS / CPU / restart count summary, or "n/a">
- **Findings:**
  - <one bullet per leak/crash/restart, or "—" when clean>
- **Evidence:** <path to soak log, or "—">

# NR Regrep

> Re-greps the merged tree against every Negative Requirement in SPEC.md. Catches re-introduced
> violations the merge itself may have re-added under a different file path.

- **Status:** <pass | fail>
- **Negative Requirements scanned:** <count>
- **Violations re-introduced:** <count>
- **Findings:**
  - <one bullet per re-introduction: NR id + offending path:line>
- **Evidence:** <command output path, or commit sha scanned>

---

## Confidence aggregation rule

The `confidence` frontmatter field is computed mechanically from per-section `Status`:

- **`high`** — every required-for-tier section is `pass`. (See the harden policy by tier in the skill
  for which sections are required for `--focused`, `--standard`, `--full`.)
- **`partial`** — at most one required section is `partial`, and zero sections are `fail`. Soak
  reporting `skipped` (because no long-running entrypoint exists) does not count against `high`
  for tiers that mark soak optional.
- **`low`** — any required section is `fail`, OR more than one section is `partial`.

`/forge:harden` writes this field; do not edit it manually. Re-running the harden phase recomputes it
from the latest section statuses.
