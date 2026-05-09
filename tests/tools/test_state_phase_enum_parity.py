"""Single-source-of-truth lock for the shared phase vocabulary.

``current_phase.enum`` and ``routing.phase_list.items.enum`` describe the same
set of lifecycle phases, with one structural difference: ``current_phase``
includes the terminal ``done`` state, while ``phase_list`` enumerates phases a
feature will execute (``done`` is never a phase to execute). Drift between the
two enums is silent and corrosive; this test makes drift loud.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_phase_list_enum_matches_current_phase_minus_done(schemas_dir: Path) -> None:
    schema = json.loads((schemas_dir / "state.schema.json").read_text(encoding="utf-8"))

    current_phase_enum = set(schema["properties"]["current_phase"]["enum"])
    phase_list_enum = set(
        schema["properties"]["routing"]["properties"]["phase_list"]["items"]["enum"]
    )

    assert phase_list_enum == current_phase_enum - {"done"}, (
        "phase_list.items.enum must equal current_phase.enum minus 'done'; "
        f"current_phase={sorted(current_phase_enum)}, "
        f"phase_list={sorted(phase_list_enum)}"
    )
