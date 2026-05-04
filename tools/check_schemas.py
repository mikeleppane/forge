"""Validate that every shipped JSON Schema is itself a valid Draft 2020-12 schema.

Also validates the state.json template against state.schema.json (after substituting
its placeholder feature_id) and the SPEC.md template's frontmatter against
spec-frontmatter.schema.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"
TEMPLATES_DIR = REPO_ROOT / "templates"


def _check_schema(name: str) -> None:
    """Validate a single shipped schema against Draft 2020-12 metaschema."""
    schema = json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    print(f"OK schema {name}")


def _check_state_template() -> None:
    """Validate templates/feature/state.json against state.schema.json."""
    schema = json.loads((SCHEMAS_DIR / "state.schema.json").read_text(encoding="utf-8"))
    template: dict[str, Any] = json.loads(
        (TEMPLATES_DIR / "feature" / "state.json").read_text(encoding="utf-8")
    )
    template["feature_id"] = "2026-05-03-template-check"
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    ).validate(template)
    print("OK template state.json")


def _check_spec_template_frontmatter() -> None:
    """Validate templates/feature/SPEC.md frontmatter against spec-frontmatter.schema.json."""
    schema = json.loads(
        (SCHEMAS_DIR / "spec-frontmatter.schema.json").read_text(encoding="utf-8")
    )
    body = (TEMPLATES_DIR / "feature" / "SPEC.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", body, flags=re.DOTALL)
    if not match:
        raise SystemExit("SPEC.md template missing frontmatter block")
    fm: dict[str, Any] = yaml.safe_load(match.group(1))
    fm["id"] = "2026-05-03-template-check"
    fm["tier"] = "focused"
    fm["created"] = "2026-05-03"
    fm["capability"] = "template-check"
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    ).validate(fm)
    print("OK template SPEC.md frontmatter")


def main() -> int:
    """Run all schema and template checks; return 0 on success, 1 on failure."""
    try:
        for name in ("state.schema.json", "frontmatter.schema.json", "spec-frontmatter.schema.json"):
            _check_schema(name)
        _check_state_template()
        _check_spec_template_frontmatter()
    except (jsonschema.SchemaError, jsonschema.ValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
