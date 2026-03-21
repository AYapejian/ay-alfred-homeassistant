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

import re  # noqa: E402

from ha_workflow.alfred import AlfredIcon, AlfredItem, AlfredOutput  # noqa: E402
from ha_workflow.cache import EntityCache, open_cache  # noqa: E402
from ha_workflow.config import Config  # noqa: E402
from ha_workflow.entities import Entity, get_domain_config  # noqa: E402
from ha_workflow.errors import handle_error  # noqa: E402
from ha_workflow.ha_client import HAClient  # noqa: E402
from ha_workflow.query_parser import ParsedQuery, parse_query  # noqa: E402
from ha_workflow.search import fuzzy_search, regex_search  # noqa: E402
from ha_workflow.suggestions import build_domain_suggestions  # noqa: E402
from ha_workflow.usage import UsageRecord, open_usage_tracker  # noqa: E402

_LOCK_FILENAME = ".refresh.lock"
_DEBUG = os.environ.get("HA_DEBUG", "")
_SYSTEM_ENTITY = "__system__"

# ---------------------------------------------------------------------------
# System commands — surfaced as search results, executed via action handler
# ---------------------------------------------------------------------------

_SYSTEM_COMMANDS: list[dict[str, str]] = [
    # History commands
    {
        "title": "History: Clear usage data",
        "subtitle": "System \u00b7 Reset search suggestions and rankings",
        "action": "usage_clear",
        "keywords": "history clear usage reset suggestions data",
    },
    # Cache commands
    {
        "title": "Cache: Refresh entities",
        "subtitle": "System \u00b7 Re-fetch all entities from Home Assistant",
        "action": "cache_refresh",
        "keywords": "cache refresh reload entities update",
    },
]

# macOS system icon — the Preferences app gives a gear/settings look
_SYSTEM_ICON = AlfredIcon(
    path="/System/Applications/System Settings.app",
    type="fileicon",
)


def _match_system_commands(query: str) -> list[AlfredItem]:
    """Return system command items matching *query*.

    Returns **all** system commands when *query* is empty (for the
    default view).  When *query* is non-empty, filters by keyword match.

    Uses a macOS system icon and "System" subtitle prefix to visually
    distinguish these from entity search results.
    """
    query_lower = query.strip().lower()
    items: list[AlfredItem] = []
    for cmd in _SYSTEM_COMMANDS:
        if query_lower:
            words = query_lower.split()
            keywords = cmd["keywords"]
            if not all(w in keywords for w in words):
                continue
        items.append(
            AlfredItem(
                title=cmd["title"],
                subtitle=cmd["subtitle"],
                arg=_SYSTEM_ENTITY,
                icon=_SYSTEM_ICON,
                uid=f"system_{cmd['action']}",
                variables={
                    "entity_id": _SYSTEM_ENTITY,
                    "action": cmd["action"],
                    "domain": "__system__",
                },
                valid=True,
            )
        )
    return items


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
    tracker = open_usage_tracker(config)
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
            _maybe_refresh_background(config)

        if cache_empty:
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
            usage_stats = tracker.get_usage_stats()
            parsed = parse_query(query)
            _dbg(f"search: parsed mode={parsed.mode} domain={parsed.domain_filter}")

            if parsed.mode == "regex":
                output = _search_regex(cache, parsed)
            elif parsed.domain_filter:
                output = _search_domain_filtered(cache, parsed, usage_stats)
            else:
                output = _search_fuzzy(cache, parsed, usage_stats)

            # System commands always at the top, across all search modes
            sys_items = _match_system_commands(query)
            if sys_items:
                output.items = sys_items + output.items

            if needs_refresh:
                output.rerun = 1.0
    finally:
        cache.close()
        tracker.close()

    sys.stdout.write(output.to_json() + "\n")


def _search_regex(cache: EntityCache, parsed: ParsedQuery) -> AlfredOutput:
    """Handle regex search mode."""
    all_entities = cache.get_all()
    try:
        results = regex_search(all_entities, parsed.regex_pattern or "")
        _dbg(f"search: {len(results)} regex results")
        return _build_search_output(results)
    except re.error as exc:
        return AlfredOutput(
            items=[
                AlfredItem(
                    title="Invalid regex pattern",
                    subtitle=str(exc),
                    valid=False,
                )
            ]
        )


def _search_domain_filtered(
    cache: EntityCache,
    parsed: ParsedQuery,
    usage_stats: dict[str, UsageRecord],
) -> AlfredOutput:
    """Handle domain-filtered search (e.g. ``light:bedroom``)."""
    domain_entities = cache.get_by_domain(parsed.domain_filter or "")
    _dbg(f"search: {len(domain_entities)} entities in domain {parsed.domain_filter}")
    results = fuzzy_search(domain_entities, parsed.text, usage_stats=usage_stats)
    _dbg(f"search: {len(results)} results for {parsed.text!r}")
    return _build_search_output(results)


def _search_fuzzy(
    cache: EntityCache,
    parsed: ParsedQuery,
    usage_stats: dict[str, UsageRecord],
) -> AlfredOutput:
    """Handle standard fuzzy search with optional domain suggestions."""
    all_entities = cache.get_all()
    _dbg(f"search: {len(all_entities)} entities in cache")
    results = fuzzy_search(all_entities, parsed.text, usage_stats=usage_stats)
    _dbg(f"search: {len(results)} results for {parsed.text!r}")
    output = _build_search_output(results)

    if parsed.text:
        # Prepend domain suggestions when query looks like a partial domain name
        domain_counts = cache.get_domain_counts()
        suggestions = build_domain_suggestions(parsed.text, domain_counts)
        if suggestions:
            output.items = suggestions + output.items

    return output


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


def _cmd_action(args: list[str]) -> None:
    """Execute an action on an entity (or system command)."""
    entity_id = args[0] if args else ""
    action = args[1] if len(args) > 1 else ""

    if entity_id == _SYSTEM_ENTITY:
        _cmd_system_action(action)
        return

    # Entity actions — Phase 3 will implement this fully
    _cmd_stub("action")


def _cmd_system_action(action: str) -> None:
    """Dispatch a system command triggered from search results."""
    config = Config.from_env()

    if action == "usage_clear":
        tracker = open_usage_tracker(config)
        try:
            tracker.clear()
        finally:
            tracker.close()
        sys.stdout.write("Usage history cleared\n")

    elif action == "cache_refresh":
        cache = open_cache(config)
        try:
            _refresh_cache(config, cache)
            count = len(cache.get_all())
            sys.stdout.write(f"Cache refreshed: {count} entities\n")
        finally:
            cache.close()

    else:
        sys.stdout.write(f"Unknown system action: {action}\n")


def _cmd_record_usage(entity_id: str) -> None:
    """Record that the user selected an entity."""
    if not entity_id:
        return
    config = Config.from_env()
    tracker = open_usage_tracker(config)
    try:
        tracker.record_usage(entity_id)
        _dbg(f"record-usage: {entity_id}")
    finally:
        tracker.close()


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
        _cmd_action(args[1:])
    elif command == "actions":
        _cmd_stub("actions")
    elif command == "record-usage":
        entity_id = args[1] if len(args) > 1 else ""
        _cmd_record_usage(entity_id)
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
