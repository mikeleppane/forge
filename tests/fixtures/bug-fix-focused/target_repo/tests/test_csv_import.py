"""Tests for the dummy CSV import path."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "import" / "csv.py"
_spec = importlib.util.spec_from_file_location("fixture_csv", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
_csv_mod = importlib.util.module_from_spec(_spec)
sys.modules["fixture_csv"] = _csv_mod
_spec.loader.exec_module(_csv_mod)
import_row = _csv_mod.import_row  # type: ignore[attr-defined]


def test_trims_leading_and_trailing() -> None:
    assert import_row(["  alice@example.com  "]) == ["alice@example.com"]


def test_preserves_internal_whitespace() -> None:
    assert import_row(["Alice  Smith"]) == ["Alice  Smith"]
