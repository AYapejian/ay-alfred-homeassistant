"""Exception hierarchy and top-level error handler."""

from __future__ import annotations

import json
import sys

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class HAWorkflowError(Exception):
    """Base exception for the HA Alfred workflow."""


class ConfigError(HAWorkflowError):
    """Missing or invalid configuration."""


class HAConnectionError(HAWorkflowError):
    """Network / connection failure talking to Home Assistant."""


class HAAuthError(HAWorkflowError):
    """HTTP 401 / 403 from Home Assistant."""


# ---------------------------------------------------------------------------
# Alfred-friendly error output
# ---------------------------------------------------------------------------

def _error_item(title: str, subtitle: str = "") -> dict[str, object]:
    return {
        "items": [
            {
                "title": title,
                "subtitle": subtitle,
                "icon": {"path": "icons/error.png"},
                "valid": False,
            }
        ]
    }


def handle_error(exc: BaseException) -> None:
    """Write an Alfred Script Filter JSON error to *stdout* and exit 0.

    Alfred only displays output when the process exits 0, so we must not
    use a non-zero exit code here.
    """
    if isinstance(exc, ConfigError):
        payload = _error_item("Configuration Error", str(exc))
    elif isinstance(exc, HAAuthError):
        payload = _error_item(
            "Authentication Failed",
            "Check your HA_TOKEN in workflow variables.",
        )
    elif isinstance(exc, HAConnectionError):
        payload = _error_item("Connection Error", str(exc))
    elif isinstance(exc, HAWorkflowError):
        payload = _error_item("Workflow Error", str(exc))
    else:
        payload = _error_item("Unexpected Error", str(exc))

    sys.stdout.write(json.dumps(payload))
    sys.stdout.write("\n")
    sys.stdout.flush()
