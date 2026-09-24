"""Action execution script.

Invoked by Alfred as a Run Script node. Reads all inputs from Alfred
environment variables:

  entity_id  — HA entity to act on (or ``__system__`` for system commands)
  action     — action name (e.g. ``toggle``, ``turn_on``, ``cache_refresh``)
  domain     — entity domain (e.g. ``light``)
  params     — optional raw param string (``key:value,key:value``)

Outputs a plain-text notification message to stdout for Alfred's
Post Notification node.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Optional

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

from ha_lib.actions import dispatch_action  # noqa: E402
from ha_lib.cache import open_cache  # noqa: E402
from ha_lib.client import HAClient  # noqa: E402
from ha_lib.config import Config  # noqa: E402
from ha_lib.errors import HAWorkflowError, handle_error  # noqa: E402
from ha_lib.notify import notify, notify_error  # noqa: E402
from ha_lib.params import parse_service_params  # noqa: E402
from ha_lib.profiles import SERVER_ENV_VAR, split_action  # noqa: E402
from ha_lib.server_actions import (  # noqa: E402
    ServerActionContext,
    run_server_action,
)
from ha_lib.usage import open_usage_tracker  # noqa: E402

_SYSTEM_ENTITY = "__system__"
_SERVER_ENTITY = "__server__"


def _spawn_refresh(config: Config) -> None:
    """Background cache refresh for *config*'s server (shared with search)."""
    from ha_workflow.scripts.search_filter import _maybe_refresh_background

    _maybe_refresh_background(config)


def _server_context() -> ServerActionContext:
    """Real dependencies for server actions: dialogs, Keychain, HTTP."""
    from ha_lib.keychain import SecurityCliTokenStore
    from ha_lib.prompter import OsascriptPrompter

    return ServerActionContext(
        env=dict(os.environ),
        prompter=OsascriptPrompter(),
        token_store=SecurityCliTokenStore(),
        client_factory=lambda cfg, timeout: HAClient(cfg, timeout=timeout),
        spawn_refresh=_spawn_refresh,
    )


_YAML_SPECIAL_CHARS = frozenset(":#[]{},&*!|>")


# "Lake House: " when several servers are configured, else "" — set once
# the target server is known (see _set_notify_prefix).
_notify_prefix: list[str] = [""]


def _notify(message: str) -> None:
    notify(_notify_prefix[0] + message)


def _notify_error(message: str) -> None:
    notify_error(_notify_prefix[0] + message)


def _set_notify_prefix() -> None:
    """Name the target server in notifications when there is more than one."""
    _notify_prefix[0] = ""
    try:
        config = Config.from_env()
    except HAWorkflowError:
        return  # the action itself will report the configuration problem
    if config.is_multi_server:
        _notify_prefix[0] = f"{config.server_display_name}: "


def _record_usage(config: Config, entity_id: str) -> None:
    tracker = open_usage_tracker(config)
    try:
        tracker.record_usage(entity_id)
    finally:
        tracker.close()


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


def _lookup_device_id(client: HAClient, entity_id: str) -> str:
    for entry in client.get_entity_registry():
        if entry.get("entity_id") == entity_id:
            return entry.get("device_id") or ""
    return ""


def _lookup_device(client: HAClient, device_id: str) -> Optional[dict[str, Any]]:
    for dev in client.get_device_registry():
        if dev.get("id") == device_id:
            return dev
    return None


def _lookup_area_id(client: HAClient, entity_id: str) -> str:
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


def _cmd_copy(config: Config, entity_id: str, action: str) -> None:
    client = HAClient(config)
    if action == "copy_entity_id":
        text = entity_id
        msg = f"Copied: {entity_id}"
    elif action == "copy_entity_details":
        state = client.get_state(entity_id)
        text = _format_as_yaml(state)
        friendly = state.get("attributes", {}).get("friendly_name", entity_id)
        msg = f"Copied details for {friendly}"
    elif action == "copy_device_details":
        device_id = _lookup_device_id(client, entity_id)
        if not device_id:
            _notify_error(f"No device found for {entity_id}")
            return
        device = _lookup_device(client, device_id)
        if not device:
            _notify_error(f"Device {device_id} not found")
            return
        text = _format_as_yaml(device)
        msg = f"Copied device details for {entity_id}"
    else:
        _notify_error(f"Unknown copy action: {action}")
        return

    try:
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
    except Exception as exc:
        _notify_error(f"Failed to copy to clipboard: {exc}")
        return
    _notify(msg)


