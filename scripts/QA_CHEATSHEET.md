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
