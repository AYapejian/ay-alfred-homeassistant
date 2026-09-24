"""Token storage for server profiles — the macOS login Keychain.

Tokens of additional server profiles are stored as generic passwords:
service ``com.ayapejian.alfred-homeassistant`` (the workflow bundle id),
account = profile id.  The default profile's token stays in Alfred's
workflow configuration and never passes through here.

**A token never appears in a process argument list.**  ``ps`` shows argv to
every user on the machine, so:

* writes send ``add-generic-password … -w <token>`` to ``security -i`` on
  **stdin** (argv is just ``security -i``);
* reads use ``find-generic-password -w``, which prints the token to stdout.
"""

from __future__ import annotations

import re
import subprocess
from typing import Optional, Protocol

from ha_lib.errors import HAWorkflowError

KEYCHAIN_SERVICE = "com.ayapejian.alfred-homeassistant"
# Module-level so tests can point it somewhere harmless.
SECURITY_BIN = "/usr/bin/security"

_ACCOUNT_RE = re.compile(r"^p-[0-9a-f]{8}$")
# HA long-lived tokens are JWTs (base64url + dots).  A strict allowlist also
# means the token needs no quoting on the `security -i` command line.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._~+/=-]+$")
_MAX_TOKEN_LEN = 4096
_ITEM_NOT_FOUND = 44  # errSecItemNotFound, as returned by `security`
_TIMEOUT = 15


class TokenStoreError(HAWorkflowError):
    """The token store failed (never carries the token itself)."""


class TokenStore(Protocol):
    """Where server-profile tokens live."""

    def get(self, profile_id: str) -> Optional[str]:
        """Return the token, or ``None`` when no item exists."""
        ...

    def set(self, profile_id: str, token: str) -> None:
        """Create or replace the token."""
        ...

    def delete(self, profile_id: str) -> None:
        """Remove the token; a missing item is not an error."""
        ...


def validate_token(token: str) -> str:
    """Return *token* stripped, or raise :class:`TokenStoreError`."""
    cleaned = token.strip()
    if not cleaned:
        raise TokenStoreError("The token is empty.")
    if len(cleaned) > _MAX_TOKEN_LEN:
        raise TokenStoreError("The token is too long.")
    if not _TOKEN_RE.match(cleaned):
        raise TokenStoreError(
            "The token contains unexpected characters. Paste the long-lived "
            "access token exactly as Home Assistant shows it."
        )
    return cleaned


def _check_account(profile_id: str) -> None:
    if not _ACCOUNT_RE.match(profile_id):
        raise TokenStoreError(f"Invalid profile id for the Keychain: {profile_id!r}")


class SecurityCliTokenStore:
    """:class:`TokenStore` backed by ``/usr/bin/security``."""

    def _run(
        self, args: list[str], stdin: Optional[str] = None
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [SECURITY_BIN, *args],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise TokenStoreError(
                f"Could not run the Keychain tool: {type(exc).__name__}"
            ) from None

    def get(self, profile_id: str) -> Optional[str]:
        _check_account(profile_id)
        proc = self._run(
            ["find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", profile_id, "-w"]
        )
        if proc.returncode == _ITEM_NOT_FOUND:
            return None
        if proc.returncode != 0:
            # stdout may hold secret material; report only the exit code.
            raise TokenStoreError(
                f"Keychain lookup failed (security exit {proc.returncode})."
            )
        token = proc.stdout.strip()
        return token or None

    def set(self, profile_id: str, token: str) -> None:
        _check_account(profile_id)
        cleaned = validate_token(token)
        command = (
            f"add-generic-password -U -s {KEYCHAIN_SERVICE} "
            f"-a {profile_id} -w {cleaned}\n"
        )
        proc = self._run(["-i"], stdin=command)
        if proc.returncode != 0:
            raise TokenStoreError(
                f"Keychain write failed (security exit {proc.returncode})."
            )
        # `security -i` can exit 0 when a command inside it failed: read back.
        if self.get(profile_id) != cleaned:
            raise TokenStoreError("Could not verify the token in the Keychain.")

    def delete(self, profile_id: str) -> None:
        _check_account(profile_id)
        proc = self._run(
            ["delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", profile_id]
        )
        if proc.returncode not in (0, _ITEM_NOT_FOUND):
            raise TokenStoreError(
                f"Keychain delete failed (security exit {proc.returncode})."
            )


class InMemoryTokenStore:
    """:class:`TokenStore` held in a dict — for tests and development."""

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}
        self.reads = 0

    def get(self, profile_id: str) -> Optional[str]:
        self.reads += 1
        return self._tokens.get(profile_id)

    def set(self, profile_id: str, token: str) -> None:
        _check_account(profile_id)
        self._tokens[profile_id] = validate_token(token)

    def delete(self, profile_id: str) -> None:
        self._tokens.pop(profile_id, None)
