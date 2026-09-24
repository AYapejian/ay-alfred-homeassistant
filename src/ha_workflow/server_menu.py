"""``ha server:`` — the server list shown in Alfred.

Pure presentation: callers gather :class:`ServerRow` values from their copy
of the library (``ha_lib`` for the Alfred scripts, ``ha_workflow`` for the
CLI) and this module turns them into Script Filter items.  Nothing here reads
config, opens a cache for writing, or contacts a server — the list must
render when the active server is down, uncached or misconfigured.

Item payloads follow the ``__system__`` dispatch pattern: ``entity_id`` is
:data:`SERVER_ENTITY` and ``action`` is ``server_<verb>[::<server id>]``.
"""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional

from ha_workflow.alfred import AlfredIcon, AlfredItem, AlfredMod, AlfredOutput

SERVER_ENTITY = "__server__"
DEFAULT_SERVER_ID = "default"

SERVER_ICON = AlfredIcon(path="icons/_server.png")
ACTIVE_ICON = AlfredIcon(path="icons/_server_active.png")
_WARN_ICON = AlfredIcon(path="icons/_system.png")

_QUERY_RE = re.compile(r"^\s*server(?::(?P<filter>.*)|\s*)$", re.IGNORECASE | re.DOTALL)
_CHECK = "✓ "
_DOT = " · "


@dataclass(frozen=True)
class ServerRow:
    """One configured server plus its locally known status."""

    id: str
    name: str
    host: str
    is_default: bool
    entity_count: Optional[int] = None
    last_refresh: Optional[float] = None
    last_error: Optional[str] = None
    last_error_at: Optional[float] = None


def parse_server_query(query: str) -> Optional[str]:
    """Filter text for a ``server:`` / ``server`` query, else ``None``."""
    match = _QUERY_RE.match(query)
    if not match:
        return None
    return (match.group("filter") or "").strip()


def server_action(verb: str, server_id: Optional[str] = None) -> str:
    """``server_<verb>`` or ``server_<verb>::<server id>``."""
    return f"server_{verb}::{server_id}" if server_id else f"server_{verb}"


def ago(seconds: float) -> str:
    """Compact relative time: ``45s ago``, ``3m ago``, ``2h ago``, ``4d ago``."""
    secs = max(0, int(seconds))
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _variables(action: str) -> dict[str, str]:
    return {"entity_id": SERVER_ENTITY, "action": action, "domain": SERVER_ENTITY}


def _blocked_mods(subtitle: str) -> dict[str, AlfredMod]:
    return {
        key: AlfredMod(subtitle=subtitle, valid=False) for key in ("cmd", "alt", "ctrl")
    }


def _matches(row: ServerRow, words: Sequence[str]) -> bool:
    haystack = f"{row.name} {row.host}".casefold()
    return all(word in haystack for word in words)


def _row_item(row: ServerRow, active: bool, now: float) -> AlfredItem:
    parts: list[str] = []
    if active:
        parts.append("Active")
    parts.append(row.host)
    if row.entity_count:
        noun = "entity" if row.entity_count == 1 else "entities"
        count = f"{row.entity_count} {noun}"
        parts.append(count if active else f"{count} cached")
    else:
        parts.append("no cached entities")
    if active and row.last_refresh is not None:
        parts.append(f"refreshed {ago(now - row.last_refresh)}")
    if not active:
        parts.append("↵ switch")
    subtitle = _DOT.join(parts)
    if row.last_error:
        when = f" {ago(now - row.last_error_at)}" if row.last_error_at else ""
        subtitle += f"{_DOT}last refresh failed{when}: {row.last_error}"

    if row.is_default:
        cmd_sub = "Server actions… (test connection)"
        other_sub = "Default server: configured in Alfred → Workflows → Configure"
    else:
        cmd_sub = "Server actions… (test, re-enter token, remove)"
        other_sub = "⌘ ↵ for server actions"

    return AlfredItem(
        title=f"{_CHECK}{row.name}" if active else row.name,
        subtitle=subtitle,
        arg=row.id,
        icon=ACTIVE_ICON if active else SERVER_ICON,
        variables=_variables(server_action("switch", row.id)),
        valid=True,
        mods={
            # ⌘ is wired to the actions Script Filter: a server sub-menu.
            "cmd": AlfredMod(
                subtitle=cmd_sub,
                valid=True,
                variables=_variables(server_action("menu", row.id)),
            ),
            # ⌥ / ⌃ are wired to copy-entity / open-in-HA: not for servers.
            "alt": AlfredMod(subtitle=other_sub, valid=False),
            "ctrl": AlfredMod(subtitle=other_sub, valid=False),
        },
    )


