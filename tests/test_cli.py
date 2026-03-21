"""Tests for ha_workflow.cli."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from ha_workflow.cli import main


class TestCommandDispatch:
    def test_no_args_shows_stub(self, capsys: object) -> None:
        main([])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["items"][0]["valid"] is False

    def test_search_stub(self, capsys: object) -> None:
        main(["search", "lights"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]

    def test_action_stub(self, capsys: object) -> None:
        main(["action", "light.living_room", "toggle"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]

    def test_actions_stub(self, capsys: object) -> None:
        main(["actions", "light.living_room"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]

    def test_cache_stub(self, capsys: object) -> None:
        main(["cache", "refresh"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]

    def test_unknown_command_stub(self, capsys: object) -> None:
        main(["bogus"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]


class TestConfigValidate:
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_success(
        self,
        mock_from_env: MagicMock,
        mock_client_cls: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_config.return_value = {
            "version": "2024.6.0",
            "location_name": "Home",
        }
        mock_client_cls.return_value = mock_client

        main(["config", "validate"])

        out = capsys.readouterr().out
        data = json.loads(out)
        item = data["items"][0]
        assert item["title"] == "Connected to Home Assistant"
        assert "2024.6.0" in item["subtitle"]
        assert "Home" in item["subtitle"]

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_no_location(
        self,
        mock_from_env: MagicMock,
        mock_client_cls: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_config.return_value = {
            "version": "2024.6.0",
        }
        mock_client_cls.return_value = mock_client

        main(["config", "validate"])

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["items"][0]["subtitle"] == "v2024.6.0"
