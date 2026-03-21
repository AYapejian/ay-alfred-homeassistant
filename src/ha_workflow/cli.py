"""CLI entry point for the Alfred workflow.

Invoked as::

    /usr/bin/python3 ha_workflow/cli.py <command> [args...]
"""

from __future__ import annotations

import os
import subprocess
import sys

# When Alfred runs ``python3 ha_workflow/cli.py …``, Python sets sys.path[0]
# to the ha_workflow/ directory (the script's parent).  Package-level imports
# like ``from ha_workflow.alfred import …`` need the *workflow root* (the
# directory that *contains* ha_workflow/) on sys.path instead.
_WORKFLOW_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKFLOW_ROOT not in sys.path:
    sys.path.insert(0, _WORKFLOW_ROOT)

from ha_workflow.alfred import AlfredIcon, AlfredItem, AlfredOutput  # noqa: E402
from ha_workflow.cache import EntityCache, open_cache  # noqa: E402
from ha_workflow.config import Config  # noqa: E402
from ha_workflow.entities import Entity, get_domain_config  # noqa: E402
from ha_workflow.errors import handle_error  # noqa: E402
from ha_workflow.ha_client import HAClient  # noqa: E402
from ha_workflow.search import fuzzy_search  # noqa: E402

_LOCK_FILENAME = ".refresh.lock"
_DEBUG = os.environ.get("HA_DEBUG", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dbg(msg: str) -> None:
    """Write a debug line to stderr (visible in Alfred's debug log)."""
    if _DEBUG:
        sys.stderr.write(f"[ha-debug] {msg}\n")
        sys.stderr.flush()


def _refresh_cache(config: Config, cache: EntityCache) -> None:
    """Synchronously fetch all states from HA and replace the cache."""
    _dbg(f"refresh_cache: url={config.ha_url[:40]}")
    client = HAClient(config)
    states = client.get_states()
    _dbg(f"refresh_cache: get_states returned {len(states)} items")
    entities = [Entity.from_state_dict(s) for s in states]
    cache.refresh(entities)
    _dbg(f"refresh_cache: wrote {len(entities)} entities to cache")


def _maybe_refresh_background(config: Config) -> None:
    """Spawn a detached subprocess to refresh the cache, if not already running."""
    lock_path = config.cache_dir / _LOCK_FILENAME

    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
            os.kill(pid, 0)  # signal 0 = existence check
            _dbg(f"bg_refresh: lock held by pid {pid} (alive), skipping")
            return  # refresh already in progress
        except (ValueError, OSError):
            # Stale or invalid lock — remove and proceed
            _dbg("bg_refresh: removing stale lock")
            lock_path.unlink(missing_ok=True)

    cli_path = os.path.abspath(__file__)
    _dbg(f"bg_refresh: spawning {sys.executable} {cli_path} cache refresh")
    _dbg(f"bg_refresh: cwd={_WORKFLOW_ROOT}")

    # Log background refresh output to a file for debugging
    log_path = config.cache_dir / "refresh.log"
    os.makedirs(str(config.cache_dir), exist_ok=True)
    log_file = open(str(log_path), "w")  # noqa: SIM115

    bg_env = {**os.environ, "HA_DEBUG": "1"}
    proc = subprocess.Popen(
        [sys.executable, cli_path, "cache", "refresh"],
        cwd=_WORKFLOW_ROOT,
        stdout=log_file,
        stderr=log_file,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=bg_env,
    )

    lock_path.write_text(str(proc.pid))
    _dbg(f"bg_refresh: spawned pid {proc.pid}")


def _build_search_output(entities: list[Entity]) -> AlfredOutput:
    """Convert a list of entities to Alfred Script Filter JSON."""
    items: list[AlfredItem] = []
    for entity in entities:
        dc = get_domain_config(entity.domain)
        subtitle = f"{entity.domain} \u00b7 {dc.subtitle_formatter(entity)}"

        item = AlfredItem(
            title=entity.friendly_name,
            subtitle=subtitle,
            arg=entity.entity_id,
            icon=AlfredIcon(path=dc.icon_path),
            uid=entity.entity_id,
            autocomplete=entity.friendly_name,
            variables={
                "entity_id": entity.entity_id,
                "action": dc.default_action,
                "domain": entity.domain,
            },
            valid=bool(dc.default_action),
        )
        items.append(item)

    if not items:
        items.append(
            AlfredItem(
                title="No matching entities",
                subtitle="Try a different search term",
                valid=False,
            )
        )

    return AlfredOutput(items=items)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _cmd_config_validate() -> None:
    """Call HA ``GET /api/config`` and report the connection status."""
    config = Config.from_env()
    client = HAClient(config)
    ha_config = client.get_config()
    version = ha_config.get("version", "unknown")
    location = ha_config.get("location_name", "")
    subtitle = f"v{version}"
    if location:
        subtitle = f"{location} — {subtitle}"
    output = AlfredOutput(
        items=[
            AlfredItem(
                title="Connected to Home Assistant",
                subtitle=subtitle,
                icon=AlfredIcon(path="icon.png"),
                valid=False,
            )
        ]
    )
    sys.stdout.write(output.to_json() + "\n")


def _cmd_search(query: str) -> None:
    """Search cached entities and return Alfred JSON results."""
    config = Config.from_env()
    cache = open_cache(config)
    _dbg(f"search: query={query!r} db={cache._db_path}")

    try:
        age = cache.get_cache_age()
        cache_empty = age is None
        needs_refresh = cache.is_stale(config.cache_ttl)
        _dbg(
            f"search: age={age} empty={cache_empty}"
            f" stale={needs_refresh} ttl={config.cache_ttl}"
        )

        if cache_empty or needs_refresh:
            # Always use background refresh — a sync refresh blocks the Script
            # Filter and gets killed by Alfred's queuemode (terminate previous).
            _maybe_refresh_background(config)

        if cache_empty:
            # No data at all — show a loading message and ask Alfred to re-run
            output = AlfredOutput(
                items=[
                    AlfredItem(
                        title="Loading entities\u2026",
                        subtitle="Fetching data from Home Assistant",
                        icon=AlfredIcon(path="icon.png"),
                        valid=False,
                    )
                ],
                rerun=1.0,
            )
        else:
            all_entities = cache.get_all()
            _dbg(f"search: {len(all_entities)} entities in cache")
            results = fuzzy_search(all_entities, query)
            _dbg(f"search: {len(results)} results for {query!r}")
            output = _build_search_output(results)

            if needs_refresh:
                output.rerun = 1.0
    finally:
        cache.close()

    sys.stdout.write(output.to_json() + "\n")


def _cmd_cache(args: list[str]) -> None:
    """Handle ``cache refresh`` and ``cache status`` subcommands."""
    if not args:
        _cmd_stub("cache")
        return

    sub = args[0]
    config = Config.from_env()
    cache = open_cache(config)

    try:
        if sub == "refresh":
            _dbg(f"cache refresh: db={cache._db_path}")
            _refresh_cache(config, cache)
            # Clean up lock file (we may have been invoked as a background refresh)
            lock_path = config.cache_dir / _LOCK_FILENAME
            if lock_path.exists():
                lock_path.unlink(missing_ok=True)
            _dbg("cache refresh: lock cleaned")
            count = len(cache.get_all())
            output = AlfredOutput(
                items=[
                    AlfredItem(
                        title=f"Cache refreshed: {count} entities",
                        subtitle="Entity cache is up to date",
                        icon=AlfredIcon(path="icon.png"),
                        valid=False,
                    )
                ]
            )
            sys.stdout.write(output.to_json() + "\n")
        elif sub == "status":
            age = cache.get_cache_age()
            count = len(cache.get_all())
            if age is None:
                subtitle = "Never refreshed"
            else:
                subtitle = f"Age: {int(age)}s \u00b7 {count} entities"
            output = AlfredOutput(
                items=[
                    AlfredItem(
                        title="Entity Cache Status",
                        subtitle=subtitle,
                        icon=AlfredIcon(path="icon.png"),
                        valid=False,
                    )
                ]
            )
            sys.stdout.write(output.to_json() + "\n")
        else:
            _cmd_stub(f"cache {sub}")
    finally:
        cache.close()


def _cmd_stub(name: str) -> None:
    """Emit a placeholder item for commands wired in later phases."""
    output = AlfredOutput(
        items=[
            AlfredItem(
                title=f"{name} — not yet implemented",
                subtitle="This command will be available in a future update.",
                valid=False,
            )
        ]
    )
    sys.stdout.write(output.to_json() + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Dispatch CLI commands."""
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        _cmd_stub("ha_workflow")
        return

    command = args[0]

    if command == "config" and len(args) >= 2 and args[1] == "validate":
        _cmd_config_validate()
    elif command == "search":
        query = " ".join(args[1:])
        _cmd_search(query)
    elif command == "action":
        _cmd_stub("action")
    elif command == "actions":
        _cmd_stub("actions")
    elif command == "cache":
        _cmd_cache(args[1:])
    else:
        _cmd_stub(command)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        handle_error(exc)
