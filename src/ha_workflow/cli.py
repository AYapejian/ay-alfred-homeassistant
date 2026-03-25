"""CLI entry point for the Alfred workflow.

Invoked as::

    /usr/bin/python3 ha_workflow/cli.py <command> [args...]
"""

from __future__ import annotations

import calendar
import os
import subprocess
import sys
import time
from typing import Any, NamedTuple, Optional

# When Alfred runs ``python3 ha_workflow/cli.py …``, Python sets sys.path[0]
# to the ha_workflow/ directory (the script's parent).  Package-level imports
# like ``from ha_workflow.alfred import …`` need the *workflow root* (the
# directory that *contains* ha_workflow/) on sys.path instead.
_WORKFLOW_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKFLOW_ROOT not in sys.path:
    sys.path.insert(0, _WORKFLOW_ROOT)

import re  # noqa: E402

from ha_workflow.actions import dispatch_action  # noqa: E402
from ha_workflow.alfred import (  # noqa: E402
    AlfredIcon,
    AlfredItem,
    AlfredMod,
    AlfredOutput,
)
from ha_workflow.cache import EntityCache, open_cache  # noqa: E402
from ha_workflow.config import Config  # noqa: E402
from ha_workflow.entities import Entity, get_domain_config  # noqa: E402
from ha_workflow.errors import handle_error  # noqa: E402
from ha_workflow.ha_client import HAClient  # noqa: E402
from ha_workflow.notify import (  # noqa: E402
    notify,
    notify_background_error,
    notify_error,
)
from ha_workflow.query_parser import ParsedQuery, parse_query  # noqa: E402
from ha_workflow.search import fuzzy_search, regex_search  # noqa: E402
from ha_workflow.suggestions import build_domain_suggestions  # noqa: E402
from ha_workflow.usage import UsageRecord, open_usage_tracker  # noqa: E402

_LOCK_FILENAME = ".refresh.lock"
_DEBUG = os.environ.get("HA_DEBUG", "")
_SYSTEM_ENTITY = "__system__"
_YAML_SPECIAL_CHARS = frozenset(":#[]{},&*!|>")

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
    # HA system commands
    {
        "title": "System: Restart Home Assistant",
        "subtitle": "System \u00b7 Restart the HA instance",
        "action": "ha_restart",
        "keywords": "restart reboot home assistant ha system server",
    },
    {
        "title": "System: Check config",
        "subtitle": "System \u00b7 Validate Home Assistant configuration",
        "action": "ha_check_config",
        "keywords": "check config validate configuration yaml test",
    },
    {
        "title": "System: View error log",
        "subtitle": "System \u00b7 Copy recent HA error log to clipboard",
        "action": "ha_error_log",
        "keywords": "log logs error errors view show debug",
    },
]

# System command icon — grey cog on rounded square
_SYSTEM_ICON = AlfredIcon(path="icons/_system.png")


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
            query_words = query_lower.split()
            keyword_words = cmd["keywords"].split()
            # Each query word must be a prefix of at least one keyword
            if not all(
                any(kw.startswith(qw) for kw in keyword_words) for qw in query_words
            ):
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


class _RegistryInfo(NamedTuple):
    """Per-entity info resolved from the HA registries."""

    area_name: str
    device_id: str


def _build_registry_lookup(client: HAClient) -> dict[str, _RegistryInfo]:
    """Fetch entity, device, and area registries.

    Returns ``{entity_id: _RegistryInfo}`` with area resolved through the
    device when the entity itself has no direct ``area_id``.
    """
    try:
        # area_id → area name
        area_names: dict[str, str] = {}
        for area in client.get_area_registry():
            aid = area.get("area_id", "")
            name = area.get("name", "")
            if aid and name:
                area_names[aid] = name

        # device id → area_id
        device_areas: dict[str, str] = {}
        for dev in client.get_device_registry():
            did = dev.get("id", "")
            aid = dev.get("area_id", "")
            if did and aid:
                device_areas[did] = aid

        # entity_id → (area_name, device_id)
        lookup: dict[str, _RegistryInfo] = {}
        for entry in client.get_entity_registry():
            eid = entry.get("entity_id", "")
            if not eid:
                continue

            device_id = entry.get("device_id") or ""

            # Entity-level area_id takes priority over device-level
            area_id = entry.get("area_id") or ""
            if not area_id and device_id:
                area_id = device_areas.get(device_id, "")

            area_name = area_names.get(area_id, "")
            lookup[eid] = _RegistryInfo(area_name=area_name, device_id=device_id)

        return lookup
    except Exception:
        _dbg("_build_registry_lookup: failed, returning empty lookup")
        return {}


