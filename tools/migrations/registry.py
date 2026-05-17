"""Registry for schema-versioned file migrations.

Every existing versioned file is treated as schema_version 1. The registry
records that baseline contract without modifying any file. schema_version and
flow_version are independent axes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Version axes are intentionally separate:
# - schema_version is the per-file file-format version.
# - flow_version belongs only to the state.json lifecycle protocol.


class MigrationRegistryError(RuntimeError):
    """Raised when a schema migration cannot be registered or applied."""


@dataclass(frozen=True)
class Migration:
    """Typed schema migration between two versions for one file kind."""

    file_kind: str
    from_version: int
    to_version: int
    transform: Callable[[dict[str, Any]], dict[str, Any]]
    inverse: Callable[[dict[str, Any]], dict[str, Any]] | None = None


REGISTRY: dict[tuple[str, int], Migration] = {}


def register(migration: Migration) -> Migration:
    """Register a migration by file kind and source schema version.

    Args:
        migration: Migration contract to store.

    Returns:
        The same migration instance, unchanged.

    Raises:
        MigrationRegistryError: If the migration has invalid versions.
    """
    _validate_migration(migration)
    REGISTRY[(migration.file_kind, migration.from_version)] = migration
    return migration


def apply_pending(file_kind: str, doc: dict[str, Any]) -> dict[str, Any]:
    """Apply all registered forward migrations for a file kind.

    Args:
        file_kind: File kind whose migration chain should be used.
        doc: Parsed document payload. Missing schema_version means version 1.

    Returns:
        Migrated document payload. If no migration is pending, returns a
        shallow copy of the input document.

    Raises:
        MigrationRegistryError: If the document version is invalid, newer than
            the registry knows about, or cannot reach the latest known version.
    """
    current_version = _schema_version(doc)
    latest_version = _latest_known_version(file_kind)
    current_doc = dict(doc)

    if latest_version is None:
        return current_doc
    if current_version > latest_version:
        raise MigrationRegistryError(
            f"{file_kind} schema_version {current_version} is newer than "
            f"latest registered version {latest_version}"
        )

    while current_version < latest_version:
        migration = REGISTRY.get((file_kind, current_version))
        if migration is None:
            raise MigrationRegistryError(
                f"{file_kind} migration chain is broken at schema_version "
                f"{current_version}; latest registered version is {latest_version}"
            )
        if migration.to_version <= migration.from_version:
            raise MigrationRegistryError(
                f"{file_kind} migration {migration.from_version}->"
                f"{migration.to_version} does not advance"
            )

        current_doc = dict(migration.transform(dict(current_doc)))
        current_doc["schema_version"] = migration.to_version
        current_version = migration.to_version

    return current_doc


def _validate_migration(migration: Migration) -> None:
    if not migration.file_kind:
        raise MigrationRegistryError("migration file_kind must be non-empty")
    if migration.from_version < 1 or migration.to_version < 1:
        raise MigrationRegistryError("migration versions must be greater than or equal to 1")
    if migration.to_version < migration.from_version:
        raise MigrationRegistryError(
            f"{migration.file_kind} migration cannot move backward: "
            f"{migration.from_version}->{migration.to_version}"
        )
    if migration.to_version == migration.from_version and migration.from_version != 1:
        raise MigrationRegistryError(
            f"{migration.file_kind} identity migration is only valid for version 1"
        )


def _schema_version(doc: dict[str, Any]) -> int:
    version = doc.get("schema_version", 1)
    if not isinstance(version, int):
        raise MigrationRegistryError("schema_version must be an integer")
    if version < 1:
        raise MigrationRegistryError("schema_version must be greater than or equal to 1")
    return version


def _latest_known_version(file_kind: str) -> int | None:
    versions = [
        version
        for migration in REGISTRY.values()
        if migration.file_kind == file_kind
        for version in (migration.from_version, migration.to_version)
    ]
    if not versions:
        return None
    return max(versions)