def _cmd_open(config: Config, entity_id: str, action: str) -> None:
    import urllib.parse

    ha_url = config.ha_url
    safe_id = urllib.parse.quote(entity_id, safe="")
    client = HAClient(config)

    if action == "open_entity":
        url = f"{ha_url}/config/entities?filter={safe_id}"
    elif action == "open_device":
        device_id = _lookup_device_id(client, entity_id)
        if not device_id:
            _notify_error(f"No device found for {entity_id}")
            return
        url = f"{ha_url}/config/devices/device/{device_id}"
    elif action == "open_area":
        area_id = _lookup_area_id(client, entity_id)
        if not area_id:
            _notify_error(f"No area found for {entity_id}")
            return
        url = f"{ha_url}/config/areas/area/{area_id}"
    elif action == "open_history":
        url = f"{ha_url}/history?entity_id={safe_id}"
    else:
        _notify_error(f"Unknown open action: {action}")
        return

    try:
        subprocess.run(["open", url], check=True)
    except Exception as exc:
        _notify_error(f"Failed to open in browser: {exc}")
        return
    _notify("Opened in Home Assistant")


def _cmd_system(config: Config, action: str) -> None:
    if action == "usage_clear":
        tracker = open_usage_tracker(config)
        try:
            tracker.clear()
        finally:
            tracker.close()
        _notify("Usage history cleared")

    elif action == "cache_refresh":
        cache = open_cache(config)
        try:
            from ha_lib.client import HAClient as _HAClient
            from ha_lib.entities import Entity

            client = _HAClient(config)
            states = client.get_states()

            # build minimal registry lookup
            area_names: dict[str, str] = {}
            for area in client.get_area_registry():
                aid = area.get("area_id", "")
                name = area.get("name", "")
                if aid and name:
                    area_names[aid] = name
            device_areas: dict[str, str] = {}
            for dev in client.get_device_registry():
                did = dev.get("id", "")
                aid = dev.get("area_id", "")
                if did and aid:
                    device_areas[did] = aid
            entity_info: dict[str, tuple[str, str]] = {}
            for entry in client.get_entity_registry():
                eid = entry.get("entity_id", "")
                if not eid:
                    continue
                did = entry.get("device_id") or ""
                aid = entry.get("area_id") or ""
                if not aid and did:
                    aid = device_areas.get(did, "")
                entity_info[eid] = (area_names.get(aid, ""), did)

            entities: list[Entity] = []
            for s in states:
                eid = s.get("entity_id", "")
                info = entity_info.get(eid, ("", ""))
                entities.append(
                    Entity.from_state_dict(s, area_name=info[0], device_id=info[1])
                )
            cache.refresh(entities)
            count = len(entities)
        finally:
            cache.close()
        _notify(f"Cache refreshed: {count} entities")

    elif action == "ha_restart":
        client = HAClient(config)
        try:
            client.call_service("homeassistant", "restart")
            _notify("Home Assistant is restarting")
        except Exception as exc:
            _notify_error(f"Restart failed: {exc}")

    elif action == "ha_check_config":
        client = HAClient(config)
        try:
            result = client.check_config()
            errors = result.get("errors")
            if errors:
                _notify_error(f"Config invalid: {errors}")
            else:
                _notify("Configuration is valid")
        except Exception as exc:
            _notify_error(f"Config check failed: {exc}")

    elif action == "ha_error_log":
        client = HAClient(config)
        try:
            log_text = client.get_error_log()
        except Exception as exc:
            msg = str(exc)
            if "404" in msg:
                _notify_error(
                    "Error log not available (endpoint returned 404). "
                    "This endpoint is not supported via Nabu Casa cloud — "
                    "use a local HA URL instead."
                )
            else:
                _notify_error(f"Failed to fetch error log: {exc}")
            return
        if not log_text or not log_text.strip():
            _notify("Error log is empty")
            return
        try:
            subprocess.run(["pbcopy"], input=log_text.encode("utf-8"), check=True)
        except Exception as exc:
            _notify_error(f"Failed to copy log to clipboard: {exc}")
            return
        first_line = log_text.strip().split("\n")[0][:80]
        lines = log_text.strip().count("\n") + 1
        _notify(f"Error log copied ({lines} lines): {first_line}")

    else:
        _notify_error(f"Unknown system action: {action}")


