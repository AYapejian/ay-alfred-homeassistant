"""Every item carries the server id; the runner acts on *that* server.

Scenario used throughout: a default server and a Keychain profile "Lake
House".  Items produced from Lake's cache must execute against Lake even
after the active server is switched back to the default.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from ha_lib.actions import ActionResult
from ha_lib.cache import open_cache
from ha_lib.config import Config
from ha_lib.entities import Entity
from tests.server_fakes import (
    CABIN_URL,
    DEFAULT_URL,
    LAKE_ID,
    LAKE_URL,
    base_env,
    write_profiles,
)

_PACKAGES = ["ha_workflow", "ha_lib"]


# ---------------------------------------------------------------------------
# tag_action / split_action — both library copies
# ---------------------------------------------------------------------------


@pytest.fixture(params=_PACKAGES)
def profiles(request: pytest.FixtureRequest) -> ModuleType:
    return importlib.import_module(f"{request.param}.profiles")


class TestTagging:
    @pytest.mark.parametrize(
        ("action", "tagged"),
        [
            ("toggle", f"toggle@@{LAKE_ID}"),
            ("", f"@@{LAKE_ID}"),
            ("turn_on::brightness:50%", f"turn_on@@{LAKE_ID}::brightness:50%"),
            ("toggle@@default", f"toggle@@{LAKE_ID}"),
        ],
    )
    def test_tag(self, profiles: ModuleType, action: str, tagged: str) -> None:
        assert profiles.tag_action(action, LAKE_ID) == tagged

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("toggle", ("toggle", None)),
            (f"toggle@@{LAKE_ID}", ("toggle", LAKE_ID)),
            (f"@@{LAKE_ID}", ("", LAKE_ID)),
            (f"turn_on@@{LAKE_ID}::a@@b", ("turn_on::a@@b", LAKE_ID)),
            ("server_switch::p-1", ("server_switch::p-1", None)),
            ("toggle@@", ("toggle", None)),
        ],
    )
    def test_split(
        self, profiles: ModuleType, raw: str, expected: tuple[str, Optional[str]]
    ) -> None:
        assert profiles.split_action(raw) == expected

    def test_round_trip(self, profiles: ModuleType) -> None:
        raw = profiles.tag_action("turn_on::x:1", "default")
        assert profiles.split_action(raw) == ("turn_on::x:1", "default")


# ---------------------------------------------------------------------------
# Fixtures: default + Lake, with Lake's cache seeded
# ---------------------------------------------------------------------------


def _entity(entity_id: str, name: str, state: str = "on") -> Entity:
    return Entity.from_state_dict(
        {"entity_id": entity_id, "state": state, "attributes": {"friendly_name": name}}
    )


def _setup(tmp_path: Path, active: str = LAKE_ID) -> dict[str, str]:
    write_profiles(tmp_path)
    (tmp_path / "data" / "active_server").write_text(active + "\n")
    env = base_env(tmp_path)
    for server, ents in (
        (LAKE_ID, [_entity("light.dock", "Dock Light")]),
        ("default", [_entity("light.kitchen", "Kitchen Light")]),
    ):
        cfg = Config.from_env({**env, "HA_SERVER": server})
        cache = open_cache(cfg)
        cache.refresh(ents)
        cache.close()
    return env


def _run_search(env: dict[str, str], query: str) -> Any:
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


# ---------------------------------------------------------------------------
# Search items carry the server id
# ---------------------------------------------------------------------------


class TestSearchItemsTagged:
    def test_entity_item_and_mods(self, tmp_path: Path) -> None:
        env = _setup(tmp_path)
        out = _run_search(env, "dock")
        item = next(i for i in out["items"] if i["title"] == "Dock Light")
        assert item["variables"]["action"] == f"toggle@@{LAKE_ID}"
        assert item["mods"]["cmd"]["variables"]["action"] == f"@@{LAKE_ID}"
        assert item["mods"]["ctrl"]["variables"]["action"] == f"open_entity@@{LAKE_ID}"
        assert item["mods"]["alt"]["variables"]["action"] == (
            f"copy_entity_id@@{LAKE_ID}"
        )

    def test_default_server_items_tagged_default(self, tmp_path: Path) -> None:
        env = _setup(tmp_path, active="default")
        out = _run_search(env, "kitchen")
        item = next(i for i in out["items"] if i["title"] == "Kitchen Light")
        assert item["variables"]["action"] == "toggle@@default"

    def test_quick_exec_item(self, tmp_path: Path) -> None:
        env = _setup(tmp_path)
        out = _run_search(env, "light.dock brightness:50%")
        assert out["items"][0]["variables"]["action"] == f"turn_on@@{LAKE_ID}"

    def test_system_items(self, tmp_path: Path) -> None:
        env = _setup(tmp_path)
        out = _run_search(env, "system")
        actions = [i["variables"]["action"] for i in out["items"]]
        assert actions
        assert all(a.endswith(f"@@{LAKE_ID}") for a in actions)


# ---------------------------------------------------------------------------
# The runner resolves config for the tagged server
# ---------------------------------------------------------------------------


def _run_runner(
    env: dict[str, str], entity_id: str, action: str, **extra: str
) -> tuple[list[Config], MagicMock, str]:
    runner = importlib.import_module("ha_workflow.scripts.action_runner")
    seen: list[Config] = []

    def fake_client(config: Config, *a: Any, **k: Any) -> MagicMock:
        seen.append(config)
        return MagicMock()

    out: list[str] = []
    item_env = {**env, "entity_id": entity_id, "action": action, **extra}
    with (
        patch.dict(os.environ, item_env, clear=True),
        patch.object(runner, "HAClient", side_effect=fake_client),
        patch.object(
            runner, "dispatch_action", return_value=ActionResult(True, "Dock: on")
        ) as dispatch,
        patch.object(runner, "notify", side_effect=out.append),
        patch.object(runner, "notify_error", side_effect=out.append),
    ):
        runner.main()
    return seen, dispatch, "\n".join(out)


class TestRunnerResolution:
    def test_entity_action_goes_to_tagged_server_after_switch(
        self, tmp_path: Path
    ) -> None:
        env = _setup(tmp_path, active="default")  # switched away from Lake
        with patch.dict(os.environ, {}, clear=False):
            seen, dispatch, _ = _run_runner(
                env, "light.dock", f"toggle@@{LAKE_ID}", domain="light"
            )
        assert [c.server_id for c in seen] == [LAKE_ID]
        assert seen[0].ha_url == LAKE_URL
        assert dispatch.call_args.args[1:3] == ("light.dock", "toggle")

    def test_usage_recorded_on_tagged_server(self, tmp_path: Path) -> None:
        from ha_lib.usage import open_usage_tracker

        env = _setup(tmp_path, active="default")
        _run_runner(env, "light.dock", f"toggle@@{LAKE_ID}", domain="light")
        lake = Config.from_env({**env, "HA_SERVER": LAKE_ID})
        default = Config.from_env({**env, "HA_SERVER": "default"})
        for cfg, expected in ((lake, True), (default, False)):
            tracker = open_usage_tracker(cfg)
            try:
                found = tracker.get_usage_record("light.dock") is not None
            finally:
                tracker.close()
            assert found is expected

    def test_untagged_action_uses_active_server(self, tmp_path: Path) -> None:
        env = _setup(tmp_path, active="default")
        seen, _, _ = _run_runner(env, "light.kitchen", "toggle", domain="light")
        assert seen[0].ha_url == DEFAULT_URL

    def test_system_action_goes_to_tagged_server(self, tmp_path: Path) -> None:
        env = _setup(tmp_path, active="default")
        seen, _, _ = _run_runner(env, "__system__", f"ha_restart@@{LAKE_ID}")
        assert seen[0].ha_url == LAKE_URL

    def test_removed_server_fails_closed_with_plain_message(
        self, tmp_path: Path
    ) -> None:
        env = _setup(tmp_path, active="default")
        seen, dispatch, out = _run_runner(
            env, "light.dock", "toggle@@p-ffffffff", domain="light"
        )
        assert seen == []
        dispatch.assert_not_called()
        assert "not configured" in out
        assert not out.lstrip().startswith("{")

    def test_ha_server_not_leaked_between_runs(self, tmp_path: Path) -> None:
        env = _setup(tmp_path, active="default")
        _run_runner(env, "light.dock", f"toggle@@{LAKE_ID}", domain="light")
        assert "HA_SERVER" not in os.environ


# ---------------------------------------------------------------------------
# actions / params Script Filters keep the tag
# ---------------------------------------------------------------------------


def _run_filter(module: str, env: dict[str, str], query: str = "") -> Any:
    mod = importlib.import_module(f"ha_workflow.scripts.{module}")
    buf: list[str] = []
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(mod.sys, "argv", [f"{module}.py", query]),
        patch.object(mod.sys.stdout, "write", side_effect=buf.append),
    ):
        mod.main()
    return json.loads("".join(buf))


class TestSubmenusKeepTag:
    def test_actions_filter_reads_tagged_server_cache(self, tmp_path: Path) -> None:
        env = _setup(tmp_path, active="default")
        out = _run_filter(
            "actions_filter",
            {
                **env,
                "entity_id": "light.dock",
                "domain": "light",
                "action": f"@@{LAKE_ID}",
            },
        )
        assert out["items"][0]["title"] == "Dock Light"  # from Lake's cache
        actions = [i["variables"]["action"] for i in out["items"] if i.get("variables")]
        assert actions
        assert all(a.endswith(f"@@{LAKE_ID}") for a in actions)

    def test_params_filter_preserves_tag(self, tmp_path: Path) -> None:
        env = _setup(tmp_path)
        out = _run_filter(
            "params_filter",
            {
                **env,
                "entity_id": "light.dock",
                "domain": "light",
                "action": f"turn_on@@{LAKE_ID}",
            },
            "brightness:50%",
        )
        confirm = out["items"][0]
        assert confirm["valid"] is True
        assert confirm["variables"]["action"] == f"turn_on@@{LAKE_ID}"
        assert confirm["variables"]["params"] == "brightness:50%"

    def test_params_filter_hints_use_bare_action(self, tmp_path: Path) -> None:
        env = _setup(tmp_path)
        out = _run_filter(
            "params_filter",
            {
                **env,
                "entity_id": "light.dock",
                "domain": "light",
                "action": f"turn_on@@{LAKE_ID}",
            },
        )
        assert out["items"][0]["title"] == "Set parameters for Turn On"


# ---------------------------------------------------------------------------
# open_in_ha + background refresh
# ---------------------------------------------------------------------------


def test_open_in_ha_uses_tagged_server(tmp_path: Path) -> None:
    oih = importlib.import_module("ha_workflow.scripts.open_in_ha")
    env = _setup(tmp_path, active="default")
    item_env = {**env, "entity_id": "light.dock", "action": f"open_entity@@{LAKE_ID}"}
    with (
        patch.dict(os.environ, item_env, clear=True),
        patch.object(oih.subprocess, "run") as run,
        patch.object(oih, "notify"),
    ):
        oih.main()
    url = run.call_args.args[0][1]
    assert url.startswith(LAKE_URL + "/config/entities")


@pytest.mark.parametrize(
    ("module", "package"),
    [
        ("ha_workflow.scripts.search_filter", "ha_lib"),
        ("ha_workflow.cli", "ha_workflow"),
    ],
)
def test_background_refresh_pins_server(
    tmp_path: Path, module: str, package: str
) -> None:
    mod = importlib.import_module(module)
    config_mod = importlib.import_module(f"{package}.config")
    write_profiles(tmp_path)
    cfg = config_mod.Config.from_env({**base_env(tmp_path), "HA_SERVER": LAKE_ID})
    with patch.object(mod.subprocess, "Popen") as popen:
        popen.return_value.pid = 4242
        mod._maybe_refresh_background(cfg)
    assert popen.call_args.kwargs["env"]["HA_SERVER"] == LAKE_ID


def test_cli_action_decodes_tag(tmp_path: Path) -> None:
    cli = importlib.import_module("ha_workflow.cli")
    env = _setup(tmp_path, active="default")
    seen: list[Any] = []
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(cli, "HAClient", side_effect=lambda c, *a, **k: seen.append(c)),
        patch.object(cli, "dispatch_action", return_value=ActionResult(True, "ok")),
        patch.object(cli, "notify"),
        patch.object(cli, "_cmd_record_usage"),
    ):
        cli.main(["action", "light.dock", f"toggle@@{LAKE_ID}"])
    assert seen[0].ha_url == LAKE_URL
    assert CABIN_URL not in {c.ha_url for c in seen}
