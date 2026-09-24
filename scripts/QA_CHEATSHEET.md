# Phase 3 QA Cheatsheet

## Quick Start

```bash
# Run automated smoke test (read-only, needs HA_URL + HA_TOKEN)
uv run python scripts/qa_smoke_test.py

# Include state-changing actions (toggle, restart)
uv run python scripts/qa_smoke_test.py --write
```

---

## Feature Checklist

### Search (Alfred: `ha <query>`)

| Test | Command | Expected |
|------|---------|----------|
| Empty query | `ha` | System commands at top, then entities sorted by usage |
| Fuzzy search | `ha bedroom` | Entities matching "bedroom" in name/id/area |
| Domain filter | `ha light:` | Only light entities |
| Domain + text | `ha light:bed` | Lights matching "bed" |
| Regex | `ha /.*kitchen.*/` | Entities matching regex |
| Bad regex | `ha /[bad/` | "Invalid regex pattern" error item |
| System cmd search | `ha restart` | "System: Restart Home Assistant" appears |
| System cmd search | `ha check config` | "System: Check config" appears |
| System cmd search | `ha error log` | "System: View error log" appears |

### Default Action (Enter on search result)

| Test | Action | Expected |
|------|--------|----------|
| Toggle light | Enter on a light | Notification: "Toggled {name}" |
| Toggle switch | Enter on a switch | Notification: "Toggled {name}" |
| Sensor (no action) | Enter on a sensor | Nothing (item is not valid/selectable) |
| Press button | Enter on a button | Notification: "Pressed {name}" |
| Run scene | Enter on a scene | Notification: "Turned on {name}" |
| Lock | Enter on a lock | Notification: "Locked {name}" |

### Action Sub-Menu (Cmd+Enter on search result)

| Test | Expected |
|------|----------|
| Cmd on light | Sub-menu: header → Toggle, Turn On, Turn Off → Copy/Open → Advanced stub |
| Cmd on sensor | Sub-menu: header → Copy/Open → Advanced stub (no domain actions) |
| Cmd on cover | Sub-menu: header → Toggle, Open Cover, Close Cover, Stop Cover → Copy/Open |
| Header shows friendly name | First item is non-selectable with entity name |
| Header shows last changed | Subtitle includes "Changed Xm ago" (if entity has last_changed) |
| Copy Entity ID | Copies `entity_id` to clipboard |
| Copy Entity Details | Copies full YAML state to clipboard |
| Copy Device Details | Only shown if entity has device_id; copies device YAML |
| Open Entity | Opens HA entity config page in browser |
| Open Device | Only shown if device_id; opens HA device page |
| Open Area | Only shown if area; opens HA area page |
| Open History | Opens HA history view for entity |
| Advanced Action Call | Non-selectable, shows "Coming soon" |

### System Commands (Enter on system command search result)

| Command | Expected |
|---------|----------|
| History: Clear usage data | "Usage history cleared" |
| Cache: Refresh entities | "Cache refreshed: N entities" |
| System: Restart HA | "Home Assistant is restarting" (actually restarts!) |
| System: Check config | "Configuration is valid" or "Config invalid: {errors}" |
| System: View error log | "Error log copied to clipboard (N lines): {first line}" |

### Server profiles (`ha server:`) — manual, on a real Mac

These cannot be covered by automated tests (real dialogs, the real Keychain, Alfred's variable propagation). Use the demo HA (`make demo-ha-up`) as the second server.

| Check | Expected |
|-------|----------|
| `ha server:` with only the default configured | `✓ Default` + `Add server…` |
| **Add server…** → name / URL / token dialogs | Each dialog comes to the front; the token field shows bullets; Cancel at any step adds nothing |
| First Keychain write and read | No Keychain access prompt (the item is created and read by `/usr/bin/security`) |
| Keychain Access → search `com.ayapejian.alfred-homeassistant` | One item per added server, account = its `p-…` id |
| `ps aux \| grep security` while adding | Only `security -i` is visible, never the token |
| Wrong token → **Save anyway** / **Cancel** | Cancel is the default button; Cancel adds nothing |
| Enter on the new server | Notification `Switched to <name> (HA <version>)`; `ha` shows its entities |
| With 2 servers: entity subtitles | Start with the server badge/name |
| With 2 servers: `ha system` | All five titles end with `(<server name>)` |
| Enter on an entity of the added server | Notification starts `<name>:`; the state changes on that server, not the default (the `action@@<id>` variable reached the Run Script) |
| ⌘ Enter on that entity → **Turn On** → Set parameters `brightness:50%` → Enter | Lands on the same server (the tag survives the actions and params Script Filters) |
| Open `ha light`, then in a second Alfred window switch servers, then press Enter on the first window's result | The action lands on the server the result was listed from |
| ⌘ Enter on a server → **Test connection** | `<name>: connected · HA <version>` |
| ⌘ Enter → **Re-enter token…** | Hidden dialog; `Token updated for <name>` |
| ⌘ Enter → **Remove server…** | Dialog says cache and usage history are deleted, Cancel is default; after Remove the Keychain item and `servers/p-…/` dirs are gone |
| Remove the *active* server, then `ha light` | Error pointing to `ha server:` — no silent fallback |
| ⌥ / ⌃ Enter on a server item | Not actionable (subtitle points to ⌘) |
| **Edit servers file…** | `profiles.json` opens in the default text editor; no tokens in it |
| Break `profiles.json` (invalid JSON) | `ha server:` shows `Servers file is invalid: …` first, default still listed and switchable |

### Viewers (from sub-menu)

| Action | Expected |
|--------|----------|
| Show Entity Details | YAML copied to clipboard, notification with name + state |
| View History | Last hour of state changes copied, notification with count |

---

## CLI Quick Reference

```bash
# Test without Alfred (set env vars first)
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your-token-here"
cd /path/to/ay-alfred-homeassistant-addon

# Search
uv run python src/ha_workflow/cli.py search ""           # all entities
uv run python src/ha_workflow/cli.py search "bedroom"    # fuzzy
uv run python src/ha_workflow/cli.py search "light:"     # domain filter
uv run python src/ha_workflow/cli.py search "/kitchen/"  # regex
uv run python src/ha_workflow/cli.py search "restart"    # system cmd

# Actions sub-menu
uv run python src/ha_workflow/cli.py actions "light.bedroom"
uv run python src/ha_workflow/cli.py actions "sensor.temperature"

# Execute actions
uv run python src/ha_workflow/cli.py action "light.bedroom" "toggle"
uv run python src/ha_workflow/cli.py action "light.bedroom" "copy_entity_id"
uv run python src/ha_workflow/cli.py action "light.bedroom" "copy_entity_details"
uv run python src/ha_workflow/cli.py action "light.bedroom" "open_entity"
uv run python src/ha_workflow/cli.py action "light.bedroom" "open_history"
uv run python src/ha_workflow/cli.py action "light.bedroom" "show_details"
uv run python src/ha_workflow/cli.py action "light.bedroom" "view_history"

# System commands
uv run python src/ha_workflow/cli.py action "__system__" "usage_clear"
uv run python src/ha_workflow/cli.py action "__system__" "cache_refresh"
uv run python src/ha_workflow/cli.py action "__system__" "ha_check_config"
uv run python src/ha_workflow/cli.py action "__system__" "ha_error_log"
uv run python src/ha_workflow/cli.py action "__system__" "ha_restart"  # ⚠️ actually restarts

# Cache
uv run python src/ha_workflow/cli.py cache refresh
uv run python src/ha_workflow/cli.py cache status

# Config
uv run python src/ha_workflow/cli.py config validate
```
