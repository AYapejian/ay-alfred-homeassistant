"""Tests for ha_workflow.entities."""

from __future__ import annotations

from typing import Any

from ha_workflow.entities import (
    DOMAIN_REGISTRY,
    DomainConfig,
    Entity,
    get_domain_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_dict(**overrides: Any) -> dict[str, Any]:
    """Build a minimal HA state dict with sensible defaults."""
    base: dict[str, Any] = {
        "entity_id": "light.living_room",
        "state": "on",
        "attributes": {"friendly_name": "Living Room Light"},
        "last_changed": "2026-03-20T10:00:00+00:00",
        "last_updated": "2026-03-20T10:00:00+00:00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


class TestEntityConstruction:
    def test_fields(self) -> None:
        e = Entity(
            entity_id="light.kitchen",
            domain="light",
            state="off",
            friendly_name="Kitchen Light",
            attributes={"brightness": 128},
            last_changed="2026-03-20T10:00:00+00:00",
            last_updated="2026-03-20T10:00:00+00:00",
        )
        assert e.entity_id == "light.kitchen"
        assert e.domain == "light"
        assert e.state == "off"
        assert e.friendly_name == "Kitchen Light"
        assert e.attributes == {"brightness": 128}

    def test_frozen(self) -> None:
        e = Entity(
            entity_id="switch.a",
            domain="switch",
            state="on",
            friendly_name="A",
            attributes={},
            last_changed="",
            last_updated="",
        )
        try:
            e.state = "off"  # type: ignore[misc]
            raised = False
        except AttributeError:
            raised = True
        assert raised


class TestFromStateDict:
    def test_full_data(self) -> None:
        data = _state_dict()
        e = Entity.from_state_dict(data)
        assert e.entity_id == "light.living_room"
        assert e.domain == "light"
        assert e.state == "on"
        assert e.friendly_name == "Living Room Light"
        assert e.last_changed == "2026-03-20T10:00:00+00:00"

    def test_missing_friendly_name_falls_back_to_entity_id(self) -> None:
        data = _state_dict(attributes={})
        e = Entity.from_state_dict(data)
        assert e.friendly_name == "light.living_room"

    def test_none_attributes_treated_as_empty(self) -> None:
        data = _state_dict(attributes=None)
        e = Entity.from_state_dict(data)
        assert e.attributes == {}
        assert e.friendly_name == "light.living_room"

    def test_missing_state_defaults_to_unknown(self) -> None:
        data = _state_dict()
        del data["state"]
        e = Entity.from_state_dict(data)
        assert e.state == "unknown"

    def test_domain_extracted_from_entity_id(self) -> None:
        data = _state_dict(entity_id="sensor.temperature")
        e = Entity.from_state_dict(data)
        assert e.domain == "sensor"

    def test_complex_entity_id(self) -> None:
        data = _state_dict(entity_id="binary_sensor.front_door.motion")
        e = Entity.from_state_dict(data)
        assert e.domain == "binary_sensor"

    def test_area_name_default_empty(self) -> None:
        data = _state_dict()
        e = Entity.from_state_dict(data)
        assert e.area_name == ""

    def test_area_name_passed_through(self) -> None:
        data = _state_dict()
        e = Entity.from_state_dict(data, area_name="Kitchen")
        assert e.area_name == "Kitchen"

    def test_device_id_default_empty(self) -> None:
        data = _state_dict()
        e = Entity.from_state_dict(data)
        assert e.device_id == ""

    def test_device_id_passed_through(self) -> None:
        data = _state_dict()
        e = Entity.from_state_dict(data, device_id="abc123")
        assert e.device_id == "abc123"


class TestDeviceClass:
    def test_present(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(attributes={"device_class": "temperature"})
        )
        assert e.device_class == "temperature"

    def test_absent(self) -> None:
        e = Entity.from_state_dict(_state_dict(attributes={}))
        assert e.device_class is None

    def test_non_string_ignored(self) -> None:
        e = Entity.from_state_dict(_state_dict(attributes={"device_class": 42}))
        assert e.device_class is None


# ---------------------------------------------------------------------------
# DomainConfig & Registry
# ---------------------------------------------------------------------------


class TestDomainRegistry:
    def test_all_expected_domains_present(self) -> None:
        expected = {
            "light",
            "switch",
            "sensor",
            "binary_sensor",
            "automation",
            "script",
            "scene",
            "climate",
            "media_player",
            "cover",
            "fan",
            "lock",
            "vacuum",
            "camera",
            "weather",
            "person",
            "zone",
            "input_boolean",
            "input_number",
            "input_select",
            "input_text",
            "group",
            "timer",
            "counter",
            "input_datetime",
            "number",
            "select",
            "button",
            "humidifier",
            "water_heater",
            "siren",
            "update",
        }
        assert expected.issubset(set(DOMAIN_REGISTRY.keys()))

    def test_all_entries_are_domain_config(self) -> None:
        for domain, config in DOMAIN_REGISTRY.items():
            assert isinstance(config, DomainConfig), domain

    def test_all_entries_have_valid_fields(self) -> None:
        for domain, config in DOMAIN_REGISTRY.items():
            assert isinstance(config.default_action, str), domain
            assert isinstance(config.available_actions, tuple), domain
            assert isinstance(config.icon_path, str), domain
            assert config.icon_path, f"{domain}: icon_path must not be empty"
            assert callable(config.subtitle_formatter), domain

    def test_default_action_in_available_actions_when_nonempty(self) -> None:
        for domain, config in DOMAIN_REGISTRY.items():
            if config.default_action:
                assert config.default_action in config.available_actions, (
                    f"{domain}: default_action {config.default_action!r} "
                    f"not in available_actions"
                )


class TestGetDomainConfig:
    def test_known_domain(self) -> None:
        cfg = get_domain_config("light")
        assert cfg.default_action == "toggle"

    def test_unknown_domain_returns_fallback(self) -> None:
        cfg = get_domain_config("totally_made_up")
        assert cfg.default_action == ""
        assert cfg.available_actions == ()


# ---------------------------------------------------------------------------
# Subtitle formatters
# ---------------------------------------------------------------------------


class TestSubtitleFormatters:
    def test_default_subtitle(self) -> None:
        e = Entity.from_state_dict(_state_dict(entity_id="switch.kitchen", state="on"))
        cfg = get_domain_config("switch")
        assert cfg.subtitle_formatter(e) == "On"

    def test_default_subtitle_replaces_underscores(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(entity_id="automation.a", state="not_running")
        )
        cfg = get_domain_config("automation")
        assert cfg.subtitle_formatter(e) == "Not Running"

    def test_light_subtitle_basic(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="light.a", state="on", attributes={"friendly_name": "A"}
            )
        )
        cfg = get_domain_config("light")
        assert cfg.subtitle_formatter(e) == "On"

    def test_light_subtitle_with_brightness(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="light.a",
                state="on",
                attributes={"friendly_name": "A", "brightness": 255},
            )
        )
        cfg = get_domain_config("light")
        result = cfg.subtitle_formatter(e)
        assert "100%" in result
        assert "On" in result

    def test_light_subtitle_with_color_temp(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="light.a",
                state="on",
                attributes={"friendly_name": "A", "color_temp_kelvin": 4000},
            )
        )
        cfg = get_domain_config("light")
        result = cfg.subtitle_formatter(e)
        assert "4000K" in result

    def test_sensor_subtitle_with_unit(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="sensor.temp",
                state="23.5",
                attributes={"friendly_name": "Temp", "unit_of_measurement": "\u00b0C"},
            )
        )
        cfg = get_domain_config("sensor")
        assert cfg.subtitle_formatter(e) == "23.5 \u00b0C"

    def test_sensor_subtitle_no_unit(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="sensor.text",
                state="hello",
                attributes={"friendly_name": "T"},
            )
        )
        cfg = get_domain_config("sensor")
        assert cfg.subtitle_formatter(e) == "hello"

    def test_climate_subtitle(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="climate.hvac",
                state="heating",
                attributes={
                    "friendly_name": "HVAC",
                    "current_temperature": 21,
                    "temperature": 24,
                },
            )
        )
        cfg = get_domain_config("climate")
        result = cfg.subtitle_formatter(e)
        assert "Heating" in result
        assert "Current: 21\u00b0" in result
        assert "Target: 24\u00b0" in result

    def test_media_player_subtitle_with_source(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="media_player.tv",
                state="playing",
                attributes={"friendly_name": "TV", "media_title": "Movie"},
            )
        )
        cfg = get_domain_config("media_player")
        result = cfg.subtitle_formatter(e)
        assert "Playing" in result
        assert "Movie" in result

    def test_cover_subtitle_with_position(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="cover.blind",
                state="open",
                attributes={"friendly_name": "Blind", "current_position": 75},
            )
        )
        cfg = get_domain_config("cover")
        result = cfg.subtitle_formatter(e)
        assert "Open" in result
        assert "75%" in result

    def test_update_subtitle_needs_update(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="update.firmware",
                state="on",
                attributes={
                    "friendly_name": "Firmware",
                    "installed_version": "1.0",
                    "latest_version": "2.0",
                },
            )
        )
        cfg = get_domain_config("update")
        result = cfg.subtitle_formatter(e)
        assert "1.0" in result
        assert "2.0" in result
        assert "\u2192" in result

    def test_update_subtitle_up_to_date(self) -> None:
        e = Entity.from_state_dict(
            _state_dict(
                entity_id="update.firmware",
                state="off",
                attributes={
                    "friendly_name": "Firmware",
                    "installed_version": "2.0",
                    "latest_version": "2.0",
                },
            )
        )
        cfg = get_domain_config("update")
        result = cfg.subtitle_formatter(e)
        assert "up to date" in result
