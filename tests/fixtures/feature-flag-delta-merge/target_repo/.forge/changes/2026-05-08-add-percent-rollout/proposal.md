---
id: 2026-05-08-add-percent-rollout
affects_capability: feature-flag
status: approved
created: "2026-05-08"
---

# Change: add percent rollout scenario

## Affects

sections [Scenarios]

## Delta

+ ADD: scenario-3: percent rollout
  - Given a feature flag `foo` with percent rollout `50`
  - When 1000 unique users read the flag
  - Then approximately 500 receive `true` (within ±5% tolerance)

## Rationale

Percent rollout was previously out-of-scope (Scope section); we are now
adding partial rollout support. This delta adds the user-visible scenario
only — implementation lives in a separate feature folder.
