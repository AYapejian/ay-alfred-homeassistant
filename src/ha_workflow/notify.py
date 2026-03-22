"""macOS notification helpers for the Alfred workflow.

Two mechanisms:

1. **Alfred Post Notification** — stdout text flows through the Alfred
   workflow graph to the notification output node.  Fast but unreliable
   (depends on correct wiring and Alfred processing the output).

2. **macOS native notification** — ``osascript -e 'display notification'``.
   Always visible as a system toast/banner.  Works from background
   processes too.

Foreground action handlers should call :func:`notify` which does both:
writes to stdout (for Alfred) AND posts a macOS notification (belt and
suspenders).  Background processes should call :func:`notify_background`
which only posts the macOS notification (no Alfred context).
"""

from __future__ import annotations

import contextlib
import subprocess
import sys

_TITLE = "Home Assistant"


def _escape_applescript(s: str) -> str:
    """Escape a string for AppleScript double-quoted context."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _macos_notification(
    message: str,
    title: str = _TITLE,
    subtitle: str = "",
    sound: str = "",
) -> None:
    """Post a macOS notification via osascript (fire-and-forget)."""
    safe_msg = _escape_applescript(message)
    safe_title = _escape_applescript(title)
    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    if subtitle:
        safe_sub = _escape_applescript(subtitle)
        script += f' subtitle "{safe_sub}"'
    if sound:
        safe_sound = _escape_applescript(sound)
        script += f' sound name "{safe_sound}"'
    with contextlib.suppress(OSError):
        subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )


def notify(message: str, subtitle: str = "") -> None:
    """Notify the user of a foreground action result.

    Writes *message* to stdout (for Alfred's notification pipeline) AND
    posts a macOS native notification (guaranteed visibility).
    """
    sys.stdout.write(message + "\n")
    _macos_notification(message, subtitle=subtitle)


def notify_error(message: str, subtitle: str = "") -> None:
    """Notify the user of an error (foreground or background).

    Same as :func:`notify` but adds the system alert sound so errors
    are audibly distinct from success notifications.
    """
    sys.stdout.write(message + "\n")
    _macos_notification(message, subtitle=subtitle, sound="Funk")


def notify_background(message: str, subtitle: str = "") -> None:
    """Notify from a background process (no stdout, macOS toast only)."""
    _macos_notification(message, subtitle=subtitle)


def notify_background_error(message: str, subtitle: str = "") -> None:
    """Notify a background error (macOS toast with alert sound)."""
    _macos_notification(message, subtitle=subtitle, sound="Funk")
