"""Tests for active-server resolution in ``Config.from_env()``.

Resolution order: ``HA_SERVER`` env > ``active_server`` file > ``default``.
Runs against both library copies; tokens come from the in-memory store.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

_PACKAGES = ["ha_workflow", "ha_lib"]
_LAKE_ID = "p-1a2b3c4d"
_LAKE_URL = "https://lake.example.net"
_LAKE_TOKEN = "lake.token.value"


class _Lib:
    def __init__(self, package: str) -> None:
        self.package = package
        self.config: ModuleType = importlib.import_module(f"{package}.config")
        self.profiles: ModuleType = importlib.import_module(f"{package}.profiles")
        self.keychain: ModuleType = importlib.import_module(f"{package}.keychain")
        self.errors: ModuleType = importlib.import_module(f"{package}.errors")
        client_mod = "ha_client" if package == "ha_workflow" else "client"
        self.client: ModuleType = importlib.import_module(f"{package}.{client_mod}")


@pytest.fixture(params=_PACKAGES)
def lib(request: pytest.FixtureRequest) -> _Lib:
    return _Lib(request.param)


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {
        "HA_URL": "http://ha.local:8123",
        "HA_TOKEN": "default-token",
        "alfred_workflow_cache": str(tmp_path / "cache"),
        "alfred_workflow_data": str(tmp_path / "data"),
    }
    env.update(extra)
    return env


def _write_profiles(tmp_path: Path, payload: Any = None) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = {
            "schema_version": 1,
            "profiles": [
                {
                    "id": _LAKE_ID,
                    "name": "Lake House",
                    "urls": [_LAKE_URL],
                    "token_source": "keychain",
                    "badge": "LAKE",
                    "preferred_label": "lake_fav",
                }
            ],
        }
    text = payload if isinstance(payload, str) else json.dumps(payload)
    (data_dir / "profiles.json").write_text(text)


def _store(lib: _Lib, token: str = _LAKE_TOKEN) -> Any:
    store = lib.keychain.InMemoryTokenStore()
    store.set(_LAKE_ID, token)
    store.reads = 0
    return store


# ---------------------------------------------------------------------------
# Active pointer file
# ---------------------------------------------------------------------------


class TestActivePointer:
    def test_missing_is_none(self, lib: _Lib, tmp_path: Path) -> None:
        assert lib.profiles.read_active_server(tmp_path) is None

    def test_round_trip_atomic(self, lib: _Lib, tmp_path: Path) -> None:
        lib.profiles.write_active_server(tmp_path, _LAKE_ID)
        assert lib.profiles.read_active_server(tmp_path) == _LAKE_ID
        assert (tmp_path / "active_server").read_text() == _LAKE_ID + "\n"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["active_server"]

    def test_blank_file_is_none(self, lib: _Lib, tmp_path: Path) -> None:
        (tmp_path / "active_server").write_text("  \n")
        assert lib.profiles.read_active_server(tmp_path) is None

    def test_write_rejects_bad_id(self, lib: _Lib, tmp_path: Path) -> None:
        with pytest.raises(lib.errors.ConfigError):
            lib.profiles.write_active_server(tmp_path, "../evil")


# ---------------------------------------------------------------------------
# Resolution order
# ---------------------------------------------------------------------------


class TestResolution:
    def test_default_when_nothing_set(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.config.Config.from_env(_env(tmp_path))
        assert cfg.server_id == "default"
        assert cfg.server_key == lib.config.server_key_for_url("http://ha.local:8123")
        assert cfg.server_count == 1
        assert cfg.server_name == "Default"
        assert cfg.get_token() == "default-token"

    def test_pointer_file_selects_profile(self, lib: _Lib, tmp_path: Path) -> None:
        _write_profiles(tmp_path)
        lib.profiles.write_active_server(tmp_path / "data", _LAKE_ID)
        store = _store(lib)
        cfg = lib.config.Config.from_env(_env(tmp_path), token_store=store)
        assert cfg.server_id == _LAKE_ID
        assert cfg.ha_url == _LAKE_URL
        assert cfg.server_key == _LAKE_ID
        assert cfg.server_cache_dir == tmp_path / "cache" / "servers" / _LAKE_ID
        assert cfg.server_name == "Lake House"
        assert cfg.server_badge == "LAKE"
        assert cfg.server_prefix == "LAKE"
        assert cfg.server_count == 2
        assert cfg.preferred_label == "lake_fav"

    def test_env_overrides_pointer(self, lib: _Lib, tmp_path: Path) -> None:
        _write_profiles(tmp_path)
        lib.profiles.write_active_server(tmp_path / "data", _LAKE_ID)
        cfg = lib.config.Config.from_env(_env(tmp_path, HA_SERVER="default"))
        assert cfg.server_id == "default"
        assert cfg.ha_url == "http://ha.local:8123"

    def test_env_selects_profile_without_pointer(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        _write_profiles(tmp_path)
        cfg = lib.config.Config.from_env(
            _env(tmp_path, HA_SERVER=_LAKE_ID), token_store=_store(lib)
        )
        assert cfg.server_id == _LAKE_ID

    def test_blank_env_falls_through_to_pointer(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        _write_profiles(tmp_path)
        lib.profiles.write_active_server(tmp_path / "data", _LAKE_ID)
        cfg = lib.config.Config.from_env(
            _env(tmp_path, HA_SERVER="  "), token_store=_store(lib)
        )
        assert cfg.server_id == _LAKE_ID

    def test_keychain_profile_needs_no_ha_url(self, lib: _Lib, tmp_path: Path) -> None:
        _write_profiles(tmp_path)
        env = _env(tmp_path, HA_SERVER=_LAKE_ID)
        del env["HA_URL"]
        del env["HA_TOKEN"]
        cfg = lib.config.Config.from_env(env, token_store=_store(lib))
        assert cfg.ha_url == _LAKE_URL
        assert cfg.server_count == 1

    def test_default_display_name_override(self, lib: _Lib, tmp_path: Path) -> None:
        _write_profiles(
            tmp_path, {"schema_version": 1, "default": {"name": "Home"}, "profiles": []}
        )
        cfg = lib.config.Config.from_env(_env(tmp_path))
        assert cfg.server_name == "Home"
        assert cfg.server_prefix == "Home"


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_stale_pointer_raises(self, lib: _Lib, tmp_path: Path) -> None:
        _write_profiles(tmp_path)
        lib.profiles.write_active_server(tmp_path / "data", "p-ffffffff")
        with pytest.raises(lib.errors.ConfigError, match="ha server:") as info:
            lib.config.Config.from_env(_env(tmp_path))
        assert "p-ffffffff" in str(info.value)

    def test_stale_env_raises(self, lib: _Lib, tmp_path: Path) -> None:
        with pytest.raises(lib.errors.ConfigError, match="not configured"):
            lib.config.Config.from_env(_env(tmp_path, HA_SERVER="p-ffffffff"))

    @pytest.mark.parametrize("bad", ["../x", "P-1A2B3C4D", "lake", "p-1a2b"])
    def test_malformed_id_raises(self, lib: _Lib, tmp_path: Path, bad: str) -> None:
        with pytest.raises(lib.errors.ConfigError, match="server id"):
            lib.config.Config.from_env(_env(tmp_path, HA_SERVER=bad))

    def test_invalid_file_with_profile_selected_raises(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        _write_profiles(tmp_path, "{broken")
        with pytest.raises(lib.errors.ConfigError, match="invalid"):
            lib.config.Config.from_env(_env(tmp_path, HA_SERVER=_LAKE_ID))

    def test_invalid_file_default_still_works(self, lib: _Lib, tmp_path: Path) -> None:
        _write_profiles(tmp_path, "{broken")
        cfg = lib.config.Config.from_env(_env(tmp_path))
        assert cfg.server_id == "default"
        # A broken file may be hiding other servers: keep the wrong-house
        # signals on.
        assert cfg.server_count > 1

    def test_default_selected_without_ha_url_raises(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        env = _env(tmp_path)
        del env["HA_URL"]
        with pytest.raises(lib.errors.ConfigError, match="HA_URL"):
            lib.config.Config.from_env(env)

    def test_keychain_miss_raises_on_token_use(self, lib: _Lib, tmp_path: Path) -> None:
        _write_profiles(tmp_path)
        empty = lib.keychain.InMemoryTokenStore()
        cfg = lib.config.Config.from_env(
            _env(tmp_path, HA_SERVER=_LAKE_ID), token_store=empty
        )
        with pytest.raises(lib.errors.ConfigError, match="Lake House"):
            cfg.get_token()

    def test_keychain_error_raises_config_error(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        _write_profiles(tmp_path)
        store = _store(lib)
        with patch.object(
            store, "get", side_effect=lib.keychain.TokenStoreError("locked")
        ):
            cfg = lib.config.Config.from_env(
                _env(tmp_path, HA_SERVER=_LAKE_ID), token_store=store
            )
            with pytest.raises(lib.errors.ConfigError, match="Lake House"):
                cfg.get_token()


# ---------------------------------------------------------------------------
# Lazy token
# ---------------------------------------------------------------------------


class TestLazyToken:
    def test_from_env_never_reads_keychain(self, lib: _Lib, tmp_path: Path) -> None:
        _write_profiles(tmp_path)
        store = _store(lib)
        cfg = lib.config.Config.from_env(
            _env(tmp_path, HA_SERVER=_LAKE_ID), token_store=store
        )
        _ = (cfg.server_key, cfg.server_cache_dir, cfg.server_prefix)
        assert store.reads == 0
        assert cfg.get_token() == _LAKE_TOKEN
        assert cfg.get_token() == _LAKE_TOKEN
        assert store.reads == 1  # memoized

    def test_client_uses_resolved_token(self, lib: _Lib, tmp_path: Path) -> None:
        _write_profiles(tmp_path)
        cfg = lib.config.Config.from_env(
            _env(tmp_path, HA_SERVER=_LAKE_ID), token_store=_store(lib)
        )
        client = lib.client.HAClient(cfg)
        assert client._token == _LAKE_TOKEN
        assert client._base_url == _LAKE_URL

    def test_token_not_in_repr(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.config.Config.from_env(_env(tmp_path))
        assert "default-token" not in repr(cfg)
