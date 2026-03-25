"""Tests for ha_workflow.params — short-syntax parameter parser."""

from __future__ import annotations

import pytest

from ha_workflow.params import parse_service_params


class TestBasicParsing:
    def test_single_int(self) -> None:
        result = parse_service_params("brightness:128", "light", "turn_on")
        assert result == {"brightness": 128}

    def test_single_float(self) -> None:
        result = parse_service_params("transition:2.5", "light", "turn_on")
        assert result == {"transition": 2.5}

    def test_single_string(self) -> None:
        result = parse_service_params("effect:rainbow", "light", "turn_on")
        assert result == {"effect": "rainbow"}

    def test_multiple_params(self) -> None:
        result = parse_service_params("brightness:128,transition:2", "light", "turn_on")
        assert result == {"brightness": 128, "transition": 2.0}

    def test_empty_string(self) -> None:
        assert parse_service_params("", "light", "turn_on") == {}

    def test_whitespace_only(self) -> None:
        assert parse_service_params("   ", "light", "turn_on") == {}


class TestBrightnessPercentage:
    def test_percentage_50(self) -> None:
        result = parse_service_params("brightness:50%", "light", "turn_on")
        assert result == {"brightness": 128}  # ceil(50/100 * 255)

    def test_percentage_100(self) -> None:
        result = parse_service_params("brightness:100%", "light", "turn_on")
        assert result == {"brightness": 255}

    def test_percentage_0(self) -> None:
        result = parse_service_params("brightness:0%", "light", "turn_on")
        assert result == {"brightness": 0}

    def test_percentage_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="0-100"):
            parse_service_params("brightness:150%", "light", "turn_on")

    def test_raw_int_passthrough(self) -> None:
        # Without %, treat as raw 0-255 value
        result = parse_service_params("brightness:200", "light", "turn_on")
        assert result == {"brightness": 200}


class TestRGBColor:
    def test_rgb_basic(self) -> None:
        result = parse_service_params("rgb_color:255,0,128", "light", "turn_on")
        assert result == {"rgb_color": [255, 0, 128]}

    def test_rgb_with_other_params(self) -> None:
        result = parse_service_params(
            "rgb_color:255,0,0,transition:2", "light", "turn_on"
        )
        # rgb_color parser stops at transition:2 (has colon)
        assert result["rgb_color"] == [255, 0, 0]
        assert result["transition"] == 2.0

    def test_rgb_wrong_count(self) -> None:
        with pytest.raises(ValueError, match="3 RGB"):
            parse_service_params("rgb_color:255,0", "light", "turn_on")

    def test_rgb_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="0-255"):
            parse_service_params("rgb_color:256,0,0", "light", "turn_on")


class TestTypeCoercion:
    def test_invalid_int(self) -> None:
        with pytest.raises(ValueError, match="integer"):
            parse_service_params("brightness:abc", "light", "turn_on")

    def test_invalid_float(self) -> None:
        with pytest.raises(ValueError, match="number"):
            parse_service_params("temperature:warm", "climate", "set_temperature")

    def test_climate_temperature(self) -> None:
        result = parse_service_params("temperature:22.5", "climate", "set_temperature")
        assert result == {"temperature": 22.5}


class TestMinMaxValidation:
    def test_fan_speed_valid(self) -> None:
        result = parse_service_params("percentage:75", "fan", "turn_on")
        assert result == {"percentage": 75}

    def test_fan_speed_too_high(self) -> None:
        with pytest.raises(ValueError, match="<= 100"):
            parse_service_params("percentage:150", "fan", "turn_on")

    def test_fan_speed_too_low(self) -> None:
        with pytest.raises(ValueError, match=">= 0"):
            parse_service_params("percentage:-5", "fan", "turn_on")

    def test_volume_valid(self) -> None:
        result = parse_service_params("volume_level:0.5", "media_player", "volume_set")
        assert result == {"volume_level": 0.5}

    def test_volume_too_high(self) -> None:
        with pytest.raises(ValueError, match=r"<= 1\.0"):
            parse_service_params("volume_level:1.5", "media_player", "volume_set")


class TestUnknownKeys:
    def test_unknown_key_passthrough(self) -> None:
        result = parse_service_params("custom_attr:hello", "light", "turn_on")
        assert result == {"custom_attr": "hello"}

    def test_unknown_domain_action(self) -> None:
        result = parse_service_params("foo:bar", "unknown_domain", "unknown_action")
        assert result == {"foo": "bar"}


class TestMalformedInput:
    def test_no_colon(self) -> None:
        with pytest.raises(ValueError, match="key:value"):
            parse_service_params("brightness", "light", "turn_on")

    def test_empty_key(self) -> None:
        with pytest.raises(ValueError, match="Empty parameter"):
            parse_service_params(":50", "light", "turn_on")

    def test_value_with_colon(self) -> None:
        # Value can contain colons (split on first only)
        result = parse_service_params("effect:color:loop", "light", "turn_on")
        assert result == {"effect": "color:loop"}


class TestInputHelpers:
    def test_input_number(self) -> None:
        result = parse_service_params("value:42.5", "input_number", "set_value")
        assert result == {"value": 42.5}

    def test_input_select(self) -> None:
        result = parse_service_params("option:morning", "input_select", "select_option")
        assert result == {"option": "morning"}

    def test_input_text(self) -> None:
        result = parse_service_params("value:hello world", "input_text", "set_value")
        assert result == {"value": "hello world"}
