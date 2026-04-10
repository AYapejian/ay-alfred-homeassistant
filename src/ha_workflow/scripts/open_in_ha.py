"""Open entity URL in Home Assistant browser.

Invoked by Alfred as a Run Script node (⌃ Enter from search results)::

    python3 scripts/open_in_ha.py

Reads ``entity_id`` and ``HA_URL`` from environment variables, then opens
``{HA_URL}/config/entities?filter={entity_id}`` via the ``open`` command.
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.parse

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

from ha_lib.config import Config  # noqa: E402
from ha_lib.errors import handle_error  # noqa: E402
from ha_lib.notify import notify, notify_error  # noqa: E402


def main() -> None:
    entity_id = os.environ.get("entity_id", "").strip()
    if not entity_id:
        notify_error("No entity_id in environment")
        return

    try:
        config = Config.from_env()
    except Exception as exc:
        notify_error(f"Configuration error: {exc}")
        return

    safe_id = urllib.parse.quote(entity_id, safe="")
    url = f"{config.ha_url}/config/entities?filter={safe_id}"

    try:
        subprocess.run(["open", url], check=True)
    except Exception as exc:
        notify_error(f"Failed to open in browser: {exc}")
        return

    notify("Opened in Home Assistant")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        handle_error(exc)
