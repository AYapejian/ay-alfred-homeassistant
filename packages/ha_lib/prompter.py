"""Native dialogs for server management, behind a :class:`Prompter` protocol.

Alfred's Run Script has no terminal, so secrets are entered through
AppleScript ``display dialog … with hidden answer``.  Dialog text is passed
to ``osascript`` as run-handler **arguments**, never spliced into the script,
so a server name cannot inject AppleScript.  The answer comes back on stdout;
nothing typed by the user ever appears in a process argument list.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import Optional, Protocol

from ha_lib.errors import HAWorkflowError

OSASCRIPT_BIN = "/usr/bin/osascript"
_USER_CANCELED = "-128"
_GIVE_UP_SECONDS = 300
_TIMEOUT = _GIVE_UP_SECONDS + 30

_ASK_TEXT = f"""
on run argv
  activate
  set r to display dialog (item 2 of argv) default answer (item 3 of argv) \
with title (item 1 of argv) buttons {{"Cancel", "OK"}} default button "OK" \
cancel button "Cancel" giving up after {_GIVE_UP_SECONDS}
  if gave up of r then error number -128
  return text returned of r
end run
"""

_ASK_HIDDEN = _ASK_TEXT.replace("giving up after", "with hidden answer giving up after")

_CHOOSE = f"""
on run argv
  activate
  set r to display dialog (item 2 of argv) with title (item 1 of argv) \
buttons (items 5 thru -1 of argv) default button (item 3 of argv) \
cancel button (item 4 of argv) with icon caution giving up after {_GIVE_UP_SECONDS}
  if gave up of r then error number -128
  return button returned of r
end run
"""


class PromptError(HAWorkflowError):
    """A dialog could not be shown."""


class Prompter(Protocol):
    """Asks the user things.  ``None`` / ``False`` mean *cancelled*."""

    def ask_text(
        self, title: str, message: str, default: str = "", hidden: bool = False
    ) -> Optional[str]:
        """Text entry; ``hidden`` shows bullets (for tokens)."""
        ...

    def confirm(self, title: str, message: str, ok_label: str) -> bool:
        """OK / Cancel with **Cancel as the default button**."""
        ...

    def choose(
        self, title: str, message: str, buttons: Sequence[str], default: str
    ) -> Optional[str]:
        """Pick one of *buttons*; ``"Cancel"`` (or closing) returns ``None``."""
        ...


class OsascriptPrompter:
    """:class:`Prompter` using ``osascript`` ``display dialog``."""

    def _run(self, script: str, args: Sequence[str]) -> Optional[str]:
        try:
            proc = subprocess.run(
                [OSASCRIPT_BIN, "-e", script, *args],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PromptError(
                f"Could not show a dialog: {type(exc).__name__}"
            ) from None
        if proc.returncode != 0:
            if _USER_CANCELED in proc.stderr:
                return None
            raise PromptError(f"Dialog failed (osascript exit {proc.returncode}).")
        # osascript appends one newline to the result.
        out = proc.stdout
        return out[:-1] if out.endswith("\n") else out

    def ask_text(
        self, title: str, message: str, default: str = "", hidden: bool = False
    ) -> Optional[str]:
        script = _ASK_HIDDEN if hidden else _ASK_TEXT
        return self._run(script, [title, message, default])

    def confirm(self, title: str, message: str, ok_label: str) -> bool:
        choice = self._run(
            _CHOOSE, [title, message, "Cancel", "Cancel", "Cancel", ok_label]
        )
        return choice == ok_label

    def choose(
        self, title: str, message: str, buttons: Sequence[str], default: str
    ) -> Optional[str]:
        labels = [b for b in buttons if b != "Cancel"]
        choice = self._run(
            _CHOOSE, [title, message, default, "Cancel", "Cancel", *labels]
        )
        return None if choice in (None, "Cancel") else choice
