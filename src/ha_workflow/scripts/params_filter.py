"""Parameter entry Script Filter.

Invoked by Alfred as::

    python3 scripts/params_filter.py "{query}"

Reads ``entity_id``, ``action``, ``domain`` from Alfred environment variables.
Shows param hints when query is empty, confirmation item when params are typed.

This replaces the old inline param entry hack (_cmd_actions_param_entry).
Params travel as clean Alfred variables — no ``action::param_str`` encoding.
"""

from __future__ import annotations

import os
import sys

# Ensure the workflow root and packages/ are on sys.path.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKFLOW_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
for _p in (_WORKFLOW_ROOT, os.path.join(_WORKFLOW_ROOT, "packages")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ha_lib.entities import get_action_params, get_domain_config  # noqa: E402
from ha_lib.errors import handle_error  # noqa: E402
from ha_lib.params import parse_service_params  # noqa: E402
from ha_workflow.alfred import AlfredIcon, AlfredItem, AlfredOutput  # noqa: E402

_DEBUG = os.environ.get("HA_DEBUG", "")


def _dbg(msg: str) -> None:
    if _DEBUG:
        sys.stderr.write(f"[ha-debug] {msg}\n")
        sys.stderr.flush()


def _format_param_summary(parsed: dict[str, object]) -> str:
    """Build a human-readable summary of parsed service params."""
    parts: list[str] = []
    for k, v in parsed.items():
        if k == "brightness" and isinstance(v, int):
            pct = round(v / 255 * 100)
            tip = "use brightness:30% for 30%"
            hint = f"brightness={v}/255 (\u2248{pct}%) \u00b7 {tip}"
            parts.append(hint)
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def main() -> None:
    entity_id = os.environ.get("entity_id", "").strip()
    action = os.environ.get("action", "").strip()
    domain = os.environ.get("domain", "").strip()
    query = " ".join(sys.argv[1:]).strip()

    _dbg(f"params_filter: entity_id={entity_id!r} action={action!r} query={query!r}")

    if not entity_id or not action:
        output = AlfredOutput(
            items=[AlfredItem(title="Missing entity or action", valid=False)]
        )
        sys.stdout.write(output.to_json() + "\n")
        return

    if not domain:
        domain = entity_id.split(".")[0] if "." in entity_id else ""

    dc = get_domain_config(domain)
    params = get_action_params(domain, action)
    friendly = entity_id.split(".", 1)[1].replace("_", " ").title()
    action_label = action.replace("_", " ").title()

    items: list[AlfredItem] = []

    if not query or ":" not in query:
        # Show available params as hints
        if not params:
            items.append(
                AlfredItem(
                    title="No parameters available",
                    subtitle=f"{action} for {domain} has no configurable parameters",
                    valid=False,
                )
            )
        else:
            items.append(
                AlfredItem(
                    title=f"Set parameters for {action_label}",
                    subtitle="Type key:value pairs (e.g. brightness:50%,transition:2)",
                    icon=AlfredIcon(path=dc.icon_path),
                    valid=False,
                )
            )
            for p in params:
                req = " (required)" if p.required else ""
                items.append(
                    AlfredItem(
                        title=f"{p.label}{req}",
                        subtitle=(
                            f"{p.name}:<value> \u00b7 {p.hint}"
                            if p.hint
                            else f"{p.name}:<value>"
                        ),
                        icon=AlfredIcon(path=dc.icon_path),
                        valid=False,
                        autocomplete=f"{p.name}:",
                    )
                )
    else:
        # Parse and validate params; show confirmation item
        try:
            parsed = parse_service_params(query, domain, action)
        except ValueError as exc:
            items.append(
                AlfredItem(
                    title="Invalid parameters",
                    subtitle=str(exc),
                    icon=AlfredIcon(path=dc.icon_path),
                    valid=False,
                )
            )
            output = AlfredOutput(items=items)
            sys.stdout.write(output.to_json() + "\n")
            return

        if not parsed:
            items.append(
                AlfredItem(
                    title="No parameters parsed",
                    subtitle="Type key:value pairs separated by commas",
                    icon=AlfredIcon(path=dc.icon_path),
                    valid=False,
                )
            )
        else:
            summary = _format_param_summary(parsed)
            items.append(
                AlfredItem(
                    title=f"\u21b5 {action_label} {friendly}",
                    subtitle=summary,
                    icon=AlfredIcon(path=dc.icon_path),
                    arg=entity_id,
                    variables={
                        "entity_id": entity_id,
                        "action": action,
                        "domain": domain,
                        # Pass the raw param string; action_runner.py will parse it.
                        "params": query,
                        "param_mode": "",
                    },
                    valid=True,
                )
            )
            # Show parsed params as non-actionable detail items
            for k, v in parsed.items():
                items.append(
                    AlfredItem(
                        title=f"{k}: {v}",
                        subtitle=f"Parameter for {action_label}",
                        icon=AlfredIcon(path=dc.icon_path),
                        valid=False,
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
