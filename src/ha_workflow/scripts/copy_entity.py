"""Copy entity ID to clipboard via pbcopy.

Invoked by Alfred as a Run Script node (⌥ Enter from search results)::

    python3 scripts/copy_entity.py

Reads ``entity_id`` from Alfred environment variable, pipes to ``pbcopy``,
prints a short notification message to stdout.
"""

from __future__ import annotations

import os
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

from ha_lib.errors import handle_error  # noqa: E402
from ha_lib.notify import notify, notify_error  # noqa: E402


def main() -> None:
    entity_id = os.environ.get("entity_id", "").strip()
    if not entity_id:
        notify_error("No entity_id in environment")
        return

    try:
        subprocess.run(["pbcopy"], input=entity_id.encode("utf-8"), check=True)
    except Exception as exc:
        notify_error(f"Failed to copy to clipboard: {exc}")
        return

    notify(f"Copied: {entity_id}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        handle_error(exc)
