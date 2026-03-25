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

    @patch("ha_workflow.cli._cmd_record_usage")
    @patch("ha_workflow.cli.dispatch_action")
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_action_dispatches(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        mock_dispatch: MagicMock,
        mock_record: MagicMock,
        capsys: object,
    ) -> None:
        from ha_workflow.actions import ActionResult

        mock_from_env.return_value = MagicMock()
        mock_dispatch.return_value = ActionResult(success=True, message="Toggled")
        main(["action", "light.living_room", "toggle"])
        mock_dispatch.assert_called_once()

    def test_actions_lists_domain_actions(self, capsys: object) -> None:
        main(["actions", "light.living_room"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert any(item["title"] == "Toggle" for item in data["items"])

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

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_items_have_cmd_modifier(
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
        item = data["items"][0]
        # Cmd modifier must be present for sub-menu routing
        assert "mods" in item
        assert "cmd" in item["mods"]
        cmd_mod = item["mods"]["cmd"]
        assert cmd_mod["valid"] is True
        assert cmd_mod["variables"]["entity_id"] == "light.living_room"

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_display_only_entity_has_cmd_modifier(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        mock_open_tracker: MagicMock,
        capsys: object,
    ) -> None:
        """Display-only entities (sensors) must also have Cmd modifier."""
        entities = [
            _entity("sensor.temperature", "23.5", "Temperature"),
        ]
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(entities=entities)
        mock_open_tracker.return_value = _mock_tracker()

        main(["search", "temperature"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        item = data["items"][0]
        # Base valid=False (no default action), but Cmd must be valid
        assert item.get("valid") is False
        assert item["mods"]["cmd"]["valid"] is True
        assert item["mods"]["cmd"]["variables"]["entity_id"] == "sensor.temperature"


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

    @patch("ha_workflow.cli._cmd_record_usage")
    @patch("ha_workflow.cli.dispatch_action")
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_entity_action_toggle(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        mock_dispatch: MagicMock,
        mock_record: MagicMock,
        capsys: object,
    ) -> None:
        from ha_workflow.actions import ActionResult

        mock_from_env.return_value = MagicMock()
        mock_dispatch.return_value = ActionResult(
            success=True, message="Toggled Living Room Light"
        )

        main(["action", "light.living_room", "toggle"])

        mock_dispatch.assert_called_once()
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Toggled Living Room Light" in out
        mock_record.assert_called_once_with("light.living_room")

    @patch("ha_workflow.cli._cmd_record_usage")
    @patch("ha_workflow.cli.dispatch_action")
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_entity_action_failure_no_usage(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        mock_dispatch: MagicMock,
        mock_record: MagicMock,
        capsys: object,
    ) -> None:
        from ha_workflow.actions import ActionResult

        mock_from_env.return_value = MagicMock()
        mock_dispatch.return_value = ActionResult(
            success=False, message="Connection error: timeout"
        )

        main(["action", "light.living_room", "toggle"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Connection error" in out
        mock_record.assert_not_called()

    def test_entity_action_missing_args(self, capsys: object) -> None:
        main(["action", "light.living_room"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Missing" in out

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_ha_restart(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_ha_client.return_value = mock_client

        main(["action", "__system__", "ha_restart"])

        mock_client.call_service.assert_called_once_with("homeassistant", "restart")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "restarting" in out.lower()

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_ha_restart_failure(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        from ha_workflow.errors import HAConnectionError

        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.call_service.side_effect = HAConnectionError("timeout")
        mock_ha_client.return_value = mock_client

        main(["action", "__system__", "ha_restart"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "failed" in out.lower()

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_ha_check_config_valid(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.check_config.return_value = {"result": "valid", "errors": None}
        mock_ha_client.return_value = mock_client

        main(["action", "__system__", "ha_check_config"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "valid" in out.lower()

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_ha_check_config_invalid(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.check_config.return_value = {
            "result": "invalid",
            "errors": "Integration 'foo' not found",
        }
        mock_ha_client.return_value = mock_client

        main(["action", "__system__", "ha_check_config"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "invalid" in out.lower()
        assert "foo" in out

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_ha_check_config_failure(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        from ha_workflow.errors import HAConnectionError

        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.check_config.side_effect = HAConnectionError("timeout")
        mock_ha_client.return_value = mock_client

        main(["action", "__system__", "ha_check_config"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "failed" in out.lower()

    @patch("ha_workflow.cli.subprocess.run")
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_ha_error_log(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        mock_run: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_error_log.return_value = (
            "2026-03-22 ERROR (MainThread) [homeassistant] Something broke\n"
            "2026-03-22 WARNING (MainThread) [custom] Another issue\n"
        )
        mock_ha_client.return_value = mock_client

        main(["action", "__system__", "ha_error_log"])

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["pbcopy"]
        assert b"Something broke" in call_args[1]["input"]
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "copied" in out.lower()
        assert "2 lines" in out

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_ha_error_log_empty(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_error_log.return_value = ""
        mock_ha_client.return_value = mock_client

        main(["action", "__system__", "ha_error_log"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "empty" in out.lower()

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_system_action_ha_error_log_failure(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        from ha_workflow.errors import HAConnectionError

        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_error_log.side_effect = HAConnectionError("timeout")
        mock_ha_client.return_value = mock_client

        main(["action", "__system__", "ha_error_log"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "failed" in out.lower()


class TestSystemCommandsSearch:
    """Test that new system commands surface in search results."""

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_restart_surfaces_in_search(
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

        main(["search", "restart"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        titles = [i["title"] for i in data["items"]]
        assert "System: Restart Home Assistant" in titles

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_check_config_surfaces_in_search(
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

        main(["search", "check config"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        titles = [i["title"] for i in data["items"]]
        assert "System: Check config" in titles

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_logs_surfaces_in_search(
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

        main(["search", "error log"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        titles = [i["title"] for i in data["items"]]
        assert "System: View error log" in titles

    @patch("ha_workflow.cli.open_usage_tracker")
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_all_system_commands_on_empty_query(
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
        sys_items = [
            i
            for i in data["items"]
            if i.get("variables", {}).get("domain") == "__system__"
        ]
        # Should have all 5 system commands
        assert len(sys_items) == 5


class TestActionsCommand:
    def test_actions_for_light(self, capsys: object) -> None:
        main(["actions", "light.living_room"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        titles = [item["title"] for item in data["items"]]
        # Header + domain actions + copy/open/advanced
        assert "Living Room" in titles[0]  # header
        assert "Toggle" in titles
        assert "Turn On" in titles
        assert "Turn Off" in titles
        # Actionable items (skip header) have correct variables
        for item in data["items"]:
            if item.get("valid") and "variables" in item:
                assert item["variables"]["entity_id"] == "light.living_room"
                assert item["variables"]["domain"] == "light"
                assert "action" in item["variables"]

    def test_actions_for_cover(self, capsys: object) -> None:
        main(["actions", "cover.garage"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        titles = [item["title"] for item in data["items"]]
        assert "Open Cover" in titles
        assert "Close Cover" in titles
        assert "Stop Cover" in titles

    def test_actions_display_only_shows_submenu(self, capsys: object) -> None:
        """Display-only entities still show copy/open actions."""
        main(["actions", "sensor.temperature"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        titles = [item["title"] for item in data["items"]]
        assert "Temperature" in titles[0]
        assert "Copy Entity ID" in titles
        assert "Open Entity" in titles
        assert "Open History" in titles

    def test_actions_no_entity(self, capsys: object) -> None:
        main(["actions"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "No entity" in data["items"][0]["title"]

    def test_actions_malformed_entity_id(self, capsys: object) -> None:
        main(["actions", "badentity"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "Invalid entity ID" in data["items"][0]["title"]
        assert data["items"][0]["valid"] is False

    def test_submenu_includes_advanced_action_call(self, capsys: object) -> None:
        main(["actions", "light.living_room"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        adv = [i for i in data["items"] if "Advanced Action Call" in i["title"]]
        assert len(adv) == 1
        assert adv[0]["valid"] is False
        assert "brightness" in adv[0]["subtitle"].lower()

    def test_submenu_parameterized_hint(self, capsys: object) -> None:
        """Turn On action for lights shows param hints in subtitle."""
        main(["actions", "light.living_room"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        turn_on = [i for i in data["items"] if i.get("title") == "Turn On"]
        assert len(turn_on) == 1
        assert "brightness" in turn_on[0]["subtitle"].lower()

    def test_submenu_no_advanced_for_sensor(self, capsys: object) -> None:
        """Sensors have no actions, so no Advanced Action Call."""
        main(["actions", "sensor.temperature"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        adv = [i for i in data["items"] if "Advanced Action Call" in i.get("title", "")]
        assert len(adv) == 0

    def test_submenu_copy_entity_id(self, capsys: object) -> None:
        main(["actions", "light.living_room"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        copy_items = [i for i in data["items"] if i["title"] == "Copy Entity ID"]
        assert len(copy_items) == 1
        assert copy_items[0]["variables"]["action"] == "copy_entity_id"

    def test_submenu_open_history(self, capsys: object) -> None:
        main(["actions", "light.living_room"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        items = [i for i in data["items"] if i["title"] == "Open History"]
        assert len(items) == 1
        assert items[0]["variables"]["action"] == "open_history"


# ---------------------------------------------------------------------------
# Parameterized actions
# ---------------------------------------------------------------------------


class TestActionWithParams:
    @patch("ha_workflow.cli._cmd_record_usage")
    @patch("ha_workflow.cli.dispatch_action")
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_inline_params_passed(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        mock_dispatch: MagicMock,
        mock_record: MagicMock,
        capsys: object,
    ) -> None:
        from ha_workflow.actions import ActionResult

        mock_from_env.return_value = MagicMock()
        mock_dispatch.return_value = ActionResult(success=True, message="Turned on")
        main(["action", "light.bedroom", "turn_on", "brightness:128"])
        mock_dispatch.assert_called_once()
        call_args = mock_dispatch.call_args
        assert call_args[1]["service_data"] == {"brightness": 128}

    @patch("ha_workflow.cli._cmd_record_usage")
    @patch("ha_workflow.cli.dispatch_action")
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_inline_multiple_params(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        mock_dispatch: MagicMock,
        mock_record: MagicMock,
        capsys: object,
    ) -> None:
        from ha_workflow.actions import ActionResult

        mock_from_env.return_value = MagicMock()
        mock_dispatch.return_value = ActionResult(success=True, message="Turned on")
        main(
            [
                "action",
                "light.bedroom",
                "turn_on",
                "brightness:50%,transition:2",
            ]
        )
        call_args = mock_dispatch.call_args
        sd = call_args[1]["service_data"]
        assert sd["brightness"] == 128
        assert sd["transition"] == 2.0

    def test_inline_invalid_params_shows_error(self, capsys: object) -> None:
        main(["action", "light.bedroom", "turn_on", "brightness:abc"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "integer" in out.lower()


class TestActionParamCommand:
    def test_empty_query_lists_params(self, capsys: object) -> None:
        main(["action-param", "light.bedroom", "turn_on"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        titles = [i["title"] for i in data["items"]]
        assert any("Brightness" in t for t in titles)
        assert any("Color Temp" in t for t in titles)

    def test_valid_query_shows_confirmation(self, capsys: object) -> None:
        main(
            [
                "action-param",
                "light.bedroom",
                "turn_on",
                "brightness:128",
            ]
        )
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert data["items"][0]["valid"] is True
        assert "brightness=128" in data["items"][0]["subtitle"]

    def test_invalid_query_shows_error(self, capsys: object) -> None:
        main(
            [
                "action-param",
                "light.bedroom",
                "turn_on",
                "brightness:abc",
            ]
        )
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert data["items"][0]["valid"] is False
        assert "Invalid" in data["items"][0]["title"]

    def test_no_params_available(self, capsys: object) -> None:
        main(["action-param", "light.bedroom", "toggle"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "No parameters" in data["items"][0]["title"]

    def test_missing_entity(self, capsys: object) -> None:
        main(["action-param"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "Missing" in data["items"][0]["title"]


# ---------------------------------------------------------------------------
# Area lookup
# ---------------------------------------------------------------------------


class TestBuildRegistryLookup:
    def _mock_client(
        self,
        areas: list[dict[str, str]],
        devices: list[dict[str, str]],
        entities: list[dict[str, str]],
    ) -> MagicMock:
        client = MagicMock()
        client.get_area_registry.return_value = areas
        client.get_device_registry.return_value = devices
        client.get_entity_registry.return_value = entities
        return client

    def test_entity_direct_area(self) -> None:
        """Entity with its own area_id resolves directly."""
        from ha_workflow.cli import _build_registry_lookup

        client = self._mock_client(
            areas=[{"area_id": "kitchen", "name": "Kitchen"}],
            devices=[],
            entities=[
                {"entity_id": "light.sink", "area_id": "kitchen", "device_id": ""},
            ],
        )
        lookup = _build_registry_lookup(client)
        assert lookup["light.sink"].area_name == "Kitchen"

    def test_area_inherited_from_device(self) -> None:
        """Entity without area_id inherits area from its device."""
        from ha_workflow.cli import _build_registry_lookup

        client = self._mock_client(
            areas=[{"area_id": "living_room", "name": "Living Room"}],
            devices=[{"id": "dev_1", "area_id": "living_room"}],
            entities=[
                {"entity_id": "light.lamp", "area_id": "", "device_id": "dev_1"},
            ],
        )
        lookup = _build_registry_lookup(client)
        assert lookup["light.lamp"].area_name == "Living Room"
        assert lookup["light.lamp"].device_id == "dev_1"

    def test_entity_area_overrides_device_area(self) -> None:
        """Entity-level area_id takes priority over the device's area."""
        from ha_workflow.cli import _build_registry_lookup

        client = self._mock_client(
            areas=[
                {"area_id": "garage", "name": "Garage"},
                {"area_id": "office", "name": "Office"},
            ],
            devices=[{"id": "dev_1", "area_id": "garage"}],
            entities=[
                {"entity_id": "light.desk", "area_id": "office", "device_id": "dev_1"},
            ],
        )
        lookup = _build_registry_lookup(client)
        assert lookup["light.desk"].area_name == "Office"

    def test_device_id_stored(self) -> None:
        """device_id is stored in the lookup even when there's no area."""
        from ha_workflow.cli import _build_registry_lookup

        client = self._mock_client(
            areas=[],
            devices=[],
            entities=[
                {"entity_id": "sensor.temp", "area_id": "", "device_id": "dev_99"},
            ],
        )
        lookup = _build_registry_lookup(client)
        assert lookup["sensor.temp"].device_id == "dev_99"
        assert lookup["sensor.temp"].area_name == ""

    def test_empty_registries_returns_empty(self) -> None:
        from ha_workflow.cli import _build_registry_lookup

        client = self._mock_client(areas=[], devices=[], entities=[])
        assert _build_registry_lookup(client) == {}

    def test_unknown_area_id_skipped(self) -> None:
        from ha_workflow.cli import _build_registry_lookup

        client = self._mock_client(
            areas=[{"area_id": "living_room", "name": "Living Room"}],
            devices=[],
            entities=[
                {"entity_id": "light.x", "area_id": "nonexistent", "device_id": ""},
            ],
        )
        lookup = _build_registry_lookup(client)
        assert lookup["light.x"].area_name == ""


# ---------------------------------------------------------------------------
# Entity viewer actions (Phase 3: 3.8, 3.9)
# ---------------------------------------------------------------------------


class TestShowDetails:
    @patch("ha_workflow.cli.subprocess.run")
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_show_details_copies_yaml(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        mock_run: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_state.return_value = {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {
                "friendly_name": "Living Room Light",
                "brightness": 200,
            },
        }
        mock_ha_client.return_value = mock_client

        main(["action", "light.living_room", "show_details"])

        mock_run.assert_called_once()
        clipboard = mock_run.call_args[1]["input"].decode("utf-8")
        assert "entity_id: light.living_room" in clipboard
        assert "state: on" in clipboard
        assert "brightness: 200" in clipboard
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Copied details" in out
        assert "Living Room Light" in out
        assert "(on)" in out

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_show_details_failure(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        from ha_workflow.errors import HAConnectionError

        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_state.side_effect = HAConnectionError("timeout")
        mock_ha_client.return_value = mock_client

        main(["action", "light.living_room", "show_details"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Failed" in out


class TestViewHistory:
    @patch("ha_workflow.cli.subprocess.run")
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_view_history_copies_log(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        mock_run: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_history.return_value = [
            {
                "entity_id": "light.living_room",
                "state": "off",
                "last_changed": "2026-03-22T10:00:00.000000+00:00",
            },
            {
                "entity_id": "light.living_room",
                "state": "on",
                "last_changed": "2026-03-22T10:30:00.000000+00:00",
            },
        ]
        mock_ha_client.return_value = mock_client

        main(["action", "light.living_room", "view_history"])

        mock_run.assert_called_once()
        clipboard = mock_run.call_args[1]["input"].decode("utf-8")
        assert "light.living_room" in clipboard
        assert "10:00:00" in clipboard
        assert "off" in clipboard
        assert "10:30:00" in clipboard
        assert "on" in clipboard
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "2 state changes" in out

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_view_history_no_changes(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_history.return_value = []
        mock_ha_client.return_value = mock_client

        main(["action", "light.living_room", "view_history"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "No history found" in out

    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_view_history_failure(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_history.side_effect = Exception("network error")
        mock_ha_client.return_value = mock_client

        main(["action", "light.living_room", "view_history"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Failed" in out


class TestFormatAsYaml:
    def test_simple_dict(self) -> None:
        from ha_workflow.cli import _format_as_yaml

        result = _format_as_yaml({"key": "value", "num": 42})
        assert "key: value" in result
        assert "num: 42" in result

    def test_nested_dict(self) -> None:
        from ha_workflow.cli import _format_as_yaml

        result = _format_as_yaml({"outer": {"inner": "val"}})
        assert "outer:" in result
        assert "  inner: val" in result

    def test_list(self) -> None:
        from ha_workflow.cli import _format_as_yaml

        result = _format_as_yaml({"items": ["a", "b"]})
        assert "items:" in result
        assert "- a" in result
        assert "- b" in result

    def test_none_and_bool(self) -> None:
        from ha_workflow.cli import _format_as_yaml

        result = _format_as_yaml({"x": None, "y": True, "z": False})
        assert "x: null" in result
        assert "y: true" in result
        assert "z: false" in result


class TestFormatHistoryEntry:
    def test_normal_entry(self) -> None:
        from ha_workflow.cli import _format_history_entry

        entry = {
            "state": "on",
            "last_changed": "2026-03-22T10:30:00.123+00:00",
        }
        result = _format_history_entry(entry)
        assert "10:30:00" in result
        assert "on" in result

    def test_missing_fields(self) -> None:
        from ha_workflow.cli import _format_history_entry

        result = _format_history_entry({})
        assert "?" in result


# ---------------------------------------------------------------------------
# ha_client.get_history() tests
# ---------------------------------------------------------------------------


class TestHAClientGetHistory:
    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_get_history_returns_flat_list(self, mock_urlopen: MagicMock) -> None:
        from ha_workflow.config import Config
        from ha_workflow.ha_client import HAClient

        changes = [
            {"state": "off", "last_changed": "2026-03-22T10:00:00"},
            {"state": "on", "last_changed": "2026-03-22T10:30:00"},
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([changes]).encode("utf-8")
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        config = MagicMock(spec=Config)
        config.ha_url = "http://ha.local:8123"
        config.ha_token = "test-token"
        client = HAClient(config)
        result = client.get_history("light.test", hours=1)
        assert len(result) == 2
        assert result[0]["state"] == "off"
        assert result[1]["state"] == "on"

    @patch("ha_workflow.ha_client.urllib.request.urlopen")
    def test_get_history_empty(self, mock_urlopen: MagicMock) -> None:
        from ha_workflow.config import Config
        from ha_workflow.ha_client import HAClient

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[[]]"
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        config = MagicMock(spec=Config)
        config.ha_url = "http://ha.local:8123"
        config.ha_token = "test-token"
        client = HAClient(config)
        result = client.get_history("light.test")
        assert result == []

    def test_get_history_connection_error_returns_empty(self) -> None:
        from ha_workflow.config import Config
        from ha_workflow.ha_client import HAClient

        config = MagicMock(spec=Config)
        config.ha_url = "http://nonexistent:9999"
        config.ha_token = "test-token"
        client = HAClient(config, timeout=1)
        result = client.get_history("light.test")
        assert result == []


# ---------------------------------------------------------------------------
# Copy / Open action handlers
# ---------------------------------------------------------------------------


class TestCopyAction:
    @patch("ha_workflow.cli.subprocess.run")
    @patch("ha_workflow.cli.Config.from_env")
    def test_copy_entity_id(
        self,
        mock_from_env: MagicMock,
        mock_run: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        main(["action", "light.living_room", "copy_entity_id"])
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["input"] == b"light.living_room"
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Copied: light.living_room" in out

    @patch("ha_workflow.cli.subprocess.run")
    @patch("ha_workflow.cli.HAClient")
    @patch("ha_workflow.cli.Config.from_env")
    def test_copy_entity_details(
        self,
        mock_from_env: MagicMock,
        mock_ha_client: MagicMock,
        mock_run: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.get_state.return_value = {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"friendly_name": "Living Room Light"},
        }
        mock_ha_client.return_value = mock_client
        main(["action", "light.living_room", "copy_entity_details"])
        mock_run.assert_called_once()
        clipboard = mock_run.call_args[1]["input"].decode("utf-8")
        assert "entity_id: light.living_room" in clipboard
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "Copied details" in out


class TestOpenAction:
    @patch("ha_workflow.cli.subprocess.run")
    @patch("ha_workflow.cli.Config.from_env")
    def test_open_entity(
        self,
        mock_from_env: MagicMock,
        mock_run: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(ha_url="http://ha.local:8123")
        main(["action", "light.living_room", "open_entity"])
        mock_run.assert_called_once()
        url = mock_run.call_args[0][0][1]
        assert "config/entities?filter=light.living_room" in url

    @patch("ha_workflow.cli.subprocess.run")
    @patch("ha_workflow.cli.Config.from_env")
    def test_open_history(
        self,
        mock_from_env: MagicMock,
        mock_run: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(ha_url="http://ha.local:8123")
        main(["action", "light.living_room", "open_history"])
        url = mock_run.call_args[0][0][1]
        assert "history?entity_id=light.living_room" in url

    @patch("ha_workflow.cli._lookup_device_id")
    @patch("ha_workflow.cli.Config.from_env")
    def test_open_device_no_device(
        self,
        mock_from_env: MagicMock,
        mock_lookup_id: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(ha_url="http://ha.local:8123")
        mock_lookup_id.return_value = ""
        main(["action", "light.living_room", "open_device"])
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert "No device found" in out


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


class TestLookupHelpers:
    def test_lookup_device_id_found(self) -> None:
        from ha_workflow.cli import _lookup_device_id

        client = MagicMock()
        client.get_entity_registry.return_value = [
            {"entity_id": "light.lamp", "device_id": "dev_1"},
        ]
        assert _lookup_device_id(client, "light.lamp") == "dev_1"

    def test_lookup_device_id_not_found(self) -> None:
        from ha_workflow.cli import _lookup_device_id

        client = MagicMock()
        client.get_entity_registry.return_value = []
        assert _lookup_device_id(client, "light.lamp") == ""

    def test_lookup_area_id_direct(self) -> None:
        from ha_workflow.cli import _lookup_area_id

        client = MagicMock()
        client.get_entity_registry.return_value = [
            {"entity_id": "light.lamp", "area_id": "kitchen", "device_id": ""},
        ]
        assert _lookup_area_id(client, "light.lamp") == "kitchen"

    def test_lookup_area_id_via_device(self) -> None:
        from ha_workflow.cli import _lookup_area_id

        client = MagicMock()
        client.get_entity_registry.return_value = [
            {"entity_id": "light.lamp", "area_id": "", "device_id": "dev_1"},
        ]
        client.get_device_registry.return_value = [
            {"id": "dev_1", "area_id": "living_room"},
        ]
        assert _lookup_area_id(client, "light.lamp") == "living_room"
