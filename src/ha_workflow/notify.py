"""Notification helpers for the Alfred workflow.

Two distinct channels — never both for the same event:

1. **Foreground (Alfred context)** — :func:`notify` / :func:`notify_error`
   write to stdout, which flows through the Alfred workflow graph to the
   Post Notification output node.  Used by action handlers invoked from
   Alfred's UI.

2. **Background (no Alfred context)** — :func:`notify_background` /
   :func:`notify_background_error` post a macOS native notification via
   ``osascript``.  Used by detached subprocesses (cache refresh, etc.)
   where there is no Alfred pipeline to receive stdout.
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


# ---------------------------------------------------------------------------
# Foreground — stdout for Alfred's notification pipeline
# ---------------------------------------------------------------------------


def notify(message: str, subtitle: str = "") -> None:
    """Notify the user of a foreground action result.

    Writes *message* to stdout so Alfred's Post Notification output node
    displays it.  Do NOT call from background processes.
    """
    sys.stdout.write(message + "\n")


def notify_error(message: str, subtitle: str = "") -> None:
    """Notify the user of a foreground error.

    Same stdout channel as :func:`notify`.  The ``subtitle`` parameter is
    accepted for API compatibility but currently unused (Alfred's Post
    Notification node only shows the text body).
    """
    sys.stdout.write(message + "\n")


# ---------------------------------------------------------------------------
# Background — macOS toast (no Alfred context)
# ---------------------------------------------------------------------------


def notify_background(message: str, subtitle: str = "") -> None:
    """Notify from a background process (macOS toast, no stdout)."""
    _macos_notification(message, subtitle=subtitle)


def notify_background_error(message: str, subtitle: str = "") -> None:
    """Notify a background error (macOS toast with alert sound)."""
    _macos_notification(message, subtitle=subtitle, sound="Funk")
