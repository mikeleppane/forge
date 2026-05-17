"""Tests for the per-file coverage floor CI helper.

The helper enforces ``max(absolute_floor, baseline_pct)`` against a Cobertura
``coverage.xml`` for every path listed in the baseline file. Tests invoke the
helper as a CLI subprocess (``python -m tools.check_coverage_floor``) and
assert on exit code, stdout, and stderr.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent


def _write_coverage_xml(path: Path, files: dict[str, float]) -> None:
    """Emit a minimal Cobertura ``coverage.xml`` for the given filename → line-rate map."""
    classes = "\n".join(
        f'        <class filename="{filename}" line-rate="{rate}" />'
        for filename, rate in files.items()
    )
    xml = dedent(
        f"""\
        <?xml version="1.0" ?>
        <coverage line-rate="0.9" version="6.0">
          <packages>
            <package name="forge" line-rate="0.9">
              <classes>
        {classes}
              </classes>
            </package>
          </packages>
        </coverage>
        """
    )
    path.write_text(xml, encoding="utf-8")


def _run_gate(
    coverage_xml: Path,
    baseline: Path | None = None,
    absolute_floor: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the gate CLI as a subprocess and return its CompletedProcess."""
    cmd: list[str] = [sys.executable, "-m", "tools.check_coverage_floor", str(coverage_xml)]
    if baseline is not None:
        cmd.extend(["--baseline", str(baseline)])
    if absolute_floor is not None:
        cmd.extend(["--absolute-floor", str(absolute_floor)])
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_passes_when_all_files_meet_floor(tmp_path: Path) -> None:
    """A file above both its baseline and the absolute floor passes the gate."""
    baseline = tmp_path / "coverage.txt"
    baseline.write_text("tools/foo.py: 90%\n", encoding="utf-8")
    coverage_xml = tmp_path / "coverage.xml"
    _write_coverage_xml(coverage_xml, {"tools/foo.py": 0.92})

    result = _run_gate(coverage_xml, baseline=baseline)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Gate PASS" in result.stdout
    assert "BREACH" not in result.stdout


def test_fails_when_file_below_absolute_floor(tmp_path: Path) -> None:
    """A file below the absolute floor (default 85) produces exit 1 and a BREACH line."""
    baseline = tmp_path / "coverage.txt"
    baseline.write_text("tools/foo.py: 60%\n", encoding="utf-8")
    coverage_xml = tmp_path / "coverage.xml"
    _write_coverage_xml(coverage_xml, {"tools/foo.py": 0.60})

    result = _run_gate(coverage_xml, baseline=baseline)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "BREACH tools/foo.py" in result.stdout
    assert "Gate FAIL" in result.stdout


def test_ratchets_floor_to_baseline_when_above_absolute(tmp_path: Path) -> None:
    """Baseline 95% ratchets the floor above the absolute floor; a drop to 90% fails."""
    baseline = tmp_path / "coverage.txt"
    baseline.write_text("tools/foo.py: 95%\n", encoding="utf-8")
    coverage_xml = tmp_path / "coverage.xml"
    _write_coverage_xml(coverage_xml, {"tools/foo.py": 0.90})

    result = _run_gate(coverage_xml, baseline=baseline)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "BREACH tools/foo.py" in result.stdout
    assert "floor 95%" in result.stdout


def test_ignores_files_not_in_baseline(tmp_path: Path) -> None:
    """Files present in coverage.xml but absent from the baseline are not enforced."""
    baseline = tmp_path / "coverage.txt"
    baseline.write_text("tools/foo.py: 90%\n", encoding="utf-8")
    coverage_xml = tmp_path / "coverage.xml"
    _write_coverage_xml(
        coverage_xml,
        {
            "tools/foo.py": 0.92,
            "tools/bar.py": 0.10,
            "hooks/baz.py": 0.05,
        },
    )

    result = _run_gate(coverage_xml, baseline=baseline)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 files checked" in result.stdout
    assert "tools/bar.py" not in result.stdout
    assert "hooks/baz.py" not in result.stdout


def test_missing_baseline_file_exits_2(tmp_path: Path) -> None:
    """A non-existent baseline path is a configuration error (exit 2)."""
    coverage_xml = tmp_path / "coverage.xml"
    _write_coverage_xml(coverage_xml, {"tools/foo.py": 0.95})
    missing_baseline = tmp_path / "does-not-exist.txt"

    result = _run_gate(coverage_xml, baseline=missing_baseline)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "baseline" in result.stderr.lower()


def test_missing_coverage_xml_exits_2(tmp_path: Path) -> None:
    """A non-existent coverage.xml path is a configuration error (exit 2)."""
    baseline = tmp_path / "coverage.txt"
    baseline.write_text("tools/foo.py: 90%\n", encoding="utf-8")
    missing_xml = tmp_path / "no-such-coverage.xml"

    result = _run_gate(missing_xml, baseline=baseline)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "coverage" in result.stderr.lower()


def test_baseline_file_absent_from_coverage_xml_exits_2(tmp_path: Path) -> None:
    """If the baseline names a file not present in coverage.xml, exit 2."""
    baseline = tmp_path / "coverage.txt"
    baseline.write_text("tools/foo.py: 90%\n", encoding="utf-8")
    coverage_xml = tmp_path / "coverage.xml"
    _write_coverage_xml(coverage_xml, {"tools/other.py": 0.99})

    result = _run_gate(coverage_xml, baseline=baseline)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "tools/foo.py" in result.stderr


def test_malformed_baseline_line_exits_2(tmp_path: Path) -> None:
    """A baseline line missing the ``:`` separator is a configuration error."""
    baseline = tmp_path / "coverage.txt"
    baseline.write_text("tools/foo.py 95%\n", encoding="utf-8")
    coverage_xml = tmp_path / "coverage.xml"
    _write_coverage_xml(coverage_xml, {"tools/foo.py": 0.99})

    result = _run_gate(coverage_xml, baseline=baseline)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "baseline" in result.stderr.lower()
