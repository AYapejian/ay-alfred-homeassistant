"""SQLite entity cache."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional, Union

from ha_workflow.config import Config
from ha_workflow.entities import Entity


class EntityCache:
    """Read/write cache of Home Assistant entity state backed by SQLite."""

    def __init__(self, db_path: Union[str, Path]) -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self._db_path)), exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS entities (
                entity_id     TEXT PRIMARY KEY,
                domain        TEXT NOT NULL,
                state         TEXT NOT NULL,
                friendly_name TEXT NOT NULL,
                attributes_json TEXT NOT NULL,
                last_changed  TEXT NOT NULL,
                last_updated  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_entities_domain
                ON entities (domain);
            CREATE INDEX IF NOT EXISTS idx_entities_friendly_name
                ON entities (friendly_name);

            CREATE TABLE IF NOT EXISTS cache_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, entities: list[Entity]) -> None:
        """Replace **all** cached entities with *entities*."""
        cur = self._conn.cursor()
        cur.execute("DELETE FROM entities")
        cur.executemany(
            "INSERT INTO entities "
            "(entity_id, domain, state, friendly_name, "
            "attributes_json, last_changed, last_updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    e.entity_id,
                    e.domain,
                    e.state,
                    e.friendly_name,
                    json.dumps(e.attributes),
                    e.last_changed,
                    e.last_updated,
                )
                for e in entities
            ],
        )
        cur.execute(
            "INSERT OR REPLACE INTO cache_meta (key, value) VALUES ('last_refresh', ?)",
            (str(time.time()),),
        )
        self._conn.commit()

    def get_all(self) -> list[Entity]:
        """Return every cached entity."""
        cur = self._conn.execute(
            "SELECT entity_id, domain, state, friendly_name, "
            "attributes_json, last_changed, last_updated "
            "FROM entities"
        )
        return [self._row_to_entity(row) for row in cur.fetchall()]

    def search(self, query: str) -> list[Entity]:
        """Basic SQL LIKE search on ``entity_id`` and ``friendly_name``."""
        pattern = f"%{query}%"
        cur = self._conn.execute(
            "SELECT entity_id, domain, state, friendly_name, "
            "attributes_json, last_changed, last_updated "
            "FROM entities "
            "WHERE entity_id LIKE ? OR friendly_name LIKE ?",
            (pattern, pattern),
        )
        return [self._row_to_entity(row) for row in cur.fetchall()]

    def get_cache_age(self) -> Optional[float]:
        """Seconds since the last refresh, or ``None`` if never refreshed."""
        cur = self._conn.execute(
            "SELECT value FROM cache_meta WHERE key = 'last_refresh'"
        )
        row = cur.fetchone()
        if row is None:
            return None
        return time.time() - float(row[0])

    def is_stale(self, ttl: int) -> bool:
        """Return ``True`` if the cache is empty or older than *ttl* seconds."""
        age = self.get_cache_age()
        if age is None:
            return True
        return age > ttl

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_entity(row: tuple[Any, ...]) -> Entity:
        return Entity(
            entity_id=row[0],
            domain=row[1],
            state=row[2],
            friendly_name=row[3],
            attributes=json.loads(row[4]),
            last_changed=row[5],
            last_updated=row[6],
        )


def open_cache(config: Config) -> EntityCache:
    """Open the entity cache for the given workflow configuration."""
    db_path = config.cache_dir / "entities.db"
    return EntityCache(db_path)
