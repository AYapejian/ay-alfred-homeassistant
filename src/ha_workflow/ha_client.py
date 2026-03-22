"""Home Assistant REST API client (stdlib only)."""

from __future__ import annotations

import datetime
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional, Union

from ha_workflow.config import Config
from ha_workflow.errors import HAAuthError, HAConnectionError

_DEFAULT_TIMEOUT = 10


class HAClient:
    """Thin wrapper around the HA REST API using ``urllib.request``."""

    def __init__(self, config: Config, timeout: int = _DEFAULT_TIMEOUT) -> None:
        self._base_url = config.ha_url
        self._token = config.ha_token
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict[str, Any]] = None,
    ) -> Union[dict[str, Any], list[Any], str]:
        """Issue an HTTP request and return the parsed response."""
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        body: Optional[bytes] = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw: str = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise HAAuthError(f"Authentication failed (HTTP {exc.code})") from exc
            raise HAConnectionError(f"HTTP {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise HAConnectionError(str(exc)) from exc

        # Some endpoints (e.g. error_log) return plain text.
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return json.loads(raw)  # type: ignore[no-any-return]
        return raw

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_states(self) -> list[dict[str, Any]]:
        """``GET /api/states`` — all entity states."""
        result = self._request("GET", "/api/states")
        assert isinstance(result, list)
        return result

    def get_state(self, entity_id: str) -> dict[str, Any]:
        """``GET /api/states/{entity_id}`` — single entity state."""
        result = self._request("GET", f"/api/states/{entity_id}")
        assert isinstance(result, dict)
        return result

    def call_service(
        self,
        domain: str,
        service: str,
        data: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """``POST /api/services/{domain}/{service}``."""
        result = self._request("POST", f"/api/services/{domain}/{service}", data=data)
        assert isinstance(result, list)
        return result

    def get_config(self) -> dict[str, Any]:
        """``GET /api/config`` — HA instance configuration."""
        result = self._request("GET", "/api/config")
        assert isinstance(result, dict)
        return result

    def get_error_log(self) -> str:
        """``GET /api/error_log`` — plain-text error log."""
        result = self._request("GET", "/api/error_log")
        assert isinstance(result, str)
        return result

    def get_entity_registry(self) -> list[dict[str, Any]]:
        """``GET /api/config/entity_registry`` — entity registry entries.

        Returns a list of dicts with ``entity_id``, ``area_id``, etc.
        Requires HA 2022.6+.  Returns an empty list on failure so callers
        can degrade gracefully.
        """
        try:
            result = self._request("GET", "/api/config/entity_registry")
            if isinstance(result, list):
                return result
        except (HAConnectionError, HAAuthError):
            pass
        return []

    def get_device_registry(self) -> list[dict[str, Any]]:
        """``GET /api/config/device_registry`` — device registry entries.

        Returns a list of dicts with ``id``, ``area_id``, etc.
        Requires HA 2022.6+.  Returns an empty list on failure so callers
        can degrade gracefully.
        """
        try:
            result = self._request("GET", "/api/config/device_registry")
            if isinstance(result, list):
                return result
        except (HAConnectionError, HAAuthError):
            pass
        return []

    def get_area_registry(self) -> list[dict[str, Any]]:
        """``GET /api/config/area_registry`` — area registry entries.

        Returns a list of dicts with ``area_id``, ``name``, etc.
        Requires HA 2022.6+.  Returns an empty list on failure so callers
        can degrade gracefully.
        """
        try:
            result = self._request("GET", "/api/config/area_registry")
            if isinstance(result, list):
                return result
        except (HAConnectionError, HAAuthError):
            pass
        return []

    def get_history(
        self,
        entity_id: str,
        hours: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch state history for *entity_id* over the last *hours*.

        Uses ``GET /api/history/period/<start>?filter_entity_id=<id>``.
        Returns a flat list of state-change dicts (newest last).
        Returns an empty list on failure.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        start = now - datetime.timedelta(hours=hours)
        start_str = start.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

        safe_id = urllib.parse.quote(entity_id, safe="")
        path = (
            f"/api/history/period/{start_str}"
            f"?filter_entity_id={safe_id}"
            f"&minimal_response"
        )
        try:
            result = self._request("GET", path)
            # API returns [[change1, change2, ...]] (list of lists)
            if isinstance(result, list) and result:
                inner = result[0]
                if isinstance(inner, list):
                    return inner
        except (HAConnectionError, HAAuthError):
            pass
        return []

    def check_config(self) -> dict[str, Any]:
        """``POST /api/config/core/check_config``."""
        result = self._request("POST", "/api/config/core/check_config")
        assert isinstance(result, dict)
        return result
