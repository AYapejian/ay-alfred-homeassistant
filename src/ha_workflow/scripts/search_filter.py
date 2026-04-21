"""Entity search Script Filter.

Invoked by Alfred as::

    python3 scripts/search_filter.py "{query}"

Outputs Alfred Script Filter JSON to stdout.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

# Ensure the workflow root and packages/ are on sys.path.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKFLOW_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
for _p in (
    _WORKFLOW_ROOT,
    os.path.join(_WORKFLOW_ROOT, "packages"),
    os.path.join(_WORKFLOW_ROOT, "src"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ha_lib.cache as _lib_cache  # noqa: E402
import ha_lib.search as _lib_search  # noqa: E402
import ha_lib.suggestions as _lib_suggestions  # noqa: E402
from ha_lib.config import Config  # noqa: E402
from ha_lib.entities import Entity, get_domain_config  # noqa: E402
from ha_lib.errors import handle_error  # noqa: E402
from ha_lib.inference import infer_action  # noqa: E402
from ha_lib.params import extract_param_keys, parse_service_params  # noqa: E402
from ha_lib.query_parser import ParsedQuery, parse_query  # noqa: E402
from ha_lib.usage import UsageRecord, open_usage_tracker  # noqa: E402
from ha_workflow.alfred import (  # noqa: E402
    AlfredIcon,
    AlfredItem,
    AlfredMod,
    AlfredOutput,
)

_LOCK_FILENAME = ".refresh.lock"
_DEBUG = os.environ.get("HA_DEBUG", "")
_SYSTEM_ENTITY = "__system__"

# ---------------------------------------------------------------------------
# System commands
# ---------------------------------------------------------------------------

_SYSTEM_COMMANDS: list[dict[str, str]] = [
    {
        "title": "History: Clear usage data",
        "subtitle": "System \u00b7 Reset search suggestions and rankings",
        "action": "usage_clear",
        "keywords": "history clear usage reset suggestions data",
    },
    {
        "title": "Cache: Refresh entities",
        "subtitle": "System \u00b7 Re-fetch all entities from Home Assistant",
        "action": "cache_refresh",
        "keywords": "cache refresh reload entities update",
    },
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

_SYSTEM_ICON = AlfredIcon(path="icons/_system.png")

# Top domains to show as hint items on empty query (Phase E)
_DOMAIN_HINTS = [
    ("light", "Lights only"),
    ("switch", "Switches only"),
    ("automation", "Automations only"),
    ("sensor", "Sensors only"),
    ("climate", "Climate devices only"),
    ("media_player", "Media players only"),
]


def _dbg(msg: str) -> None:
    if _DEBUG:
        sys.stderr.write(f"[ha-debug] {msg}\n")
        sys.stderr.flush()


def _match_system_commands(query: str) -> list[AlfredItem]:
    # Hidden behind the `system` subcommand: the first token of *query* must
    # equal "system" before any items are returned.  Remaining tokens filter
    # the list by keyword prefix.
    tokens = query.strip().lower().split()
    if not tokens or tokens[0] != "system":
        return []
    filter_words = tokens[1:]
    items: list[AlfredItem] = []
    for cmd in _SYSTEM_COMMANDS:
        if filter_words:
            keyword_words = cmd["keywords"].split()
            if not all(
                any(kw.startswith(qw) for kw in keyword_words) for qw in filter_words
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


def _build_search_output(entities: list[Entity], query: str = "") -> AlfredOutput:
    """Convert a list of entities to Alfred Script Filter JSON."""
    items: list[AlfredItem] = []
    for entity in entities:
        dc = get_domain_config(entity.domain)
        state_text = dc.subtitle_formatter(entity)
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
                "alt": AlfredMod(
                    subtitle="Copy entity ID",
                    valid=True,
                    variables={
                        "entity_id": entity.entity_id,
                        "domain": entity.domain,
                        "action": "copy_entity_id",
                    },
                ),
                "ctrl": AlfredMod(
                    subtitle="Open in Home Assistant",
                    valid=True,
                    variables={
                        "entity_id": entity.entity_id,
                        "domain": entity.domain,
                        "action": "open_entity",
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

    # Phase E — domain hint items at the bottom when query is empty
    if not query.strip():
        for domain, hint in _DOMAIN_HINTS:
            dc = get_domain_config(domain)
            items.append(
                AlfredItem(
                    title=f"Filter by domain: ha {domain} \u2039name\u203a",
                    subtitle=hint,
                    icon=AlfredIcon(path=dc.icon_path),
                    valid=False,
                    autocomplete=f"{domain}:",
                    uid=f"domain_hint_{domain}",
                )
            )

    return AlfredOutput(items=items)


def _maybe_refresh_background(config: Config) -> None:
    """Spawn a detached subprocess to refresh the cache, if not already running."""
    lock_path = config.cache_dir / _LOCK_FILENAME
    cli_path = os.path.join(
        _WORKFLOW_ROOT,
        "src",
        "ha_workflow",
        "cli.py",
    )

    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
            os.kill(pid, 0)
            _dbg(f"bg_refresh: lock held by pid {pid} (alive), skipping")
            return
        except (ValueError, OSError):
            _dbg("bg_refresh: removing stale lock")
            lock_path.unlink(missing_ok=True)

    _dbg(f"bg_refresh: spawning {sys.executable} {cli_path} cache refresh")

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


def main() -> None:
    query = " ".join(sys.argv[1:])
    config = Config.from_env()
    cache = _lib_cache.open_cache(config)
    tracker = open_usage_tracker(config)
    _dbg(f"search: query={query!r}")

    try:
        age = cache.get_cache_age()
        cache_empty = age is None
        needs_refresh = cache.is_stale(config.cache_ttl)

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
            # `system` subcommand: show only system commands, no entity search.
            sys_items = _match_system_commands(query)
            if sys_items:
                output = AlfredOutput(items=sys_items)
                if needs_refresh:
                    output.rerun = 1.0
            else:
                usage_stats = tracker.get_usage_stats()
                parsed = parse_query(query)
                _dbg(f"search: parsed mode={parsed.mode} domain={parsed.domain_filter}")

                if parsed.mode == "regex":
                    output = _search_regex(cache, parsed)
                elif parsed.mode == "quick_exec":
                    output = _quick_exec(cache, parsed, usage_stats, query)
                elif parsed.domain_filter:
                    output = _search_domain_filtered(cache, parsed, usage_stats, query)
                else:
                    output = _search_fuzzy(cache, parsed, usage_stats, query)

                if needs_refresh:
                    output.rerun = 1.0
    finally:
        cache.close()
        tracker.close()

    sys.stdout.write(output.to_json() + "\n")


def _search_regex(
    cache: _lib_cache.EntityCache,
    parsed: ParsedQuery,
) -> AlfredOutput:
    all_entities = cache.get_all()
    try:
        results = _lib_search.regex_search(all_entities, parsed.regex_pattern or "")
        return _build_search_output(results, "")
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
    cache: _lib_cache.EntityCache,
    parsed: ParsedQuery,
    usage_stats: dict[str, UsageRecord],
    query: str,
) -> AlfredOutput:
    domain_entities = cache.get_by_domain(parsed.domain_filter or "")
    results = _lib_search.fuzzy_search(
        domain_entities, parsed.text, usage_stats=usage_stats
    )
    return _build_search_output(results, query)


def _format_param_summary(parsed: dict[str, object]) -> str:
    """Short human-readable summary of parsed service params."""
    parts: list[str] = []
    for k, v in parsed.items():
        if k == "brightness" and isinstance(v, int):
            pct = round(v / 255 * 100)
            parts.append(f"brightness={v}/255 (\u2248{pct}%)")
        elif k == "rgb_color" and isinstance(v, list) and len(v) == 3:
            parts.append(f"rgb={v[0]},{v[1]},{v[2]}")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def _quick_exec(
    cache: _lib_cache.EntityCache,
    parsed: ParsedQuery,
    usage_stats: dict[str, UsageRecord],
    query: str,
) -> AlfredOutput:
    """Build an Alfred output for the quick-exec syntax.

    If the entity is unknown, fall back to fuzzy search so typos behave like
    normal queries.  If params fail to parse, show an error row **followed**
    by fuzzy matches so the user can still find what they meant.
    """
    entity_id = parsed.entity_id or ""
    raw_params = parsed.raw_params or ""

    entity = cache.get_by_entity_id(entity_id)
    if entity is None:
        # Unknown entity — run normal fuzzy search over the whole query.
        fallback = ParsedQuery(
            mode="fuzzy",
            text=query.strip(),
            domain_filter=None,
            regex_pattern=None,
        )
        return _search_fuzzy(cache, fallback, usage_stats, query)

    dc = get_domain_config(entity.domain)

    # Two-pass: extract the keys the user typed so infer_action can pick the
    # right service, then re-parse with that action for type coercion +
    # validation (e.g. brightness:80% → 204 when action is light.turn_on).
    action = infer_action(entity.domain, extract_param_keys(raw_params))
    try:
        service_data = (
            parse_service_params(raw_params, entity.domain, action)
            if raw_params
            else {}
        )
    except ValueError as exc:
        items: list[AlfredItem] = [
            AlfredItem(
                title=f"Invalid parameters for {entity.friendly_name}",
                subtitle=str(exc),
                icon=AlfredIcon(path=dc.icon_path),
                valid=False,
            )
        ]
        return AlfredOutput(items=items)

    if not action:
        return AlfredOutput(
            items=[
                AlfredItem(
                    title=f"No action available for {entity.friendly_name}",
                    subtitle=f"Domain '{entity.domain}' has no default action",
                    icon=AlfredIcon(path=dc.icon_path),
                    valid=False,
                )
            ]
        )

    action_label = action.replace("_", " ").title()
    if service_data:
        summary = _format_param_summary(service_data)
        subtitle = f"{action_label} \u2192 {summary}"
    else:
        subtitle = f"{action_label} \u00b7 {entity.entity_id}"

    item = AlfredItem(
        title=f"\u21b5 {action_label} {entity.friendly_name}",
        subtitle=subtitle,
        arg=entity.entity_id,
        icon=AlfredIcon(path=dc.icon_path),
        variables={
            "entity_id": entity.entity_id,
            "action": action,
            "domain": entity.domain,
            "params": raw_params,
        },
        valid=True,
    )
    return AlfredOutput(items=[item])


def _search_fuzzy(
    cache: _lib_cache.EntityCache,
    parsed: ParsedQuery,
    usage_stats: dict[str, UsageRecord],
    query: str,
) -> AlfredOutput:
    all_entities = cache.get_all()
    results = _lib_search.fuzzy_search(
        all_entities, parsed.text, usage_stats=usage_stats
    )
    output = _build_search_output(results, query)

    if parsed.text:
        domain_counts = cache.get_domain_counts()
        suggestion_tuples = _lib_suggestions.get_domain_suggestion_items(
            parsed.text, domain_counts
        )
        suggestion_items = [
            AlfredItem(
                title=(
                    f"Filter: {domain} ({count} "
                    f"{'entity' if count == 1 else 'entities'})"
                ),
                subtitle=f"Tab to filter by {domain}",
                icon=AlfredIcon(path=icon_path),
                autocomplete=autocomplete,
                uid=f"domain_suggestion_{domain}",
                valid=False,
            )
            for domain, icon_path, count, autocomplete in suggestion_tuples
        ]
        if suggestion_items:
            output.items = suggestion_items + output.items

    return output


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        handle_error(exc)
