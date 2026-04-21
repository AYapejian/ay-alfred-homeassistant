"""Action submenu Script Filter.

Invoked by Alfred as::

    python3 scripts/actions_filter.py "{query}"

Reads ``entity_id`` and ``domain`` from Alfred environment variables.
Outputs Alfred Script Filter JSON to stdout.
"""

from __future__ import annotations

import calendar
import os
import sys
import time
from typing import Optional

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

from ha_lib.cache import open_cache  # noqa: E402
from ha_lib.config import Config  # noqa: E402
from ha_lib.entities import Entity, get_action_params, get_domain_config  # noqa: E402
from ha_lib.errors import handle_error  # noqa: E402
from ha_lib.query_parser import parse_query  # noqa: E402
from ha_workflow.alfred import AlfredIcon, AlfredItem, AlfredOutput  # noqa: E402
from ha_workflow.quick_exec import build_quick_exec_output  # noqa: E402

_SYSTEM_ICON = AlfredIcon(path="icons/_system.png")
_DEBUG = os.environ.get("HA_DEBUG", "")


def _dbg(msg: str) -> None:
    if _DEBUG:
        sys.stderr.write(f"[ha-debug] {msg}\n")
        sys.stderr.flush()


def _format_relative_time(iso_timestamp: str) -> str:
    """Convert an ISO-8601 timestamp to a human-readable relative string."""
    if not iso_timestamp:
        return ""
    try:
        clean = iso_timestamp.split(".")[0].replace("Z", "").replace("+00:00", "")
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


def _get_cached_entity(config: Config, entity_id: str) -> Optional[Entity]:
    cache = open_cache(config)
    try:
        for e in cache.get_all():
            if e.entity_id == entity_id:
                return e
        return None
    finally:
        cache.close()


def main() -> None:
    entity_id = os.environ.get("entity_id", "").strip()
    domain = os.environ.get("domain", "").strip()
    query = " ".join(sys.argv[1:])

    # Quick-exec in the submenu: if the user types a well-formed
    # ``<domain>.<object_id> [params]`` query, render the quick-exec row
    # instead of the regular submenu so the same syntax works anywhere.
    parsed = parse_query(query)
    if parsed.mode == "quick_exec" and parsed.entity_id:
        try:
            config = Config.from_env()
            cache = open_cache(config)
            try:
                qx_output = build_quick_exec_output(
                    cache, parsed.entity_id, parsed.raw_params or ""
                )
            finally:
                cache.close()
        except Exception:
            qx_output = None
        if qx_output is not None:
            sys.stdout.write(qx_output.to_json() + "\n")
            return

    if not entity_id:
        output = AlfredOutput(
            items=[AlfredItem(title="No entity selected", valid=False)]
        )
        sys.stdout.write(output.to_json() + "\n")
        return

    if not domain:
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

    try:
        config = Config.from_env()
        entity = _get_cached_entity(config, entity_id)
    except Exception:
        entity = None

    friendly = (
        entity.friendly_name
        if entity
        else entity_id.split(".", 1)[1].replace("_", " ").title()
    )
    last_changed = entity.last_changed if entity else ""
    area_name = entity.area_name if entity else ""
    device_id = entity.device_id if entity else ""

    items: list[AlfredItem] = []

    # --- Header item ---
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
        params = get_action_params(domain, action)
        if params:
            param_hints = ", ".join(p.label.lower() for p in params)
            subtitle = f"{friendly} \u00b7 supports: {param_hints}"
        else:
            subtitle = f"{friendly} \u00b7 {domain}"

        # Phase D: param-capable actions route to params Script Filter node
        # via valid=True with param_mode variable; no encoding hack.
        if params:
            items.append(
                AlfredItem(
                    title=label,
                    subtitle=subtitle,
                    icon=AlfredIcon(path=dc.icon_path),
                    arg=entity_id,
                    variables={
                        "entity_id": entity_id,
                        "action": action,
                        "domain": domain,
                        "params": "",
                        "param_mode": "1",
                    },
                    valid=True,
                )
            )
        else:
            items.append(
                AlfredItem(
                    title=label,
                    subtitle=subtitle,
                    icon=AlfredIcon(path=dc.icon_path),
                    arg=entity_id,
                    variables={
                        "entity_id": entity_id,
                        "action": action,
                        "domain": domain,
                        "params": "",
                        "param_mode": "",
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
            arg=entity_id,
            variables={
                "entity_id": entity_id,
                "action": "copy_entity_id",
                "domain": domain,
                "params": "",
                "param_mode": "",
            },
            valid=True,
        )
    )
    items.append(
        AlfredItem(
            title="Copy Entity Details",
            subtitle="Full entity state as YAML",
            icon=_SYSTEM_ICON,
            arg=entity_id,
            variables={
                "entity_id": entity_id,
                "action": "copy_entity_details",
                "domain": domain,
                "params": "",
                "param_mode": "",
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
                arg=entity_id,
                variables={
                    "entity_id": entity_id,
                    "action": "copy_device_details",
                    "domain": domain,
                    "params": "",
                    "param_mode": "",
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
            arg=entity_id,
            variables={
                "entity_id": entity_id,
                "action": "open_entity",
                "domain": domain,
                "params": "",
                "param_mode": "",
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
                arg=entity_id,
                variables={
                    "entity_id": entity_id,
                    "action": "open_device",
                    "domain": domain,
                    "params": "",
                    "param_mode": "",
                },
                valid=True,
            )
        )
    if area_name:
        items.append(
            AlfredItem(
                title="Open Area",
                subtitle=f"{area_name} in Home Assistant",
                icon=_SYSTEM_ICON,
                arg=entity_id,
                variables={
                    "entity_id": entity_id,
                    "action": "open_area",
                    "domain": domain,
                    "params": "",
                    "param_mode": "",
                },
                valid=True,
            )
        )
    items.append(
        AlfredItem(
            title="Open History",
            subtitle="Entity history in Home Assistant",
            icon=_SYSTEM_ICON,
            arg=entity_id,
            variables={
                "entity_id": entity_id,
                "action": "open_history",
                "domain": domain,
                "params": "",
                "param_mode": "",
            },
            valid=True,
        )
    )

    output = AlfredOutput(items=items)
    sys.stdout.write(output.to_json() + "\n")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        handle_error(exc)
