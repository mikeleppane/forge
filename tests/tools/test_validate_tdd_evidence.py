"""Tests for ``tools.validate.tdd_evidence``.

The validator asserts every acceptance criterion implemented during the
execute phase has a paired test commit landing strictly before its impl
commit. The tests inject a fake ``git_show_files`` callable so we never
shell out to git.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from tools import validate
from tools.validate.tdd_evidence import validate_tdd_evidence


def _write_spec(feature_dir: Path, ac_count: int = 1) -> None:
    lines = ["---", "id: 2026-05-08-tdd-fixture", "---", "", "# Acceptance Criteria", ""]
    lines.extend(f"{idx}. AC number {idx} description" for idx in range(1, ac_count + 1))
    lines.append("")
    (feature_dir / "SPEC.md").write_text("\n".join(lines), encoding="utf-8")


def _write_state(feature_dir: Path, commits: list[dict[str, str]]) -> None:
    payload = {
        "feature_id": "2026-05-08-tdd-fixture",
        "tier": "focused",
        "current_phase": "execute",
        "phases": {"execute": {"status": "in_progress"}},
        "skipped": [],
        "deviations": [],
        "commits": commits,
    }
    (feature_dir / "state.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_slice(feature_dir: Path, slice_n: int, ac_to_shas: dict[str, list[str]]) -> None:
    """Write a slice-N.summary mapping AC ids to commit shas.

    The validator parses lines of the form ``AC-<n>: <sha>`` (one sha per
    line, multiple lines allowed for the same AC).
    """
    lines = [f"# Slice {slice_n} summary", ""]
    for ac_id, shas in ac_to_shas.items():
        lines.extend(f"{ac_id}: {sha}" for sha in shas)
    (feature_dir / f"slice-{slice_n}.summary").write_text("\n".join(lines), encoding="utf-8")


def _make_feature(tmp_path: Path) -> Path:
    feature_dir = tmp_path / ".forge" / "features" / "2026-05-08-tdd-fixture"
    feature_dir.mkdir(parents=True)
    return feature_dir


def _no_files(_sha: str) -> list[str]:
    return []


def _git_show(mapping: dict[str, list[str]]) -> Callable[[str], list[str]]:
    def _inner(sha: str) -> list[str]:
        return mapping.get(sha, [])

    return _inner


def test_tdd_evidence_paired_commit_passes(tmp_path: Path) -> None:
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=1)
    _write_state(
        feature_dir,
        [
            {
                "sha": "aaaaaaa",
                "phase": "execute",
                "subject": "test(validate): add failing test for AC-1",
                "logged_at": "2026-05-08T10:00:00Z",
            },
            {
                "sha": "bbbbbbb",
                "phase": "execute",
                "subject": "feat(validate): implement AC-1",
                "logged_at": "2026-05-08T10:05:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["aaaaaaa", "bbbbbbb"]})

    git_show = _git_show({"aaaaaaa": ["tests/tools/test_foo.py"]})
    findings = validate_tdd_evidence(tmp_path, "2026-05-08-tdd-fixture", git_show_files=git_show)

    assert findings == []


def test_tdd_evidence_missing_test_blocks(tmp_path: Path) -> None:
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=1)
    _write_state(
        feature_dir,
        [
            {
                "sha": "1111111",
                "phase": "execute",
                "subject": "feat(validate): implement AC-1",
                "logged_at": "2026-05-08T10:00:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["1111111"]})

    findings = validate_tdd_evidence(tmp_path, "2026-05-08-tdd-fixture", git_show_files=_no_files)

    assert any(f.severity == "BLOCK" and "missing_test_pair" in f.message for f in findings), [
        (f.severity, f.message) for f in findings
    ]


def test_tdd_evidence_test_after_impl_blocks(tmp_path: Path) -> None:
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=1)
    _write_state(
        feature_dir,
        [
            {
                "sha": "2222222",
                "phase": "execute",
                "subject": "feat(validate): implement AC-1",
                "logged_at": "2026-05-08T10:00:00Z",
            },
            {
                "sha": "3333333",
                "phase": "execute",
                "subject": "test(validate): add test for AC-1",
                "logged_at": "2026-05-08T10:05:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["2222222", "3333333"]})

    git_show = _git_show({"3333333": ["tests/tools/test_x.py"]})
    findings = validate_tdd_evidence(tmp_path, "2026-05-08-tdd-fixture", git_show_files=git_show)

    blocks = [f for f in findings if f.severity == "BLOCK"]
    assert blocks, "ordering violation must surface a BLOCK"
    assert any("missing_test_pair" in f.message for f in blocks)


def test_tdd_evidence_exception_adr_skips_pairing(tmp_path: Path) -> None:
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=1)
    _write_state(
        feature_dir,
        [
            {
                "sha": "4444444",
                "phase": "execute",
                "subject": "feat(validate): implement AC-1",
                "logged_at": "2026-05-08T10:00:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["4444444"]})
    (feature_dir / "decisions.md").write_text(
        "## TDD Exception: AC-1\n\n- Rationale: trivial fix\n",
        encoding="utf-8",
    )

    findings = validate_tdd_evidence(tmp_path, "2026-05-08-tdd-fixture", git_show_files=_no_files)

    assert all(f.severity != "BLOCK" for f in findings), [(f.severity, f.message) for f in findings]


def test_tdd_evidence_suspicious_test_commit_low(tmp_path: Path) -> None:
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=1)
    _write_state(
        feature_dir,
        [
            {
                "sha": "5555555",
                "phase": "execute",
                "subject": "test(validate): add test for AC-1",
                "logged_at": "2026-05-08T10:00:00Z",
            },
            {
                "sha": "6666666",
                "phase": "execute",
                "subject": "feat(validate): implement AC-1",
                "logged_at": "2026-05-08T10:05:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["5555555", "6666666"]})

    git_show = _git_show(
        {
            "5555555": ["tests/tools/test_x.py", "tools/foo.py"],
            "6666666": ["tools/foo.py"],
        }
    )
    findings = validate_tdd_evidence(tmp_path, "2026-05-08-tdd-fixture", git_show_files=git_show)

    lows = [f for f in findings if f.severity == "LOW"]
    assert lows, "test commit touching production paths must surface LOW finding"
    assert any("suspicious_test_commit" in f.message for f in lows)


def test_tdd_evidence_refactor_skipped_with_info(tmp_path: Path) -> None:
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=1)
    _write_state(
        feature_dir,
        [
            {
                "sha": "7777777",
                "phase": "execute",
                "subject": "refactor(validate): rename helper",
                "logged_at": "2026-05-08T10:00:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["7777777"]})

    git_show = _git_show({"7777777": ["tools/foo.py"]})
    findings = validate_tdd_evidence(tmp_path, "2026-05-08-tdd-fixture", git_show_files=git_show)

    assert all(f.severity != "BLOCK" for f in findings), [(f.severity, f.message) for f in findings]
    assert any(
        f.severity == "INFO" and "refactor_touches_production" in f.message for f in findings
    ), [(f.severity, f.message) for f in findings]


def test_tdd_evidence_docs_only_no_block(tmp_path: Path) -> None:
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=1)
    _write_state(
        feature_dir,
        [
            {
                "sha": "8888888",
                "phase": "execute",
                "subject": "docs(validate): clarify rule",
                "logged_at": "2026-05-08T10:00:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["8888888"]})

    findings = validate_tdd_evidence(tmp_path, "2026-05-08-tdd-fixture", git_show_files=_no_files)

    assert all(f.severity != "BLOCK" for f in findings), [(f.severity, f.message) for f in findings]


def test_tdd_evidence_feature_missing_blocks(tmp_path: Path) -> None:
    findings = validate_tdd_evidence(
        tmp_path, "2026-05-08-does-not-exist", git_show_files=_no_files
    )

    assert len(findings) == 1
    assert findings[0].severity == "BLOCK"
    assert "feature_missing" in findings[0].message


def test_tdd_evidence_findings_sorted_deterministically(tmp_path: Path) -> None:
    """Findings must sort by (severity_rank, code, ac_id) so output is stable."""
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=2)
    _write_state(
        feature_dir,
        [
            {
                "sha": "ddddddd",
                "phase": "execute",
                "subject": "feat(validate): implement AC-2",
                "logged_at": "2026-05-08T10:00:00Z",
            },
            {
                "sha": "ccccccc",
                "phase": "execute",
                "subject": "feat(validate): implement AC-1",
                "logged_at": "2026-05-08T10:00:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["ccccccc"], "AC-2": ["ddddddd"]})

    findings = validate_tdd_evidence(tmp_path, "2026-05-08-tdd-fixture", git_show_files=_no_files)

    blocks = [f for f in findings if f.severity == "BLOCK"]
    assert len(blocks) == 2
    # AC-1 must precede AC-2 in sort order.
    assert "AC-1" in blocks[0].message
    assert "AC-2" in blocks[1].message


def test_tdd_evidence_cli_target_registered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=1)
    _write_state(
        feature_dir,
        [
            {
                "sha": "9999999",
                "phase": "execute",
                "subject": "feat(validate): implement AC-1",
                "logged_at": "2026-05-08T10:00:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["9999999"]})

    rc = validate.main(
        [
            "--target",
            "tdd_evidence",
            "--repo-root",
            str(tmp_path),
            str(feature_dir),
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 1, "missing test pair must drive non-zero exit"
    assert payload["target"] == "tdd_evidence"
    assert any(f["severity"] == "BLOCK" for f in payload["findings"])


def test_tdd_evidence_cli_target_all_includes_tdd(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    feature_dir = _make_feature(tmp_path)
    _write_spec(feature_dir, ac_count=1)
    _write_state(
        feature_dir,
        [
            {
                "sha": "aabbccd",
                "phase": "execute",
                "subject": "feat(validate): implement AC-1",
                "logged_at": "2026-05-08T10:00:00Z",
            },
        ],
    )
    _write_slice(feature_dir, 1, {"AC-1": ["aabbccd"]})
    # Stub out PLAN.md frontmatter the `all` fan-out expects (none here).

    rc = validate.main(["--target", "all", "--repo-root", str(tmp_path)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    targets_seen = {f.get("target") for f in payload["findings"]}
    assert "tdd_evidence" in targets_seen, payload
    assert rc == 1
