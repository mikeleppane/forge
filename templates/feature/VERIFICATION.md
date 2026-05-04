---
spec: <feature-id>
generated: <YYYY-MM-DD>
---

# Coverage

| Acceptance | Method | Status | Evidence |
|---|---|---|---|
| crit-1 | <code-audit \| scenario-exec \| UAT> | <EVIDENCED \| PASS \| FAIL \| UNVERIFIABLE \| PENDING> | <file:line or test command exit code or UAT timestamp> |

# Negative-requirement checks

| Negative | Method | Status | Evidence |
|---|---|---|---|
| MUST NOT <...> | <code-audit \| scenario-exec> | <EVIDENCED \| PASS \| FAIL> | <evidence> |

# Gaps

> Bulleted list of criteria still unverified or failing. Empty if every criterion is EVIDENCED or PASS.

# Skipped phases (carry-over risks)

> Bulleted list. For each skipped phase: phase name + risk introduced.
> Examples:
> - scenarios skipped → no executable backstop, full UAT required.
> - crucible skipped → no UNDERSTANDING.md, intent traceability weak.
