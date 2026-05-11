"""Lint: every ```json state.json example block in README.md must validate.

The README ships illustrative ``state.json`` fenced blocks under the
"What the artifacts look like" section. Those examples are read as
context by both humans and agents, so drift between the example shape
and the live schema teaches both the wrong contract.

This test extracts every ```json fenced block whose ``feature_id``
matches the state.json ID pattern (i.e., the block is plausibly a
state.json payload, not an unrelated JSON example like a config or
schema snippet) and validates each against ``schemas/state.schema.json``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

_FENCED_JSON = re.compile(r"```json\n(?P<body>.+?)\n```", re.DOTALL)
_STATE_FEATURE_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9](?:[a-z0-9]|-(?=[a-z0-9]))+$")


def _extract_state_blocks(markdown: str) -> list[tuple[int, dict[str, object]]]:
    """Return [(line_number, payload)] for fenced ```json blocks shaped like state.json.

    A block qualifies as a state.json example when it parses as a JSON
    object and its top-level ``feature_id`` matches the state.json
    feature_id pattern. Other ``json`` blocks (schema snippets, config
    examples) are ignored.
    """
    matches: list[tuple[int, dict[str, object]]] = []
    for match in _FENCED_JSON.finditer(markdown):
        body = match.group("body")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        feature_id = payload.get("feature_id")
        if not isinstance(feature_id, str):
            continue
        if not _STATE_FEATURE_ID.match(feature_id):
            continue
        line = markdown.count("\n", 0, match.start()) + 1
        matches.append((line, payload))
    return matches


def test_readme_state_json_examples_validate_against_schema(repo_root: Path) -> None:
    """Every state.json example block in README.md must satisfy state.schema.json."""
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    schema = json.loads((repo_root / "schemas" / "state.schema.json").read_text(encoding="utf-8"))
    blocks = _extract_state_blocks(readme)

    assert blocks, (
        "No state.json example blocks detected in README.md — extractor may be "
        "misconfigured if examples actually exist"
    )

    failures: list[str] = []
    for line, payload in blocks:
        try:
            jsonschema.validate(payload, schema)
        except jsonschema.ValidationError as exc:
            failures.append(f"README.md:{line} — {exc.message}")

    assert not failures, "README state.json examples drifted from schema:\n" + "\n".join(failures)
