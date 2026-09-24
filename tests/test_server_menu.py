"""Tests for the ``ha server:`` listing.

Exercised through both entry points — the shipped Script Filter
(``search_filter.py``) and the dev CLI (``cli.py search``) — plus the
read-only per-server status reader in both library copies.
"""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

_LAKE_ID = "p-1a2b3c4d"
_CABIN_ID = "p-00c0ffee"
_PACKAGES = ["ha_workflow", "ha_lib"]


def _env(tmp_path: Path, with_default: bool = True, **extra: str) -> dict[str, str]:
    env = {
        "alfred_workflow_cache": str(tmp_path / "cache"),
        "alfred_workflow_data": str(tmp_path / "data"),
        "PATH": os.environ.get("PATH", ""),
    }
    if with_default:
        env["HA_URL"] = "http://ha.local:8123"
        env["HA_TOKEN"] = "default-token"
    env.update(extra)
    return env


def _profile(pid: str, name: str, url: str, **extra: Any) -> dict[str, Any]:
    entry = {"id": pid, "name": name, "urls": [url], "token_source": "keychain"}
    entry.update(extra)
    return entry


def _write_profiles(tmp_path: Path, payload: Any = None) -> None:
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    if payload is None:
        payload = {
            "schema_version": 1,
            "profiles": [
                _profile(_LAKE_ID, "Lake House", "https://lake.example.net"),
                _profile(_CABIN_ID, "Cabin", "http://cabin.local:8123"),
            ],
        }
    text = payload if isinstance(payload, str) else json.dumps(payload)
    (data / "profiles.json").write_text(text)


def _seed_cache(tmp_path: Path, key: str, count: int, age: float = 180.0) -> Path:
    server_cache = tmp_path / "cache" / "servers" / key
    server_cache.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(server_cache / "entities.db"))
    conn.executescript(
        "CREATE TABLE entities (entity_id TEXT PRIMARY KEY);"
        "CREATE TABLE cache_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
    )
    conn.executemany(
        "INSERT INTO entities VALUES (?)", [(f"light.l{i}",) for i in range(count)]
    )
    conn.execute(
        "INSERT INTO cache_meta VALUES ('last_refresh', ?)", (str(time.time() - age),)
    )
    conn.commit()
    conn.close()
    return server_cache


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _run_search_filter(
    query: str, env: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    mod = importlib.import_module("ha_workflow.scripts.search_filter")
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(mod.sys, "argv", ["search_filter.py", query]),
        patch.object(mod.Config, "from_env", side_effect=AssertionError("config used")),
        patch.object(mod.subprocess, "Popen", side_effect=AssertionError("spawned")),
    ):
        mod.main()
    return json.loads(capsys.readouterr().out)  # type: ignore[no-any-return]


def _run_cli(
    query: str, env: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    mod = importlib.import_module("ha_workflow.cli")
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(mod.Config, "from_env", side_effect=AssertionError("config used")),
        patch.object(mod.subprocess, "Popen", side_effect=AssertionError("spawned")),
    ):
        mod.main(["search", query])
    return json.loads(capsys.readouterr().out)  # type: ignore[no-any-return]


Runner = Callable[[str, dict[str, str], pytest.CaptureFixture[str]], dict[str, Any]]


@pytest.fixture(params=["search_filter", "cli"])
def run(request: pytest.FixtureRequest) -> Runner:
    return _run_search_filter if request.param == "search_filter" else _run_cli


def _titles(out: dict[str, Any]) -> list[str]:
    return [i["title"] for i in out["items"]]


