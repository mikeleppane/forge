---
spec: 2026-05-07-demo-feature
target: code
status: resolved
cycles: 2
---

# Findings

| ID | Severity | Status | Location | Problem | Recommended Fix | Source |
|----|----------|--------|----------|---------|-----------------|--------|
| F-1 | HIGH | resolved | src/services/checkout.py:142 | [constitution:A1] direct ORM session call | moved in commit deadbeef | heavy-subagent |
