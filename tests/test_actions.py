"""Tests for ha_workflow.actions."""

from __future__ import annotations

from unittest.mock import MagicMock

from ha_workflow.actions import ActionResult, dispatch_action
from ha_workflow.errors import HAAuthError, HAConnectionError


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.call_service.return_value = []
    return client


class TestDispatchAction:
    def test_toggle_light(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "light.living_room", "toggle")
        assert result.success is True
        assert "Toggled" in result.message
        assert "Living Room" in result.message
        client.call_service.assert_called_once_with(
            "light", "toggle", {"entity_id": "light.living_room"}
        )

    def test_turn_on(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "switch.fan", "turn_on")
        assert result.success is True
        assert "Turned on" in result.message
        client.call_service.assert_called_once_with(
            "switch", "turn_on", {"entity_id": "switch.fan"}
        )

    def test_turn_off(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "light.bedroom", "turn_off")
        assert result.success is True
        assert "Turned off" in result.message

    def test_lock(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "lock.front_door", "lock")
        assert result.success is True
        assert "Locked" in result.message
        client.call_service.assert_called_once_with(
            "lock", "lock", {"entity_id": "lock.front_door"}
        )

    def test_unlock(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "lock.front_door", "unlock")
        assert result.success is True
        assert "Unlocked" in result.message

    def test_cover_actions(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "cover.garage", "open_cover")
        assert result.success is True
        assert "Opened" in result.message
        client.call_service.assert_called_once_with(
            "cover", "open_cover", {"entity_id": "cover.garage"}
        )

    def test_button_press(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "button.doorbell", "press")
        assert result.success is True
        assert "Pressed" in result.message

    def test_automation_trigger(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "automation.night_mode", "trigger")
        assert result.success is True
        assert "Triggered" in result.message

    def test_scene_turn_on(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "scene.movie_time", "turn_on")
        assert result.success is True

    def test_vacuum_start(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "vacuum.roborock", "start")
        assert result.success is True
        assert "Started" in result.message

    def test_media_player_play(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "media_player.tv", "media_play")
        assert result.success is True
        client.call_service.assert_called_once_with(
            "media_player", "media_play", {"entity_id": "media_player.tv"}
        )

    def test_with_service_data(self) -> None:
        client = _mock_client()
        result = dispatch_action(
            client,
            "climate.hvac",
            "set_temperature",
            service_data={"temperature": 22},
        )
        assert result.success is True
        client.call_service.assert_called_once_with(
            "climate",
            "set_temperature",
            {"entity_id": "climate.hvac", "temperature": 22},
        )


class TestDispatchActionErrors:
    def test_invalid_entity_id(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "bad_id", "toggle")
        assert result.success is False
        assert "Invalid entity ID" in result.message
        client.call_service.assert_not_called()

    def test_display_only_domain(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "sensor.temperature", "toggle")
        assert result.success is False
        assert "No actions available" in result.message
        client.call_service.assert_not_called()

    def test_unknown_action(self) -> None:
        client = _mock_client()
        result = dispatch_action(client, "light.living_room", "explode")
        assert result.success is False
        assert "Unknown action" in result.message
        assert "toggle" in result.message  # shows available actions
        client.call_service.assert_not_called()

    def test_connection_error(self) -> None:
        client = _mock_client()
        client.call_service.side_effect = HAConnectionError("timeout")
        result = dispatch_action(client, "light.living_room", "toggle")
        assert result.success is False
        assert "Connection error" in result.message

    def test_auth_error(self) -> None:
        client = _mock_client()
        client.call_service.side_effect = HAAuthError("401")
        result = dispatch_action(client, "light.living_room", "toggle")
        assert result.success is False
        assert "Auth error" in result.message


class TestActionResult:
    def test_dataclass_fields(self) -> None:
        r = ActionResult(success=True, message="ok")
        assert r.success is True
        assert r.message == "ok"
