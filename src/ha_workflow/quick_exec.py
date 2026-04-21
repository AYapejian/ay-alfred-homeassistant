"""Shared quick-exec builder used by the main search and action submenu.

Quick-exec syntax is ``<domain>.<object_id> [param:value,param:value...]``.
When a user types a well-formed quick-exec, both the main search filter and
the action submenu render a single actionable row that fires the chosen
service call on Enter.
"""

from __future__ import annotations

from typing import Optional

from ha_lib.cache import EntityCache
from ha_lib.entities import get_domain_config
from ha_lib.inference import infer_action
from ha_lib.params import extract_param_keys, parse_service_params
from ha_workflow.alfred import AlfredIcon, AlfredItem, AlfredOutput


def format_param_summary(parsed: dict[str, object]) -> str:
    """Short human-readable summary of parsed service params."""
    parts: list[str] = []
    for k, v in parsed.items():
        if k == "brightness" and isinstance(v, int):
            pct = round(v / 255 * 100)
            parts.append(f"brightness={v}/255 (≈{pct}%)")
        elif k == "rgb_color" and isinstance(v, list) and len(v) == 3:
            parts.append(f"rgb={v[0]},{v[1]},{v[2]}")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def build_quick_exec_output(
    cache: EntityCache,
    entity_id: str,
    raw_params: str,
) -> Optional[AlfredOutput]:
    """Build the quick-exec :class:`AlfredOutput` for *entity_id* + *raw_params*.

    Returns ``None`` when *entity_id* is not in the cache — the caller should
    fall back to its own default behavior (fuzzy search, regular submenu, etc).
    Otherwise returns an :class:`AlfredOutput` containing exactly one row:
    the executable action, a parse-error row, or a no-action-available row.
    """
    entity = cache.get_by_entity_id(entity_id)
    if entity is None:
        return None

    dc = get_domain_config(entity.domain)

    # Two-pass: extract the keys the user typed so infer_action can pick the
    # right service, then re-parse with that action for type coercion +
    # validation (e.g. brightness:80% -> 204 when action is light.turn_on).
    action = infer_action(entity.domain, extract_param_keys(raw_params))
    try:
        service_data = (
            parse_service_params(raw_params, entity.domain, action)
            if raw_params
            else {}
        )
    except ValueError as exc:
        return AlfredOutput(
            items=[
                AlfredItem(
                    title=f"Invalid parameters for {entity.friendly_name}",
                    subtitle=str(exc),
                    icon=AlfredIcon(path=dc.icon_path),
                    valid=False,
                )
            ]
        )

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
        summary = format_param_summary(service_data)
        subtitle = f"{action_label} → {summary}"
    else:
        subtitle = f"{action_label} · {entity.entity_id}"

    item = AlfredItem(
        title=f"↵ {action_label} {entity.friendly_name}",
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
