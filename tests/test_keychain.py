"""Tests for the Keychain token store.

The real Keychain is never touched: ``conftest.py`` points the ``security``
binary at a path that does not exist, and every test here patches
``subprocess.run`` in the module under test.
"""

from __future__ import annotations

import importlib
import subprocess
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_PACKAGES = ["ha_workflow", "ha_lib"]
_SECRET = "eyJhbGciOiJIUzI1NiJ9.SECRET-token-value.sig_123"
_PID = "p-1a2b3c4d"


@pytest.fixture(params=_PACKAGES)
def kc(request: pytest.FixtureRequest) -> ModuleType:
    return importlib.import_module(f"{request.param}.keychain")


def _completed(rc: int = 0, stdout: str = "", stderr: str = "") -> Any:
    return subprocess.CompletedProcess(
        args=[], returncode=rc, stdout=stdout, stderr=stderr
    )


def _all_argv(run: MagicMock) -> list[str]:
    argv: list[str] = []
    for call in run.call_args_list:
        args = call.args[0] if call.args else call.kwargs["args"]
        argv.extend(str(a) for a in args)
    return argv


class TestConftestGuard:
    def test_security_binary_is_disabled_in_tests(self, kc: ModuleType) -> None:
        store = kc.SecurityCliTokenStore()
        with pytest.raises(kc.TokenStoreError):
            store.get(_PID)


class TestSecurityCliTokenStore:
    def test_set_never_puts_token_in_argv(self, kc: ModuleType) -> None:
        store = kc.SecurityCliTokenStore()
        # First call: `security -i` (write); second: read-back.
        with patch.object(
            kc.subprocess,
            "run",
            side_effect=[_completed(), _completed(stdout=_SECRET + "\n")],
        ) as run:
            store.set(_PID, _SECRET)

        argv = _all_argv(run)
        assert all(_SECRET not in a for a in argv), argv
        write_call = run.call_args_list[0]
        assert write_call.args[0][1:] == ["-i"]
        stdin = write_call.kwargs["input"]
        assert _SECRET in stdin
        assert "add-generic-password" in stdin
        assert "-U" in stdin.split()
        assert kc.KEYCHAIN_SERVICE in stdin
        assert _PID in stdin

    def test_set_verifies_by_reading_back(self, kc: ModuleType) -> None:
        store = kc.SecurityCliTokenStore()
        with (
            patch.object(
                kc.subprocess,
                "run",
                side_effect=[_completed(), _completed(rc=44, stderr="not found")],
            ),
            pytest.raises(kc.TokenStoreError, match="verify"),
        ):
            store.set(_PID, _SECRET)

    def test_get_uses_find_generic_password_w(self, kc: ModuleType) -> None:
        store = kc.SecurityCliTokenStore()
        with patch.object(
            kc.subprocess, "run", return_value=_completed(stdout=_SECRET + "\n")
        ) as run:
            assert store.get(_PID) == _SECRET
        argv = run.call_args.args[0]
        assert argv[1:] == [
            "find-generic-password",
            "-s",
            kc.KEYCHAIN_SERVICE,
            "-a",
            _PID,
            "-w",
        ]

    def test_get_missing_item_is_none(self, kc: ModuleType) -> None:
        store = kc.SecurityCliTokenStore()
        with patch.object(
            kc.subprocess, "run", return_value=_completed(rc=44, stderr="not found")
        ):
            assert store.get(_PID) is None

    def test_get_other_failure_raises_without_echoing_output(
        self, kc: ModuleType
    ) -> None:
        store = kc.SecurityCliTokenStore()
        with (
            patch.object(
                kc.subprocess, "run", return_value=_completed(rc=51, stdout=_SECRET)
            ),
            pytest.raises(kc.TokenStoreError) as info,
        ):
            store.get(_PID)
        assert _SECRET not in str(info.value)

    def test_delete(self, kc: ModuleType) -> None:
        store = kc.SecurityCliTokenStore()
        with patch.object(kc.subprocess, "run", return_value=_completed()) as run:
            store.delete(_PID)
        argv = run.call_args.args[0]
        assert argv[1:] == [
            "delete-generic-password",
            "-s",
            kc.KEYCHAIN_SERVICE,
            "-a",
            _PID,
        ]

    def test_delete_missing_is_ok(self, kc: ModuleType) -> None:
        store = kc.SecurityCliTokenStore()
        with patch.object(kc.subprocess, "run", return_value=_completed(rc=44)):
            store.delete(_PID)

    @pytest.mark.parametrize("bad", ["default", "../x", "p-XYZ", ""])
    def test_rejects_invalid_account(self, kc: ModuleType, bad: str) -> None:
        store = kc.SecurityCliTokenStore()
        with (
            patch.object(kc.subprocess, "run") as run,
            pytest.raises(kc.TokenStoreError),
        ):
            store.get(bad)
        run.assert_not_called()

    def test_os_error_is_token_store_error(self, kc: ModuleType) -> None:
        store = kc.SecurityCliTokenStore()
        with (
            patch.object(kc.subprocess, "run", side_effect=OSError("boom")),
            pytest.raises(kc.TokenStoreError),
        ):
            store.get(_PID)


class TestValidateToken:
    @pytest.mark.parametrize(
        "bad",
        ["", "   ", "has space", 'quote"d', "back\\slash", "new\nline", "x" * 5000],
    )
    def test_rejects(self, kc: ModuleType, bad: str) -> None:
        with pytest.raises(kc.TokenStoreError):
            kc.validate_token(bad)

    def test_accepts_jwt_and_strips(self, kc: ModuleType) -> None:
        assert kc.validate_token(f"  {_SECRET}\n") == _SECRET

    def test_set_validates_before_running_anything(self, kc: ModuleType) -> None:
        store = kc.SecurityCliTokenStore()
        with (
            patch.object(kc.subprocess, "run") as run,
            pytest.raises(kc.TokenStoreError),
        ):
            store.set(_PID, "bad token")
        run.assert_not_called()


class TestInMemoryTokenStore:
    def test_round_trip(self, kc: ModuleType) -> None:
        store = kc.InMemoryTokenStore()
        assert store.get(_PID) is None
        store.set(_PID, _SECRET)
        assert store.get(_PID) == _SECRET
        store.delete(_PID)
        assert store.get(_PID) is None
        assert store.reads == 3