def _refresh_cache(config: Config, cache: EntityCache) -> None:
    """Synchronously fetch all states from HA and replace the cache."""
    _dbg(f"refresh_cache: url={config.ha_url[:40]}")
    client = HAClient(config)
    states = client.get_states()
    _dbg(f"refresh_cache: get_states returned {len(states)} items")

    registry = _build_registry_lookup(client)
    _dbg(f"refresh_cache: registry lookup has {len(registry)} entries")

    entities = []
    for s in states:
        eid = s.get("entity_id", "")
        info = registry.get(eid)
        entities.append(
            Entity.from_state_dict(
                s,
                area_name=info.area_name if info else "",
                device_id=info.device_id if info else "",
            )
        )
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
        state_text = dc.subtitle_formatter(entity)
        # Use area name as subtitle prefix when available, fall back to domain
        prefix = entity.area_name if entity.area_name else entity.domain
        subtitle = f"{prefix} \u00b7 {state_text}"

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
            mods={
                "cmd": AlfredMod(
                    subtitle="Actions\u2026",
                    valid=True,
                    variables={
                        "entity_id": entity.entity_id,
                        "domain": entity.domain,
                    },
                ),
            },
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
            try:
                _refresh_cache(config, cache)
            except Exception as exc:
                # Background refresh — user may not see stderr, so toast it
                notify_background_error(
                    f"Cache refresh failed: {exc}",
                    subtitle="Home Assistant may be unreachable",
                )
                raise
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

    if not entity_id or not action:
        notify_error("Missing entity_id or action")
        return

    # Viewer actions — copy detailed info to clipboard
    if action == "show_details":
        _cmd_show_details(entity_id)
        return
    if action == "view_history":
        _cmd_view_history(entity_id)
        return

    # Route copy/open actions to their dedicated handlers
    if action.startswith("copy_"):
        _cmd_copy_action(entity_id, action)
        return
    if action.startswith("open_"):
        _cmd_open_action(entity_id, action)
        return

    config = Config.from_env()
    client = HAClient(config)
    result = dispatch_action(client, entity_id, action)
    if result.success:
        notify(result.message)
        _cmd_record_usage(entity_id)
    else:
        notify_error(result.message)


def _cmd_system_action(action: str) -> None:
    """Dispatch a system command triggered from search results."""
    config = Config.from_env()

    if action == "usage_clear":
        tracker = open_usage_tracker(config)
        try:
            tracker.clear()
        finally:
            tracker.close()
        notify("Usage history cleared")

    elif action == "cache_refresh":
        cache = open_cache(config)
        try:
            _refresh_cache(config, cache)
            count = len(cache.get_all())
            notify(f"Cache refreshed: {count} entities")
        finally:
            cache.close()

    elif action == "ha_restart":
        client = HAClient(config)
        try:
            client.call_service("homeassistant", "restart")
            notify("Home Assistant is restarting")
        except Exception as exc:
            notify_error(f"Restart failed: {exc}")

    elif action == "ha_check_config":
        client = HAClient(config)
        try:
            result = client.check_config()
            errors = result.get("errors")
            if errors:
                notify_error(f"Config invalid: {errors}")
            else:
                notify("Configuration is valid")
        except Exception as exc:
            notify_error(f"Config check failed: {exc}")

    elif action == "ha_error_log":
        client = HAClient(config)
        try:
            log_text = client.get_error_log()
        except Exception as exc:
            msg = str(exc)
            if "404" in msg:  # string match: HAClient embeds status code in message
                notify_error(
                    "Error log not available (endpoint returned 404). "
                    "This endpoint is not supported via Nabu Casa cloud — "
                    "use a local HA URL instead."
                )
            else:
                notify_error(f"Failed to fetch error log: {exc}")
            return
        if not log_text or not log_text.strip():
            notify("Error log is empty")
            return
        try:
            subprocess.run(["pbcopy"], input=log_text.encode("utf-8"), check=True)
        except Exception as exc:
            notify_error(f"Failed to copy log to clipboard: {exc}")
            return
        first_line = log_text.strip().split("\n")[0][:80]
        lines = log_text.strip().count("\n") + 1
        notify(f"Error log copied ({lines} lines): {first_line}")

    else:
        notify_error(f"Unknown system action: {action}")


