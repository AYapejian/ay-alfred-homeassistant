"""Configuration module — reads Alfred environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ha_workflow.errors import ConfigError

_DEFAULT_CACHE_TTL = 60
_DEFAULT_PREFERRED_LABEL = "alfred_preferred"


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
