"""Fakes shared by the server-profile tests: dialogs, HTTP client, env."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

from ha_lib.config import Config
from ha_lib.errors import HAConnectionError
from ha_lib.keychain import InMemoryTokenStore
from ha_lib.server_actions import ServerActionContext

LAKE_ID = "p-1a2b3c4d"
LAKE_URL = "https://lake.example.net"
LAKE_TOKEN = "lake.token.value"
CABIN_ID = "p-00c0ffee"
CABIN_URL = "http://cabin.local:8123"
DEFAULT_URL = "http://ha.local:8123"


class FakePrompter:
    """Scripted :class:`Prompter`: pops one answer per dialog, records calls."""

    def __init__(self, answers: Sequence[Any] = ()) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[Any, ...]] = []

    def _next(self) -> Any:
        if not self.answers:
            raise AssertionError(f"unexpected dialog; calls so far: {self.calls}")
        return self.answers.pop(0)

    def ask_text(
        self, title: str, message: str, default: str = "", hidden: bool = False
    ) -> Optional[str]:
        self.calls.append(("ask_text", title, message, default, hidden))
        return self._next()  # type: ignore[no-any-return]

    def confirm(self, title: str, message: str, ok_label: str) -> bool:
        self.calls.append(("confirm", title, message, ok_label))
        return bool(self._next())

    def choose(
        self, title: str, message: str, buttons: Sequence[str], default: str
    ) -> Optional[str]:
        self.calls.append(("choose", title, message, tuple(buttons), default))
        return self._next()  # type: ignore[no-any-return]


class FakeClient:
    def __init__(self, owner: FakeHA, config: Config) -> None:
        self._owner = owner
        self._config = config

    def get_config(self) -> dict[str, Any]:
        url = self._config.ha_url
        token = self._config.get_token()
        self._owner.requests.append((url, token))
        if url in self._owner.down:
            raise HAConnectionError("timed out")
        expected = self._owner.tokens.get(url)
        if expected is not None and token != expected:
            raise HAConnectionError("Authentication failed (HTTP 401)")
        return {"version": "2026.9.1", "location_name": self._owner.names.get(url, "")}


class FakeHA:
    """Pretend HA servers keyed by URL."""

    def __init__(self) -> None:
        self.down: set[str] = set()
        self.tokens: dict[str, str] = {}
        self.names: dict[str, str] = {LAKE_URL: "Lake"}
        self.requests: list[tuple[str, str]] = []

    def factory(self, config: Config, timeout: int) -> FakeClient:
        return FakeClient(self, config)


def base_env(tmp_path: Path, with_default: bool = True) -> dict[str, str]:
    env = {
        "alfred_workflow_cache": str(tmp_path / "cache"),
        "alfred_workflow_data": str(tmp_path / "data"),
        "PATH": os.environ.get("PATH", ""),
    }
    if with_default:
        env["HA_URL"] = DEFAULT_URL
        env["HA_TOKEN"] = "default-token"
    return env


def write_profiles(tmp_path: Path, *entries: dict[str, Any]) -> None:
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    if not entries:
        entries = (
            {"id": LAKE_ID, "name": "Lake House", "urls": [LAKE_URL]},
            {"id": CABIN_ID, "name": "Cabin", "urls": [CABIN_URL]},
        )
    (data / "profiles.json").write_text(
        json.dumps({"schema_version": 1, "profiles": list(entries)})
    )


def make_context(
    tmp_path: Path,
    answers: Sequence[Any] = (),
    with_default: bool = True,
) -> tuple[ServerActionContext, FakePrompter, InMemoryTokenStore, FakeHA, list[Any]]:
    """Context with fakes; returns (ctx, prompter, store, ha, side_effects)."""
    prompter = FakePrompter(answers)
    store = InMemoryTokenStore()
    ha = FakeHA()
    effects: list[Any] = []
    ctx = ServerActionContext(
        env=base_env(tmp_path, with_default),
        prompter=prompter,
        token_store=store,
        client_factory=ha.factory,
        spawn_refresh=lambda cfg: effects.append(("refresh", cfg.server_id)),
        open_file=lambda path: effects.append(("open", path)),
    )
    return ctx, prompter, store, ha, effects