# ---------------------------------------------------------------------------
# Entity viewer actions
# ---------------------------------------------------------------------------


def _format_as_yaml(data: Any, indent: int = 0) -> str:
    """Format a dict/list as simple YAML-like text (no external dependency)."""
    lines: list[str] = []
    prefix = "  " * indent

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)) and value:
                lines.append(f"{prefix}{key}:")
                lines.append(_format_as_yaml(value, indent + 1))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}-")
                lines.append(_format_as_yaml(item, indent + 1))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{_yaml_scalar(data)}")

    return "\n".join(lines)


def _yaml_scalar(value: object) -> str:
    """Format a scalar value for YAML-like output."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if any(c in _YAML_SPECIAL_CHARS for c in s):
        return f'"{s}"'
    return s


def _format_history_entry(entry: dict[str, Any]) -> str:
    """Format a single history state-change entry as a readable line."""
    state = entry.get("state", "?")
    changed = entry.get("last_changed", "")
    # Extract time portion from ISO timestamp
    time_part = changed.split("T")[1].split(".")[0] if "T" in changed else changed
    return f"{time_part}  {state}"


def _get_cached_entity(config: Config, entity_id: str) -> Optional[Entity]:
    """Look up an entity from the cache by ID. Returns ``None`` if not found."""
    cache = open_cache(config)
    try:
        for e in cache.get_all():
            if e.entity_id == entity_id:
                return e
        return None
    finally:
        cache.close()


def _format_relative_time(iso_timestamp: str) -> str:
    """Convert an ISO-8601 timestamp to a human-readable relative string."""
    if not iso_timestamp:
        return ""
    try:
        # HA timestamps: "2024-03-21T10:30:00.123456+00:00"
        clean = iso_timestamp.split(".")[0].replace("Z", "").replace("+00:00", "")
        # calendar.timegm interprets struct_time as UTC (unlike time.mktime)
        ts = float(calendar.timegm(time.strptime(clean, "%Y-%m-%dT%H:%M:%S")))
        delta = time.time() - ts
        if delta < 0:
            return "just now"
        if delta < 60:
            return f"{int(delta)}s ago"
        if delta < 3600:
            return f"{int(delta // 60)}m ago"
        if delta < 86400:
            return f"{int(delta // 3600)}h ago"
        return f"{int(delta // 86400)}d ago"
    except (ValueError, OverflowError):
        return ""


# ---------------------------------------------------------------------------
# Copy / Open action handlers
# ---------------------------------------------------------------------------


def _cmd_copy_action(entity_id: str, action: str) -> None:
    """Handle copy-to-clipboard actions."""
    config = Config.from_env()

    if action == "copy_entity_id":
        text = entity_id
        msg = f"Copied: {entity_id}"
    elif action == "copy_entity_details":
        client = HAClient(config)
        state = client.get_state(entity_id)
        text = _format_as_yaml(state)
        friendly = state.get("attributes", {}).get("friendly_name", entity_id)
        msg = f"Copied details for {friendly}"
    elif action == "copy_device_details":
        client = HAClient(config)
        device_id = _lookup_device_id(client, entity_id)
        if not device_id:
            notify_error(f"No device found for {entity_id}")
            return
        device = _lookup_device(client, device_id)
        if not device:
            notify_error(f"Device {device_id} not found")
            return
        text = _format_as_yaml(device)
        msg = f"Copied device details for {entity_id}"
    else:
        notify_error(f"Unknown copy action: {action}")
        return

    try:
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
    except Exception as exc:
        notify_error(f"Failed to copy to clipboard: {exc}")
        return
    notify(msg)


def _cmd_open_action(entity_id: str, action: str) -> None:
    """Handle open-in-Home-Assistant actions."""
    import urllib.parse

    config = Config.from_env()
    ha_url = config.ha_url
    safe_id = urllib.parse.quote(entity_id, safe="")

    if action == "open_entity":
        url = f"{ha_url}/config/entities?filter={safe_id}"
    elif action == "open_device":
        client = HAClient(config)
        device_id = _lookup_device_id(client, entity_id)
        if not device_id:
            notify_error(f"No device found for {entity_id}")
            return
        url = f"{ha_url}/config/devices/device/{device_id}"
    elif action == "open_area":
        client = HAClient(config)
        area_id = _lookup_area_id(client, entity_id)
        if not area_id:
            notify_error(f"No area found for {entity_id}")
            return
        url = f"{ha_url}/config/areas/area/{area_id}"
    elif action == "open_history":
        url = f"{ha_url}/history?entity_id={safe_id}"
    else:
        notify_error(f"Unknown open action: {action}")
        return

    try:
        subprocess.run(["open", url], check=True)
    except Exception as exc:
        notify_error(f"Failed to open in browser: {exc}")
        return
    notify("Opened in Home Assistant")


def _lookup_device_id(client: HAClient, entity_id: str) -> str:
    """Look up the device_id for *entity_id* from the entity registry."""
    for entry in client.get_entity_registry():
        if entry.get("entity_id") == entity_id:
            return entry.get("device_id") or ""
    return ""


def _lookup_device(client: HAClient, device_id: str) -> Optional[dict[str, Any]]:
    """Look up a device dict from the device registry by ID."""
    for dev in client.get_device_registry():
        if dev.get("id") == device_id:
            return dev
    return None


def _lookup_area_id(client: HAClient, entity_id: str) -> str:
    """Look up the area_id for *entity_id*, falling back to the device's area."""
    entity_reg = client.get_entity_registry()
    device_id = ""
    area_id = ""
    for entry in entity_reg:
        if entry.get("entity_id") == entity_id:
            area_id = entry.get("area_id") or ""
            device_id = entry.get("device_id") or ""
            break
    if area_id:
        return area_id
    if device_id:
        for dev in client.get_device_registry():
            if dev.get("id") == device_id:
                return dev.get("area_id") or ""
    return ""