def main() -> None:
    """Run the action; configuration problems become a plain notification."""
    try:
        _main()
    except HAWorkflowError as exc:
        # Run Script output is the notification text: keep it readable.
        notify_error(str(exc))
    finally:
        _notify_prefix[0] = ""


def _main() -> None:
    entity_id = os.environ.get("entity_id", "").strip()
    action, server_id = split_action(os.environ.get("action", "").strip())
    domain = os.environ.get("domain", "").strip()
    if server_id:
        # The item names the server whose cache produced it.  Every
        # Config.from_env() below (and any child process) resolves that
        # server, never whichever one happens to be active now.
        os.environ[SERVER_ENV_VAR] = server_id
    # Phase D: params come cleanly via Alfred variable — no ::encoding hack
    raw_params = os.environ.get("params", "").strip()

    if entity_id == _SERVER_ENTITY:
        notify(run_server_action(action, _server_context()))
        return

    _set_notify_prefix()

    if entity_id == _SYSTEM_ENTITY:
        config = Config.from_env()
        _cmd_system(config, action)
        return

    if not entity_id or not action:
        _notify_error("Missing entity_id or action")
        return

    # Route viewer / copy / open actions
    if action in ("show_details", "view_history"):
        # Legacy routing — kept for backward compatibility
        config = Config.from_env()
        client = HAClient(config)
        if action == "show_details":
            try:
                state = client.get_state(entity_id)
                text = _format_as_yaml(state)
                friendly = state.get("attributes", {}).get("friendly_name", entity_id)
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
                current_state = state.get("state", "unknown")
                _notify(f"Copied details for {friendly} ({current_state})")
            except Exception as exc:
                _notify_error(f"Failed to fetch details: {exc}")
        else:
            try:
                changes = client.get_history(entity_id, hours=1)
                if not changes:
                    _notify("No history found (last hour)")
                    return
                lines_out = [f"History for {entity_id} (last hour)", ""]
                for entry in changes:
                    state = entry.get("state", "?")
                    changed = entry.get("last_changed", "")
                    if "T" in changed:
                        time_part = changed.split("T")[1].split(".")[0]
                    else:
                        time_part = changed
                    lines_out.append(f"{time_part}  {state}")
                text = "\n".join(lines_out)
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
                _notify(f"History copied ({len(changes)} state changes)")
            except Exception as exc:
                _notify_error(f"Failed to fetch history: {exc}")
        return

    if action.startswith("copy_"):
        config = Config.from_env()
        _cmd_copy(config, entity_id, action)
        return

    if action.startswith("open_"):
        config = Config.from_env()
        _cmd_open(config, entity_id, action)
        return

    # Guard: action_param is a UI routing pseudo-action, not executable
    if action == "action_param":
        _notify_error(
            "Parameter entry was not completed. Use the actions menu to set parameters."
        )
        return

    # Phase D: params come via $params variable — no ::encoding
    if not domain:
        domain = entity_id.split(".")[0] if "." in entity_id else ""

    service_data: Optional[dict[str, object]] = None
    if raw_params:
        try:
            service_data = parse_service_params(raw_params, domain, action)
        except ValueError as exc:
            _notify_error(str(exc))
            return

    config = Config.from_env()
    client = HAClient(config)
    result = dispatch_action(client, entity_id, action, service_data=service_data)
    if result.success:
        _notify(result.message)
        _record_usage(config, entity_id)
    else:
        _notify_error(result.message)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        handle_error(exc)