def build_server_actions_menu(row: Optional[ServerRow], active: bool) -> AlfredOutput:
    """The ⌘ sub-menu for one server (shown by the actions Script Filter)."""
    if row is None:
        return AlfredOutput(
            items=[
                AlfredItem(
                    title="Server not found",
                    subtitle="It may have been removed — go back to 'ha server:'",
                    icon=_WARN_ICON,
                    valid=False,
                )
            ]
        )

    def action_item(title: str, subtitle: str, verb: str) -> AlfredItem:
        variables = _variables(server_action(verb, row.id))
        variables.update({"params": "", "param_mode": ""})
        return AlfredItem(
            title=title,
            subtitle=subtitle,
            arg=row.id,
            icon=SERVER_ICON,
            variables=variables,
            valid=True,
        )

    state = "active" if active else "not active"
    items = [
        AlfredItem(
            title=row.name,
            subtitle=f"{row.host} · {state}",
            icon=ACTIVE_ICON if active else SERVER_ICON,
            valid=False,
        )
    ]
    if not active:
        items.append(
            action_item(
                f"Switch to {row.name}",
                "Make this the server Alfred searches and controls",
                "switch",
            )
        )
    items.append(
        action_item(
            "Test connection",
            "Reports the Home Assistant version, or the error",
            "test",
        )
    )
    if row.is_default:
        items.append(
            AlfredItem(
                title="Default server",
                subtitle="URL and token: Alfred → Workflows → Configure",
                icon=_WARN_ICON,
                valid=False,
            )
        )
    else:
        items.append(
            action_item(
                "Re-enter token…",
                "Hidden dialog; the token is stored in the macOS Keychain",
                "token",
            )
        )
        items.append(
            action_item(
                "Remove server…",
                "Asks first. Deletes its token, cached entities and usage history",
                "remove",
            )
        )
    return AlfredOutput(items=items)


def build_server_menu(
    rows: Sequence[ServerRow],
    active_id: str,
    filter_text: str = "",
    file_error: Optional[str] = None,
    file_exists: bool = False,
    now: Optional[float] = None,
) -> AlfredOutput:
    """Build the ``server:`` Script Filter output.

    Order: problem banners, the active server, the others alphabetically,
    then "Add server…" and "Edit servers file…".
    """
    now = time.time() if now is None else now
    items: list[AlfredItem] = []

    if file_error:
        items.append(
            AlfredItem(
                title=f"Servers file is invalid: {file_error}",
                subtitle="↵ open profiles.json to fix it",
                icon=_WARN_ICON,
                arg="server_edit",
                variables=_variables(server_action("edit")),
                valid=True,
                mods=_blocked_mods("↵ open profiles.json to fix it"),
            )
        )

    known_ids = {row.id for row in rows}
    if rows and active_id not in known_ids:
        items.append(
            AlfredItem(
                title=f"Active server {active_id!r} is not configured",
                subtitle="It was removed or renamed — choose a server below",
                icon=_WARN_ICON,
                valid=False,
            )
        )

    if not rows:
        items.append(
            AlfredItem(
                title="No servers configured",
                subtitle="Add a server below, or set up the default one",
                icon=_WARN_ICON,
                valid=False,
            )
        )

    words = filter_text.casefold().split()
    active = [r for r in rows if r.id == active_id]
    others = sorted(
        (r for r in rows if r.id != active_id), key=lambda r: r.name.casefold()
    )
    for row in active + others:
        if words and not _matches(row, words):
            continue
        items.append(_row_item(row, row.id == active_id, now))

    items.append(
        AlfredItem(
            title="Add server…",
            subtitle="Name, URL and token — the token is kept in the macOS Keychain",
            arg="server_add",
            icon=SERVER_ICON,
            variables=_variables(server_action("add")),
            valid=True,
            mods=_blocked_mods("↵ to add a server"),
        )
    )
    if not rows:
        items.append(
            AlfredItem(
                title="Configure the default server",
                subtitle=(
                    "Alfred → Workflows → Home Assistant → Configure: "
                    "set HA URL and HA Token (workflow configuration)"
                ),
                icon=_WARN_ICON,
                valid=False,
            )
        )
    if file_exists:
        items.append(
            AlfredItem(
                title="Edit servers file…",
                subtitle="Open profiles.json (names, URLs, badges — no tokens)",
                arg="server_edit",
                icon=_WARN_ICON,
                variables=_variables(server_action("edit")),
                valid=True,
                mods=_blocked_mods("↵ to open profiles.json"),
            )
        )
    return AlfredOutput(items=items)