def _cmd_show_details(entity_id: str) -> None:
    """Fetch full entity state, format as YAML, copy to clipboard."""
    config = Config.from_env()
    client = HAClient(config)
    try:
        state = client.get_state(entity_id)
        text = _format_as_yaml(state)
        friendly = state.get("attributes", {}).get("friendly_name", entity_id)
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        current_state = state.get("state", "unknown")
        notify(f"Copied details for {friendly} ({current_state})")
    except Exception as exc:
        notify_error(f"Failed to fetch details: {exc}")


def _cmd_view_history(entity_id: str) -> None:
    """Fetch entity history, format as text, copy to clipboard."""
    config = Config.from_env()
    client = HAClient(config)
    try:
        changes = client.get_history(entity_id, hours=1)
        if not changes:
            notify("No history found (last hour)", subtitle=entity_id)
            return
        lines = [f"History for {entity_id} (last hour)", ""]
        for entry in changes:
            lines.append(_format_history_entry(entry))
        text = "\n".join(lines)
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        notify(f"History copied ({len(changes)} state changes)")
    except Exception as exc:
        notify_error(f"Failed to fetch history: {exc}")


def _cmd_actions(args: list[str]) -> None:
    """List available actions for an entity (Cmd modifier sub-menu).

    Shows: entity header, domain actions, copy actions, open-in-HA actions,
    and an advanced action call stub.
    """
    entity_id = args[0] if args else ""
    if not entity_id:
        output = AlfredOutput(
            items=[AlfredItem(title="No entity selected", valid=False)]
        )
        sys.stdout.write(output.to_json() + "\n")
        return

    domain = entity_id.split(".")[0] if "." in entity_id else ""
    if not domain:
        output = AlfredOutput(
            items=[
                AlfredItem(
                    title="Invalid entity ID",
                    subtitle=entity_id,
                    valid=False,
                )
            ]
        )
        sys.stdout.write(output.to_json() + "\n")
        return

    dc = get_domain_config(domain)

    # Fetch entity from cache for header info
    try:
        config = Config.from_env()
        entity = _get_cached_entity(config, entity_id)
    except Exception:
        entity = None

    friendly = (
        entity.friendly_name
        if entity
        else (entity_id.split(".", 1)[1].replace("_", " ").title())
    )
    last_changed = entity.last_changed if entity else ""
    area_name = entity.area_name if entity else ""
    device_id = entity.device_id if entity else ""

    items: list[AlfredItem] = []

    # --- Header item (not actionable) ---
    header_subtitle = entity_id
    relative = _format_relative_time(last_changed)
    if relative:
        header_subtitle += f" \u00b7 Changed {relative}"
    items.append(
        AlfredItem(
            title=friendly,
            subtitle=header_subtitle,
            icon=AlfredIcon(path=dc.icon_path),
            valid=False,
        )
    )

    # --- Domain actions ---
    for action in dc.available_actions:
        label = action.replace("_", " ").title()
        items.append(
            AlfredItem(
                title=label,
                subtitle=f"{friendly} \u00b7 {domain}",
                icon=AlfredIcon(path=dc.icon_path),
                variables={
                    "entity_id": entity_id,
                    "action": action,
                    "domain": domain,
                },
                valid=True,
            )
        )

    # --- Copy actions ---
    items.append(
        AlfredItem(
            title="Copy Entity ID",
            subtitle=entity_id,
            icon=_SYSTEM_ICON,
            variables={
                "entity_id": entity_id,
                "action": "copy_entity_id",
                "domain": domain,
            },
            valid=True,
        )
    )
    items.append(
        AlfredItem(
            title="Copy Entity Details",
            subtitle="Full entity state as YAML",
            icon=_SYSTEM_ICON,
            variables={
                "entity_id": entity_id,
                "action": "copy_entity_details",
                "domain": domain,
            },
            valid=True,
        )
    )
    if device_id:
        items.append(
            AlfredItem(
                title="Copy Device Details",
                subtitle="Device registry info as YAML",
                icon=_SYSTEM_ICON,
                variables={
                    "entity_id": entity_id,
                    "action": "copy_device_details",
                    "domain": domain,
                },
                valid=True,
            )
        )

    # --- Open in Home Assistant ---
    items.append(
        AlfredItem(
            title="Open Entity",
            subtitle="View in Home Assistant",
            icon=_SYSTEM_ICON,
            variables={
                "entity_id": entity_id,
                "action": "open_entity",
                "domain": domain,
            },
            valid=True,
        )
    )
    if device_id:
        items.append(
            AlfredItem(
                title="Open Device",
                subtitle="Device page in Home Assistant",
                icon=_SYSTEM_ICON,
                variables={
                    "entity_id": entity_id,
                    "action": "open_device",
                    "domain": domain,
                },
                valid=True,
            )
        )
    # NOTE: area_name comes from the cache, but open_area resolves area_id
    # from the live registry.  If the cache is stale the user may see this
    # item but get "No area found" — an acceptable trade-off vs an API call
    # on every Cmd keypress.  The cache refreshes within CACHE_TTL seconds.
    if area_name:
        items.append(
            AlfredItem(
                title="Open Area",
                subtitle=f"{area_name} in Home Assistant",
                icon=_SYSTEM_ICON,
                variables={
                    "entity_id": entity_id,
                    "action": "open_area",
                    "domain": domain,
                },
                valid=True,
            )
        )
    items.append(
        AlfredItem(
            title="Open History",
            subtitle="Entity history in Home Assistant",
            icon=_SYSTEM_ICON,
            variables={
                "entity_id": entity_id,
                "action": "open_history",
                "domain": domain,
            },
            valid=True,
        )
    )

    # --- Advanced Action Call (stub) ---
    items.append(
        AlfredItem(
            title="Advanced Action Call",
            subtitle=f"Coming soon \u2014 advanced controls for {domain} entities",
            icon=AlfredIcon(path=dc.icon_path),
            valid=False,
        )
    )

    output = AlfredOutput(items=items)
    sys.stdout.write(output.to_json() + "\n")


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


def main(argv: Optional[list[str]] = None) -> None:
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
        _cmd_actions(args[1:])
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