def _by_title(out: dict[str, Any], title: str) -> dict[str, Any]:
    for item in out["items"]:
        if item["title"] == title:
            return item  # type: ignore[no-any-return]
    raise AssertionError(f"{title!r} not in {_titles(out)}")


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestRouting:
    @pytest.mark.parametrize("query", ["server:", "server", "SERVER:", " server: "])
    def test_server_query_routes_to_menu(
        self,
        run: Runner,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        query: str,
    ) -> None:
        out = run(query, _env(tmp_path), capsys)
        assert "Add server…" in _titles(out)

    @pytest.mark.parametrize("query", ["server room", "servers", "serverx:"])
    def test_other_queries_are_not_the_menu(self, query: str) -> None:
        menu = importlib.import_module("ha_workflow.server_menu")
        assert menu.parse_server_query(query) is None

    def test_filter_text_extracted(self) -> None:
        menu = importlib.import_module("ha_workflow.server_menu")
        assert menu.parse_server_query("server:lake") == "lake"
        assert menu.parse_server_query("server") == ""


# ---------------------------------------------------------------------------
# Listing states
# ---------------------------------------------------------------------------


class TestListing:
    def test_default_only(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = run("server:", _env(tmp_path), capsys)
        assert _titles(out) == ["✓ Default", "Add server…"]
        active = out["items"][0]
        assert active["subtitle"].startswith("Active · ha.local:8123")
        assert active["variables"] == {
            "entity_id": "__server__",
            "action": "server_switch::default",
            "domain": "__server__",
        }
        assert active["arg"] == "default"
        assert "uid" not in active
        assert active["icon"]["path"] == "icons/_server_active.png"

    def test_several_active_first_then_alphabetical(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_profiles(tmp_path)
        (tmp_path / "data" / "active_server").write_text(_LAKE_ID + "\n")
        _seed_cache(tmp_path, _LAKE_ID, 412)
        out = run("server:", _env(tmp_path), capsys)
        assert _titles(out) == [
            "✓ Lake House",
            "Cabin",
            "Default",
            "Add server…",
            "Edit servers file…",
        ]
        lake = out["items"][0]
        assert lake["subtitle"] == (
            "Active · lake.example.net · 412 entities · refreshed 3m ago"
        )
        cabin = _by_title(out, "Cabin")
        assert cabin["subtitle"] == ("cabin.local:8123 · no cached entities · ↵ switch")
        assert cabin["variables"]["action"] == f"server_switch::{_CABIN_ID}"
        assert cabin["icon"]["path"] == "icons/_server.png"

    def test_mods_route_to_server_actions_submenu(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_profiles(tmp_path)
        out = run("server:", _env(tmp_path), capsys)
        lake = _by_title(out, "Lake House")
        assert lake["mods"]["cmd"]["valid"] is True
        assert lake["mods"]["cmd"]["variables"] == {
            "entity_id": "__server__",
            "action": f"server_menu::{_LAKE_ID}",
            "domain": "__server__",
        }
        # ⌥ / ⌃ are wired to copy / open-in-HA in info.plist: blocked here.
        assert lake["mods"]["alt"]["valid"] is False
        assert lake["mods"]["ctrl"]["valid"] is False
        default = _by_title(out, "✓ Default")
        assert "Configure" in default["mods"]["alt"]["subtitle"]

    def test_filter_by_name_or_host(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_profiles(tmp_path)
        assert _titles(run("server:lake", _env(tmp_path), capsys))[0] == "Lake House"
        by_host = _titles(run("server:cabin.local", _env(tmp_path), capsys))
        assert by_host[0] == "Cabin"
        assert "Lake House" not in by_host
        assert "Add server…" in by_host

    def test_last_refresh_failure_shown(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_profiles(tmp_path)
        cache = _seed_cache(tmp_path, _CABIN_ID, 7, age=3600)
        err = {
            "items": [
                {
                    "title": "Connection Error",
                    "subtitle": "timed out",
                    "icon": {"path": "icons/error.png"},
                    "valid": False,
                }
            ]
        }
        (cache / "refresh.log").write_text("[ha-debug] x\n" + json.dumps(err) + "\n")
        stamp = time.time() - 300
        os.utime(cache / "refresh.log", (stamp, stamp))
        out = run("server:", _env(tmp_path), capsys)
        cabin = _by_title(out, "Cabin")
        assert cabin["subtitle"].endswith("· last refresh failed 5m ago: timed out")

    def test_invalid_file(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_profiles(tmp_path, "{broken")
        out = run("server:", _env(tmp_path), capsys)
        first = out["items"][0]
        assert first["title"].startswith("Servers file is invalid:")
        assert first["variables"]["action"] == "server_edit"
        assert first["valid"] is True
        assert "✓ Default" in _titles(out)

    def test_stale_pointer(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_profiles(tmp_path)
        (tmp_path / "data" / "active_server").write_text("p-ffffffff\n")
        out = run("server:", _env(tmp_path), capsys)
        assert out["items"][0]["valid"] is False
        assert "not configured" in out["items"][0]["title"]
        assert not any(t.startswith("✓") for t in _titles(out))
        assert "Default" in _titles(out)

    def test_no_servers_at_all(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = run("server:", _env(tmp_path, with_default=False), capsys)
        titles = _titles(out)
        assert titles[0] == "No servers configured"
        assert "Add server…" in titles
        assert any(
            "workflow configuration" in (i.get("subtitle") or "")
            or "Configure" in i["title"]
            for i in out["items"]
        )

    def test_renders_without_ha_url_and_without_cache(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_profiles(tmp_path)
        (tmp_path / "data" / "active_server").write_text(_LAKE_ID + "\n")
        out = run("server:", _env(tmp_path, with_default=False), capsys)
        assert _titles(out)[:2] == ["✓ Lake House", "Cabin"]
        # Listing never creates per-server storage.
        assert not (tmp_path / "cache" / "servers").exists()

    def test_add_item_payload(
        self, run: Runner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out = run("server:", _env(tmp_path), capsys)
        add = _by_title(out, "Add server…")
        assert add["variables"]["action"] == "server_add"
        assert add["variables"]["entity_id"] == "__server__"
        assert all(m["valid"] is False for m in add["mods"].values())


# ---------------------------------------------------------------------------
# read_server_status — both library copies
# ---------------------------------------------------------------------------


@pytest.fixture(params=_PACKAGES)
def storage(request: pytest.FixtureRequest) -> ModuleType:
    return importlib.import_module(f"{request.param}.storage")


class TestReadServerStatus:
    def test_absent(self, storage: ModuleType, tmp_path: Path) -> None:
        st = storage.read_server_status(tmp_path / "cache", "abc")
        assert st.entity_count is None
        assert st.last_refresh is None
        assert st.last_error is None
        assert not (tmp_path / "cache").exists()

    def test_counts_and_refresh(self, storage: ModuleType, tmp_path: Path) -> None:
        _seed_cache(tmp_path, "abc", 3, age=60)
        st = storage.read_server_status(tmp_path / "cache", "abc")
        assert st.entity_count == 3
        assert st.last_refresh is not None
        assert time.time() - st.last_refresh == pytest.approx(60, abs=5)

    def test_failure_older_than_success_is_ignored(
        self, storage: ModuleType, tmp_path: Path
    ) -> None:
        cache = _seed_cache(tmp_path, "abc", 3, age=10)
        err = {
            "items": [
                {
                    "title": "Connection Error",
                    "subtitle": "boom",
                    "icon": {"path": "icons/error.png"},
                }
            ]
        }
        (cache / "refresh.log").write_text(json.dumps(err))
        stamp = time.time() - 600
        os.utime(cache / "refresh.log", (stamp, stamp))
        st = storage.read_server_status(tmp_path / "cache", "abc")
        assert st.last_error is None

    def test_success_log_is_not_an_error(
        self, storage: ModuleType, tmp_path: Path
    ) -> None:
        cache = _seed_cache(tmp_path, "abc", 3, age=10)
        ok = {"items": [{"title": "Cache refreshed: 3 entities"}]}
        (cache / "refresh.log").write_text(json.dumps(ok))
        assert storage.read_server_status(tmp_path / "cache", "abc").last_error is None

    def test_unsafe_key_rejected(self, storage: ModuleType, tmp_path: Path) -> None:
        st = storage.read_server_status(tmp_path / "cache", "../etc")
        assert st.entity_count is None
