"""Tests for ha_workflow.cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from ha_workflow.cache import EntityCache, open_cache
from ha_workflow.config import Config
from ha_workflow.entities import Entity

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
        last_changed="2026-03-20T10:00:00+00:00",
        last_updated="2026-03-20T10:00:00+00:00",
    )


def _mem_cache() -> EntityCache:
    return EntityCache(":memory:")


SAMPLE_ENTITIES: list[Entity] = [
    _entity("light.living_room", "on", "Living Room Light"),
    _entity("switch.kitchen", "off", "Kitchen Switch"),
    _entity("sensor.temperature", "23.5", "Temperature"),
]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class TestSchema:
    def test_tables_created(self) -> None:
        cache = _mem_cache()
        cur = cache._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cur.fetchall()}
        assert "entities" in tables
        assert "cache_meta" in tables
        cache.close()

    def test_indexes_created(self) -> None:
        cache = _mem_cache()
        cur = cache._conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cur.fetchall()}
        assert "idx_entities_domain" in indexes
        assert "idx_entities_friendly_name" in indexes
        cache.close()


# ---------------------------------------------------------------------------
# refresh + get_all
# ---------------------------------------------------------------------------


class TestRefresh:
    def test_refresh_and_get_all(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        result = cache.get_all()
        assert len(result) == 3
        ids = {e.entity_id for e in result}
        assert ids == {"light.living_room", "switch.kitchen", "sensor.temperature"}
        cache.close()

    def test_refresh_replaces_all(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        new = [_entity("fan.bedroom", "on", "Bedroom Fan")]
        cache.refresh(new)
        result = cache.get_all()
        assert len(result) == 1
        assert result[0].entity_id == "fan.bedroom"
        cache.close()

    def test_refresh_with_empty_list(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        cache.refresh([])
        assert cache.get_all() == []
        cache.close()

    def test_attributes_roundtrip(self) -> None:
        e = _entity("sensor.temp", "23.5", "Temp", unit_of_measurement="°C")
        cache = _mem_cache()
        cache.refresh([e])
        result = cache.get_all()
        assert result[0].attributes["unit_of_measurement"] == "°C"
        cache.close()


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_matches_entity_id(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        result = cache.search("kitchen")
        assert len(result) == 1
        assert result[0].entity_id == "switch.kitchen"
        cache.close()

    def test_matches_friendly_name(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        result = cache.search("Living")
        assert len(result) == 1
        assert result[0].entity_id == "light.living_room"
        cache.close()

    def test_no_matches(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        result = cache.search("zzzzz_no_match")
        assert result == []
        cache.close()

    def test_multiple_matches(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        # "oo" appears in "living_room" and "Room"
        result = cache.search("oo")
        ids = {e.entity_id for e in result}
        assert "light.living_room" in ids
        cache.close()


# ---------------------------------------------------------------------------
# get_by_domain / get_domain_counts
# ---------------------------------------------------------------------------


class TestDomainMethods:
    def test_get_by_domain_returns_matching(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        result = cache.get_by_domain("light")
        assert len(result) == 1
        assert result[0].entity_id == "light.living_room"
        cache.close()

    def test_get_by_domain_no_match(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        result = cache.get_by_domain("vacuum")
        assert result == []
        cache.close()

    def test_get_by_domain_multiple(self) -> None:
        entities = [*SAMPLE_ENTITIES, _entity("light.kitchen", "off", "Kitchen Light")]
        cache = _mem_cache()
        cache.refresh(entities)
        result = cache.get_by_domain("light")
        assert len(result) == 2
        ids = {e.entity_id for e in result}
        assert ids == {"light.living_room", "light.kitchen"}
        cache.close()

    def test_get_domain_counts(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        counts = cache.get_domain_counts()
        assert counts == {"light": 1, "switch": 1, "sensor": 1}
        cache.close()

    def test_get_domain_counts_empty_cache(self) -> None:
        cache = _mem_cache()
        counts = cache.get_domain_counts()
        assert counts == {}
        cache.close()

    def test_get_by_domain_empty_cache(self) -> None:
        cache = _mem_cache()
        result = cache.get_by_domain("light")
        assert result == []
        cache.close()


# ---------------------------------------------------------------------------
# Cache age / staleness
# ---------------------------------------------------------------------------


class TestCacheAge:
    def test_none_when_never_refreshed(self) -> None:
        cache = _mem_cache()
        assert cache.get_cache_age() is None
        cache.close()

    def test_is_stale_when_never_refreshed(self) -> None:
        cache = _mem_cache()
        assert cache.is_stale(60) is True
        cache.close()

    def test_not_stale_after_refresh(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        assert cache.is_stale(60) is False
        cache.close()

    def test_age_positive_after_refresh(self) -> None:
        cache = _mem_cache()
        cache.refresh(SAMPLE_ENTITIES)
        age = cache.get_cache_age()
        assert age is not None
        assert age >= 0
        cache.close()

    @patch("ha_workflow.cache.time.time")
    def test_stale_after_ttl(self, mock_time: Any) -> None:
        cache = _mem_cache()
        mock_time.return_value = 1000.0
        cache.refresh(SAMPLE_ENTITIES)
        mock_time.return_value = 1061.0  # 61 seconds later
        assert cache.is_stale(60) is True
        cache.close()

    @patch("ha_workflow.cache.time.time")
    def test_not_stale_within_ttl(self, mock_time: Any) -> None:
        cache = _mem_cache()
        mock_time.return_value = 1000.0
        cache.refresh(SAMPLE_ENTITIES)
        mock_time.return_value = 1030.0  # 30 seconds later
        assert cache.is_stale(60) is False
        cache.close()


# ---------------------------------------------------------------------------
# open_cache
# ---------------------------------------------------------------------------


class TestOpenCache:
    def test_creates_db_file(self, tmp_path: Path) -> None:
        config = Config(
            ha_url="http://ha.local:8123",
            ha_token="test-token",
            cache_ttl=60,
            cache_dir=tmp_path / "cache",
            data_dir=tmp_path / "data",
        )
        cache = open_cache(config)
        db_file = tmp_path / "cache" / "entities.db"
        assert db_file.exists()
        cache.close()
