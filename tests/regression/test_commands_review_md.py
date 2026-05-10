"""Static contract tests pinning the /forge:review command file.

The command documents the cross-AI manual-mode flags now that the
underlying skill branch and helpers exist. These tests lock the
contract so the description hedge and the prior stub flag definitions
cannot silently return, and so the new flag surface stays documented
for users of the command file.
"""

from __future__ import annotations

from pathlib import Path

COMMAND = Path("commands/review.md")


def _command_body() -> str:
    return COMMAND.read_text(encoding="utf-8")


def test_description_frontmatter_no_longer_hedges_about_future_milestone() -> None:
    body = _command_body()
    frontmatter_end = body.find("\n---", 4)
    assert frontmatter_end != -1, "command file must have a closing frontmatter fence"
    frontmatter = body[:frontmatter_end]
    assert "M4 territory" not in frontmatter, (
        "Description frontmatter must drop the prior cross-AI hedge "
        "now that the manual mode dispatch branch exists"
    )


def test_body_does_not_carry_prior_stub_flag_message() -> None:
    body = _command_body()
    assert "M4 territory; not implemented in M2" not in body, (
        "Stub flag definition must be replaced with the real cross-AI flag contract"
    )


def test_body_documents_cross_ai_flag_with_real_behavior() -> None:
    body = _command_body()
    assert "--cross-ai" in body, (
        "Body must document the --cross-ai flag so users can discover the manual-mode dispatch path"
    )
    assert "not implemented" not in body, (
        "Documented --cross-ai flag must describe real behavior, not a not-implemented stub"
    )


def test_body_documents_cross_ai_paste_flag() -> None:
    body = _command_body()
    assert "--cross-ai-paste" in body, (
        "Body must document the --cross-ai-paste flag so users can discover the paste-back path"
    )
