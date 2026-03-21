"""Tests for ha_workflow.suggestions."""

from __future__ import annotations

from typing import Any

from ha_workflow.entities import Entity
from ha_workflow.suggestions import build_domain_suggestions, sort_by_usage
from ha_workflow.usage import UsageRecord

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


SAMPLE_COUNTS: dict[str, int] = {
    "light": 42,
    "switch": 18,
    "sensor": 120,
    "binary_sensor": 55,
    "automation": 30,
    "climate": 3,
    "lock": 2,
}


# ---------------------------------------------------------------------------
# build_domain_suggestions
# ---------------------------------------------------------------------------


class TestBuildDomainSuggestions:
    def test_prefix_match(self) -> None:
        items = build_domain_suggestions("li", SAMPLE_COUNTS)
        assert len(items) == 1
        assert items[0].autocomplete == "light:"
        assert "42" in items[0].title

    def test_multiple_matches(self) -> None:
        # "se" matches sensor
        items = build_domain_suggestions("se", SAMPLE_COUNTS)
        domains = [i.autocomplete for i in items]
        assert "sensor:" in domains

    def test_binary_sensor_match(self) -> None:
        items = build_domain_suggestions("bi", SAMPLE_COUNTS)
        assert len(items) == 1
        assert items[0].autocomplete == "binary_sensor:"

    def test_no_match(self) -> None:
        items = build_domain_suggestions("zz", SAMPLE_COUNTS)
        assert items == []

    def test_empty_query(self) -> None:
        items = build_domain_suggestions("", SAMPLE_COUNTS)
        assert items == []

    def test_single_char_too_short(self) -> None:
        items = build_domain_suggestions("l", SAMPLE_COUNTS)
        assert items == []

    def test_full_domain_name_no_suggestion(self) -> None:
        # "light" is a complete domain — don't suggest it
        items = build_domain_suggestions("light", SAMPLE_COUNTS)
        assert items == []

    def test_multi_word_no_suggestion(self) -> None:
        items = build_domain_suggestions("li room", SAMPLE_COUNTS)
        assert items == []

    def test_uppercase_no_suggestion(self) -> None:
        items = build_domain_suggestions("LI", SAMPLE_COUNTS)
        assert items == []

    def test_sorted_by_count_descending(self) -> None:
        counts = {"sensor": 100, "switch": 50, "scene": 10, "script": 5, "select": 3}
        items = build_domain_suggestions("s", counts, max_suggestions=10)
        # "s" is only 1 char, too short
        assert items == []

        items = build_domain_suggestions("sc", counts)
        domains = [i.autocomplete for i in items]
        assert domains == ["scene:", "script:"]

    def test_max_suggestions_cap(self) -> None:
        # Create counts where "au" matches automation
        items = build_domain_suggestions("au", SAMPLE_COUNTS, max_suggestions=1)
        assert len(items) <= 1

    def test_items_are_not_valid(self) -> None:
        items = build_domain_suggestions("li", SAMPLE_COUNTS)
        for item in items:
            assert item.valid is False

    def test_uid_set(self) -> None:
        items = build_domain_suggestions("li", SAMPLE_COUNTS)
        assert items[0].uid == "domain_suggestion_light"

    def test_singular_entity_label(self) -> None:
        counts = {"light": 1}
        items = build_domain_suggestions("li", counts)
        assert "1 entity)" in items[0].title


# ---------------------------------------------------------------------------
# sort_by_usage
# ---------------------------------------------------------------------------


SORT_ENTITIES = [
    _entity("light.a", "on", "Alpha Light"),
    _entity("light.b", "on", "Beta Light"),
    _entity("light.c", "on", "Charlie Light"),
]


class TestSortByUsage:
    def test_no_usage_alphabetical(self) -> None:
        result = sort_by_usage(SORT_ENTITIES)
        names = [e.friendly_name for e in result]
        assert names == ["Alpha Light", "Beta Light", "Charlie Light"]

    def test_usage_sorts_by_score(self) -> None:
        now = 1000000.0
        stats = {
            "light.c": UsageRecord("light.c", 50, now),
            "light.a": UsageRecord("light.a", 10, now),
        }
        result = sort_by_usage(SORT_ENTITIES, stats, now=now)
        ids = [e.entity_id for e in result]
        # c (50 uses) first, a (10 uses) second, b (no usage) last
        assert ids.index("light.c") < ids.index("light.a")
        assert ids.index("light.a") < ids.index("light.b")

    def test_max_results(self) -> None:
        result = sort_by_usage(SORT_ENTITIES, max_results=2)
        assert len(result) == 2

    def test_empty_stats_alphabetical(self) -> None:
        result = sort_by_usage(SORT_ENTITIES, {})
        names = [e.friendly_name for e in result]
        assert names == ["Alpha Light", "Beta Light", "Charlie Light"]
