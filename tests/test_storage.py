"""Tests for per-server storage isolation (server key, dirs, legacy migration).

Every test runs against both copies of the library code — ``ha_workflow``
(used by ``cli.py``) and ``ha_lib`` (used by the Alfred scripts) — so the two
cannot drift apart.
"""

from __future__ import annotations

import importlib
import json
import sqlite3
import threading
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

_PACKAGES = ["ha_workflow", "ha_lib"]


class _Lib:
    """The config/cache/usage/storage modules of one library copy."""

    def __init__(self, package: str) -> None:
        self.package = package
        self.config: ModuleType = importlib.import_module(f"{package}.config")
        self.cache: ModuleType = importlib.import_module(f"{package}.cache")
        self.usage: ModuleType = importlib.import_module(f"{package}.usage")
        self.storage: ModuleType = importlib.import_module(f"{package}.storage")

    def make_config(self, tmp_path: Path, ha_url: str = "http://ha.local:8123") -> Any:
        return self.config.Config.from_env(
            {
                "HA_URL": ha_url,
                "HA_TOKEN": "secret-token-value",
                "alfred_workflow_cache": str(tmp_path / "cache"),
                "alfred_workflow_data": str(tmp_path / "data"),
            }
        )


@pytest.fixture(params=_PACKAGES)
def lib(request: pytest.FixtureRequest) -> _Lib:
    return _Lib(request.param)


# ---------------------------------------------------------------------------
# server_key normalization
# ---------------------------------------------------------------------------


class TestServerKey:
    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("http://ha.local:8123", "http://ha.local:8123/"),
            ("http://ha.local:8123", "HTTP://HA.LOCAL:8123"),
            ("http://ha.local", "http://ha.local:80"),
            ("https://ha.example.com", "https://ha.example.com:443/"),
            ("http://ha.local:8123", "  http://ha.local:8123  "),
            ("https://ha.example.com/ha", "https://ha.example.com/ha/"),
            ("http://ha.local:8123", "http://user:pw@ha.local:8123"),
        ],
    )
    def test_equivalent_urls_same_key(self, lib: _Lib, a: str, b: str) -> None:
        assert lib.config.server_key_for_url(a) == lib.config.server_key_for_url(b)

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("http://ha.local:8123", "http://demo.local:8123"),
            ("http://ha.local:8123", "http://ha.local:8124"),
            ("http://ha.local:8123", "https://ha.local:8123"),
            ("https://ha.example.com:443", "https://ha.example.com:8443"),
            ("https://ha.example.com/a", "https://ha.example.com/b"),
        ],
    )
    def test_different_servers_different_keys(self, lib: _Lib, a: str, b: str) -> None:
        assert lib.config.server_key_for_url(a) != lib.config.server_key_for_url(b)

    def test_key_is_12_hex_chars(self, lib: _Lib) -> None:
        key = lib.config.server_key_for_url("http://ha.local:8123")
        assert len(key) == 12
        int(key, 16)  # raises if not hex

    def test_normalized_url_strips_userinfo_and_default_port(self, lib: _Lib) -> None:
        norm = lib.config.normalize_server_url("HTTPS://user:pw@HA.Example.com:443/")
        assert norm == "https://ha.example.com"

    def test_normalize_keeps_ipv6_brackets(self, lib: _Lib) -> None:
        norm = lib.config.normalize_server_url("http://[::1]:8123/")
        assert norm == "http://[::1]:8123"

    def test_both_packages_agree(self) -> None:
        url = "http://ha.local:8123"
        keys = {_Lib(p).config.server_key_for_url(url) for p in _PACKAGES}
        assert len(keys) == 1


# ---------------------------------------------------------------------------
# Config per-server dirs
# ---------------------------------------------------------------------------


