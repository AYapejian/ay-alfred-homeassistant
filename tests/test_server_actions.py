"""Tests for server actions: switch, test, re-enter token, remove, edit.

Dialogs, the token store and HTTP are all fakes (``tests/server_fakes.py``).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ha_lib import prompter as prompter_mod
from ha_lib.profiles import load_profiles_file, read_active_server
from ha_lib.server_actions import run_server_action, split_server_action
from tests.server_fakes import (
    CABIN_ID,
    DEFAULT_URL,
    LAKE_ID,
    LAKE_TOKEN,
    LAKE_URL,
    make_context,
    write_profiles,
)

_NEW_TOKEN = "new.lake.token"


def _servers_dir(tmp_path: Path, kind: str, key: str) -> Path:
    return tmp_path / kind / "servers" / key


def test_split_server_action() -> None:
    assert split_server_action(f"server_switch::{LAKE_ID}") == ("switch", LAKE_ID)
    assert split_server_action("server_add") == ("add", "")


def test_unknown_verb(tmp_path: Path) -> None:
    ctx, *_ = make_context(tmp_path)
    assert "Unknown server action" in run_server_action("server_bogus::x", ctx)


# ---------------------------------------------------------------------------
# Switch
# ---------------------------------------------------------------------------


class TestSwitch:
    def test_switch_writes_pointer_and_refreshes(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, _, store, ha, effects = make_context(tmp_path)
        store.set(LAKE_ID, LAKE_TOKEN)
        msg = run_server_action(f"server_switch::{LAKE_ID}", ctx)
        assert msg == "Switched to Lake House (HA 2026.9.1)"
        assert read_active_server(tmp_path / "data") == LAKE_ID
        assert effects == [("refresh", LAKE_ID)]
        assert ha.requests == [(LAKE_URL, LAKE_TOKEN)]

    def test_switch_to_unreachable_is_allowed(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, _, store, ha, _ = make_context(tmp_path)
        store.set(LAKE_ID, LAKE_TOKEN)
        ha.down.add(LAKE_URL)
        msg = run_server_action(f"server_switch::{LAKE_ID}", ctx)
        assert msg.startswith("Switched to Lake House (unreachable: timed out")
        assert "cached entities" in msg
        assert read_active_server(tmp_path / "data") == LAKE_ID

    def test_switch_back_to_default(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        (tmp_path / "data" / "active_server").write_text(LAKE_ID)
        ctx, *_ = make_context(tmp_path)
        msg = run_server_action("server_switch::default", ctx)
        assert msg.startswith("Switched to Default")
        assert read_active_server(tmp_path / "data") == "default"

    def test_unknown_server_leaves_pointer(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, *_ = make_context(tmp_path)
        msg = run_server_action("server_switch::p-ffffffff", ctx)
        assert "not configured" in msg
        assert read_active_server(tmp_path / "data") is None

    def test_unusable_default_leaves_pointer(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        (tmp_path / "data" / "active_server").write_text(LAKE_ID)
        ctx, *_ = make_context(tmp_path, with_default=False)
        msg = run_server_action("server_switch::default", ctx)
        assert "not configured" in msg
        assert read_active_server(tmp_path / "data") == LAKE_ID

    def test_fresh_cache_is_not_refreshed(self, tmp_path: Path) -> None:
        from ha_lib.cache import open_cache
        from ha_lib.config import Config

        write_profiles(tmp_path)
        ctx, _, store, _, effects = make_context(tmp_path)
        store.set(LAKE_ID, LAKE_TOKEN)
        cfg = Config.from_env({**ctx.env, "HA_SERVER": LAKE_ID}, token_store=store)
        cache = open_cache(cfg)
        cache.refresh([])
        cache.close()
        run_server_action(f"server_switch::{LAKE_ID}", ctx)
        assert effects == []


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


class TestTestConnection:
    def test_ok(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, _, store, _, _ = make_context(tmp_path)
        store.set(LAKE_ID, LAKE_TOKEN)
        msg = run_server_action(f"server_test::{LAKE_ID}", ctx)
        assert msg == "Lake House: connected · HA 2026.9.1 · Lake"
        assert read_active_server(tmp_path / "data") is None  # no switch

    def test_failure(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, _, store, ha, _ = make_context(tmp_path)
        store.set(LAKE_ID, LAKE_TOKEN)
        ha.down.add(LAKE_URL)
        msg = run_server_action(f"server_test::{LAKE_ID}", ctx)
        assert msg == "Lake House: connection failed — timed out"

    def test_missing_token_named(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, *_ = make_context(tmp_path)
        msg = run_server_action(f"server_test::{LAKE_ID}", ctx)
        assert "Lake House" in msg
        assert "Keychain" in msg

    def test_default(self, tmp_path: Path) -> None:
        ctx, _, _, ha, _ = make_context(tmp_path)
        assert "connected" in run_server_action("server_test::default", ctx)
        assert ha.requests == [(DEFAULT_URL, "default-token")]


# ---------------------------------------------------------------------------
# Re-enter token
# ---------------------------------------------------------------------------


class TestReToken:
    def test_hidden_dialog_and_store(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, prompter, store, ha, _ = make_context(tmp_path, [_NEW_TOKEN])
        msg = run_server_action(f"server_token::{LAKE_ID}", ctx)
        assert msg == "Token updated for Lake House"
        assert store.get(LAKE_ID) == _NEW_TOKEN
        assert prompter.calls[0][0] == "ask_text"
        assert prompter.calls[0][4] is True  # hidden answer
        assert ha.requests == [(LAKE_URL, _NEW_TOKEN)]

    def test_cancel(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, _, store, _, _ = make_context(tmp_path, [None])
        store.set(LAKE_ID, LAKE_TOKEN)
        assert "Cancelled" in run_server_action(f"server_token::{LAKE_ID}", ctx)
        assert store.get(LAKE_ID) == LAKE_TOKEN

    def test_rejected_token_then_cancel(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, prompter, store, ha, _ = make_context(tmp_path, [_NEW_TOKEN, None])
        store.set(LAKE_ID, LAKE_TOKEN)
        ha.tokens[LAKE_URL] = LAKE_TOKEN
        assert "Cancelled" in run_server_action(f"server_token::{LAKE_ID}", ctx)
        assert store.get(LAKE_ID) == LAKE_TOKEN
        assert prompter.calls[1][3] == ("Cancel", "Save anyway")
        assert prompter.calls[1][4] == "Cancel"

    def test_offline_then_save_anyway(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, _, store, ha, _ = make_context(tmp_path, [_NEW_TOKEN, "Save anyway"])
        ha.down.add(LAKE_URL)
        assert run_server_action(f"server_token::{LAKE_ID}", ctx).startswith(
            "Token updated"
        )
        assert store.get(LAKE_ID) == _NEW_TOKEN

    def test_malformed_token_rejected(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, _, store, ha, _ = make_context(tmp_path, ["not a token"])
        msg = run_server_action(f"server_token::{LAKE_ID}", ctx)
        assert "unexpected characters" in msg
        assert store.get(LAKE_ID) is None
        assert ha.requests == []

    def test_default_refused(self, tmp_path: Path) -> None:
        ctx, prompter, *_ = make_context(tmp_path)
        assert "Configure" in run_server_action("server_token::default", ctx)
        assert prompter.calls == []


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


def _seed_storage(tmp_path: Path, key: str) -> None:
    for kind in ("cache", "data"):
        d = _servers_dir(tmp_path, kind, key)
        d.mkdir(parents=True, exist_ok=True)
        (d / "marker").write_text(key)


class TestRemove:
    def test_confirm_dialog_defaults_to_cancel_and_says_what_is_deleted(
        self, tmp_path: Path
    ) -> None:
        write_profiles(tmp_path)
        ctx, prompter, *_ = make_context(tmp_path, [False])
        msg = run_server_action(f"server_remove::{LAKE_ID}", ctx)
        assert msg == "Cancelled — Lake House kept"
        _, _, text, ok_label = prompter.calls[0]
        assert "cached entities and usage history" in text
        assert ok_label == "Remove"
        pf = load_profiles_file(tmp_path / "data")
        assert pf is not None and pf.get(LAKE_ID) is not None

    def test_remove_deletes_profile_storage_and_token(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        _seed_storage(tmp_path, LAKE_ID)
        _seed_storage(tmp_path, CABIN_ID)
        ctx, _, store, _, _ = make_context(tmp_path, [True])
        store.set(LAKE_ID, LAKE_TOKEN)
        store.set(CABIN_ID, "cabin.token")
        msg = run_server_action(f"server_remove::{LAKE_ID}", ctx)
        assert msg == "Removed Lake House"
        pf = load_profiles_file(tmp_path / "data")
        assert pf is not None
        assert [p.id for p in pf.profiles] == [CABIN_ID]
        assert store.get(LAKE_ID) is None
        assert store.get(CABIN_ID) == "cabin.token"
        for kind in ("cache", "data"):
            assert not _servers_dir(tmp_path, kind, LAKE_ID).exists()
            assert _servers_dir(tmp_path, kind, CABIN_ID).exists()

    def test_removing_active_server_fails_closed(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        (tmp_path / "data" / "active_server").write_text(LAKE_ID)
        ctx, *_ = make_context(tmp_path, [True])
        msg = run_server_action(f"server_remove::{LAKE_ID}", ctx)
        assert "choose one with 'ha server:'" in msg
        # No silent switch to another server.
        assert read_active_server(tmp_path / "data") == LAKE_ID

    def test_unknown_keys_survive_remove(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        data.mkdir(parents=True)
        (data / "profiles.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "future": True,
                    "profiles": [
                        {"id": LAKE_ID, "name": "Lake House", "urls": [LAKE_URL]},
                        {
                            "id": CABIN_ID,
                            "name": "Cabin",
                            "urls": ["http://c.x"],
                            "keep": 1,
                        },
                    ],
                }
            )
        )
        ctx, *_ = make_context(tmp_path, [True])
        run_server_action(f"server_remove::{LAKE_ID}", ctx)
        raw = json.loads((data / "profiles.json").read_text())
        assert raw["future"] is True
        assert raw["profiles"][0]["keep"] == 1

    def test_default_refused(self, tmp_path: Path) -> None:
        ctx, prompter, *_ = make_context(tmp_path)
        assert "Configure" in run_server_action("server_remove::default", ctx)
        assert prompter.calls == []


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------


class TestEdit:
    def test_opens_existing_file(self, tmp_path: Path) -> None:
        write_profiles(tmp_path)
        ctx, _, _, _, effects = make_context(tmp_path)
        run_server_action("server_edit", ctx)
        assert effects == [("open", tmp_path / "data" / "profiles.json")]

    def test_creates_skeleton_when_missing(self, tmp_path: Path) -> None:
        ctx, _, _, _, effects = make_context(tmp_path)
        run_server_action("server_edit", ctx)
        path = tmp_path / "data" / "profiles.json"
        assert json.loads(path.read_text())["profiles"] == []
        assert effects == [("open", path)]


# ---------------------------------------------------------------------------
# OsascriptPrompter — argv shape only; osascript is never executed
# ---------------------------------------------------------------------------


def _done(rc: int = 0, out: str = "", err: str = "") -> Any:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=out, stderr=err)


class TestOsascriptPrompter:
    def test_conftest_blocks_real_osascript(self) -> None:
        with pytest.raises(prompter_mod.PromptError):
            prompter_mod.OsascriptPrompter().ask_text("t", "m")

    def test_text_passed_as_arguments_not_script(self) -> None:
        p = prompter_mod.OsascriptPrompter()
        evil = 'Lake" & (do shell script "rm -rf ~") & "'
        with patch.object(
            prompter_mod.subprocess, "run", return_value=_done(out="answer\n")
        ) as run:
            assert p.ask_text(evil, "msg", default="http://") == "answer"
        argv = run.call_args.args[0]
        script = argv[2]
        assert evil not in script
        assert argv[3:] == [evil, "msg", "http://"]
        assert "hidden answer" not in script

    def test_hidden_answer(self) -> None:
        p = prompter_mod.OsascriptPrompter()
        with patch.object(
            prompter_mod.subprocess, "run", return_value=_done(out="tok\n")
        ) as run:
            assert p.ask_text("t", "m", hidden=True) == "tok"
        assert "with hidden answer" in run.call_args.args[0][2]

    def test_cancel_is_none(self) -> None:
        p = prompter_mod.OsascriptPrompter()
        with patch.object(
            prompter_mod.subprocess,
            "run",
            return_value=_done(rc=1, err="execution error: User canceled. (-128)"),
        ):
            assert p.ask_text("t", "m") is None
            assert p.confirm("t", "m", "Remove") is False
            assert p.choose("t", "m", ["Cancel", "Save anyway"], "Cancel") is None

    def test_confirm_default_button_is_cancel(self) -> None:
        p = prompter_mod.OsascriptPrompter()
        with patch.object(
            prompter_mod.subprocess, "run", return_value=_done(out="Remove\n")
        ) as run:
            assert p.confirm("Remove server", "Remove X?", "Remove") is True
        argv = run.call_args.args[0]
        # [bin, -e, script, title, message, default, cancel, *buttons]
        assert argv[5] == "Cancel"
        assert argv[6] == "Cancel"
        assert argv[7:] == ["Cancel", "Remove"]

    def test_other_failure_raises(self) -> None:
        p = prompter_mod.OsascriptPrompter()
        with (
            patch.object(
                prompter_mod.subprocess, "run", return_value=_done(rc=1, err="boom")
            ),
            pytest.raises(prompter_mod.PromptError),
        ):
            p.ask_text("t", "m")


def test_no_real_dialog_env_leak() -> None:
    assert os.environ.get("HA_SERVER") is None


# ---------------------------------------------------------------------------
# Wiring: action_runner dispatch + the ⌘ server sub-menu
# ---------------------------------------------------------------------------


class TestRunnerDispatch:
    def test_server_entity_routes_to_server_actions(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ha_workflow.scripts.action_runner as runner

        write_profiles(tmp_path)
        ctx, _, store, _, _ = make_context(tmp_path)
        store.set(LAKE_ID, LAKE_TOKEN)
        env = {
            **ctx.env,
            "entity_id": "__server__",
            "action": f"server_test::{LAKE_ID}",
            "domain": "__server__",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(runner, "_server_context", return_value=ctx),
        ):
            runner.main()
        assert capsys.readouterr().out.startswith("Lake House: connected")

    def test_real_context_uses_real_backends(self, tmp_path: Path) -> None:
        import ha_workflow.scripts.action_runner as runner
        from ha_lib.keychain import SecurityCliTokenStore
        from ha_lib.prompter import OsascriptPrompter

        ctx = runner._server_context()
        assert isinstance(ctx.prompter, OsascriptPrompter)
        assert isinstance(ctx.token_store, SecurityCliTokenStore)


def _actions_menu(env: dict[str, str], capsys: pytest.CaptureFixture[str]) -> Any:
    import ha_workflow.scripts.actions_filter as af

    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(af.Config, "from_env", side_effect=AssertionError("config")),
    ):
        af.main()
    return json.loads(capsys.readouterr().out)


class TestServerSubmenu:
    def test_keychain_server(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        write_profiles(tmp_path)
        ctx, *_ = make_context(tmp_path)
        out = _actions_menu(
            {
                **ctx.env,
                "entity_id": "__server__",
                "action": f"server_menu::{LAKE_ID}",
            },
            capsys,
        )
        titles = [i["title"] for i in out["items"]]
        assert titles == [
            "Lake House",
            "Switch to Lake House",
            "Test connection",
            "Re-enter token…",
            "Remove server…",
        ]
        actions = [i["variables"]["action"] for i in out["items"][1:]]
        assert actions == [
            f"server_switch::{LAKE_ID}",
            f"server_test::{LAKE_ID}",
            f"server_token::{LAKE_ID}",
            f"server_remove::{LAKE_ID}",
        ]
        assert all(
            i["variables"]["entity_id"] == "__server__" for i in out["items"][1:]
        )

    def test_active_default_server(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ctx, *_ = make_context(tmp_path)
        out = _actions_menu(
            {**ctx.env, "entity_id": "__server__", "action": "server_menu::default"},
            capsys,
        )
        titles = [i["title"] for i in out["items"]]
        assert titles == ["Default", "Test connection", "Default server"]

    def test_unknown_server(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ctx, *_ = make_context(tmp_path)
        out = _actions_menu(
            {**ctx.env, "entity_id": "__server__", "action": "server_menu::p-99999999"},
            capsys,
        )
        assert out["items"][0]["title"] == "Server not found"
