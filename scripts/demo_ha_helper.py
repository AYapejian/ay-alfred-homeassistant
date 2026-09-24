"""Helper for scripts/demo-ha.sh — onboarding, token, and seed for the demo HA.

Talks ONLY to the local demo instance (default http://127.0.0.1:8124). Not part
of the shipped workflow. Run through the shell wrapper, which invokes it as::

    uv run --no-project --with websockets python scripts/demo_ha_helper.py <cmd>

Subcommands:
    onboard  Complete every onboarding step still pending (user, core config,
             analytics, integration) so the web UI is fully usable.
    token    Create (or replace) the demo long-lived access token and write it
             to the token file with mode 600. The token is never printed.
    seed     Idempotently create a few areas and the ``alfred_preferred``
             label, and assign them to some demo entities.

The credentials below are demo-only and deliberately obvious.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

DEMO_NAME = "Demo User"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo-password"  # demo-only, localhost-only instance
TOKEN_CLIENT_NAME = "ay-alfred-demo"
TOKEN_LIFESPAN_DAYS = 3650

PREFERRED_LABEL_NAME = "Alfred Preferred"
PREFERRED_LABEL_ID = "alfred_preferred"

# Areas to ensure exist, and which demo entities to place in them. Only
# entities with a unique_id are in the entity registry and can take an area or
# label — the demo locks and media players have none, so they are not listed.
SEED_AREAS = ["Living Room", "Kitchen", "Office", "Garage"]
SEED_ENTITY_AREAS = {
    "light.ceiling_lights": "Living Room",
    "fan.living_room_fan": "Living Room",
    "light.kitchen_lights": "Kitchen",
    "light.office_rgbw_lights": "Office",
    "cover.garage_door": "Garage",
}
# Entities that get the alfred_preferred label (ranked higher by the workflow).
SEED_PREFERRED = ["light.kitchen_lights", "switch.decorative_lights", "climate.hvac"]


class DemoError(RuntimeError):
    """Fatal helper error with a message for the user."""


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------


def _request(
    method: str,
    url: str,
    *,
    json_body: Optional[dict[str, Any]] = None,
    form_body: Optional[dict[str, str]] = None,
    token: Optional[str] = None,
) -> tuple[int, Any]:
    headers: dict[str, str] = {}
    data: Optional[bytes] = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif form_body is not None:
        data = urllib.parse.urlencode(form_body).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    try:
        payload: Any = json.loads(raw) if raw else None
    except ValueError:
        payload = raw.decode(errors="replace")
    return status, payload


def _client_id(base: str) -> str:
    return base + "/"


def _exchange_code(base: str, code: str) -> dict[str, Any]:
    status, payload = _request(
        "POST",
        base + "/auth/token",
        form_body={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": _client_id(base),
        },
    )
    if status != 200 or not isinstance(payload, dict) or "access_token" not in payload:
        raise DemoError(f"token exchange failed (HTTP {status})")
    return payload


def _login(base: str) -> str:
    """Log in with the demo credentials; return a short-lived access token."""
    status, flow = _request(
        "POST",
        base + "/auth/login_flow",
        json_body={
            "client_id": _client_id(base),
            "handler": ["homeassistant", None],
            "redirect_uri": _client_id(base),
        },
    )
    if status != 200 or not isinstance(flow, dict) or "flow_id" not in flow:
        raise DemoError(f"could not start login flow (HTTP {status}): {flow}")
    status, result = _request(
        "POST",
        f"{base}/auth/login_flow/{flow['flow_id']}",
        json_body={
            "client_id": _client_id(base),
            "username": DEMO_USERNAME,
            "password": DEMO_PASSWORD,
        },
    )
    if (
        status != 200
        or not isinstance(result, dict)
        or result.get("type") != "create_entry"
    ):
        raise DemoError(
            f"demo login failed (HTTP {status}); was the instance onboarded "
            "by this script? Try `scripts/demo-ha.sh reset`."
        )
    return str(_exchange_code(base, str(result["result"]))["access_token"])


# ---------------------------------------------------------------------------
# onboard
# ---------------------------------------------------------------------------


def _pending_steps(base: str) -> list[str]:
    status, steps = _request("GET", base + "/api/onboarding")
    if status != 200 or not isinstance(steps, list):
        raise DemoError(f"GET /api/onboarding failed (HTTP {status})")
    return [s["step"] for s in steps if not s.get("done")]


def cmd_onboard(base: str) -> None:
    pending = _pending_steps(base)
    if not pending:
        print("onboarding: already complete")
        return
    print(f"onboarding: pending steps {pending}")

    access_token: Optional[str] = None
    if "user" in pending:
        status, payload = _request(
            "POST",
            base + "/api/onboarding/users",
            json_body={
                "name": DEMO_NAME,
                "username": DEMO_USERNAME,
                "password": DEMO_PASSWORD,
                "client_id": _client_id(base),
                "language": "en",
            },
        )
        if status != 200 or not isinstance(payload, dict):
            raise DemoError(f"onboarding user step failed (HTTP {status}): {payload}")
        access_token = str(_exchange_code(base, payload["auth_code"])["access_token"])
        print("onboarding: user created")
    if access_token is None:
        access_token = _login(base)

    for step in ("core_config", "analytics", "integration"):
        if step not in pending:
            continue
        body: dict[str, Any] = {}
        if step == "integration":
            body = {
                "client_id": _client_id(base),
                "redirect_uri": _client_id(base) + "?auth_callback=1",
            }
        status, payload = _request(
            "POST",
            f"{base}/api/onboarding/{step}",
            json_body=body,
            token=access_token,
        )
        if status != 200:
            raise DemoError(f"onboarding {step} step failed (HTTP {status}): {payload}")
        print(f"onboarding: {step} done")

    remaining = _pending_steps(base)
    if remaining:
        raise DemoError(f"onboarding incomplete, still pending: {remaining}")
    print("onboarding: complete")


# ---------------------------------------------------------------------------
# WebSocket helpers (token, seed)
# ---------------------------------------------------------------------------


class _WS:
    """Minimal HA WebSocket client: authenticate, then request/response."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn
        self._next_id = 1

    @classmethod
    async def connect(cls, base: str, access_token: str) -> _WS:
        import websockets  # provided by `uv run --with websockets`

        ws_url = base.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
        conn = await websockets.connect(ws_url + "/api/websocket", max_size=None)
        hello = json.loads(await conn.recv())
        if hello.get("type") != "auth_required":
            raise DemoError(f"unexpected websocket greeting: {hello.get('type')}")
        await conn.send(json.dumps({"type": "auth", "access_token": access_token}))
        auth = json.loads(await conn.recv())
        if auth.get("type") != "auth_ok":
            raise DemoError(f"websocket auth failed: {auth.get('type')}")
        return cls(conn)

    async def call(self, msg_type: str, **fields: Any) -> Any:
        msg_id = self._next_id
        self._next_id += 1
        await self._conn.send(json.dumps({"id": msg_id, "type": msg_type, **fields}))
        while True:
            reply = json.loads(await self._conn.recv())
            if reply.get("id") == msg_id and reply.get("type") == "result":
                break
        if not reply.get("success"):
            raise DemoError(f"{msg_type} failed: {reply.get('error')}")
        return reply.get("result")

    async def close(self) -> None:
        await self._conn.close()


