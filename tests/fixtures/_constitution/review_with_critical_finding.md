---
spec: 2026-05-07-demo-feature
target: code
status: open
cycles: 1
---

# Findings

| ID | Severity | Status | Location | Problem | Recommended Fix | Source |
|----|----------|--------|----------|---------|-----------------|--------|
| F-1 | HIGH | open | src/services/checkout.py:142 | [constitution:A1] direct ORM session call (Article 1 — Repository pattern) | move call to repository/ | heavy-subagent |
| F-2 | MEDIUM | open | src/util/log.py:88 | [constitution:A4] verbose logger swallows stack | propagate exc_info | heavy-subagent |
| F-3 | LOW  | open | tests/util/__init__.py | trailing whitespace | strip | self |
