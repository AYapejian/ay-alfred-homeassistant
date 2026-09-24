"""Per-server storage layout — directory setup, ``server.json``, legacy migration.

Everything that belongs to one Home Assistant server lives in its own
subdirectory, keyed by :attr:`Config.server_key`, so switching ``HA_URL``
can never mix or clobber another server's data::

    <cache_dir>/servers/<key>/entities.db     entity cache
    <cache_dir>/servers/<key>/.refresh.lock   background-refresh PID file
    <cache_dir>/servers/<key>/refresh.log     background-refresh output
    <data_dir>/servers/<key>/usage.db         usage history (survives cache wipes)
    <data_dir>/servers/<key>/server.json      non-secret debug info (URL, profile)
    <data_dir>/servers/.legacy-migrated       one-time migration marker

Before per-server storage existed these files sat flat in ``cache_dir`` /
``data_dir``.  :func:`migrate_legacy_storage` moves them — once — into the
directory of the default server (``HA_URL``) configured at upgrade time.
Legacy files predate server profiles, so they never belong to one.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ha_workflow.config import SAFE_SERVER_KEY, Config, normalize_server_url
from ha_workflow.profiles import DEFAULT_PROFILE_ID

SERVERS_DIRNAME = "servers"
SERVER_INFO_FILENAME = "server.json"
MIGRATION_MARKER_FILENAME = ".legacy-migrated"
_MIGRATION_LOCK_FILENAME = ".migrate.lock"

# SQLite sidecar files that must travel with their database.
_SQLITE_SIDECARS = (
    "-wal",
    "-shm",
    "-journal",
)

# Legacy flat files that are per-server, grouped by their home directory.
# Databases carry their SQLite sidecars along with them.
_LEGACY_CACHE_DBS = ("entities.db",)
_LEGACY_CACHE_FILES = ("refresh.log", ".refresh.lock")
_LEGACY_DATA_DBS = ("usage.db",)


def prepare_server_storage(config: Config) -> None:
    """Create the current server's directories, migrate legacy files, and
    record ``server.json``.

    Cheap after the first call (a few ``stat`` calls), so every entry point
    that opens per-server storage can call it unconditionally.
    """
    os.makedirs(config.server_cache_dir, exist_ok=True)
    os.makedirs(config.server_data_dir, exist_ok=True)
    try:
        # Legacy files come from the pre-profiles, single-server layout: only
        # the default server may inherit them.
        if config.server_id == DEFAULT_PROFILE_ID:
            migrate_legacy_storage(config)
    except OSError as exc:
        # A failed migration (e.g. a permission error) must not break search:
        # no marker is written, so the next invocation retries.  A legacy file
        # that merely vanishes mid-move is skipped inside _move_legacy — some
        # other process moved it — and does not block the marker.
        sys.stderr.write(f"[ha-workflow] legacy storage migration failed: {exc}\n")
    try:
        _write_server_info(config)
    except OSError as exc:
        # server.json is advisory debug info; never let it block search.
        sys.stderr.write(f"[ha-workflow] could not write server.json: {exc}\n")


def migrate_legacy_storage(config: Config) -> list[str]:
    """Move legacy flat per-server files into the current server's dirs.

    Runs at most once per install: a marker in ``<data_dir>/servers/`` records
    completion, so a stray legacy file appearing later is never attributed to
    a different server.  An existing per-server file is never overwritten.
    Concurrent invocations (Alfred can launch script filters in rapid
    succession) serialize on an ``flock``; moves use :func:`os.replace` and
    tolerate a file vanishing underneath them.

    Returns the names of the files that this call moved.
    """
    servers_root = config.data_dir / SERVERS_DIRNAME
    marker = servers_root / MIGRATION_MARKER_FILENAME
    if marker.exists():
        return []

    os.makedirs(servers_root, exist_ok=True)
    moved: list[str] = []
    with open(servers_root / _MIGRATION_LOCK_FILENAME, "a") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        # Another invocation may have finished while we waited for the lock.
        if marker.exists():
            return []

        for name in _LEGACY_CACHE_DBS:
            moved += _move_legacy(
                config.cache_dir, config.server_cache_dir, name, _SQLITE_SIDECARS
            )
        for name in _LEGACY_CACHE_FILES:
            moved += _move_legacy(config.cache_dir, config.server_cache_dir, name, ())
        for name in _LEGACY_DATA_DBS:
            moved += _move_legacy(
                config.data_dir, config.server_data_dir, name, _SQLITE_SIDECARS
            )

        marker_info = {
            "migrated_at": _now_iso(),
            "server_key": config.server_key,
            "moved": moved,
        }
        marker.write_text(json.dumps(marker_info, indent=2) + "\n")
    return moved


def _move_legacy(
    src_dir: Path, dst_dir: Path, name: str, sidecars: tuple[str, ...]
) -> list[str]:
    """Move ``src_dir/name`` (plus sidecars) into ``dst_dir`` unless the
    destination already exists.  Returns the names actually moved."""
    src = src_dir / name
    dst = dst_dir / name
    if not src.exists() or dst.exists():
        return []

    os.makedirs(dst_dir, exist_ok=True)
    try:
        os.replace(src, dst)
    except FileNotFoundError:
        return []
    moved = [name]
    for suffix in sidecars:
        try:
            os.replace(src_dir / (name + suffix), dst_dir / (name + suffix))
        except FileNotFoundError:
            continue
        moved.append(name + suffix)
    return moved


def _write_server_info(config: Config) -> None:
    """Write ``server.json`` (URL, key, profile, created); never the token.

    Rewritten only when the URL or profile name/id changed (a profile's URL
    or name can be edited without changing its storage key).
    """
    path = config.server_data_dir / SERVER_INFO_FILENAME
    wanted = {
        "url": normalize_server_url(config.ha_url),
        "key": config.server_key,
        "profile_id": config.server_id,
        "profile_name": config.server_display_name,
    }
    info: dict[str, object] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = {}
        if isinstance(loaded, dict):
            info = loaded
        if all(info.get(k) == v for k, v in wanted.items()):
            return
    info.update(wanted)
    info.setdefault("created", _now_iso())
    fd, tmp_name = tempfile.mkstemp(
        dir=str(config.server_data_dir), prefix=".server.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(json.dumps(info, indent=2) + "\n")
        os.replace(tmp_name, path)
    except OSError:
        Path(tmp_name).unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class ServerStatus:
    """What is known about a server from local state alone (no network)."""

    entity_count: Optional[int] = None
    last_refresh: Optional[float] = None
    # Most recent background-refresh failure, if newer than the last success.
    last_error: Optional[str] = None
    last_error_at: Optional[float] = None


def read_server_status(cache_dir: Path, server_key: str) -> ServerStatus:
    """Read a server's cached entity count, last refresh and last failure.

    Read-only: never creates directories or databases, never contacts the
    server.  Anything unreadable is reported as unknown (``None``).
    """
    if not SAFE_SERVER_KEY.match(server_key):
        return ServerStatus()
    server_dir = Path(cache_dir) / SERVERS_DIRNAME / server_key
    count: Optional[int] = None
    last_refresh: Optional[float] = None
    db_path = server_dir / "entities.db"
    if db_path.is_file():
        try:
            conn = sqlite3.connect(str(db_path), timeout=1)
            try:
                row = conn.execute("SELECT COUNT(*) FROM entities").fetchone()
                count = int(row[0]) if row else None
                meta = conn.execute(
                    "SELECT value FROM cache_meta WHERE key = 'last_refresh'"
                ).fetchone()
                last_refresh = float(meta[0]) if meta else None
            finally:
                conn.close()
        except (sqlite3.Error, ValueError, TypeError):
            pass

    last_error, last_error_at = _read_refresh_failure(server_dir / "refresh.log")
    if (
        last_error_at is not None
        and last_refresh is not None
        and last_error_at <= last_refresh
    ):
        last_error, last_error_at = None, None
    return ServerStatus(
        entity_count=count,
        last_refresh=last_refresh,
        last_error=last_error,
        last_error_at=last_error_at,
    )


def _read_refresh_failure(log_path: Path) -> tuple[Optional[str], Optional[float]]:
    """``(reason, mtime)`` when the last refresh logged an error item."""
    try:
        mtime = log_path.stat().st_mtime
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None, None
    for raw in reversed(lines):
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        items = payload.get("items") if isinstance(payload, dict) else None
        if not items or not isinstance(items[0], dict):
            return None, None
        first = items[0]
        icon = first.get("icon") or {}
        if isinstance(icon, dict) and "error" in str(icon.get("path", "")):
            reason = str(first.get("subtitle") or first.get("title") or "error")
            return reason, mtime
        return None, None
    return None, None


def delete_server_storage(config: Config) -> None:
    """Remove this server's cache and data dirs (entities, usage, logs)."""
    for root in (config.server_cache_dir, config.server_data_dir):
        shutil.rmtree(root, ignore_errors=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
