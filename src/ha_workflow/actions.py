"""Action dispatcher — maps action names to HA service calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ha_workflow.entities import get_domain_config
from ha_workflow.errors import HAAuthError, HAConnectionError
from ha_workflow.ha_client import HAClient


@dataclass
class ActionResult:
    """Outcome of an action dispatch."""

    success: bool
    message: str


# Actions whose HA service name differs from our action name.
# Currently empty — all actions map 1:1. Add overrides here if a
# user-facing action name ever diverges from the HA service name
# (e.g. "open" -> "open_cover").
_SERVICE_OVERRIDES: dict[str, str] = {}


def _action_label(action: str) -> str:
    """Human-readable label for an action name (e.g. ``turn_on`` → ``Turned on``)."""
    past: dict[str, str] = {
        "toggle": "Toggled",
        "turn_on": "Turned on",
        "turn_off": "Turned off",
        "lock": "Locked",
        "unlock": "Unlocked",
        "open_cover": "Opened",
        "close_cover": "Closed",
        "stop_cover": "Stopped",
        "press": "Pressed",
        "trigger": "Triggered",
        "start": "Started",
        "stop": "Stopped",
        "cancel": "Cancelled",
        "pause": "Paused",
        "increment": "Incremented",
        "decrement": "Decremented",
        "reset": "Reset",
        "install": "Installing",
        "skip": "Skipped",
        "return_to_base": "Returning to base",
        "media_play": "Playing",
        "media_pause": "Paused",
        "media_stop": "Stopped",
        "set_temperature": "Temperature set",
    }
    return past.get(action, action.replace("_", " ").title())


def dispatch_action(
    client: HAClient,
    entity_id: str,
    action: str,
    service_data: Optional[dict[str, object]] = None,
) -> ActionResult:
    """Execute *action* on *entity_id* via the HA REST API.

    Returns an :class:`ActionResult` with a human-readable message suitable
    for display in an Alfred notification.
    """
    domain = entity_id.split(".")[0] if "." in entity_id else ""
    if not domain:
        return ActionResult(success=False, message=f"Invalid entity ID: {entity_id}")

    dc = get_domain_config(domain)
    if not dc.available_actions:
        return ActionResult(
            success=False,
            message=f"No actions available for {domain} entities",
        )

    if action not in dc.available_actions:
        avail = ", ".join(dc.available_actions)
        return ActionResult(
            success=False,
            message=f"Unknown action '{action}' for {domain} ({avail})",
        )

    service = _SERVICE_OVERRIDES.get(action, action)
    data: dict[str, object] = {"entity_id": entity_id}
    if service_data:
        data.update(service_data)

    try:
        client.call_service(domain, service, data)
    except HAConnectionError as exc:
        return ActionResult(success=False, message=f"Connection error: {exc}")
    except HAAuthError as exc:
        return ActionResult(success=False, message=f"Auth error: {exc}")
    except Exception as exc:
        return ActionResult(success=False, message=f"Unexpected error: {exc}")

    friendly = entity_id.split(".", 1)[1].replace("_", " ").title()
    label = _action_label(action)
    return ActionResult(success=True, message=f"{label} {friendly}")
