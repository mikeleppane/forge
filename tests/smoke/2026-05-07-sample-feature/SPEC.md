---
id: 2026-05-07-sample-feature
status: draft
tier: focused
created: 2026-05-07
capability: sample-feature
---

# Intent

Smoke fixture exercising the migrated P2b validators end-to-end against a
real feature-folder shape. The validators run from
`tests/regression/test_skill_self_review_parity.py` and must report no
BLOCK or HIGH findings on this fixture.

# Scenarios (BDD)

Scenario: Smoke run is clean (criterion-1)
  Given a feature-shaped folder under tests/smoke
  When validate_scenarios + validate_anchors + validate_plan_tasks run
  Then no gating finding appears

# Acceptance Criteria

1. Smoke fixture passes every migrated validator (criterion-1).

# Negative Requirements

- MUST NOT introduce a runtime dependency outside the existing four.
