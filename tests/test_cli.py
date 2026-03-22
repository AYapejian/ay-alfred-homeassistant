"""Tests for ha_workflow.cli."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from ha_workflow.cli import main
from ha_workflow.entities import Entity

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity(
    entity_id: str = "light.living_room",
    state: str = "on",
    friendly_name: str = "Living Room Light",
    area_name: str = "",
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
        area_name=area_name,
    )


SAMPLE_ENTITIES: list[Entity] = [
    _entity("light.living_room", "on", "Living Room Light"),
    _entity("switch.kitchen", "off", "Kitchen Switch"),
    _entity("sensor.temperature", "23.5", "Temperature"),
]


def _mock_cache(
    entities: list[Entity] | None = None,
    cache_age: float | None = 5.0,
    stale: bool = False,
    domain_counts: dict[str, int] | None = None,
) -> MagicMock:
    """Build a mock EntityCache."""
    cache = MagicMock()
    ents = entities if entities is not None else SAMPLE_ENTITIES
    cache.get_all.return_value = ents
    cache.get_cache_age.return_value = cache_age
    cache.is_stale.return_value = stale
    cache.get_domain_counts.return_value = domain_counts or {}
    cache.get_by_domain.side_effect = lambda d: [e for e in ents if e.domain == d]
    return cache


def _mock_tracker(usage_stats: dict[str, object] | None = None) -> MagicMock:
    """Build a mock UsageTracker."""
    tracker = MagicMock()
    tracker.get_usage_stats.return_value = usage_stats or {}
    return tracker


# ---------------------------------------------------------------------------
# Command dispatch (stubs that still exist)
# ---------------------------------------------------------------------------


class TestCommandDispatch:
    def test_no_args_shows_stub(self, capsys: object) -> None:
        main([])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert data["items"][0]["valid"] is False

    def test_action_stub(self, capsys: object) -> None:
        main(["action", "light.living_room", "toggle"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]

    def test_actions_stub(self, capsys: object) -> None:
        main(["actions", "light.living_room"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]

    def test_unknown_command_stub(self, capsys: object) -> None:
        main(["bogus"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]


# ---------------------------------------------------------------------------
# config validate (unchanged from Phase 1)
# ---------------------------------------------------------------------------


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

        out = capsys.readouterr().out  # type: ignore[union-attr]
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

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert data["items"][0]["subtitle"] == "v2024.6.0"


# ---------------------------------------------------------------------------
# search command
# ---------------------------------------------------------------------------


class TestSearchCommand:
    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_returns_entities(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "living"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert len(data["items"]) >= 1
        item = data["items"][0]
        assert "title" in item
        assert "variables" in item
        assert "entity_id" in item["variables"]

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_no_results(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "zzzznothing"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert data["items"][0]["title"] == "No matching entities"
        assert data["items"][0]["valid"] is False

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_empty_query_returns_all(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        # System commands prepended + 3 entities
        entity_items = [
            i
            for i in data["items"]
            if i.get("variables", {}).get("domain") != "__system__"
        ]
        assert len(entity_items) == 3
        # System commands appear first
        assert data["items"][0]["variables"]["domain"] == "__system__"

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_stale_cache_sets_rerun(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(stale=True)
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "light"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert data.get("rerun") == 1.0
        mock_bg_refresh.assert_called_once()

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_first_run_shows_loading_and_triggers_bg_refresh(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(cache_age=None)
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "light"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "Loading" in data["items"][0]["title"]
        assert data.get("rerun") == 1.0
        mock_bg_refresh.assert_called_once()

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_items_have_domain_subtitle(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "kitchen"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        item = data["items"][0]
        assert "switch" in item["subtitle"]

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_items_show_area_in_subtitle(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        entities = [
            _entity(
                "light.living_room",
                "on",
                "Living Room Light",
                area_name="Living Room",
            ),
        ]
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(entities=entities)
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "living"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        item = data["items"][0]
        assert "Living Room" in item["subtitle"]
        # Should NOT contain domain as prefix when area is present
        assert not item["subtitle"].startswith("light")

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_items_fall_back_to_domain_without_area(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        entities = [
            _entity("switch.kitchen", "off", "Kitchen Switch"),
        ]
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(entities=entities)
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "kitchen"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        item = data["items"][0]
        assert item["subtitle"].startswith("switch")


# ---------------------------------------------------------------------------
# cache commands
# ---------------------------------------------------------------------------


class TestCacheCommand:
    @patch("ha_workflow.cli._refresh_cache")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_cache_refresh(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_refresh: MagicMock,
        capsys: object,
    ) -> None:
        config = MagicMock()
        config.cache_dir = Path("/tmp/test-cache")
        mock_from_env.return_value = config
        cache = _mock_cache()
        mock_open_cache.return_value = cache

        main(["cache", "refresh"])

        mock_refresh.assert_called_once()
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "refreshed" in data["items"][0]["title"].lower()

    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_cache_status(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(cache_age=30.0)

        main(["cache", "status"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "30s" in data["items"][0]["subtitle"]
        assert "3 entities" in data["items"][0]["subtitle"]

    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_cache_status_never_refreshed(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(cache_age=None)

        main(["cache", "status"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "Never refreshed" in data["items"][0]["subtitle"]

    def test_cache_no_subcommand_shows_stub(self, capsys: object) -> None:
        main(["cache"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]


# ---------------------------------------------------------------------------
# Background refresh
# ---------------------------------------------------------------------------


class TestBackgroundRefresh:
    @patch("ha_workflow.cli.subprocess.Popen")
    @patch("ha_workflow.cli.os.makedirs")
    def test_spawns_subprocess_when_no_lock(
        self,
        mock_makedirs: MagicMock,
        mock_popen: MagicMock,
        tmp_path: Path,
    ) -> None:
        from ha_workflow.cli import _maybe_refresh_background

        mock_popen.return_value = MagicMock(pid=12345)
        config = MagicMock()
        config.cache_dir = tmp_path

        _maybe_refresh_background(config)

        mock_popen.assert_called_once()
        lock = tmp_path / ".refresh.lock"
        assert lock.read_text() == "12345"

    @patch("ha_workflow.cli.subprocess.Popen")
    @patch("ha_workflow.cli.os.kill")
    def test_skips_when_lock_pid_alive(
        self,
        mock_kill: MagicMock,
        mock_popen: MagicMock,
        tmp_path: Path,
    ) -> None:
        from ha_workflow.cli import _maybe_refresh_background

        lock = tmp_path / ".refresh.lock"
        lock.write_text("99999")
        mock_kill.return_value = None  # signal 0 succeeds = process alive

        config = MagicMock()
        config.cache_dir = tmp_path

        _maybe_refresh_background(config)

        mock_popen.assert_not_called()

    @patch("ha_workflow.cli.subprocess.Popen")
    @patch("ha_workflow.cli.os.kill")
    @patch("ha_workflow.cli.os.makedirs")
    def test_replaces_stale_lock(
        self,
        mock_makedirs: MagicMock,
        mock_kill: MagicMock,
        mock_popen: MagicMock,
        tmp_path: Path,
    ) -> None:
        from ha_workflow.cli import _maybe_refresh_background

        lock = tmp_path / ".refresh.lock"
        lock.write_text("99999")
        mock_kill.side_effect = OSError("No such process")
        mock_popen.return_value = MagicMock(pid=54321)

        config = MagicMock()
        config.cache_dir = tmp_path

        _maybe_refresh_background(config)

        mock_popen.assert_called_once()
        assert lock.read_text() == "54321"


# ---------------------------------------------------------------------------
# Enhanced search (Phase 1.5)
# ---------------------------------------------------------------------------


class TestDomainFilterSearch:
    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_domain_filter_returns_only_matching_domain(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "light:"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        # Should only return light entities
        for item in data["items"]:
            if "variables" in item:
                assert item["variables"]["domain"] == "light"

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_domain_filter_with_text(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "switch:kitchen"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert len(data["items"]) >= 1
        assert data["items"][0]["variables"]["entity_id"] == "switch.kitchen"


class TestRegexSearch:
    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_regex_search(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "/kitchen/"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert len(data["items"]) >= 1
        ids = [i.get("variables", {}).get("entity_id") for i in data["items"]]
        assert "switch.kitchen" in ids

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_invalid_regex_shows_error(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "/[invalid/"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert data["items"][0]["title"] == "Invalid regex pattern"
        assert data["items"][0]["valid"] is False


class TestDomainSuggestionsInSearch:
    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_domain_suggestions_prepended(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(
            domain_counts={"light": 10, "switch": 5, "sensor": 20}
        )
        mock_open_tracker.return_value = _mock_tracker()

        # "li" should trigger a domain suggestion for "light"
        main(["search", "li"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        # First item should be the domain suggestion
        first = data["items"][0]
        assert "Filter: light" in first["title"]
        assert first["autocomplete"] == "light:"
        assert first["valid"] is False


class TestRecordUsage:
    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli.Config.from_env")
    def test_record_usage_calls_tracker(
        self,
        mock_from_env: MagicMock,
        mock_open_tracker: MagicMock,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        tracker = _mock_tracker()
        mock_open_tracker.return_value = tracker

        main(["record-usage", "light.kitchen"])

        tracker.record_usage.assert_called_once_with("light.kitchen")
        tracker.close.assert_called_once()

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli.Config.from_env")
    def test_record_usage_no_entity_is_noop(
        self,
        mock_from_env: MagicMock,
        mock_open_tracker: MagicMock,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        tracker = _mock_tracker()
        mock_open_tracker.return_value = tracker

        main(["record-usage"])

        tracker.record_usage.assert_not_called()


class TestSystemCommandsInSearch:
    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_clear_usage_surfaces_in_search(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "history clear"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        # System command is always first
        first = data["items"][0]
        assert first["title"] == "History: Clear usage data"
        assert first["valid"] is True
        assert first["variables"]["action"] == "usage_clear"
        assert first["variables"]["entity_id"] == "__system__"
        # Distinct icon — uses system command icon, not the workflow icon
        assert first["icon"]["path"] == "icons/_system.png"
        # Subtitle has "System" prefix
        assert first["subtitle"].startswith("System")

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_refresh_cache_surfaces_in_search(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "cache refresh"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        titles = [i["title"] for i in data["items"]]
        assert "Cache: Refresh entities" in titles

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_no_system_commands_for_unrelated_query(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "living"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        sys_items = [
            i
            for i in data["items"]
            if i.get("variables", {}).get("domain") == "__system__"
        ]
        assert sys_items == []


class TestActionCommand:
    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_usage_clear(
        self,
        mock_from_env: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        tracker = _mock_tracker()
        mock_open_tracker.return_value = tracker

        main(["action", "__system__", "usage_clear"])

        tracker.clear.assert_called_once()
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "cleared" in out.lower()

    @patch("ha_workflow.cli._refresh_cache")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_cache_refresh(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_refresh: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        cache = _mock_cache()
        mock_open_cache.return_value = cache

        main(["action", "__system__", "cache_refresh"])

        mock_refresh.assert_called_once()
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "refreshed" in out.lower()

    def test_entity_action_still_stubs(self, capsys: object) -> None:
        main(["action", "light.living_room", "toggle"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "not yet implemented" in data["items"][0]["title"]


# ---------------------------------------------------------------------------
# Area lookup
# ---------------------------------------------------------------------------


class TestBuildAreaLookup:
    def test_builds_lookup_from_registries(self) -> None:
        from ha_workflow.cli import _build_area_lookup

        client = MagicMock()
        client.get_area_registry.return_value = [
            {"area_id": "living_room", "name": "Living Room"},
            {"area_id": "kitchen", "name": "Kitchen"},
        ]
        client.get_entity_registry.return_value = [
            {"entity_id": "light.living_room", "area_id": "living_room"},
            {"entity_id": "switch.kitchen", "area_id": "kitchen"},
            {"entity_id": "sensor.temp", "area_id": ""},
        ]

        lookup = _build_area_lookup(client)

        assert lookup == {
            "light.living_room": "Living Room",
            "switch.kitchen": "Kitchen",
        }
        # Entity with empty area_id should not appear
        assert "sensor.temp" not in lookup

    def test_empty_registries_returns_empty(self) -> None:
        from ha_workflow.cli import _build_area_lookup

        client = MagicMock()
        client.get_area_registry.return_value = []
        client.get_entity_registry.return_value = []

        assert _build_area_lookup(client) == {}

    def test_unknown_area_id_skipped(self) -> None:
        from ha_workflow.cli import _build_area_lookup

        client = MagicMock()
        client.get_area_registry.return_value = [
            {"area_id": "living_room", "name": "Living Room"},
        ]
        client.get_entity_registry.return_value = [
            {"entity_id": "light.x", "area_id": "nonexistent"},
        ]

        assert _build_area_lookup(client) == {}