class TestConfigServerDirs:
    def test_server_dirs_under_servers_subdir(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        key = lib.config.server_key_for_url("http://ha.local:8123")
        assert cfg.server_key == key
        assert cfg.server_cache_dir == tmp_path / "cache" / "servers" / key
        assert cfg.server_data_dir == tmp_path / "data" / "servers" / key

    def test_server_label_is_host_without_secrets(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        cfg = lib.make_config(tmp_path, "https://user:pw@HA.example.com:443/")
        assert cfg.server_label == "ha.example.com"

    def test_key_override_is_the_single_seam(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.config.Config(
            ha_url="http://ha.local:8123",
            ha_token="t",
            cache_ttl=60,
            cache_dir=tmp_path / "cache",
            data_dir=tmp_path / "data",
            server_key_override="profile-demo",
        )
        assert cfg.server_key == "profile-demo"
        assert cfg.server_cache_dir == tmp_path / "cache" / "servers" / "profile-demo"
        assert cfg.server_data_dir == tmp_path / "data" / "servers" / "profile-demo"

    @pytest.mark.parametrize(
        "bad", ["../escape", "a/b", "..", ".hidden", "-lead", "sp ace", "x" * 65]
    )
    def test_key_override_rejects_unsafe_values(
        self, lib: _Lib, tmp_path: Path, bad: str
    ) -> None:
        errors = importlib.import_module(f"{lib.package}.errors")
        cfg = lib.config.Config(
            ha_url="http://ha.local:8123",
            ha_token="t",
            cache_ttl=60,
            cache_dir=tmp_path / "cache",
            data_dir=tmp_path / "data",
            server_key_override=bad,
        )
        with pytest.raises(errors.ConfigError):
            _ = cfg.server_key


# ---------------------------------------------------------------------------
# prepare_server_storage — dirs + server.json
# ---------------------------------------------------------------------------


class TestPrepareServerStorage:
    def test_server_info_write_failure_does_not_break_callers(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        cfg = lib.make_config(tmp_path)
        with patch.object(
            lib.storage, "_write_server_info", side_effect=OSError("disk full")
        ):
            lib.storage.prepare_server_storage(cfg)  # must not raise
        assert cfg.server_data_dir.is_dir()

    def test_creates_dirs(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        lib.storage.prepare_server_storage(cfg)
        assert cfg.server_cache_dir.is_dir()
        assert cfg.server_data_dir.is_dir()

    def test_writes_server_json_without_token(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path, "http://user:pw@HA.local:8123/")
        lib.storage.prepare_server_storage(cfg)
        info_path = cfg.server_data_dir / "server.json"
        raw = info_path.read_text()
        info = json.loads(raw)
        assert info["url"] == "http://ha.local:8123"
        assert info["key"] == cfg.server_key
        assert "created" in info
        assert "secret-token-value" not in raw
        assert "pw" not in raw
        assert "token" not in {k.lower() for k in info}

    def test_server_json_not_rewritten(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        lib.storage.prepare_server_storage(cfg)
        info_path = cfg.server_data_dir / "server.json"
        info_path.write_text('{"url": "x", "created": "keep-me"}')
        lib.storage.prepare_server_storage(cfg)
        assert json.loads(info_path.read_text())["created"] == "keep-me"

    def test_open_cache_uses_server_dir(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        cache = lib.cache.open_cache(cfg)
        cache.close()
        assert (cfg.server_cache_dir / "entities.db").exists()
        assert not (tmp_path / "cache" / "entities.db").exists()
        assert (cfg.server_data_dir / "server.json").exists()

    def test_open_usage_uses_server_dir(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        tracker = lib.usage.open_usage_tracker(cfg)
        tracker.close()
        assert (cfg.server_data_dir / "usage.db").exists()
        assert not (tmp_path / "data" / "usage.db").exists()


# ---------------------------------------------------------------------------
# Switching HA_URL isolates caches and usage
# ---------------------------------------------------------------------------


class TestServerIsolation:
    def test_usage_isolated_per_server(self, lib: _Lib, tmp_path: Path) -> None:
        cfg_a = lib.make_config(tmp_path, "http://house-a.local:8123")
        cfg_b = lib.make_config(tmp_path, "http://house-b.local:8123")

        tracker_a = lib.usage.open_usage_tracker(cfg_a)
        tracker_a.record_usage("light.kitchen")
        tracker_a.close()

        tracker_b = lib.usage.open_usage_tracker(cfg_b)
        assert tracker_b.get_usage_record("light.kitchen") is None
        tracker_b.close()

        tracker_a = lib.usage.open_usage_tracker(cfg_a)
        assert tracker_a.get_usage_record("light.kitchen") is not None
        tracker_a.close()

    def test_cache_isolated_per_server(self, lib: _Lib, tmp_path: Path) -> None:
        entities_mod = importlib.import_module(f"{lib.package}.entities")
        cfg_a = lib.make_config(tmp_path, "http://house-a.local:8123")
        cfg_b = lib.make_config(tmp_path, "http://house-b.local:8123")

        cache_a = lib.cache.open_cache(cfg_a)
        cache_a.refresh(
            [
                entities_mod.Entity.from_state_dict(
                    {
                        "entity_id": "light.kitchen",
                        "state": "on",
                        "attributes": {"friendly_name": "Kitchen"},
                        "last_changed": "",
                        "last_updated": "",
                    }
                )
            ]
        )
        cache_a.close()

        cache_b = lib.cache.open_cache(cfg_b)
        assert cache_b.get_all() == []
        cache_b.close()

        cache_a = lib.cache.open_cache(cfg_a)
        assert [e.entity_id for e in cache_a.get_all()] == ["light.kitchen"]
        cache_a.close()


# ---------------------------------------------------------------------------
# Legacy flat-file migration
# ---------------------------------------------------------------------------


def _make_legacy_usage(data_dir: Path, entity_id: str = "light.legacy") -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(data_dir / "usage.db"))
    conn.execute(
        "CREATE TABLE usage_stats (entity_id TEXT PRIMARY KEY, "
        "use_count INTEGER NOT NULL DEFAULT 0, last_used_at REAL NOT NULL)"
    )
    conn.execute(
        "INSERT INTO usage_stats (entity_id, use_count, last_used_at) "
        "VALUES (?, 7, 1000.0)",
        (entity_id,),
    )
    conn.commit()
    conn.close()


def _make_legacy_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "entities.db").write_bytes(b"legacy-entities")
    (cache_dir / "refresh.log").write_text("old log")


class TestLegacyMigration:
    def test_moves_legacy_files_into_current_server(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        cfg = lib.make_config(tmp_path)
        _make_legacy_usage(tmp_path / "data")
        _make_legacy_cache(tmp_path / "cache")

        lib.storage.prepare_server_storage(cfg)

        assert not (tmp_path / "data" / "usage.db").exists()
        assert not (tmp_path / "cache" / "entities.db").exists()
        assert not (tmp_path / "cache" / "refresh.log").exists()
        assert (cfg.server_cache_dir / "entities.db").read_bytes() == b"legacy-entities"
        assert (cfg.server_cache_dir / "refresh.log").read_text() == "old log"

    def test_usage_history_preserved(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        _make_legacy_usage(tmp_path / "data")

        tracker = lib.usage.open_usage_tracker(cfg)
        record = tracker.get_usage_record("light.legacy")
        tracker.close()
        assert record is not None
        assert record.use_count == 7

    def test_moves_sqlite_sidecars(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        _make_legacy_usage(tmp_path / "data")
        (tmp_path / "data" / "usage.db-wal").write_bytes(b"")
        (tmp_path / "data" / "usage.db-shm").write_bytes(b"")

        lib.storage.prepare_server_storage(cfg)

        assert not (tmp_path / "data" / "usage.db-wal").exists()
        assert not (tmp_path / "data" / "usage.db-shm").exists()
        assert (cfg.server_data_dir / "usage.db-wal").exists()
        assert (cfg.server_data_dir / "usage.db-shm").exists()

    def test_idempotent(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        _make_legacy_usage(tmp_path / "data")

        first = lib.storage.migrate_legacy_storage(cfg)
        second = lib.storage.migrate_legacy_storage(cfg)

        assert "usage.db" in first
        assert second == []
        assert (cfg.server_data_dir / "usage.db").exists()

    def test_runs_only_once_even_for_another_server(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        cfg_a = lib.make_config(tmp_path, "http://house-a.local:8123")
        cfg_b = lib.make_config(tmp_path, "http://house-b.local:8123")
        lib.storage.prepare_server_storage(cfg_a)  # no legacy yet → marker written

        # A stray legacy file appearing later must not leak into server B.
        _make_legacy_usage(tmp_path / "data")
        lib.storage.prepare_server_storage(cfg_b)

        assert not (cfg_b.server_data_dir / "usage.db").exists()
        assert (tmp_path / "data" / "usage.db").exists()

    def test_never_clobbers_existing_server_file(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        cfg = lib.make_config(tmp_path)
        cfg.server_data_dir.mkdir(parents=True)
        (cfg.server_data_dir / "usage.db").write_bytes(b"current")
        (tmp_path / "data" / "usage.db").write_bytes(b"legacy")

        moved = lib.storage.migrate_legacy_storage(cfg)

        assert moved == []
        assert (cfg.server_data_dir / "usage.db").read_bytes() == b"current"
        assert (tmp_path / "data" / "usage.db").read_bytes() == b"legacy"

    def test_tolerates_file_vanishing_mid_migration(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        cfg = lib.make_config(tmp_path)
        _make_legacy_usage(tmp_path / "data")

        with patch(
            f"{lib.package}.storage.os.replace",
            side_effect=FileNotFoundError("gone"),
        ):
            moved = lib.storage.migrate_legacy_storage(cfg)

        assert moved == []

    def test_concurrent_invocations(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        _make_legacy_usage(tmp_path / "data")
        _make_legacy_cache(tmp_path / "cache")

        results: list[list[str]] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(8)

        def run() -> None:
            try:
                barrier.wait()
                results.append(lib.storage.migrate_legacy_storage(cfg))
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=run) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        moved_all = [name for r in results for name in r]
        assert moved_all.count("usage.db") == 1
        assert moved_all.count("entities.db") == 1

        tracker = lib.usage.open_usage_tracker(cfg)
        record = tracker.get_usage_record("light.legacy")
        tracker.close()
        assert record is not None
        assert record.use_count == 7

    def test_no_legacy_files_is_noop(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = lib.make_config(tmp_path)
        assert lib.storage.migrate_legacy_storage(cfg) == []


# ---------------------------------------------------------------------------
# System commands act on the current server only
# ---------------------------------------------------------------------------


def _seed_usage(lib: _Lib, cfg: Any, entity_id: str) -> None:
    tracker = lib.usage.open_usage_tracker(cfg)
    tracker.record_usage(entity_id)
    tracker.close()


def _has_usage(lib: _Lib, cfg: Any, entity_id: str) -> bool:
    tracker = lib.usage.open_usage_tracker(cfg)
    try:
        return tracker.get_usage_record(entity_id) is not None
    finally:
        tracker.close()


class TestClearScopedToServer:
    def test_cli_usage_clear_only_current_server(self, tmp_path: Path) -> None:
        import ha_workflow.cli as cli

        lib = _Lib("ha_workflow")
        cfg_a = lib.make_config(tmp_path, "http://house-a.local:8123")
        cfg_b = lib.make_config(tmp_path, "http://house-b.local:8123")
        _seed_usage(lib, cfg_a, "light.a")
        _seed_usage(lib, cfg_b, "light.b")

        with (
            patch.object(cli.Config, "from_env", return_value=cfg_a),
            patch.object(cli, "notify"),
        ):
            cli._cmd_system_action("usage_clear")

        assert not _has_usage(lib, cfg_a, "light.a")
        assert _has_usage(lib, cfg_b, "light.b")

    def test_action_runner_usage_clear_only_current_server(
        self, tmp_path: Path
    ) -> None:
        import ha_workflow.scripts.action_runner as runner

        lib = _Lib("ha_lib")
        cfg_a = lib.make_config(tmp_path, "http://house-a.local:8123")
        cfg_b = lib.make_config(tmp_path, "http://house-b.local:8123")
        _seed_usage(lib, cfg_a, "light.a")
        _seed_usage(lib, cfg_b, "light.b")

        with patch.object(runner, "notify"):
            runner._cmd_system(cfg_a, "usage_clear")

        assert not _has_usage(lib, cfg_a, "light.a")
        assert _has_usage(lib, cfg_b, "light.b")

    @pytest.mark.parametrize(
        "module", ["ha_workflow.cli", "ha_workflow.scripts.search_filter"]
    )
    def test_refresh_lock_and_log_per_server(self, module: str, tmp_path: Path) -> None:
        mod = importlib.import_module(module)
        package = "ha_workflow" if module == "ha_workflow.cli" else "ha_lib"
        cfg = _Lib(package).make_config(tmp_path)

        with patch.object(mod.subprocess, "Popen") as popen:
            popen.return_value.pid = 4242
            mod._maybe_refresh_background(cfg)

        assert (cfg.server_cache_dir / ".refresh.lock").read_text() == "4242"
        assert (cfg.server_cache_dir / "refresh.log").exists()
        assert not (tmp_path / "cache" / ".refresh.lock").exists()

    @pytest.mark.parametrize(
        "module", ["ha_workflow.cli", "ha_workflow.scripts.search_filter"]
    )
    def test_usage_clear_subtitle_names_current_server(
        self, module: str, tmp_path: Path
    ) -> None:
        mod = importlib.import_module(module)
        package = "ha_workflow" if module == "ha_workflow.cli" else "ha_lib"
        cfg = _Lib(package).make_config(tmp_path, "http://house-a.local:8123")

        items = mod._match_system_commands("system clear", cfg)

        usage_items = [i for i in items if "usage" in i.title.lower()]
        assert len(usage_items) == 1
        assert "house-a.local:8123" in usage_items[0].subtitle


# ---------------------------------------------------------------------------
# Server profiles — storage keyed by profile identity
# ---------------------------------------------------------------------------

_LAKE_ID = "p-1a2b3c4d"


def _profile_config(lib: _Lib, tmp_path: Path, url: str, name: str = "Lake") -> Any:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "profiles.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profiles": [
                    {
                        "id": _LAKE_ID,
                        "name": name,
                        "urls": [url],
                        "token_source": "keychain",
                    }
                ],
            }
        )
    )
    return lib.config.Config.from_env(
        {
            "HA_URL": "http://ha.local:8123",
            "HA_TOKEN": "secret-token-value",
            "HA_SERVER": _LAKE_ID,
            "alfred_workflow_cache": str(tmp_path / "cache"),
            "alfred_workflow_data": str(data_dir),
        }
    )


class TestProfileStorage:
    def test_default_profile_keeps_url_hash_key(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        cfg = lib.make_config(tmp_path)
        assert cfg.server_id == "default"
        assert cfg.server_key == lib.config.server_key_for_url("http://ha.local:8123")

    def test_profile_key_survives_url_edit(self, lib: _Lib, tmp_path: Path) -> None:
        a = _profile_config(lib, tmp_path, "https://lake.example.net")
        b = _profile_config(lib, tmp_path, "https://lake-new.example.net")
        assert a.server_key == b.server_key == _LAKE_ID
        assert a.server_data_dir == b.server_data_dir

    def test_server_json_records_profile(self, lib: _Lib, tmp_path: Path) -> None:
        cfg = _profile_config(lib, tmp_path, "https://lake.example.net")
        lib.storage.prepare_server_storage(cfg)
        info = json.loads((cfg.server_data_dir / "server.json").read_text())
        assert info["profile_id"] == _LAKE_ID
        assert info["profile_name"] == "Lake"
        assert info["key"] == _LAKE_ID
        assert "secret-token-value" not in json.dumps(info)

    def test_server_json_follows_rename_and_url_edit(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        cfg = _profile_config(lib, tmp_path, "https://lake.example.net")
        lib.storage.prepare_server_storage(cfg)
        info_path = cfg.server_data_dir / "server.json"
        created = json.loads(info_path.read_text())["created"]
        cfg2 = _profile_config(lib, tmp_path, "https://cabin.example.net", "Cabin")
        lib.storage.prepare_server_storage(cfg2)
        info = json.loads((cfg2.server_data_dir / "server.json").read_text())
        assert info["profile_name"] == "Cabin"
        assert info["url"] == "https://cabin.example.net"
        assert info["created"] == created

    def test_default_server_json_has_profile_fields(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        cfg = lib.make_config(tmp_path)
        lib.storage.prepare_server_storage(cfg)
        info = json.loads((cfg.server_data_dir / "server.json").read_text())
        assert info["profile_id"] == "default"
        assert info["profile_name"] == "Default"

    def test_legacy_files_never_migrate_into_a_profile(
        self, lib: _Lib, tmp_path: Path
    ) -> None:
        (tmp_path / "data").mkdir(parents=True)
        (tmp_path / "data" / "usage.db").write_text("legacy")
        cfg = _profile_config(lib, tmp_path, "https://lake.example.net")
        lib.storage.prepare_server_storage(cfg)
        assert (tmp_path / "data" / "usage.db").exists()
        assert not (cfg.server_data_dir / "usage.db").exists()
        assert not (tmp_path / "data" / "servers" / ".legacy-migrated").exists()
        # The default server still receives them afterwards.
        default = lib.make_config(tmp_path)
        lib.storage.prepare_server_storage(default)
        assert (default.server_data_dir / "usage.db").read_text() == "legacy"
