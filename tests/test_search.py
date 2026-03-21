"""Tests for ha_workflow.search."""

from __future__ import annotations

from typing import Any

from ha_workflow.entities import Entity
from ha_workflow.search import (
    _matches_char_sequence,
    _score_field,
    fuzzy_search,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity(
    entity_id: str = "light.living_room",
    state: str = "on",
    friendly_name: str = "Living Room Light",
    **extra_attrs: Any,
) -> Entity:
    domain = entity_id.split(".", 1)[0]
    attrs: dict[str, Any] = {"friendly_name": friendly_name, **extra_attrs}
    return Entity(
        entity_id=entity_id,
        domain=domain,
        state=state,
        friendly_name=friendly_name,
        attributes=attrs,
        last_changed="",
        last_updated="",
    )


# A diverse set of entities for search tests
ENTITIES: list[Entity] = [
    _entity("light.living_room", "on", "Living Room Light"),
    _entity("light.kitchen", "off", "Kitchen Light"),
    _entity("light.bedroom", "on", "Bedroom Light"),
    _entity("switch.kitchen_fan", "off", "Kitchen Fan"),
    _entity(
        "sensor.living_room_temperature",
        "23.5",
        "Living Room Temperature",
        device_class="temperature",
        unit_of_measurement="°C",
    ),
    _entity(
        "sensor.kitchen_humidity", "45", "Kitchen Humidity", device_class="humidity"
    ),
    _entity("binary_sensor.front_door", "off", "Front Door"),
    _entity("automation.morning_routine", "on", "Morning Routine"),
    _entity("climate.hvac", "heating", "HVAC"),
    _entity("media_player.living_room_tv", "playing", "Living Room TV"),
    _entity("cover.garage_door", "closed", "Garage Door"),
    _entity("lock.front_door", "locked", "Front Door Lock"),
    _entity("vacuum.roborock", "docked", "Roborock"),
    _entity("script.goodnight", "off", "Goodnight Script"),
    _entity("scene.movie_time", "scening", "Movie Time"),
]


# ---------------------------------------------------------------------------
# _score_field
# ---------------------------------------------------------------------------


class TestScoreField:
    def test_exact_match(self) -> None:
        assert _score_field("Kitchen Light", "Kitchen Light") == 100

    def test_exact_match_case_insensitive(self) -> None:
        assert _score_field("Kitchen Light", "kitchen light") == 100

    def test_prefix_match(self) -> None:
        assert _score_field("Kitchen Light", "Kitchen") == 80

    def test_word_boundary_match(self) -> None:
        # "Light" starts at word boundary in "Kitchen Light"
        assert _score_field("Kitchen Light", "Light") == 60

    def test_word_boundary_on_underscore(self) -> None:
        assert _score_field("living_room", "room") == 60

    def test_substring_match(self) -> None:
        # "itch" is in "Kitchen" but not at a word boundary
        assert _score_field("Kitchen Light", "itch") == 40

    def test_char_sequence_match(self) -> None:
        # "kl" matches k...L in "Kitchen Light"
        assert _score_field("Kitchen Light", "kl") == 20

    def test_no_match(self) -> None:
        assert _score_field("Kitchen Light", "zzz") == 0

    def test_scoring_order(self) -> None:
        """Ensure scores are strictly ordered: exact > prefix > word > sub > char."""
        exact = _score_field("abc", "abc")
        prefix = _score_field("abcdef", "abc")
        word = _score_field("x_abc", "abc")
        sub = _score_field("xabcx", "abc")
        char = _score_field("axbxc", "abc")
        none = _score_field("xyz", "abc")
        assert exact > prefix > word > sub > char > none


# ---------------------------------------------------------------------------
# _matches_char_sequence
# ---------------------------------------------------------------------------


class TestCharSequence:
    def test_matches(self) -> None:
        assert _matches_char_sequence("living_room", "lr") is True

    def test_matches_consecutive(self) -> None:
        assert _matches_char_sequence("living_room", "liv") is True

    def test_no_match(self) -> None:
        assert _matches_char_sequence("living_room", "xyz") is False

    def test_empty_query_matches(self) -> None:
        assert _matches_char_sequence("anything", "") is True

    def test_query_longer_than_text(self) -> None:
        assert _matches_char_sequence("ab", "abc") is False


# ---------------------------------------------------------------------------
# fuzzy_search
# ---------------------------------------------------------------------------


class TestFuzzySearch:
    def test_exact_friendly_name_ranks_first(self) -> None:
        results = fuzzy_search(ENTITIES, "Kitchen Light")
        assert results[0].entity_id == "light.kitchen"

    def test_prefix_match_on_friendly_name(self) -> None:
        results = fuzzy_search(ENTITIES, "Living")
        ids = [e.entity_id for e in results]
        # All "Living" entities should be in results
        assert "light.living_room" in ids
        assert "sensor.living_room_temperature" in ids
        assert "media_player.living_room_tv" in ids

    def test_entity_id_match(self) -> None:
        results = fuzzy_search(ENTITIES, "roborock")
        assert len(results) >= 1
        assert results[0].entity_id == "vacuum.roborock"

    def test_no_results(self) -> None:
        results = fuzzy_search(ENTITIES, "zzzznothing")
        assert results == []

    def test_empty_query_returns_all(self) -> None:
        results = fuzzy_search(ENTITIES, "")
        assert len(results) == len(ENTITIES)

    def test_empty_query_with_whitespace(self) -> None:
        results = fuzzy_search(ENTITIES, "   ")
        assert len(results) == len(ENTITIES)

    def test_max_results_cap(self) -> None:
        results = fuzzy_search(ENTITIES, "", max_results=3)
        assert len(results) == 3

    def test_custom_max_results(self) -> None:
        # All entities match "o" (substring), limit to 5
        results = fuzzy_search(ENTITIES, "o", max_results=5)
        assert len(results) <= 5

    def test_kitchen_matches_ranked(self) -> None:
        results = fuzzy_search(ENTITIES, "kitchen")
        ids = [e.entity_id for e in results]
        assert "light.kitchen" in ids
        assert "switch.kitchen_fan" in ids
        assert "sensor.kitchen_humidity" in ids


class TestMultiWordQuery:
    def test_both_words_must_match(self) -> None:
        results = fuzzy_search(ENTITIES, "living light")
        ids = [e.entity_id for e in results]
        assert "light.living_room" in ids
        # Kitchen Light has "light" but not "living"
        assert "light.kitchen" not in ids

    def test_word_order_irrelevant(self) -> None:
        results1 = fuzzy_search(ENTITIES, "living light")
        results2 = fuzzy_search(ENTITIES, "light living")
        ids1 = {e.entity_id for e in results1}
        ids2 = {e.entity_id for e in results2}
        assert ids1 == ids2

    def test_no_match_when_one_word_fails(self) -> None:
        results = fuzzy_search(ENTITIES, "kitchen zzzzz")
        assert results == []


class TestDeviceClassScoring:
    def test_device_class_contributes(self) -> None:
        results = fuzzy_search(ENTITIES, "temperature")
        ids = [e.entity_id for e in results]
        assert "sensor.living_room_temperature" in ids

    def test_humidity_device_class(self) -> None:
        results = fuzzy_search(ENTITIES, "humidity")
        ids = [e.entity_id for e in results]
        assert "sensor.kitchen_humidity" in ids


class TestEdgeCases:
    def test_single_character_query(self) -> None:
        results = fuzzy_search(ENTITIES, "k")
        # Should match entities with "k" somewhere
        assert len(results) > 0

    def test_special_regex_chars_in_query(self) -> None:
        # Should not crash — regex chars are in the query
        results = fuzzy_search(ENTITIES, "light.*room")
        # May or may not match, but must not raise
        assert isinstance(results, list)

    def test_entity_with_empty_friendly_name(self) -> None:
        entities = [_entity("sensor.x", "on", "")]
        results = fuzzy_search(entities, "sensor")
        # Should still match on entity_id
        assert len(results) == 1
