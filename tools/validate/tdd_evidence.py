"""TDD evidence validator: enforce paired test→impl commits per acceptance criterion.

For every acceptance criterion implemented during the execute phase, the
matching impl commit must be preceded by a test commit recorded earlier in
``state.commits[]``. The contract is enforced as part of the execute-phase
self-review gate; the cross-link to the prose contract is in
``skills/forge-tdd/SKILL.md``.

The validator is a pure function. Diff inspection is delegated to an
injectable ``git_show_files`` callable so tests can fake commits without
shelling out, and so production callers can swap in alternate inspectors
(e.g. a libgit2 wrapper) without touching this module.

Findings (severity → code → meaning):

- ``BLOCK`` ``tdd_evidence:feature_missing``: feature directory absent.
- ``BLOCK`` ``tdd_evidence:missing_test_pair``: AC has impl commit(s) but no
  test commit logged strictly before the earliest impl commit, and no
  ``## TDD Exception: <ac-id>`` heading in ``decisions.md``.
- ``LOW`` ``tdd_evidence:suspicious_test_commit``: test commit's diff touches
  paths outside ``tests/``.
- ``INFO`` ``tdd_evidence:refactor_touches_production``: a refactor commit on
  the AC touches production code (``src/`` or ``tools/``); pairing not required
  but flagged so reviewers notice.
- ``INFO`` ``tdd_evidence:no_impl_commits``: AC has only docs/refactor/chore
  commits, no impl. Advisory — might mean the slice misclassified its scope.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from ._feature_layout import DECISIONS_FILENAME, SPEC_FILENAME, STATE_FILENAME
from ._finding import Finding, Severity
from ._frontmatter import _read_text

TARGET = "tdd_evidence"

_AC_TAG_RE = re.compile(r"\b(?:AC-(\d+)|crit-(\d+))\b", re.IGNORECASE)
_AC_LINE_RE = re.compile(r"^(?P<ac>AC-\d+|crit-\d+)\s*:\s*(?P<sha>[0-9a-f]{7,40})", re.MULTILINE)
_SHA_NEAR_AC_RE = re.compile(r"\b([0-9a-f]{7,40})\b")
_AC_NUMBERED_RE = re.compile(r"^(\d+)\.\s+\S+", re.MULTILINE)
_ACCEPTANCE_BLOCK_RE = re.compile(r"(?ms)^# Acceptance Criteria\b[^\n]*\n(?P<body>.*?)(?=^# |\Z)")
_TDD_EXCEPTION_RE = re.compile(
    r"^##\s+TDD\s+Exception:\s+(?P<ac>AC-\d+|crit-\d+)\s*$",
    re.MULTILINE,
)

_SEVERITY_RANK: dict[Severity, int] = {
    "BLOCK": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "WARN": 4,
    "INFO": 5,
}

_PRODUCTION_PREFIXES: tuple[str, ...] = ("src/", "tools/", "hooks/", "schemas/")


def _real_git_show_files(sha: str) -> list[str]:
    """Default ``git_show_files`` impl — shells out to ``git show --name-only``."""
    proc = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", sha],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _normalise_ac_id(raw: str) -> str:
    """Return canonical ``AC-<n>`` form for matching across heterogeneous sources."""
    match = re.match(r"(?:AC|crit)-(\d+)", raw, re.IGNORECASE)
    if match is None:
        return raw
    return f"AC-{match.group(1)}"


_ROLE_BY_PREFIX: dict[str, str] = {
    "test": "test",
    "feat": "impl",
    "fix": "impl",
    "refactor": "refactor",
    "docs": "docs",
    "chore": "chore",
}


def _classify_subject(subject: str) -> str:
    """Map a Conventional-Commit subject to a role.

    Returns one of: ``test`` / ``impl`` / ``refactor`` / ``docs`` / ``chore``
    / ``other``. The leading type token is taken from the subject up to the
    first ``:``, ``(``, or whitespace.
    """
    head = subject.strip().split(":", 1)[0].lower()
    prefix = re.split(r"[\s(]", head, maxsplit=1)[0]
    return _ROLE_BY_PREFIX.get(prefix, "other")


def _extract_ac_ids_from_spec(spec_text: str) -> list[str]:
    block = _ACCEPTANCE_BLOCK_RE.search(spec_text)
    if block is None:
        return []
    return [f"AC-{m.group(1)}" for m in _AC_NUMBERED_RE.finditer(block.group("body"))]


def _parse_slice_summaries(feature_dir: Path) -> dict[str, set[str]]:
    """Walk ``slice-*.summary`` files; return AC -> set of commit SHAs.

    Two parsing strategies are supported (both forgiving):

    1. Explicit ``AC-<n>: <sha>`` lines.
    2. Lines containing both an AC tag and a SHA in any order — useful when
       authors record ``feat(...): AC-1 implemented in abcdef0`` style.
    """
    out: dict[str, set[str]] = {}
    for summary_path in sorted(feature_dir.glob("slice-*.summary")):
        text = _read_text(summary_path)
        if text is None:
            continue
        for match in _AC_LINE_RE.finditer(text):
            ac_id = _normalise_ac_id(match.group("ac"))
            out.setdefault(ac_id, set()).add(match.group("sha"))
        for line in text.splitlines():
            ac_match = _AC_TAG_RE.search(line)
            sha_match = _SHA_NEAR_AC_RE.search(line)
            if ac_match is None or sha_match is None:
                continue
            digits = ac_match.group(1) or ac_match.group(2)
            ac_id = f"AC-{digits}"
            out.setdefault(ac_id, set()).add(sha_match.group(1))
    return out


def _parse_tdd_exceptions(decisions_text: str) -> set[str]:
    return {_normalise_ac_id(m.group("ac")) for m in _TDD_EXCEPTION_RE.finditer(decisions_text)}


def _load_execute_commits(state_path: Path) -> list[dict[str, str]]:
    text = _read_text(state_path)
    if text is None:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    commits = payload.get("commits") if isinstance(payload, dict) else None
    if not isinstance(commits, list):
        return []
    out: list[dict[str, str]] = []
    for entry in commits:
        if not isinstance(entry, dict):
            continue
        if entry.get("phase") != "execute":
            continue
        sha = str(entry.get("sha", ""))
        subject = str(entry.get("subject", ""))
        logged_at = str(entry.get("logged_at", ""))
        if not sha or not subject:
            continue
        out.append({"sha": sha, "subject": subject, "logged_at": logged_at})
    return out


def _sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_RANK.get(f.severity, 99), f.message),
    )


def _shas_match(declared: str, candidate: str) -> bool:
    """Match short and long SHAs against each other prefix-wise."""
    if not declared or not candidate:
        return False
    if declared == candidate:
        return True
    short, long = sorted((declared, candidate), key=len)
    return long.startswith(short)


def _commits_for_ac(
    ac_shas: set[str],
    execute_commits: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Filter execute_commits to those whose SHA matches one of ac_shas."""
    return [c for c in execute_commits if any(_shas_match(s, c["sha"]) for s in ac_shas)]


def _classify_ac_commits(
    ac_commits: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    roles: dict[str, list[dict[str, str]]] = {
        "test": [],
        "impl": [],
        "refactor": [],
        "docs": [],
        "chore": [],
        "other": [],
    }
    for commit in ac_commits:
        roles[_classify_subject(commit["subject"])].append(commit)
    return roles


def _diff_findings_for_ac(
    ac_id: str,
    roles: dict[str, list[dict[str, str]]],
    inspect: Callable[[str], list[str]],
    state_path: Path,
) -> list[Finding]:
    """Emit advisory findings driven by per-commit diff inspection."""
    out: list[Finding] = []
    for refactor_commit in roles["refactor"]:
        files = inspect(refactor_commit["sha"])
        if any(f.startswith(_PRODUCTION_PREFIXES) for f in files):
            out.append(
                Finding(
                    "INFO",
                    TARGET,
                    state_path,
                    f"tdd_evidence:refactor_touches_production — {ac_id} "
                    f"refactor commit {refactor_commit['sha']} touches production paths",
                )
            )
    for test_commit in roles["test"]:
        files = inspect(test_commit["sha"])
        non_test = [f for f in files if not f.startswith("tests/")]
        if files and non_test:
            out.append(
                Finding(
                    "LOW",
                    TARGET,
                    state_path,
                    f"tdd_evidence:suspicious_test_commit — {ac_id} test commit "
                    f"{test_commit['sha']} touches non-test paths: {sorted(non_test)}",
                )
            )
    return out


def _pairing_findings_for_ac(
    ac_id: str,
    roles: dict[str, list[dict[str, str]]],
    state_path: Path,
) -> list[Finding]:
    """Emit BLOCK/INFO findings driven by the test/impl pairing rule."""
    if not roles["impl"]:
        if not (roles["test"] or roles["refactor"] or roles["docs"] or roles["chore"]):
            return []
        return [
            Finding(
                "INFO",
                TARGET,
                state_path,
                f"tdd_evidence:no_impl_commits — {ac_id} has only "
                f"docs/refactor/chore commits; verify scope classification",
            )
        ]
    impl_times = [c["logged_at"] for c in roles["impl"] if c["logged_at"]]
    earliest_impl = min(impl_times) if impl_times else ""
    preceding_test = [
        t
        for t in roles["test"]
        if t["logged_at"] and earliest_impl and t["logged_at"] < earliest_impl
    ]
    if preceding_test:
        return []
    return [
        Finding(
            "BLOCK",
            TARGET,
            state_path,
            f"tdd_evidence:missing_test_pair — {ac_id} has impl commit "
            f"without a preceding test commit (and no TDD Exception ADR)",
        )
    ]


def validate_tdd_evidence(
    repo_root: Path,
    feature_id: str,
    *,
    git_show_files: Callable[[str], list[str]] | None = None,
) -> list[Finding]:
    """Assert every implemented acceptance criterion has a paired preceding test commit.

    Args:
        repo_root: Repository root containing ``.forge/features/<feature_id>/``.
        feature_id: Slug folder name under ``.forge/features``.
        git_show_files: Callable that returns the file paths touched by a
            commit, used for diff-shape inspection. Defaults to a
            ``git show --name-only`` shell-out; tests inject a fake.

    Returns:
        Sorted list of Finding records. Empty list means the feature's
        execute-phase commits satisfy the paired-commit rule.
    """
    inspect = git_show_files if git_show_files is not None else _real_git_show_files

    feature_dir = repo_root / ".forge" / "features" / feature_id
    if not feature_dir.is_dir():
        return [
            Finding(
                "BLOCK",
                TARGET,
                feature_dir,
                f"tdd_evidence:feature_missing — {feature_dir} does not exist",
            )
        ]

    spec_text = _read_text(feature_dir / SPEC_FILENAME) or ""
    decisions_text = _read_text(feature_dir / DECISIONS_FILENAME) or ""
    exceptions = _parse_tdd_exceptions(decisions_text)

    ac_ids = _extract_ac_ids_from_spec(spec_text)
    slice_map = _parse_slice_summaries(feature_dir)
    # Include any AC referenced only by a slice summary even if SPEC parsing
    # missed it — the validator must not silently skip work the slice claims.
    for slice_ac in slice_map:
        if slice_ac not in ac_ids:
            ac_ids.append(slice_ac)

    execute_commits = _load_execute_commits(feature_dir / STATE_FILENAME)

    findings: list[Finding] = []
    state_path = feature_dir / STATE_FILENAME

    for ac_id in ac_ids:
        ac_shas = slice_map.get(ac_id, set())
        roles = _classify_ac_commits(_commits_for_ac(ac_shas, execute_commits))
        findings.extend(_diff_findings_for_ac(ac_id, roles, inspect, state_path))
        if ac_id in exceptions:
            continue
        findings.extend(_pairing_findings_for_ac(ac_id, roles, state_path))

    return _sort_findings(findings)


__all__ = ["TARGET", "validate_tdd_evidence"]
