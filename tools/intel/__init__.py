"""Cross-feature trap memory package.

Public surface lives in submodules; this ``__init__`` re-exports the
:mod:`tools.intel.lessons` API so callers can write ``from tools.intel
import Lesson, append, parse, ...``.
"""

from __future__ import annotations

from tools.intel.lessons import (
    Lesson,
    LessonError,
    LessonSeverity,
    LessonStatus,
    amend_status,
    append,
    next_id,
    parse,
    parse_text,
)

__all__ = [
    "Lesson",
    "LessonError",
    "LessonSeverity",
    "LessonStatus",
    "amend_status",
    "append",
    "next_id",
    "parse",
    "parse_text",
]
