"""Registry for schema-versioned file migrations.

Every existing versioned file is treated as schema_version 1. The registry
records that baseline contract without modifying any file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

# Version axes are intentionally separate:
# - schema_version is the per-file file-format version.
# - flow_version belongs only to the state.json lifecycle protocol.
MigrationFunc = Callable[..., object]
Migration = TypeVar("Migration", bound=MigrationFunc)

REGISTRY: dict[int, MigrationFunc] = {}


def register(version: int) -> Callable[[Migration], Migration]:
    """Return a decorator that records a migration callable by schema version.

    Args:
        version: Schema version handled by the decorated callable.

    Returns:
        Decorator that stores and returns the migration callable unchanged.
    """

    def decorator(migration: Migration) -> Migration:
        REGISTRY[version] = migration
        return migration

    return decorator
