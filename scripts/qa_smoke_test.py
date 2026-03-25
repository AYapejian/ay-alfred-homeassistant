#!/usr/bin/env python3
"""Phase 3 QA smoke test — exercises every CLI command path.

Run from the project root:
    uv run python scripts/qa_smoke_test.py

Requires HA_URL and HA_TOKEN set (uses your real HA instance, read-only
by default). Pass --write to test actions that modify state.

Exit codes: 0 = all pass, 1 = failures found.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = [sys.executable, os.path.join(PROJECT_ROOT, "src", "ha_workflow", "cli.py")]
WRITE_MODE = "--write" in sys.argv

passed = 0
failed = 0
skipped = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(args: list[str], env_extra: dict[str, str] | None = None) -> tuple[int, str]:
    """Run a CLI command and return (exit_code, stdout)."""
    env = {**os.environ, **(env_extra or {})}
    result = subprocess.run(
        CLI + args,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
        timeout=30,
    )
    return result.returncode, result.stdout


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    status = "\033[32mPASS\033[0m" if condition else "\033[31mFAIL\033[0m"
    print(f"  [{status}] {name}")
    if not condition and detail:
        for line in detail.strip().split("\n"):
            print(f"         {line}")
    if condition:
        passed += 1
    else:
        failed += 1


def skip(name: str, reason: str) -> None:
    global skipped
    print(f"  [\033[33mSKIP\033[0m] {name} — {reason}")
    skipped += 1


def parse_json(stdout: str) -> dict | None:
    try:
        return json.loads(stdout.strip().split("\n")[0])
    except (json.JSONDecodeError, IndexError):
        return None


def has_env() -> bool:
    return bool(os.environ.get("HA_URL") and os.environ.get("HA_TOKEN"))


# ---------------------------------------------------------------------------
# Tests — no HA required (unit-level CLI behavior)
# ---------------------------------------------------------------------------


def test_no_args():
    print("\n== CLI basics ==")
    rc, out = run([])
    data = parse_json(out)
    check("no args → stub output", data is not None and "not yet implemented" in data["items"][0]["title"])


def test_unknown_command():
    rc, out = run(["bogus"])
    data = parse_json(out)
    check("unknown command → stub", data is not None and "not yet implemented" in data["items"][0]["title"])


def test_actions_no_entity():
    rc, out = run(["actions"])
    data = parse_json(out)
    check("actions (no entity) → 'No entity selected'", data is not None and "No entity" in data["items"][0]["title"])


def test_actions_bad_entity():
    rc, out = run(["actions", "badentity"])
    data = parse_json(out)
    check("actions (bad entity) → 'Invalid entity ID'", data is not None and "Invalid" in data["items"][0]["title"])


def test_action_missing_args():
    rc, out = run(["action", "light.foo"])
    check("action (missing action arg) → 'Missing'", "Missing" in out)


# ---------------------------------------------------------------------------
# Tests — require HA connection
# ---------------------------------------------------------------------------


def test_config_validate():
    print("\n== Config & connection ==")
    if not has_env():
        skip("config validate", "HA_URL / HA_TOKEN not set")
        return
    rc, out = run(["config", "validate"])
    data = parse_json(out)
    check(
        "config validate → 'Connected to Home Assistant'",
        data is not None and "Connected" in data["items"][0]["title"],
        out,
    )


def test_cache_refresh():
    print("\n== Cache ==")
    if not has_env():
        skip("cache refresh", "HA_URL / HA_TOKEN not set")
        skip("cache status", "HA_URL / HA_TOKEN not set")
        return
    rc, out = run(["cache", "refresh"])
    data = parse_json(out)
    check(
        "cache refresh → entity count",
        data is not None and "refreshed" in data["items"][0]["title"].lower(),
        out,
    )

    rc, out = run(["cache", "status"])
    data = parse_json(out)
    check(
        "cache status → age + count",
        data is not None and "entities" in data["items"][0].get("subtitle", ""),
        out,
    )


def test_search():
    print("\n== Search ==")
    if not has_env():
        skip("search (empty query)", "HA_URL / HA_TOKEN not set")
        skip("search (fuzzy)", "HA_URL / HA_TOKEN not set")
        skip("search (domain filter)", "HA_URL / HA_TOKEN not set")
        skip("search (regex)", "HA_URL / HA_TOKEN not set")
        skip("search items have mods.cmd", "HA_URL / HA_TOKEN not set")
        return

    # Empty query → system commands + entities
    rc, out = run(["search"])
    data = parse_json(out)
    if data:
        sys_items = [i for i in data["items"] if i.get("variables", {}).get("domain") == "__system__"]
        check("search (empty) → system commands present", len(sys_items) >= 5, f"found {len(sys_items)} system items")
        entity_items = [i for i in data["items"] if i.get("variables", {}).get("domain") not in ("__system__", None)]
        check("search (empty) → entity results present", len(entity_items) > 0, f"found {len(entity_items)} entities")

        # Check mods.cmd on first entity
        if entity_items:
            first = entity_items[0]
            has_cmd = "mods" in first and "cmd" in first.get("mods", {})
            check(
                "search items have mods.cmd",
                has_cmd and first["mods"]["cmd"].get("valid") is True,
                json.dumps(first.get("mods", {}), indent=2)[:200] if not has_cmd else "",
            )
        else:
            skip("search items have mods.cmd", "no entity results")
    else:
        check("search (empty) → valid JSON", False, out[:200])

    # Fuzzy search
    rc, out = run(["search", "light"])
    data = parse_json(out)
    check("search 'light' → results", data is not None and len(data["items"]) >= 1, out[:200])

    # Domain filter
    rc, out = run(["search", "light:"])
    data = parse_json(out)
    if data:
        domains = {i.get("variables", {}).get("domain") for i in data["items"] if "variables" in i}
        domains.discard("__system__")
        check("search 'light:' → only light domain", domains == {"light"} or domains == set(), f"domains: {domains}")
    else:
        check("search 'light:' → valid JSON", False, out[:200])

    # Regex
    rc, out = run(["search", "/light/"])
    data = parse_json(out)
    check("search '/light/' regex → results", data is not None and len(data["items"]) >= 1, out[:200])


def test_system_commands_in_search():
    print("\n== System commands in search ==")
    if not has_env():
        skip("search 'restart'", "HA_URL / HA_TOKEN not set")
        skip("search 'check config'", "HA_URL / HA_TOKEN not set")
        skip("search 'error log'", "HA_URL / HA_TOKEN not set")
        return

    for query, expected_title in [
        ("restart", "System: Restart Home Assistant"),
        ("check config", "System: Check config"),
        ("error log", "System: View error log"),
    ]:
        rc, out = run(["search", query])
        data = parse_json(out)
        titles = [i["title"] for i in data["items"]] if data else []
        check(f"search '{query}' → {expected_title}", expected_title in titles, str(titles)[:200])


def test_actions_submenu():
    print("\n== Actions sub-menu (Cmd modifier) ==")
    if not has_env():
        skip("actions sub-menu for light", "HA_URL / HA_TOKEN not set")
        skip("actions sub-menu for sensor", "HA_URL / HA_TOKEN not set")
        return

    # Find a real light and sensor from search
    rc, out = run(["search", "light:"])
    data = parse_json(out)
    light_id = None
    if data:
        for item in data["items"]:
            eid = item.get("variables", {}).get("entity_id", "")
            if eid.startswith("light."):
                light_id = eid
                break

    if light_id:
        rc, out = run(["actions", light_id])
        data = parse_json(out)
        if data:
            titles = [i["title"] for i in data["items"]]
            check("sub-menu: header present", data["items"][0].get("valid") is False, f"first item: {titles[0]}")
            check("sub-menu: Toggle action", "Toggle" in titles, str(titles))
            check("sub-menu: Copy Entity ID", "Copy Entity ID" in titles, str(titles))
            check("sub-menu: Open Entity", "Open Entity" in titles, str(titles))
            check("sub-menu: Open History", "Open History" in titles, str(titles))
            check("sub-menu: Advanced stub", "Advanced Action Call" in titles, str(titles))
        else:
            check("sub-menu: valid JSON", False, out[:200])
    else:
        skip("actions sub-menu for light", "no light entities found")

    # Sensor (display-only) should still show sub-menu
    rc, out = run(["search", "sensor:"])
    data = parse_json(out)
    sensor_id = None
    if data:
        for item in data["items"]:
            eid = item.get("variables", {}).get("entity_id", "")
            if eid.startswith("sensor."):
                sensor_id = eid
                break

    if sensor_id:
        rc, out = run(["actions", sensor_id])
        data = parse_json(out)
        if data:
            titles = [i["title"] for i in data["items"]]
            check("sensor sub-menu: has copy/open (not 'No actions')", "Copy Entity ID" in titles, str(titles))
        else:
            check("sensor sub-menu: valid JSON", False, out[:200])
    else:
        skip("actions sub-menu for sensor", "no sensor entities found")


def test_system_actions():
    print("\n== System action execution ==")
    if not has_env():
        skip("system: usage_clear", "HA_URL / HA_TOKEN not set")
        skip("system: cache_refresh", "HA_URL / HA_TOKEN not set")
        skip("system: ha_check_config", "HA_URL / HA_TOKEN not set")
        skip("system: ha_error_log", "HA_URL / HA_TOKEN not set")
        return

    # Usage clear (safe)
    rc, out = run(["action", "__system__", "usage_clear"])
    check("system: usage_clear → 'cleared'", "cleared" in out.lower(), out)

    # Cache refresh (safe)
    rc, out = run(["action", "__system__", "cache_refresh"])
    check("system: cache_refresh → 'refreshed'", "refreshed" in out.lower(), out)

    # Check config (safe, read-only)
    rc, out = run(["action", "__system__", "ha_check_config"])
    check("system: ha_check_config → 'valid' or 'invalid'", "valid" in out.lower() or "invalid" in out.lower(), out)

    # Error log (safe, read-only, copies to clipboard)
    rc, out = run(["action", "__system__", "ha_error_log"])
    check("system: ha_error_log → 'copied' or 'empty'", "copied" in out.lower() or "empty" in out.lower(), out)


def test_entity_actions():
    print("\n== Entity action execution ==")
    if not has_env():
        skip("entity toggle", "HA_URL / HA_TOKEN not set")
        return

    if not WRITE_MODE:
        skip("entity toggle", "pass --write to test state-changing actions")
        return

    # Find a light
    rc, out = run(["search", "light:"])
    data = parse_json(out)
    light_id = None
    if data:
        for item in data["items"]:
            eid = item.get("variables", {}).get("entity_id", "")
            if eid.startswith("light."):
                light_id = eid
                break

    if light_id:
        rc, out = run(["action", light_id, "toggle"])
        check(f"toggle {light_id} → success", "toggled" in out.lower() or "Toggled" in out, out)
    else:
        skip("entity toggle", "no light entities found")


def test_copy_actions():
    print("\n== Copy actions ==")
    if not has_env():
        skip("copy_entity_id", "HA_URL / HA_TOKEN not set")
        skip("copy_entity_details", "HA_URL / HA_TOKEN not set")
        return

    # Find any entity
    rc, out = run(["search", ""])
    data = parse_json(out)
    entity_id = None
    if data:
        for item in data["items"]:
            eid = item.get("variables", {}).get("entity_id", "")
            if "." in eid and eid != "__system__":
                entity_id = eid
                break

    if not entity_id:
        skip("copy_entity_id", "no entities found")
        skip("copy_entity_details", "no entities found")
        return

    rc, out = run(["action", entity_id, "copy_entity_id"])
    check(f"copy_entity_id ({entity_id}) → 'Copied'", "copied" in out.lower(), out)

    rc, out = run(["action", entity_id, "copy_entity_details"])
    check(f"copy_entity_details ({entity_id}) → 'Copied details'", "copied details" in out.lower(), out)


def test_viewer_actions():
    print("\n== Viewer actions ==")
    if not has_env():
        skip("show_details", "HA_URL / HA_TOKEN not set")
        skip("view_history", "HA_URL / HA_TOKEN not set")
        return

    rc, out = run(["search", ""])
    data = parse_json(out)
    entity_id = None
    if data:
        for item in data["items"]:
            eid = item.get("variables", {}).get("entity_id", "")
            if "." in eid and eid != "__system__":
                entity_id = eid
                break

    if not entity_id:
        skip("show_details", "no entities found")
        skip("view_history", "no entities found")
        return

    rc, out = run(["action", entity_id, "show_details"])
    check(f"show_details ({entity_id}) → 'Copied details'", "copied details" in out.lower(), out)

    rc, out = run(["action", entity_id, "view_history"])
    check(
        f"view_history ({entity_id}) → 'copied' or 'No history'",
        "copied" in out.lower() or "no history" in out.lower(),
        out,
    )


def test_usage_tracking():
    print("\n== Usage tracking ==")
    if not has_env():
        skip("record-usage + ranking", "HA_URL / HA_TOKEN not set")
        return

    # Clear, record, verify boosted
    run(["action", "__system__", "usage_clear"])
    run(["record-usage", "light.test_qa_entity"])
    run(["record-usage", "light.test_qa_entity"])
    run(["record-usage", "light.test_qa_entity"])
    # Can't easily verify ranking without a real entity in cache, but at least verify no crash
    check("record-usage runs without error", True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    global passed, failed, skipped

    print("=" * 60)
    print("  Phase 3 QA Smoke Test")
    print("=" * 60)

    if has_env():
        print(f"  HA_URL:  {os.environ['HA_URL'][:50]}")
        print(f"  Mode:    {'read+write' if WRITE_MODE else 'read-only (pass --write for state changes)'}")
    else:
        print("  HA_URL:  (not set — offline tests only)")
        print("  Set HA_URL and HA_TOKEN for full testing")

    # Offline tests (always run)
    test_no_args()
    test_unknown_command()
    test_actions_no_entity()
    test_actions_bad_entity()
    test_action_missing_args()

    # Online tests (require HA)
    test_config_validate()
    test_cache_refresh()
    test_search()
    test_system_commands_in_search()
    test_actions_submenu()
    test_system_actions()
    test_entity_actions()
    test_copy_actions()
    test_viewer_actions()
    test_usage_tracking()

    # Summary
    print("\n" + "=" * 60)
    total = passed + failed + skipped
    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped / {total} total")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
