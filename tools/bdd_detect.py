"""Detect the project's BDD framework per IDD design §6.6.

Top-level dependency declarations only — no transitive scan, no lockfile scan.
False positives are worse than missed escalations: when ambiguous, return None
and let the calling skill ask the user once.
"""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BDDFramework:
    """Resolved BDD framework binding for a project."""

    ecosystem: str
    framework: str
    features_dir: Path


_PYTHON_FEATURES_DIR = Path("tests/features")
_NODE_FEATURES_DIR = Path("features")
_RUBY_FEATURES_DIR = Path("features")
_GO_FEATURES_DIR = Path("features")


def _read_idd_config_override(repo_root: Path) -> BDDFramework | None:
    config_path = repo_root / ".idd" / "config.json"
    if not config_path.is_file():
        return None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    bdd = config.get("bdd_framework")
    if not isinstance(bdd, dict):
        return None
    try:
        return BDDFramework(
            ecosystem=str(bdd["ecosystem"]),
            framework=str(bdd["framework"]),
            features_dir=Path(str(bdd["features_dir"])),
        )
    except KeyError:
        return None


def _detect_python(repo_root: Path) -> BDDFramework | None:
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return None
    project_deps = data.get("project", {}).get("dependencies", [])
    pytest_ini = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
    declared = any("pytest-bdd" in str(dep) for dep in project_deps) or any(
        "pytest-bdd" in str(v) for v in pytest_ini.values()
    )
    if not declared:
        return None
    if not (repo_root / _PYTHON_FEATURES_DIR).is_dir():
        return None
    return BDDFramework(ecosystem="python", framework="pytest-bdd", features_dir=_PYTHON_FEATURES_DIR)


def _detect_node(repo_root: Path) -> BDDFramework | None:
    pkg = repo_root / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    if "@cucumber/cucumber" not in deps:
        return None
    has_config = (repo_root / "cucumber.js").is_file() or (repo_root / "cucumber.cjs").is_file()
    if not has_config:
        return None
    if not (repo_root / _NODE_FEATURES_DIR).is_dir():
        return None
    return BDDFramework(ecosystem="node", framework="cucumber-js", features_dir=_NODE_FEATURES_DIR)


def _detect_ruby(repo_root: Path) -> BDDFramework | None:
    gemfile = repo_root / "Gemfile"
    if not gemfile.is_file():
        return None
    if "cucumber" not in gemfile.read_text(encoding="utf-8"):
        return None
    if not (repo_root / _RUBY_FEATURES_DIR).is_dir():
        return None
    return BDDFramework(ecosystem="ruby", framework="cucumber-ruby", features_dir=_RUBY_FEATURES_DIR)


def _detect_go(repo_root: Path) -> BDDFramework | None:
    gomod = repo_root / "go.mod"
    if not gomod.is_file():
        return None
    if "github.com/cucumber/godog" not in gomod.read_text(encoding="utf-8"):
        return None
    if not (repo_root / _GO_FEATURES_DIR).is_dir():
        return None
    return BDDFramework(ecosystem="go", framework="godog", features_dir=_GO_FEATURES_DIR)


def detect(repo_root: Path) -> BDDFramework | None:
    """Return the project's BDD framework or None.

    Order: idd config override > python > node > ruby > go.
    Returns None when signals are missing, ambiguous, or transitive-only.

    Args:
        repo_root: Absolute path to the repository root to inspect.

    Returns:
        A frozen ``BDDFramework`` describing the detected ecosystem, framework,
        and features directory; ``None`` when no clear signal is present.
    """
    override = _read_idd_config_override(repo_root)
    if override is not None:
        return override
    for detector in (_detect_python, _detect_node, _detect_ruby, _detect_go):
        result = detector(repo_root)
        if result is not None:
            return result
    return None
