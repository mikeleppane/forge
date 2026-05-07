"""Pin the dispatch hook's permissiveness on the optional articles[] field (M3 P3).

`hooks/check_budget.py` only enforces `files_in_scope` + `forbidden`. The
`articles[]` budget field rides through unchanged. These tests guard against
a future hook tightening that silently regresses the dispatch contract.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / "hooks" / "check_budget.py"


def _run_hook(prompt: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(
            {
                "tool_name": "Agent",
                "tool_input": {"prompt": prompt},
            }
        ),
        capture_output=True,
        text=True,
        check=False,
    )


def test_hook_accepts_dispatch_with_articles() -> None:
    prompt = """You are an IDD test subagent.

context_budget:
{
  "spec_sections": ["Acceptance"],
  "files_in_scope": ["src/main.py"],
  "forbidden": ["read entire repo"],
  "return_format": {"max_words": 100},
  "articles": [
    {"id": "A1", "title": "Vault", "level": "CRITICAL", "rule": "Use vault.", "reference": null, "rationale": null}
  ]
}

# Task
Do work."""
    result = _run_hook(prompt)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "{}", "permissive allow → empty output"


def test_hook_accepts_dispatch_without_articles() -> None:
    prompt = """You are an IDD test subagent.

context_budget:
{
  "spec_sections": ["Acceptance"],
  "files_in_scope": ["src/main.py"],
  "forbidden": ["read entire repo"],
  "return_format": {"max_words": 100}
}

# Task
Do work."""
    result = _run_hook(prompt)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "{}"
