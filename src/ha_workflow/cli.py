"""CLI entry point for the Alfred workflow.

Invoked as::

    /usr/bin/python3 ha_workflow/cli.py <command> [args...]
"""

from __future__ import annotations

import os
import sys

# When Alfred runs ``python3 ha_workflow/cli.py …``, Python sets sys.path[0]
# to the ha_workflow/ directory (the script's parent).  Package-level imports
# like ``from ha_workflow.alfred import …`` need the *workflow root* (the
# directory that *contains* ha_workflow/) on sys.path instead.
_WORKFLOW_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKFLOW_ROOT not in sys.path:
    sys.path.insert(0, _WORKFLOW_ROOT)

from ha_workflow.alfred import AlfredIcon, AlfredItem, AlfredOutput  # noqa: E402
from ha_workflow.config import Config  # noqa: E402
from ha_workflow.errors import handle_error  # noqa: E402
from ha_workflow.ha_client import HAClient  # noqa: E402


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
        _cmd_stub("search")
    elif command == "action":
        _cmd_stub("action")
    elif command == "actions":
        _cmd_stub("actions")
    elif command == "cache":
        _cmd_stub("cache")
    else:
        _cmd_stub(command)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        handle_error(exc)
