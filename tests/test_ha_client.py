"""Tests for ha_workflow.ha_client — mocked urllib tests."""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ha_workflow.config import Config
from ha_workflow.errors import HAAuthError, HAConnectionError
from ha_workflow.ha_client import HAClient


def _config() -> Config:
    return Config.from_env({"HA_URL": "http://ha.local:8123", "HA_TOKEN": "tok"})


def _mock_response(
    body: Any,
    status: int = 200,
    content_type: str = "application/json",
) -> MagicMock:
    """Create a mock that behaves like an urlopen response context manager."""
    if isinstance(body, str):
        raw = body.encode("utf-8")
    else:
        raw = json.dumps(body).encode("utf-8")

    resp = MagicMock()
    resp.read.return_value = raw
    resp.headers = {"Content-Type": content_type}
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestGetConfig:
    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_success(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response(
            {"version": "2024.1.0", "location_name": "Home"}
        )
        client = HAClient(_config())
        result = client.get_config()
        assert result["version"] == "2024.1.0"

        # Verify auth header
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer tok"

    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_url_construction(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"version": "1"})
        HAClient(_config()).get_config()
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://ha.local:8123/api/config"


class TestGetStates:
    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_returns_list(self, mock_urlopen: MagicMock) -> None:
        states = [{"entity_id": "light.living_room", "state": "on"}]
        mock_urlopen.return_value = _mock_response(states)
        assert HAClient(_config()).get_states() == states


class TestGetState:
    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_single_entity(self, mock_urlopen: MagicMock) -> None:
        entity = {"entity_id": "light.living_room", "state": "on"}
        mock_urlopen.return_value = _mock_response(entity)
        result = HAClient(_config()).get_state("light.living_room")
        assert result["state"] == "on"
        req = mock_urlopen.call_args[0][0]
        assert "/api/states/light.living_room" in req.full_url


class TestCallService:
    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_post_with_data(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response([])
        HAClient(_config()).call_service(
            "light", "turn_on", {"entity_id": "light.living_room"}
        )
        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "POST"
        assert "/api/services/light/turn_on" in req.full_url
        assert req.data is not None


class TestGetErrorLog:
    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_returns_text(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response(
            "2024-01-01 ERROR something", content_type="text/plain"
        )
        result = HAClient(_config()).get_error_log()
        assert "ERROR" in result


class TestCheckConfig:
    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_success(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"result": "valid", "errors": None})
        result = HAClient(_config()).check_config()
        assert result["result"] == "valid"


class TestErrorHandling:
    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_401_raises_auth_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://ha.local:8123/api/config", 401, "Unauthorized", {}, io.BytesIO(b"")
        )
        with pytest.raises(HAAuthError, match="401"):
            HAClient(_config()).get_config()

    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_403_raises_auth_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://ha.local:8123/api/config", 403, "Forbidden", {}, io.BytesIO(b"")
        )
        with pytest.raises(HAAuthError):
            HAClient(_config()).get_config()

    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_500_raises_connection_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://ha.local:8123/api/config",
            500,
            "Internal Server Error",
            {},
            io.BytesIO(b""),
        )
        with pytest.raises(HAConnectionError, match="500"):
            HAClient(_config()).get_config()

    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_url_error_raises_connection_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("Name or service not known")
        with pytest.raises(HAConnectionError):
            HAClient(_config()).get_config()

    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_timeout_raises_connection_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = TimeoutError("timed out")
        with pytest.raises(HAConnectionError):
            HAClient(_config()).get_config()
