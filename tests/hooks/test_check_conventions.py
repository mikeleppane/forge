"""Subprocess tests for hooks.check_conventions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "hooks" / "check_conventions.py"


def _write_conventions(
    repo_root: Path,
    *,
    rule_id: str = "block-forbidden-text",
    pattern_kind: str = "forbidden_text",
    pattern: str = "FORBIDDEN",
    severity: str = "BLOCK",
) -> None:
    forge_dir = repo_root / ".forge"
    forge_dir.mkdir()
    payload = {
        "schema_version": 1,
        "rules": [
            {
                "id": rule_id,
                "source_file": "AGENTS.md",
                "source_line": 1,
                "pattern_kind": pattern_kind,
                "pattern": pattern,
                "scope": ["diff"],
                "severity": severity,
            },
        ],
    }
    (forge_dir / "conventions.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _run_hook(
    repo_root: Path,
    payload: dict[str, Any] | str,
) -> subprocess.CompletedProcess[str]:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    env = {"FORGE_REPO_ROOT": str(repo_root)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _write_payload(file_path: Path, content: str) -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(file_path),
            "content": content,
        },
    }


def test_positive_content_match_denies(tmp_path: Path) -> None:
    _write_conventions(tmp_path, rule_id="no-forbidden", pattern="FORBIDDEN")
    target = tmp_path / "notes.md"

    result = _run_hook(tmp_path, _write_payload(target, "contains FORBIDDEN\n"))

    assert result.returncode != 0
    assert "DENY:" in result.stderr
    assert "no-forbidden" in result.stderr


def test_positive_filename_match_denies(tmp_path: Path) -> None:
    _write_conventions(
        tmp_path,
        rule_id="no-secret-files",
        pattern_kind="filename_glob_forbidden",
        pattern="secrets/*.txt",
    )
    target = tmp_path / "secrets" / "token.txt"

    result = _run_hook(tmp_path, _write_payload(target, "safe body\n"))

    assert result.returncode != 0
    assert "DENY:" in result.stderr
    assert "no-secret-files" in result.stderr


def test_negative_match_allows(tmp_path: Path) -> None:
    _write_conventions(tmp_path, rule_id="no-forbidden", pattern="FORBIDDEN")
    target = tmp_path / "notes.md"

    result = _run_hook(tmp_path, _write_payload(target, "ordinary content\n"))

    assert result.returncode == 0
    assert result.stderr == ""


def test_high_severity_warns_not_denies(tmp_path: Path) -> None:
    _write_conventions(
        tmp_path,
        rule_id="warn-forbidden",
        pattern="FORBIDDEN",
        severity="HIGH",
    )
    target = tmp_path / "notes.md"

    result = _run_hook(tmp_path, _write_payload(target, "contains FORBIDDEN\n"))

    assert result.returncode == 0
    assert "WARN:" in result.stderr
    assert "warn-forbidden" in result.stderr


def test_short_circuit_on_state_json(tmp_path: Path) -> None:
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir()
    (forge_dir / "conventions.json").write_text("{not json", encoding="utf-8")
    target = forge_dir / "features" / "2026-05-18-demo" / "state.json"

    result = _run_hook(tmp_path, _write_payload(target, "FORBIDDEN\n"))

    assert result.returncode == 0
    assert result.stderr == ""


def test_short_circuit_on_unrelated_tool(tmp_path: Path) -> None:
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir()
    (forge_dir / "conventions.json").write_text("{not json", encoding="utf-8")
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(tmp_path / "notes.md")},
    }

    result = _run_hook(tmp_path, payload)

    assert result.returncode == 0
    assert result.stderr == ""


def test_edit_synthesizes_proposed_content(tmp_path: Path) -> None:
    _write_conventions(tmp_path, rule_id="no-post-edit-blocked", pattern="blocked")
    target = tmp_path / "notes.md"
    target.write_text("allowed\n", encoding="utf-8")
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(target),
            "old_string": "allowed",
            "new_string": "blocked",
        },
    }

    result = _run_hook(tmp_path, payload)

    assert result.returncode != 0
    assert "no-post-edit-blocked" in result.stderr


def test_multiedit_applies_edits_in_order(tmp_path: Path) -> None:
    _write_conventions(tmp_path, rule_id="no-final-blocked", pattern="blocked")
    target = tmp_path / "notes.md"
    target.write_text("alpha\n", encoding="utf-8")
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(target),
            "edits": [
                {"old_string": "alpha", "new_string": "beta"},
                {"old_string": "beta", "new_string": "blocked"},
            ],
        },
    }

    result = _run_hook(tmp_path, payload)

    assert result.returncode != 0
    assert "no-final-blocked" in result.stderr


def test_malformed_input_does_not_crash(tmp_path: Path) -> None:
    _write_conventions(tmp_path)

    result = _run_hook(tmp_path, "{not json")

    assert result.returncode == 0
    assert "WARN:" in result.stderr
    assert "not valid JSON" in result.stderr


def test_missing_file_for_edit(tmp_path: Path) -> None:
    _write_conventions(tmp_path)
    target = tmp_path / "missing.md"
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(target),
            "old_string": "before",
            "new_string": "FORBIDDEN",
        },
    }

    result = _run_hook(tmp_path, payload)

    assert result.returncode == 0
    assert "WARN:" in result.stderr
    assert "file does not exist" in result.stderr


def test_load_error_on_malformed_conventions_json(tmp_path: Path) -> None:
    forge_dir = tmp_path / ".forge"
    forge_dir.mkdir()
    (forge_dir / "conventions.json").write_text("{not json", encoding="utf-8")
    target = tmp_path / "notes.md"

    result = _run_hook(tmp_path, _write_payload(target, "FORBIDDEN\n"))

    assert result.returncode == 0
    assert "WARN:" in result.stderr
    assert "conventions.json could not be evaluated" in result.stderr
