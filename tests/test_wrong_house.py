"""Wrong-house signals: shown only when more than one server is configured.

With several servers every entity subtitle starts with the server's badge
(or name), system-command titles name the server, and every notification
after an action is prefixed with the server name.  A single-server setup
sees no extra text.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ha_lib.actions import ActionResult
from ha_lib.cache import open_cache
from ha_lib.config import Config
from ha_lib.entities import Entity
from tests.server_fakes import LAKE_ID, LAKE_URL, base_env, write_profiles

_SYSTEM_TITLES = [
    "History: Clear usage data",
    "Cache: Refresh entities",
    "System: Restart Home Assistant",
    "System: Check config",
    "System: View error log",
]


def _seed(env: dict[str, str], server: str) -> None:
    cfg = Config.from_env({**env, "HA_SERVER": server})
    cache = open_cache(cfg)
    cache.refresh(
        [
            Entity.from_state_dict(
                {
                    "entity_id": "light.dock",
                    "state": "on",
                    "attributes": {"friendly_name": "Dock Light"},
                }
            )
        ]
    )
    cache.close()


def _single(tmp_path: Path) -> dict[str, str]:
    env = base_env(tmp_path)
    _seed(env, "default")
    return env


def _multi(tmp_path: Path, badge: str = "") -> dict[str, str]:
    lake: dict[str, Any] = {"id": LAKE_ID, "name": "Lake House", "urls": [LAKE_URL]}
    if badge:
        lake["badge"] = badge
    write_profiles(tmp_path, lake)
    (tmp_path / "data" / "active_server").write_text(LAKE_ID)
    env = base_env(tmp_path)
    _seed(env, LAKE_ID)
    return env


def _search(env: dict[str, str], query: str) -> Any:
    sf = importlib.import_module("ha_workflow.scripts.search_filter")
    buf: list[str] = []
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(sf.sys, "argv", ["search_filter.py", query]),
        patch.object(sf.sys.stdout, "write", side_effect=buf.append),
        patch.object(sf.subprocess, "Popen", side_effect=AssertionError("spawn")),
    ):
        sf.main()
    return json.loads("".join(buf))


def _dock(out: Any) -> Any:
    return next(i for i in out["items"] if i["title"] == "Dock Light")


# ---------------------------------------------------------------------------
# Subtitles
# ---------------------------------------------------------------------------


class TestEntitySubtitles:
    def test_single_server_unchanged(self, tmp_path: Path) -> None:
        sub = _dock(_search(_single(tmp_path), "dock"))["subtitle"]
        assert sub == "light · On"

    def test_multi_server_prefixed_with_name(self, tmp_path: Path) -> None:
        sub = _dock(_search(_multi(tmp_path), "dock"))["subtitle"]
        assert sub == "Lake House · light · On"

    def test_badge_preferred_over_name(self, tmp_path: Path) -> None:
        sub = _dock(_search(_multi(tmp_path, badge="LAKE"), "dock"))["subtitle"]
        assert sub.startswith("LAKE · ")

    def test_quick_exec_prefixed(self, tmp_path: Path) -> None:
        out = _search(_multi(tmp_path), "light.dock brightness:50%")
        assert out["items"][0]["subtitle"].startswith("Lake House · ")

    def test_invalid_servers_file_keeps_signals_on(self, tmp_path: Path) -> None:
        env = _single(tmp_path)
        (tmp_path / "data" / "profiles.json").write_text("{broken")
        sub = _dock(_search(env, "dock"))["subtitle"]
        assert sub.startswith("Default · ")

    def test_empty_query_hint_names_server(self, tmp_path: Path) -> None:
        out = _search(_multi(tmp_path), "")
        hint = next(i for i in out["items"] if i.get("autocomplete") == "server:")
        assert "Lake House" in hint["title"]
        assert hint["valid"] is False

    def test_no_server_hint_for_single_server(self, tmp_path: Path) -> None:
        out = _search(_single(tmp_path), "")
        assert not any(i.get("autocomplete") == "server:" for i in out["items"])


# ---------------------------------------------------------------------------
# System command titles — both entry points
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("module", "package"),
    [
        ("ha_workflow.scripts.search_filter", "ha_lib"),
        ("ha_workflow.cli", "ha_workflow"),
    ],
)
class TestSystemTitles:
    def _items(self, module: str, package: str, env: dict[str, str]) -> Any:
        mod = importlib.import_module(module)
        cfg = importlib.import_module(f"{package}.config").Config.from_env(env)
        return mod._match_system_commands("system", cfg)

    def test_single_server_titles_unchanged(
        self, tmp_path: Path, module: str, package: str
    ) -> None:
        items = self._items(module, package, _single(tmp_path))
        assert [i.title for i in items] == _SYSTEM_TITLES

    def test_multi_server_titles_name_the_server(
        self, tmp_path: Path, module: str, package: str
    ) -> None:
        items = self._items(module, package, _multi(tmp_path, badge="LAKE"))
        assert [i.title for i in items] == [f"{t} (Lake House)" for t in _SYSTEM_TITLES]


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def _runner(env: dict[str, str], entity_id: str, action: str) -> str:
    runner = importlib.import_module("ha_workflow.scripts.action_runner")
    out: list[str] = []
    client = MagicMock()
    client.call_service.return_value = []
    with (
        patch.dict(
            os.environ,
            {**env, "entity_id": entity_id, "action": action, "domain": "light"},
            clear=True,
        ),
        patch.object(runner, "HAClient", return_value=client),
        patch.object(
            runner, "dispatch_action", return_value=ActionResult(True, "Dock: on")
        ),
        patch.object(runner, "notify", side_effect=out.append),
        patch.object(runner, "notify_error", side_effect=out.append),
    ):
        runner.main()
    return "\n".join(out)


class TestNotifications:
    def test_single_server_unprefixed(self, tmp_path: Path) -> None:
        assert _runner(_single(tmp_path), "light.dock", "toggle@@default") == (
            "Dock: on"
        )

    def test_entity_action_prefixed(self, tmp_path: Path) -> None:
        msg = _runner(
            _multi(tmp_path, badge="LAKE"), "light.dock", f"toggle@@{LAKE_ID}"
        )
        assert msg == "Lake House: Dock: on"

    def test_system_action_prefixed(self, tmp_path: Path) -> None:
        msg = _runner(_multi(tmp_path), "__system__", f"ha_restart@@{LAKE_ID}")
        assert msg == "Lake House: Home Assistant is restarting"

    def test_prefix_does_not_leak_into_next_run(self, tmp_path: Path) -> None:
        _runner(_multi(tmp_path), "light.dock", f"toggle@@{LAKE_ID}")
        single = tmp_path / "single"
        assert _runner(_single(single), "light.dock", "toggle@@default") == "Dock: on"

    def test_open_in_ha_prefixed(self, tmp_path: Path) -> None:
        oih = importlib.import_module("ha_workflow.scripts.open_in_ha")
        out: list[str] = []
        env = {
            **_multi(tmp_path),
            "entity_id": "light.dock",
            "action": f"open_entity@@{LAKE_ID}",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(oih.subprocess, "run"),
            patch.object(oih, "notify", side_effect=out.append),
        ):
            oih.main()
        assert out == ["Lake House: Opened in Home Assistant"]

    def test_background_refresh_failure_toast_prefixed(self, tmp_path: Path) -> None:
        cli = importlib.import_module("ha_workflow.cli")
        env = {**_multi(tmp_path), "HA_SERVER": LAKE_ID}
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(cli, "_refresh_cache", side_effect=RuntimeError("down")),
            patch.object(cli, "notify_background_error") as toast,
            pytest.raises(RuntimeError),
        ):
            cli.main(["cache", "refresh"])
        assert toast.call_args.args[0].startswith("Lake House: Cache refresh failed")


class TestActionsSubmenuHeader:
    def test_header_prefixed_when_multi(self, tmp_path: Path) -> None:
        af = importlib.import_module("ha_workflow.scripts.actions_filter")
        env = {
            **_multi(tmp_path),
            "entity_id": "light.dock",
            "domain": "light",
            "action": f"@@{LAKE_ID}",
        }
        buf: list[str] = []
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(af.sys.stdout, "write", side_effect=buf.append),
        ):
            af.main()
        header = json.loads("".join(buf))["items"][0]
        assert header["subtitle"].startswith("Lake House · light.dock")
