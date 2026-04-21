"""Tests for ha_workflow.inference."""

from __future__ import annotations

from ha_workflow.inference import infer_action


class TestInferAction:
    def test_no_params_returns_default(self) -> None:
        # light's default action is ``toggle``.
        assert infer_action("light", []) == "toggle"

    def test_light_with_brightness_infers_turn_on(self) -> None:
        assert infer_action("light", ["brightness"]) == "turn_on"

    def test_light_with_color_and_transition_infers_turn_on(self) -> None:
        assert (
            infer_action("light", ["brightness", "color_name", "transition"])
            == "turn_on"
        )

    def test_light_with_rgb_color_infers_turn_on(self) -> None:
        assert infer_action("light", ["rgb_color"]) == "turn_on"

    def test_climate_with_temperature_infers_set_temperature(self) -> None:
        assert infer_action("climate", ["temperature"]) == "set_temperature"

    def test_media_player_with_volume_infers_volume_set(self) -> None:
        assert infer_action("media_player", ["volume_level"]) == "volume_set"

    def test_fan_with_percentage_infers_turn_on(self) -> None:
        assert infer_action("fan", ["percentage"]) == "turn_on"

    def test_cover_position_tie_falls_back_to_default(self) -> None:
        # Both open_cover and close_cover declare ``position`` — ambiguous, so
        # we should not guess.  Fall back to the domain default (``toggle``).
        assert infer_action("cover", ["position"]) == "toggle"

    def test_unknown_key_falls_back_to_default(self) -> None:
        # No action declares ``wat`` for lights; fall back to default.
        assert infer_action("light", ["wat"]) == "toggle"

    def test_unknown_domain_empty(self) -> None:
        assert infer_action("nonesuch_domain", ["brightness"]) == ""

    def test_input_number_single_action(self) -> None:
        assert infer_action("input_number", ["value"]) == "set_value"

    def test_empty_keys_filtered(self) -> None:
        # Empty string keys should be ignored, not treated as "has params".
        assert infer_action("light", ["", "  "]) == "toggle"
