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


SAMPLE_ENTITIES: list[Entity] = [
    _entity("light.living_room", "on", "Living Room Light"),
    _entity("switch.kitchen", "off", "Kitchen Switch"),
    _entity("sensor.temperature", "23.5", "Temperature"),
]


def _mock_cache(
    entities: list[Entity] | None = None,
    cache_age: float | None = 5.0,
    stale: bool = False,
) -> MagicMock:
    """Build a mock EntityCache."""
    cache = MagicMock()
    cache.get_all.return_value = entities if entities is not None else SAMPLE_ENTITIES
    cache.get_cache_age.return_value = cache_age
    cache.is_stale.return_value = stale
    return cache


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
    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_returns_entities(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()

        main(["search", "living"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        # fuzzy_search will filter; at least one item should match
        assert len(data["items"]) >= 1
        item = data["items"][0]
        assert "title" in item
        assert "variables" in item
        assert "entity_id" in item["variables"]

    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_no_results(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()

        main(["search", "zzzznothing"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert data["items"][0]["title"] == "No matching entities"
        assert data["items"][0]["valid"] is False

    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_empty_query_returns_all(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()

        main(["search"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert len(data["items"]) == 3

    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_stale_cache_sets_rerun(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(stale=True)

        main(["search", "light"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert data.get("rerun") == 1.0
        mock_bg_refresh.assert_called_once()

    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_first_run_shows_loading_and_triggers_bg_refresh(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache(cache_age=None)

        main(["search", "light"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        assert "Loading" in data["items"][0]["title"]
        assert data.get("rerun") == 1.0
        mock_bg_refresh.assert_called_once()

    @patch("ha_workflow.cli._maybe_refresh_background")
    @patch("ha_workflow.cli.open_cache")
    @patch("ha_workflow.cli.Config.from_env")
    def test_search_items_have_domain_subtitle(
        self,
        mock_from_env: MagicMock,
        mock_open_cache: MagicMock,
        mock_bg_refresh: MagicMock,
        capsys: object,
    ) -> None:
        mock_from_env.return_value = MagicMock(cache_ttl=60)
        mock_open_cache.return_value = _mock_cache()

        main(["search", "kitchen"])

        out = capsys.readouterr().out  # type: ignore[union-attr]
        data = json.loads(out)
        item = data["items"][0]
        assert "switch" in item["subtitle"]


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
