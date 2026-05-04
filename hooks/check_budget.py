#!/usr/bin/env python3
"""PreToolUse hook for the Agent tool.

Reads the hook input on stdin (JSON). If the dispatch prompt lacks a `context_budget:`
block at the top, or the block is unbounded, returns a PreToolUse deny decision;
otherwise returns an empty object (allow). Idempotent and side-effect-free.

Hook input shape (per Claude Code docs):
{
  "session_id": "...",
  "hook_event_name": "PreToolUse",
  "tool_name": "Agent",
  "tool_input": { "prompt": "...", ... },
  ...
}
"""
from __future__ import annotations

import json
import re
import sys

_BUDGET_HEADER = re.compile(r"(?m)^context_budget:\s*$")
_FILES_IN_SCOPE = re.compile(r"(?ms)^\s*files_in_scope:\s*(.+?)$")
_FORBIDDEN = re.compile(r"(?ms)^\s*forbidden:\s*\n(?:\s+- .+\n?)+")
_UNBOUNDED_GLOBS = ("**", "*.py", "*.ts", "*", "all")


def evaluate(prompt: str) -> tuple[bool, str]:
    """Return (allow, reason). allow=False with reason means block.

    Args:
        prompt: The dispatch prompt body to evaluate.

    Returns:
        Tuple of (allow_flag, human-readable reason).
    """
    if not _BUDGET_HEADER.search(prompt):
        return False, "missing required `context_budget:` block in dispatch prompt"

    files_match = _FILES_IN_SCOPE.search(prompt)
    if not files_match:
        return False, "context_budget is missing `files_in_scope`"

    files_value = files_match.group(1).strip()
    if any(unbounded in files_value for unbounded in _UNBOUNDED_GLOBS) and "[" in files_value:
        return False, f"context_budget.files_in_scope is unbounded: {files_value}"

    if not _FORBIDDEN.search(prompt):
        return False, "context_budget.forbidden must list at least one explicit prohibition"

    return True, "ok"


def main() -> int:
    """Read stdin JSON, evaluate, emit decision JSON. Exit 0 on success."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({}))
        return 0

    if payload.get("tool_name") != "Agent":
        print(json.dumps({}))
        return 0

    prompt = payload.get("tool_input", {}).get("prompt", "")
    allow, reason = evaluate(prompt)

    if allow:
        print(json.dumps({}))
    else:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"IDD context-budget hook: {reason}",
            }
        }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
