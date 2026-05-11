"""Tests for hooks.check_state_writer — refuses direct writes to feature state.json."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "hooks" / "check_state_writer.py"

_spec = importlib.util.spec_from_file_location("check_state_writer", HOOK)
assert _spec is not None and _spec.loader is not None
check_state_writer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_state_writer)


# ---------------------------------------------------------------------------
# is_blocked_path — positive cases (paths the hook MUST refuse)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "blocked",
    [
        ".forge/features/2026-05-10-demo/state.json",
        "/home/mikelep/personal/dev/idd/.forge/features/2026-05-10-demo/state.json",
        "/abs/path/repo/.forge/features/csv-row-validator/state.json",
        "subdir/.forge/features/feature-id/state.json",
        "./.forge/features/x/state.json",
        "/var/work/scratch/.forge/features/2026-01-01-foo/state.json",
        "very/deep/nested/.forge/features/abc/state.json",
    ],
)
def test_is_blocked_path_refuses_feature_state_json_at_any_depth(blocked: str) -> None:
    assert check_state_writer.is_blocked_path(blocked) is True


# ---------------------------------------------------------------------------
# is_blocked_path — negative cases (paths the hook MUST allow)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "allowed",
    [
        ".forge/features/2026-05-10-demo/SPEC.md",
        ".forge/features/2026-05-10-demo/decisions.md",
        "tests/tools/fixtures/state.json",  # test fixture is not a feature
        "templates/feature/state.json",  # template seed is not a live feature
        ".forge/state.json",  # under .forge but not under features/<id>/
        ".forge/features/state.json",  # missing the feature id segment
        "docs/notes.json",
        "/abs/path/.forge/features/x/SPEC.md",
        "state.json",  # bare filename, no parent context
        "/etc/state.json",
    ],
)
def test_is_blocked_path_allows_non_feature_state_paths(allowed: str) -> None:
    assert check_state_writer.is_blocked_path(allowed) is False


def test_is_blocked_path_rejects_empty_string() -> None:
    assert check_state_writer.is_blocked_path("") is False


# ---------------------------------------------------------------------------
# evaluate — delegates by tool name and tool_input shape
# ---------------------------------------------------------------------------


def test_evaluate_allows_unrelated_tool_names() -> None:
    allow, reason = check_state_writer.evaluate(
        "Read",
        {"file_path": ".forge/features/x/state.json"},
    )
    assert allow is True
    assert reason is None


def test_evaluate_allows_agent_dispatch() -> None:
    allow, reason = check_state_writer.evaluate("Agent", {"prompt": "anything"})
    assert allow is True
    assert reason is None


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "MultiEdit"])
def test_evaluate_denies_write_family_on_feature_state_json(tool_name: str) -> None:
    allow, reason = check_state_writer.evaluate(
        tool_name,
        {"file_path": ".forge/features/2026-05-10-demo/state.json"},
    )
    assert allow is False
    assert reason is not None
    assert "tools.state" in reason


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "MultiEdit"])
def test_evaluate_allows_write_family_on_other_paths(tool_name: str) -> None:
    allow, reason = check_state_writer.evaluate(
        tool_name,
        {"file_path": ".forge/features/x/SPEC.md"},
    )
    assert allow is True
    assert reason is None


def test_evaluate_allows_write_with_missing_file_path() -> None:
    """A Write call without file_path can't match the pattern; do not block."""
    allow, reason = check_state_writer.evaluate("Write", {})
    assert allow is True
    assert reason is None


def test_evaluate_allows_multiedit_with_edits_list_alongside_file_path() -> None:
    """MultiEdit carries an edits[] list; hook only inspects file_path."""
    allow, reason = check_state_writer.evaluate(
        "MultiEdit",
        {
            "file_path": ".forge/features/x/decisions.md",
            "edits": [{"old_string": "a", "new_string": "b"}],
        },
    )
    assert allow is True
    assert reason is None


def test_evaluate_denies_multiedit_targeting_feature_state_json() -> None:
    allow, reason = check_state_writer.evaluate(
        "MultiEdit",
        {
            "file_path": ".forge/features/x/state.json",
            "edits": [{"old_string": "a", "new_string": "b"}],
        },
    )
    assert allow is False
    assert reason is not None


# ---------------------------------------------------------------------------
# main() — end-to-end subprocess test mirroring check_budget's pattern
# ---------------------------------------------------------------------------


def _run_hook(payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def test_main_denies_direct_write_to_feature_state_json() -> None:
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {
            "file_path": ".forge/features/2026-05-10-demo/state.json",
            "content": "{}",
        },
    }

    result = _run_hook(payload)

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert output["hookSpecificOutput"]["permissionDecisionReason"].startswith(
        "FORGE state-writer hook:"
    )


def test_main_allows_write_to_spec_md() -> None:
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {
            "file_path": ".forge/features/2026-05-10-demo/SPEC.md",
            "content": "# spec",
        },
    }

    result = _run_hook(payload)

    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


def test_main_allows_unrelated_tool_call() -> None:
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": ".forge/features/2026-05-10-demo/state.json"},
    }

    result = _run_hook(payload)

    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


def test_main_allows_invalid_json_stdin() -> None:
    """Malformed stdin must default to allow; the hook is not a JSON validator."""
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="{not json",
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {}
