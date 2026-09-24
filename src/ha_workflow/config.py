"""Configuration module — reads Alfred environment variables."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from ha_workflow.errors import ConfigError

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


@dataclass(frozen=True)
class Config:
    """Workflow configuration sourced from environment variables.

    Alfred 5 injects ``HA_URL`` and ``HA_TOKEN`` as Workflow Environment
    Variables.  When running outside Alfred (development), callers can set
    them in a ``.env`` or export them directly.
    """

    ha_url: str
    ha_token: str
    cache_ttl: int
    cache_dir: Path
    data_dir: Path
    preferred_label: str = _DEFAULT_PREFERRED_LABEL
    # Profile seam: when set, used instead of the URL-derived key.
    server_key_override: Optional[str] = None

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
    def from_env(cls, env: Optional[dict[str, str]] = None) -> Config:
        """Build a :class:`Config` from environment variables.

        Parameters
        ----------
        env:
            Mapping to read instead of ``os.environ`` (useful for testing).
        """
        if env is None:
            env = dict(os.environ)

        ha_url = env.get("HA_URL", "").strip().rstrip("/")
        if not ha_url:
            raise ConfigError(
                "HA_URL is not set. Configure it in the Alfred workflow variables."
            )

        ha_token = env.get("HA_TOKEN", "").strip()
        if not ha_token:
            raise ConfigError(
                "HA_TOKEN is not set. Configure it in the Alfred workflow variables."
            )

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

        # Alfred sets these; fall back to ~/.cache/ha-workflow for dev.
        dev_fallback = Path.home() / ".cache" / "ha-workflow"
        cache_dir = Path(
            env.get("alfred_workflow_cache", "").strip() or str(dev_fallback / "cache")
        )
        data_dir = Path(
            env.get("alfred_workflow_data", "").strip() or str(dev_fallback / "data")
        )

        preferred_label = (
            env.get("HA_PREFERRED_LABEL", "").strip().lower()
            or _DEFAULT_PREFERRED_LABEL
        )

        return cls(
            ha_url=ha_url,
            ha_token=ha_token,
            cache_ttl=cache_ttl,
            cache_dir=cache_dir,
            data_dir=data_dir,
            preferred_label=preferred_label,
        )
