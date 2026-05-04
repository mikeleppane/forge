"""Tests for tools.lint_frontmatter — frontmatter validator for skills/commands."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import lint_frontmatter as lint


def test_parse_extracts_yaml_block_from_top(tmp_path: Path) -> None:
    md = tmp_path / "skill.md"
    md.write_text(
        "---\nname: idd-spec\ndescription: Author a feature SPEC.md. Use when starting a new feature.\n---\n\n# body\n",
        encoding="utf-8",
    )

    result = lint.parse_frontmatter(md)

    assert result == {
        "name": "idd-spec",
        "description": "Author a feature SPEC.md. Use when starting a new feature.",
    }


def test_parse_returns_none_when_no_frontmatter(tmp_path: Path) -> None:
    md = tmp_path / "no-fm.md"
    md.write_text("# just a heading\nno frontmatter here\n", encoding="utf-8")

    assert lint.parse_frontmatter(md) is None


def test_parse_raises_on_unclosed_block(tmp_path: Path) -> None:
    md = tmp_path / "broken.md"
    md.write_text("---\nname: idd-spec\n# missing closing fence\n", encoding="utf-8")

    with pytest.raises(lint.FrontmatterError, match="unclosed"):
        lint.parse_frontmatter(md)


def test_parse_raises_on_invalid_yaml(tmp_path: Path) -> None:
    md = tmp_path / "bad-yaml.md"
    md.write_text("---\nname: : :\n---\n", encoding="utf-8")

    with pytest.raises(lint.FrontmatterError, match="YAML"):
        lint.parse_frontmatter(md)
