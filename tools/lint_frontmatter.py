"""Lint markdown frontmatter for IDD skills and commands."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class FrontmatterError(RuntimeError):
    """Raised when frontmatter cannot be parsed or fails schema validation."""


_FENCE = "---"


def parse_frontmatter(path: Path) -> dict[str, Any] | None:
    """Parse the YAML frontmatter at the top of a markdown file.

    Args:
        path: Path to the markdown file.

    Returns:
        Parsed frontmatter dict, or None if the file has no frontmatter block.

    Raises:
        FrontmatterError: Block opened but never closed, YAML invalid, or top-level
            value is not a mapping.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines or lines[0].strip() != _FENCE:
        return None

    body: list[str] = []
    closed = False
    for line in lines[1:]:
        if line.strip() == _FENCE:
            closed = True
            break
        body.append(line)

    if not closed:
        raise FrontmatterError(f"{path}: unclosed frontmatter block (missing closing '---')")

    try:
        parsed = yaml.safe_load("\n".join(body))
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"{path}: invalid YAML in frontmatter: {exc}") from exc

    if not isinstance(parsed, dict):
        raise FrontmatterError(
            f"{path}: frontmatter must be a YAML mapping, got {type(parsed).__name__}"
        )

    return parsed
