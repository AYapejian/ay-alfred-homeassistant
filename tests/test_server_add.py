"""Tests for the add-server flow: dialogs → validation → Keychain → profile."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ha_lib import server_actions
from ha_lib.profiles import is_valid_profile_id, load_profiles_file, read_active_server
from tests.server_fakes import (
    DEFAULT_URL,
    LAKE_TOKEN,
    LAKE_URL,
    make_context,
    write_profiles,
)

_ANSWERS = ["Lake House", LAKE_URL, LAKE_TOKEN]


def _profiles(tmp_path: Path) -> list[dict[str, object]]:
    path = tmp_path / "data" / "profiles.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())["profiles"]  # type: ignore[no-any-return]


class TestAddHappyPath:
    def test_adds_profile_and_token(self, tmp_path: Path) -> None:
        ctx, prompter, store, ha, _ = make_context(tmp_path, _ANSWERS)
        msg = server_actions.run_server_action("server_add", ctx)
        assert msg == ("Added Lake House (HA 2026.9.1). Use 'ha server:' to switch.")
        profiles = _profiles(tmp_path)
        assert len(profiles) == 1
        pid = str(profiles[0]["id"])
        assert is_valid_profile_id(pid)
        assert profiles[0]["name"] == "Lake House"
        assert profiles[0]["urls"] == [LAKE_URL]
        assert profiles[0]["token_source"] == "keychain"
        assert store.get(pid) == LAKE_TOKEN
        assert ha.requests == [(LAKE_URL, LAKE_TOKEN)]
        # Three dialogs: name, URL (prefilled http://), hidden token.
        kinds = [(c[0], c[3], c[4]) for c in prompter.calls]
        assert kinds == [
            ("ask_text", "", False),
            ("ask_text", "http://", False),
            ("ask_text", "", True),
        ]

    def test_token_never_written_to_profiles_file(self, tmp_path: Path) -> None:
        ctx, *_ = make_context(tmp_path, _ANSWERS)
        server_actions.run_server_action("server_add", ctx)
        text = (tmp_path / "data" / "profiles.json").read_text()
        assert LAKE_TOKEN not in text

    def test_no_auto_switch(self, tmp_path: Path) -> None:
        ctx, *_ = make_context(tmp_path, _ANSWERS)
        server_actions.run_server_action("server_add", ctx)
        assert read_active_server(tmp_path / "data") is None

    def test_trailing_slash_and_whitespace_trimmed(self, tmp_path: Path) -> None:
        ctx, *_ = make_context(
            tmp_path, ["  Lake House ", f" {LAKE_URL}/ ", f" {LAKE_TOKEN}\n"]
        )
        server_actions.run_server_action("server_add", ctx)
        profile = _profiles(tmp_path)[0]
        assert profile["name"] == "Lake House"
        assert profile["urls"] == [LAKE_URL]

    def test_offline_save_anyway(self, tmp_path: Path) -> None:
        answers = [*_ANSWERS, "Save anyway"]
        ctx, prompter, _store, ha, _ = make_context(tmp_path, answers)
        ha.down.add(LAKE_URL)
        msg = server_actions.run_server_action("server_add", ctx)
        assert msg.startswith("Added Lake House (not verified: timed out)")
        assert len(_profiles(tmp_path)) == 1
        assert prompter.calls[-1][3] == ("Cancel", "Save anyway")
        assert prompter.calls[-1][4] == "Cancel"

    def test_keeps_existing_profiles_and_unknown_keys(self, tmp_path: Path) -> None:
        write_profiles(
            tmp_path,
            {
                "id": "p-00c0ffee",
                "name": "Cabin",
                "urls": ["http://cabin.local"],
                "x": 1,
            },
        )
        ctx, *_ = make_context(tmp_path, _ANSWERS)
        server_actions.run_server_action("server_add", ctx)
        profiles = _profiles(tmp_path)
        assert [p["name"] for p in profiles] == ["Cabin", "Lake House"]
        assert profiles[0]["x"] == 1


@pytest.mark.parametrize("cancel_at", [0, 1, 2])
def test_cancel_at_every_dialog_writes_nothing(tmp_path: Path, cancel_at: int) -> None:
    answers: list[object] = [*_ANSWERS[:cancel_at], None]
    ctx, _, store, ha, _ = make_context(tmp_path, answers)
    msg = server_actions.run_server_action("server_add", ctx)
    assert msg.startswith("Cancelled")
    assert not (tmp_path / "data" / "profiles.json").exists()
    assert store._tokens == {}
    assert ha.requests == []


def test_rejected_then_cancel_writes_nothing(tmp_path: Path) -> None:
    ctx, _, store, ha, _ = make_context(tmp_path, [*_ANSWERS, None])
    ha.tokens[LAKE_URL] = "the-right-token"
    msg = server_actions.run_server_action("server_add", ctx)
    assert msg.startswith("Cancelled")
    assert not (tmp_path / "data" / "profiles.json").exists()
    assert store._tokens == {}


class TestAddValidation:
    def test_duplicate_name_rejected(self, tmp_path: Path) -> None:
        write_profiles(
            tmp_path,
            {"id": "p-00c0ffee", "name": "lake house", "urls": ["http://cabin.local"]},
        )
        ctx, prompter, *_ = make_context(tmp_path, ["Lake HOUSE"])
        msg = server_actions.run_server_action("server_add", ctx)
        assert "already" in msg
        assert len(prompter.calls) == 1

    def test_name_clash_with_default_rejected(self, tmp_path: Path) -> None:
        ctx, *_ = make_context(tmp_path, ["default"])
        assert "already" in server_actions.run_server_action("server_add", ctx)

    def test_url_of_default_server_rejected(self, tmp_path: Path) -> None:
        ctx, prompter, *_ = make_context(tmp_path, ["Other", DEFAULT_URL.upper() + "/"])
        msg = server_actions.run_server_action("server_add", ctx)
        assert "same URL" in msg or "already" in msg
        assert len(prompter.calls) == 2  # never asked for a token

    def test_bad_url_rejected(self, tmp_path: Path) -> None:
        ctx, *_ = make_context(tmp_path, ["Lake House", "lake.example.net"])
        msg = server_actions.run_server_action("server_add", ctx)
        assert "http" in msg
        assert not (tmp_path / "data" / "profiles.json").exists()

    def test_bad_token_rejected(self, tmp_path: Path) -> None:
        ctx, _, _, ha, _ = make_context(tmp_path, ["Lake House", LAKE_URL, "a b"])
        msg = server_actions.run_server_action("server_add", ctx)
        assert "unexpected characters" in msg
        assert ha.requests == []

    def test_invalid_servers_file_is_not_clobbered(self, tmp_path: Path) -> None:
        (tmp_path / "data").mkdir(parents=True)
        (tmp_path / "data" / "profiles.json").write_text("{broken")
        ctx, prompter, *_ = make_context(tmp_path, _ANSWERS)
        msg = server_actions.run_server_action("server_add", ctx)
        assert "invalid" in msg
        assert (tmp_path / "data" / "profiles.json").read_text() == "{broken"
        assert prompter.calls == []


def test_profile_write_failure_rolls_back_token(tmp_path: Path) -> None:
    ctx, _, store, _, _ = make_context(tmp_path, _ANSWERS)
    with patch.object(
        server_actions, "save_profiles_file", side_effect=OSError("disk full")
    ):
        msg = server_actions.run_server_action("server_add", ctx)
    assert "Could not save" in msg
    assert store._tokens == {}
    assert load_profiles_file(tmp_path / "data") is None
