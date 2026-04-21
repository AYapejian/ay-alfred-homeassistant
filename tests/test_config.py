"""Tests for ha_workflow.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from ha_workflow.config import Config
from ha_workflow.errors import ConfigError


def _base_env() -> dict[str, str]:
    return {"HA_URL": "http://ha.local:8123", "HA_TOKEN": "test-token"}


class TestConfigFromEnv:
    def test_minimal_valid(self) -> None:
        cfg = Config.from_env(_base_env())
        assert cfg.ha_url == "http://ha.local:8123"
        assert cfg.ha_token == "test-token"
        assert cfg.cache_ttl == 60

    def test_strips_trailing_slash(self) -> None:
        env = {**_base_env(), "HA_URL": "http://ha.local:8123/"}
        assert Config.from_env(env).ha_url == "http://ha.local:8123"

    def test_strips_whitespace(self) -> None:
        env = {"HA_URL": "  http://ha.local:8123  ", "HA_TOKEN": "  tok  "}
        cfg = Config.from_env(env)
        assert cfg.ha_url == "http://ha.local:8123"
        assert cfg.ha_token == "tok"

    def test_missing_ha_url_raises(self) -> None:
        with pytest.raises(ConfigError, match="HA_URL"):
            Config.from_env({"HA_TOKEN": "t"})

    def test_empty_ha_url_raises(self) -> None:
        with pytest.raises(ConfigError, match="HA_URL"):
            Config.from_env({"HA_URL": "", "HA_TOKEN": "t"})

    def test_missing_ha_token_raises(self) -> None:
        with pytest.raises(ConfigError, match="HA_TOKEN"):
            Config.from_env({"HA_URL": "http://ha.local"})

    def test_cache_ttl_override(self) -> None:
        env = {**_base_env(), "CACHE_TTL": "120"}
        assert Config.from_env(env).cache_ttl == 120

    def test_cache_ttl_zero_is_valid(self) -> None:
        env = {**_base_env(), "CACHE_TTL": "0"}
        assert Config.from_env(env).cache_ttl == 0

    def test_cache_ttl_negative_raises(self) -> None:
        env = {**_base_env(), "CACHE_TTL": "-1"}
        with pytest.raises(ConfigError, match="CACHE_TTL"):
            Config.from_env(env)

    def test_cache_ttl_non_integer_raises(self) -> None:
        env = {**_base_env(), "CACHE_TTL": "abc"}
        with pytest.raises(ConfigError, match="CACHE_TTL"):
            Config.from_env(env)

    def test_alfred_dirs_from_env(self) -> None:
        env = {
            **_base_env(),
            "alfred_workflow_cache": "/tmp/alfred-cache",
            "alfred_workflow_data": "/tmp/alfred-data",
        }
        cfg = Config.from_env(env)
        assert cfg.cache_dir == Path("/tmp/alfred-cache")
        assert cfg.data_dir == Path("/tmp/alfred-data")

    def test_dev_fallback_dirs(self) -> None:
        cfg = Config.from_env(_base_env())
        home = Path.home()
        assert cfg.cache_dir == home / ".cache" / "ha-workflow" / "cache"
        assert cfg.data_dir == home / ".cache" / "ha-workflow" / "data"

    def test_preferred_label_default(self) -> None:
        cfg = Config.from_env(_base_env())
        assert cfg.preferred_label == "alfred_preferred"

    def test_preferred_label_override(self) -> None:
        env = {**_base_env(), "HA_PREFERRED_LABEL": "my_favorites"}
        assert Config.from_env(env).preferred_label == "my_favorites"

    def test_preferred_label_lowercased(self) -> None:
        env = {**_base_env(), "HA_PREFERRED_LABEL": "  MixedCaseLabel  "}
        assert Config.from_env(env).preferred_label == "mixedcaselabel"

    def test_preferred_label_empty_falls_back_to_default(self) -> None:
        env = {**_base_env(), "HA_PREFERRED_LABEL": "   "}
        assert Config.from_env(env).preferred_label == "alfred_preferred"
