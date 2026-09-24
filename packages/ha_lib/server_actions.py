"""Server-management actions run from Alfred (``ha server:``).

Every action is ``server_<verb>[::<server id>]`` and returns the text for
Alfred's notification.  All side effects go through an injectable
:class:`ServerActionContext`, so tests use fake dialogs, a fake token store
and a fake HTTP client — never the real Keychain, a real dialog or a server.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from ha_lib.config import Config, workflow_dirs
from ha_lib.errors import HAWorkflowError
from ha_lib.keychain import TokenStore, validate_token
from ha_lib.profiles import (
    DEFAULT_PROFILE_ID,
    SERVER_ENV_VAR,
    Profile,
    ProfilesFile,
    ServerList,
    load_profiles_file,
    load_servers,
    profiles_path,
    read_active_server,
    save_profiles_file,
    write_active_server,
)
from ha_lib.prompter import Prompter
from ha_lib.storage import delete_server_storage, read_server_status

_PING_TIMEOUT = 5


class _Client(Protocol):
    def get_config(self) -> dict[str, Any]: ...


def _open_file(path: Path) -> None:
    subprocess.run(["/usr/bin/open", "-t", str(path)], check=True)


@dataclass
class ServerActionContext:
    """Everything a server action may touch."""

    env: Mapping[str, str]
    prompter: Prompter
    token_store: TokenStore
    client_factory: Callable[[Config, int], _Client]
    spawn_refresh: Callable[[Config], None]
    open_file: Callable[[Path], None] = field(default=_open_file)

    @property
    def data_dir(self) -> Path:
        return workflow_dirs(self.env)[1]

    @property
    def cache_dir(self) -> Path:
        return workflow_dirs(self.env)[0]

    def servers(self) -> ServerList:
        return load_servers(self.env, self.data_dir)

    def config_for(self, server_id: str) -> Config:
        """Config for *server_id* (token still unread — it is lazy)."""
        env = dict(self.env)
        env[SERVER_ENV_VAR] = server_id
        return Config.from_env(env, token_store=self.token_store)


def split_server_action(action: str) -> tuple[str, str]:
    """``server_switch::p-…`` → ``("switch", "p-…")``."""
    head, _, payload = action.partition("::")
    verb = head[len("server_") :] if head.startswith("server_") else head
    return verb, payload.strip()


def _version(info: Mapping[str, Any]) -> str:
    version = info.get("version")
    return f"HA {version}" if version else "HA"


def _profile_or_error(ctx: ServerActionContext, server_id: str) -> Profile:
    servers = ctx.servers()
    profile = servers.get(server_id)
    if profile is not None:
        return profile
    if servers.file_error and server_id != DEFAULT_PROFILE_ID:
        raise HAWorkflowError(f"Servers file is invalid: {servers.file_error}")
    raise HAWorkflowError(f"Server {server_id!r} is not configured.")


def _keychain_profile(ctx: ServerActionContext, server_id: str) -> Profile:
    profile = _profile_or_error(ctx, server_id)
    if profile.is_default:
        raise HAWorkflowError(
            f"{profile.name} is configured in Alfred → Workflows → Configure, not here."
        )
    return profile


def _file(ctx: ServerActionContext) -> ProfilesFile:
    return load_profiles_file(ctx.data_dir) or ProfilesFile()


# ---------------------------------------------------------------------------
# Verbs
# ---------------------------------------------------------------------------


def _switch(ctx: ServerActionContext, server_id: str) -> str:
    profile = _profile_or_error(ctx, server_id)
    config = ctx.config_for(server_id)  # validates before the pointer moves
    write_active_server(ctx.data_dir, server_id)
    if read_active_server(ctx.data_dir) != server_id:
        return (
            f"Could not switch to {profile.name}: "
            "the active server file did not update."
        )

    status = read_server_status(ctx.cache_dir, config.server_key)
    if (
        status.entity_count is None
        or status.last_refresh is None
        or time.time() - status.last_refresh > config.cache_ttl
    ):
        ctx.spawn_refresh(config)

    try:
        info = ctx.client_factory(config, _PING_TIMEOUT).get_config()
    except HAWorkflowError as exc:
        cached = status.entity_count or 0
        return (
            f"Switched to {profile.name} (unreachable: {exc}; "
            f"showing {cached} cached entities)"
        )
    return f"Switched to {profile.name} ({_version(info)})"


def _test(ctx: ServerActionContext, server_id: str) -> str:
    profile = _profile_or_error(ctx, server_id)
    config = ctx.config_for(server_id)
    try:
        info = ctx.client_factory(config, _PING_TIMEOUT).get_config()
    except HAWorkflowError as exc:
        return f"{profile.name}: connection failed — {exc}"
    location = info.get("location_name")
    where = f" · {location}" if location else ""
    return f"{profile.name}: connected · {_version(info)}{where}"


def _validate_token_against(
    ctx: ServerActionContext, name: str, url: str, token: str
) -> Optional[str]:
    """``None`` if *token* works on *url*, else a short reason."""
    cache_dir, data_dir = workflow_dirs(ctx.env)
    probe = Config(
        ha_url=url,
        ha_token=token,
        cache_ttl=0,
        cache_dir=cache_dir,
        data_dir=data_dir,
        server_name=name,
    )
    try:
        ctx.client_factory(probe, _PING_TIMEOUT).get_config()
    except HAWorkflowError as exc:
        return str(exc)
    return None


def _ask_token(ctx: ServerActionContext, name: str) -> Optional[str]:
    raw = ctx.prompter.ask_text(
        f"Token for {name}",
        f"Paste a long-lived access token for {name}.\n\n"
        "Home Assistant → Profile → Security → Long-lived access tokens",
        hidden=True,
    )
    if raw is None:
        return None
    return validate_token(raw)


def _token(ctx: ServerActionContext, server_id: str) -> str:
    profile = _keychain_profile(ctx, server_id)
    token = _ask_token(ctx, profile.name)
    if token is None:
        return "Cancelled — token unchanged"
    problem = _validate_token_against(ctx, profile.name, profile.url, token)
    if problem is not None:
        choice = ctx.prompter.choose(
            f"Token for {profile.name}",
            f"{profile.name} did not accept the token or is unreachable:\n{problem}",
            ["Cancel", "Save anyway"],
            default="Cancel",
        )
        if choice != "Save anyway":
            return "Cancelled — token unchanged"
    ctx.token_store.set(profile.id, token)
    return f"Token updated for {profile.name}"


def _remove(ctx: ServerActionContext, server_id: str) -> str:
    profile = _keychain_profile(ctx, server_id)
    confirmed = ctx.prompter.confirm(
        "Remove server",
        f"Remove {profile.name}? Its cached entities and usage history on this "
        "Mac are deleted.",
        ok_label="Remove",
    )
    if not confirmed:
        return f"Cancelled — {profile.name} kept"

    config = ctx.config_for(server_id)  # for its storage dirs; token not read
    save_profiles_file(ctx.data_dir, _file(ctx).without_profile(server_id))
    after = load_profiles_file(ctx.data_dir)
    if after is not None and after.get(server_id) is not None:
        return f"Could not remove {profile.name}: the servers file did not update."
    delete_server_storage(config)

    message = f"Removed {profile.name}"
    try:
        ctx.token_store.delete(server_id)
    except HAWorkflowError as exc:
        message += f", but its Keychain item could not be deleted ({exc})"
    if read_active_server(ctx.data_dir) == server_id:
        # Fail closed: no silent switch to another house.
        message += ". It was the active server — choose one with 'ha server:'"
    return message


def _edit(ctx: ServerActionContext, _server_id: str) -> str:
    path = profiles_path(ctx.data_dir)
    if not path.exists():
        save_profiles_file(ctx.data_dir, ProfilesFile())
    ctx.open_file(path)
    return "Opened the servers file"


_VERBS: dict[str, Callable[[ServerActionContext, str], str]] = {
    "switch": _switch,
    "test": _test,
    "token": _token,
    "remove": _remove,
    "edit": _edit,
}


def run_server_action(action: str, ctx: ServerActionContext) -> str:
    """Run ``server_<verb>[::<id>]`` and return the notification text."""
    verb, server_id = split_server_action(action)
    handler = _VERBS.get(verb)
    if handler is None:
        return f"Unknown server action: {action}"
    try:
        return handler(ctx, server_id)
    except HAWorkflowError as exc:
        return str(exc)
