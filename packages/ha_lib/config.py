"""Configuration module — reads Alfred environment variables."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional
from urllib.parse import urlsplit

from ha_lib.errors import ConfigError, HAWorkflowError

if TYPE_CHECKING:
    from ha_lib.keychain import TokenStore

_DEFAULT_CACHE_TTL = 60
_DEFAULT_PREFERRED_LABEL = "alfred_preferred"

_DEFAULT_PORTS = {"http": 80, "https": 443}
_SERVER_KEY_LEN = 12
# A server key names a directory under ``servers/``: no separators, no
# leading dot/dash, bounded length.
_SAFE_SERVER_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def normalize_server_url(url: str) -> str:
    """Return a canonical form of an HA base URL, used to identify the server.

    Lowercases the scheme and host, drops user-info, default ports (80/443),
    query, fragment and any trailing slash.  The path is kept (HA may sit
    behind a reverse proxy sub-path) with its original case.
    """
    raw = url.strip()
    if "://" not in raw:
        raw = "http://" + raw
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if ":" in host:  # IPv6 literal — urlsplit strips the brackets
        host = f"[{host}]"
    try:
        port: Optional[int] = parts.port
    except ValueError:
        port = None
    netloc = host
    if port is not None and port != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{port}"
    path = parts.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


def server_key_for_url(url: str) -> str:
    """Derive the stable per-server storage key for an HA base URL.

    Equivalent URLs (see :func:`normalize_server_url`) map to the same key.
    """
    digest = hashlib.sha256(normalize_server_url(url).encode("utf-8")).hexdigest()
    return digest[:_SERVER_KEY_LEN]


def workflow_dirs(env: Mapping[str, str]) -> tuple[Path, Path]:
    """``(cache_dir, data_dir)`` from Alfred's env, with a dev fallback."""
    dev_fallback = Path.home() / ".cache" / "ha-workflow"
    cache_dir = Path(
        env.get("alfred_workflow_cache", "").strip() or str(dev_fallback / "cache")
    )
    data_dir = Path(
        env.get("alfred_workflow_data", "").strip() or str(dev_fallback / "data")
    )
    return cache_dir, data_dir