def _write_secret(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(value + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


async def _token(base: str, token_file: Path) -> None:
    ws = await _WS.connect(base, _login(base))
    try:
        # HA allows one long-lived token per client_name; replace ours.
        existing = await ws.call("auth/refresh_tokens")
        for tok in existing:
            if (
                tok.get("type") == "long_lived_access_token"
                and tok.get("client_name") == TOKEN_CLIENT_NAME
            ):
                await ws.call("auth/delete_refresh_token", refresh_token_id=tok["id"])
                print(f"token: revoked previous '{TOKEN_CLIENT_NAME}' token")
        token = await ws.call(
            "auth/long_lived_access_token",
            client_name=TOKEN_CLIENT_NAME,
            lifespan=TOKEN_LIFESPAN_DAYS,
        )
    finally:
        await ws.close()
    if not isinstance(token, str) or not token:
        raise DemoError("long-lived token response was empty")
    _write_secret(token_file, token)
    print(f"token: wrote {token_file} (len={len(token)}, mode 600)")


async def _seed(base: str) -> None:
    ws = await _WS.connect(base, _login(base))
    try:
        # Areas
        areas = await ws.call("config/area_registry/list")
        area_ids = {a["name"]: a["area_id"] for a in areas}
        for name in SEED_AREAS:
            if name not in area_ids:
                created = await ws.call("config/area_registry/create", name=name)
                area_ids[name] = created["area_id"]
                print(f"seed: created area {name!r}")

        # Label
        labels = await ws.call("config/label_registry/list")
        if not any(lb["label_id"] == PREFERRED_LABEL_ID for lb in labels):
            created = await ws.call(
                "config/label_registry/create",
                name=PREFERRED_LABEL_NAME,
                icon="mdi:star",
                color="amber",
            )
            if created["label_id"] != PREFERRED_LABEL_ID:
                raise DemoError(
                    f"label created with id {created['label_id']!r}, "
                    f"expected {PREFERRED_LABEL_ID!r}"
                )
            print(f"seed: created label {PREFERRED_LABEL_ID!r}")

        # Entity assignments
        registry = await ws.call("config/entity_registry/list")
        entries = {e["entity_id"]: e for e in registry}
        wanted = set(SEED_ENTITY_AREAS) | set(SEED_PREFERRED)
        missing = sorted(eid for eid in wanted if eid not in entries)
        if missing:
            print(f"seed: WARNING entities not found, skipped: {missing}")
        for eid in sorted(wanted - set(missing)):
            entry = entries[eid]
            changes: dict[str, Any] = {}
            area_name = SEED_ENTITY_AREAS.get(eid)
            if area_name and entry.get("area_id") != area_ids[area_name]:
                changes["area_id"] = area_ids[area_name]
            labels_now = set(entry.get("labels") or [])
            if eid in SEED_PREFERRED and PREFERRED_LABEL_ID not in labels_now:
                changes["labels"] = sorted(labels_now | {PREFERRED_LABEL_ID})
            if changes:
                await ws.call("config/entity_registry/update", entity_id=eid, **changes)
                print(f"seed: updated {eid} {sorted(changes)}")
        print("seed: complete")
    finally:
        await ws.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["onboard", "token", "seed"])
    parser.add_argument("--url", default="http://127.0.0.1:8124")
    parser.add_argument("--token-file", type=Path)
    args = parser.parse_args(argv)
    base = args.url.rstrip("/")
    try:
        if args.command == "onboard":
            cmd_onboard(base)
        elif args.command == "token":
            if args.token_file is None:
                parser.error("--token-file is required for token")
            asyncio.run(_token(base, args.token_file))
        else:
            asyncio.run(_seed(base))
    except DemoError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
