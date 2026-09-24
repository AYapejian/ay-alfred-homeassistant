"""Per-server storage layout — directory setup, ``server.json``, legacy migration.

Everything that belongs to one Home Assistant server lives in its own
subdirectory, keyed by :attr:`Config.server_key`, so switching ``HA_URL``
can never mix or clobber another server's data::

    <cache_dir>/servers/<key>/entities.db     entity cache
    <cache_dir>/servers/<key>/.refresh.lock   background-refresh PID file
    <cache_dir>/servers/<key>/refresh.log     background-refresh output
    <data_dir>/servers/<key>/usage.db         usage history (survives cache wipes)
    <data_dir>/servers/<key>/server.json      non-secret debug info (URL, created)
    <data_dir>/servers/.legacy-migrated       one-time migration marker

Before per-server storage existed these files sat flat in ``cache_dir`` /
``data_dir``.  :func:`migrate_legacy_storage` moves them — once — into the
directory of whichever server is configured at upgrade time.
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ha_workflow.config import Config, normalize_server_url

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
    """Write ``server.json`` (URL, key, created) once; never the token."""
    path = config.server_data_dir / SERVER_INFO_FILENAME
    if path.exists():
        return
    info = {
        "url": normalize_server_url(config.ha_url),
        "key": config.server_key,
        "created": _now_iso(),
    }
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
