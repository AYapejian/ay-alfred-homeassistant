"""Usage tracking — records entity selection frequency and recency."""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from ha_workflow.config import Config


@dataclass(frozen=True)
class UsageRecord:
    """A single entity's usage statistics."""

    entity_id: str
    use_count: int
    last_used_at: float  # time.time() epoch


class UsageTracker:
    """Tracks which entities the user selects, backed by SQLite.

    The database lives in ``data_dir`` (not ``cache_dir``) so it survives
    cache clears — Alfred may clean ``cache_dir`` at any time, but
    ``data_dir`` persists.
    """

    def __init__(self, db_path: Union[str, Path]) -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self._db_path)), exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS usage_stats (
                entity_id    TEXT PRIMARY KEY,
                use_count    INTEGER NOT NULL DEFAULT 0,
                last_used_at REAL NOT NULL
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_usage(self, entity_id: str) -> None:
        """Record that *entity_id* was selected by the user."""
        now = time.time()
        self._conn.execute(
            "INSERT INTO usage_stats (entity_id, use_count, last_used_at) "
            "VALUES (?, 1, ?) "
            "ON CONFLICT(entity_id) DO UPDATE SET "
            "use_count = use_count + 1, "
            "last_used_at = excluded.last_used_at",
            (entity_id, now),
        )
        self._conn.commit()

    def get_usage_stats(self) -> dict[str, UsageRecord]:
        """Return all usage records keyed by entity_id."""
        cur = self._conn.execute(
            "SELECT entity_id, use_count, last_used_at FROM usage_stats"
        )
        return {
            row[0]: UsageRecord(entity_id=row[0], use_count=row[1], last_used_at=row[2])
            for row in cur.fetchall()
        }

    def get_usage_record(self, entity_id: str) -> Optional[UsageRecord]:
        """Return the usage record for *entity_id*, or ``None``."""
        cur = self._conn.execute(
            "SELECT entity_id, use_count, last_used_at "
            "FROM usage_stats WHERE entity_id = ?",
            (entity_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return UsageRecord(entity_id=row[0], use_count=row[1], last_used_at=row[2])

    def count(self) -> int:
        """Return the number of tracked entities."""
        cur = self._conn.execute("SELECT COUNT(*) FROM usage_stats")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def clear(self) -> None:
        """Delete all usage history."""
        self._conn.execute("DELETE FROM usage_stats")
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()


def open_usage_tracker(config: Config) -> UsageTracker:
    """Open the usage tracker, storing data in ``config.data_dir/usage.db``."""
    db_path = config.data_dir / "usage.db"
    return UsageTracker(db_path)