@dataclass(frozen=True)
class Config:
    """Workflow configuration for the active Home Assistant server.

    Alfred 5 injects ``HA_URL`` and ``HA_TOKEN`` as Workflow Environment
    Variables; they back the *default* server.  Additional servers come from
    server profiles (``profiles.json`` + Keychain) — see :meth:`from_env` for
    how the active one is chosen.
    """

    ha_url: str
    # Eager token (default server).  Keychain servers leave it empty and
    # resolve through ``token_loader`` on first use — see :meth:`get_token`.
    ha_token: str = field(repr=False)
    cache_ttl: int
    cache_dir: Path
    data_dir: Path
    preferred_label: str = _DEFAULT_PREFERRED_LABEL
    # Profile seam: when set, used instead of the URL-derived key.
    server_key_override: Optional[str] = None
    server_id: str = "default"
    server_name: str = ""
    server_badge: Optional[str] = None
    # How many servers are configured; >1 turns on the wrong-house signals.
    server_count: int = 1
    token_loader: Optional[Callable[[], str]] = field(
        default=None, repr=False, compare=False
    )

    def get_token(self) -> str:
        """The access token for this server.

        Keychain-backed servers read it here — never while building the
        config — so a Script Filter keystroke served from cache never runs
        ``security``.
        """
        if self.ha_token:
            return self.ha_token
        if self.token_loader is not None:
            return self.token_loader()
        raise ConfigError(f"No access token configured for {self.server_display_name}.")

    @property
    def server_display_name(self) -> str:
        """The server's name, falling back to its host."""
        return self.server_name or self.server_label

    @property
    def server_prefix(self) -> str:
        """Short label for subtitles and notifications: badge, else name."""
        return self.server_badge or self.server_display_name

    @property
    def is_multi_server(self) -> bool:
        """True when more than one server is configured (wrong-house signals on)."""
        return self.server_count > 1

    @property
    def server_key(self) -> str:
        """Identifier for the HA server this config points at.

        This is the single seam for per-server storage: everything
        server-specific lives under ``servers/<server_key>/``.  Derived from
        ``ha_url`` unless ``server_key_override`` is set (e.g. by a future
        server-profiles feature).
        """
        if self.server_key_override:
            if not _SAFE_SERVER_KEY.match(self.server_key_override):
                raise ConfigError(
                    f"Invalid server key {self.server_key_override!r}: use letters, "
                    "digits, '-' or '_' (max 64)."
                )
            return self.server_key_override
        return server_key_for_url(self.ha_url)

    @property
    def server_label(self) -> str:
        """Short human-readable server name for UI text (host[:port][/path])."""
        return normalize_server_url(self.ha_url).split("://", 1)[-1]

    @property
    def server_cache_dir(self) -> Path:
        """Per-server cache directory: ``<cache_dir>/servers/<server_key>``."""
        return self.cache_dir / "servers" / self.server_key

    @property
    def server_data_dir(self) -> Path:
        """Per-server data directory: ``<data_dir>/servers/<server_key>``."""
        return self.data_dir / "servers" / self.server_key

    @classmethod
    def from_env(
        cls,
        env: Optional[Mapping[str, str]] = None,
        token_store: Optional[TokenStore] = None,
    ) -> Config:
        """Build a :class:`Config` for the active server.

        The server is chosen by ``HA_SERVER`` (env), else the
        ``<alfred_workflow_data>/active_server`` pointer, else ``default``
        (``HA_URL`` / ``HA_TOKEN``).  A selection that cannot be resolved
        raises :class:`ConfigError` — there is never a silent fallback to a
        different server.

        Parameters
        ----------
        env:
            Mapping to read instead of ``os.environ`` (useful for testing).
        token_store:
            Where Keychain-backed tokens are read from on first use
            (defaults to the macOS Keychain).
        """
        from ha_lib.profiles import (
            DEFAULT_PROFILE_ID,
            load_servers,
            resolve_server_id,
        )

        if env is None:
            env = dict(os.environ)

        cache_ttl_raw = env.get("CACHE_TTL", "").strip()
        if cache_ttl_raw:
            try:
                cache_ttl = int(cache_ttl_raw)
                if cache_ttl < 0:
                    raise ValueError
            except ValueError as exc:
                raise ConfigError(
                    f"CACHE_TTL must be a non-negative integer, got {cache_ttl_raw!r}"
                ) from exc
        else:
            cache_ttl = _DEFAULT_CACHE_TTL

        cache_dir, data_dir = workflow_dirs(env)

        preferred_label = (
            env.get("HA_PREFERRED_LABEL", "").strip().lower()
            or _DEFAULT_PREFERRED_LABEL
        )

        server_id = resolve_server_id(env, data_dir)
        servers = load_servers(env, data_dir)
        # A broken profiles.json may be hiding other servers: count it so the
        # wrong-house signals stay on.
        server_count = len(servers.profiles) + (1 if servers.file_error else 0)

        if server_id == DEFAULT_PROFILE_ID:
            ha_url = env.get("HA_URL", "").strip().rstrip("/")
            if not ha_url:
                raise ConfigError(
                    "HA_URL is not set. Configure it in the Alfred workflow variables."
                )
            ha_token = env.get("HA_TOKEN", "").strip()
            if not ha_token:
                raise ConfigError(
                    "HA_TOKEN is not set. "
                    "Configure it in the Alfred workflow variables."
                )
            default = servers.get(DEFAULT_PROFILE_ID)
            return cls(
                ha_url=ha_url,
                ha_token=ha_token,
                cache_ttl=cache_ttl,
                cache_dir=cache_dir,
                data_dir=data_dir,
                preferred_label=preferred_label,
                server_id=DEFAULT_PROFILE_ID,
                server_name=default.name if default else "",
                server_badge=default.badge if default else None,
                server_count=max(server_count, 1),
            )

        if servers.file_error:
            raise ConfigError(
                f"Servers file is invalid: {servers.file_error}. "
                "Use 'ha server:' to fix it or choose another server."
            )
        profile = servers.get(server_id)
        if profile is None:
            raise ConfigError(
                f"Active server {server_id!r} is not configured. "
                "Use 'ha server:' to choose one."
            )

        return cls(
            ha_url=profile.url,
            ha_token="",
            cache_ttl=cache_ttl,
            cache_dir=cache_dir,
            data_dir=data_dir,
            preferred_label=profile.preferred_label or preferred_label,
            # Routed through the validated server-key seam.
            server_key_override=profile.storage_key,
            server_id=profile.id,
            server_name=profile.name,
            server_badge=profile.badge,
            server_count=server_count,
            token_loader=_keychain_token_loader(profile.id, profile.name, token_store),
        )


def _keychain_token_loader(
    profile_id: str, name: str, token_store: Optional[TokenStore]
) -> Callable[[], str]:
    """Memoizing loader that reads *profile_id*'s token on first call."""
    cached: list[str] = []

    def load() -> str:
        if cached:
            return cached[0]
        store = token_store
        if store is None:
            from ha_lib.keychain import SecurityCliTokenStore

            store = SecurityCliTokenStore()
        try:
            token = store.get(profile_id)
        except HAWorkflowError as exc:
            raise ConfigError(
                f"Could not read the token for {name!r} from the Keychain: {exc}"
            ) from exc
        if not token:
            raise ConfigError(
                f"No token for {name!r} in the Keychain. Use 'ha server:' and "
                "re-enter the token (⌘ on the server, then Re-enter token)."
            )
        cached.append(token)
        return token

    return load
