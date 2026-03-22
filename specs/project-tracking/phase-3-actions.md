# Phase 3: Actions & Entity Interaction

**Goal:** Users can act on entities, not just search them.
**Status:** In Progress
**Branch:** various (per issue)
**Depends on:** Phase 2, Phase 1.5

---

## Pre-existing Infrastructure

Phase 1.5 built the action dispatch skeleton. Phase 3 (PR #20) added the core action dispatcher.

**Completed infrastructure:**
- `actions.py` — `dispatch_action()` maps action names → HA service calls, returns `ActionResult`
- `_cmd_action()` in `cli.py` — dispatches entity actions on Enter, records usage on success
- `_cmd_actions()` in `cli.py` — lists domain-specific actions as Alfred Script Filter (Cmd modifier)
- `_cmd_system_action()` — handles `usage_clear` and `cache_refresh` system commands
- `_SYSTEM_COMMANDS` registry — searchable system actions
- `record-usage` CLI command — wired into action flow
- `ha_client.py` — `get_state()`, `get_entity_registry()`, `get_device_registry()`, `get_area_registry()`, `call_service()`, `get_error_log()`, `check_config()`

---

## Tasks

### 3.1 — Action dispatcher (`src/ha_workflow/actions.py`) ✅
- [x] **Done** — PR #20 (2026-03-22)
- Action dispatcher with validation, error handling, human-readable result messages
- Tests: `tests/test_actions.py`

### 3.2 — Default action on Enter ✅
- [x] **Done** — PR #20 (2026-03-22)
- `_cmd_action()` calls `dispatch_action()`, prints result, records usage on success

### 3.3 — Action sub-menu (Cmd modifier) — basic ✅
- [x] **Done** — PR #20 (2026-03-22)
- `_cmd_actions()` lists domain-specific actions (toggle, turn_on, etc.)
- Needs enhancement per 3.5–3.10 below

### 3.4 — HA system commands
- [ ] **Pending** — Issue #4
- Add to `_SYSTEM_COMMANDS` registry and `_cmd_system_action()` handler:
  - "System: Restart Home Assistant" — call `homeassistant/restart` with confirmation step
  - "System: Check config" — validate config, show result
  - "System: View logs" — fetch error log, display in Large Type / copy to clipboard
- Keywords: "restart", "logs", "check config"
- **Depends on:** ha_client (`get_error_log()`, `check_config()`)

### 3.5 — Enhanced sub-menu header & structure ✅
- [x] **Done** — PR #21 (2026-03-22)
- Reworked `_cmd_actions()` to show rich entity sub-menu:
  - **Header:** friendly_name as title, entity_id + relative last_changed as subtitle
  - Domain-specific actions (toggle, turn_on, etc.) below header
  - Copy, Open, and Advanced stub sections follow
- Fetches entity from cache for friendly_name, last_changed, area, device info
- Display-only entities (sensors) now show sub-menu with copy/open actions

### 3.6 — "Copy..." sub-menu ✅
- [x] **Done** — PR #21 (2026-03-22)
- Copy actions in entity sub-menu:
  - **"Copy Entity ID"** — copies entity_id to clipboard via `pbcopy`
  - **"Copy Entity Details"** — fetches full state, formats as YAML, copies via `pbcopy`
  - **"Copy Device Details"** — looks up device from registry, formats as YAML, copies (only shown if device exists)
- Routed through `_cmd_copy_action()` handler in `_cmd_action()`

### 3.7 — "Open in Home Assistant..." sub-menu ✅
- [x] **Done** — PR #21 (2026-03-22)
- Open actions in entity sub-menu (each opens URL via `open` command):
  - **"Open Entity"** — `{ha_url}/config/entities?filter={entity_id}`
  - **"Open Device"** — `{ha_url}/config/devices/device/{device_id}` (only if device exists)
  - **"Open Area"** — `{ha_url}/config/areas/area/{area_id}` (only if area exists)
  - **"Open History"** — `{ha_url}/history?entity_id={entity_id}`
- Routed through `_cmd_open_action()` handler in `_cmd_action()`
- Uses `_lookup_device_id()`, `_lookup_area_id()` helpers for registry lookups

### 3.8 — "Show Entity Details" viewer
- [ ] **Pending**
- Fetches full entity state via `ha_client.get_state()`, formats as YAML
- Displays in a new window with:
  - Syntax-highlighted YAML
  - Scrollable and foldable sections
  - Copy button to copy entire YAML to clipboard
- Implementation approach TBD — may use Alfred's Large Type, a Quick Look HTML preview, or a lightweight HTML window via `open`
- **Depends on:** `ha_client.get_state()`

### 3.9 — "View History" action
- [ ] **Pending**
- Fetch entity history via HA REST API: `GET /api/history/period/{timestamp}?filter_entity_id={entity_id}`
- Default: last 1 hour; option to expand to last 24 hours
- Format as a chronological log of state change events (timestamp + old state → new state)
- Display approach TBD — Large Type, text output, or HTML viewer
- **Requires:** New `ha_client.get_history()` method
- **Depends on:** ha_client

### 3.10 — "Advanced Action Call" (stub) ✅
- [x] **Done** — PR #21 (2026-03-22)
- Added "Advanced Action Call" item to entity sub-menu (last position)
- Displays: "Coming soon — advanced controls for {domain} entities"
- `valid=False` (not actionable yet)
- Future phase will implement domain-specific control UIs

---

## Investigate

### BUG-001 — Usage ranking
- [ ] **Pending** — Issue #5
- Usage-based auto-suggest/prioritization may not order correctly
- `record-usage` is now called from the action flow (3.2); investigate whether ranking works end-to-end

---

## Acceptance Criteria

- [x] Enter on a light → toggles it, shows notification, records usage
- [x] Cmd on a light → shows action menu (Toggle, Turn On, Turn Off)
- [x] Sub-menu title shows friendly name + entity_id, subtitle shows last changed
- [x] "Copy Entity ID" copies entity_id to clipboard
- [x] "Copy Entity Details" copies full YAML to clipboard
- [x] "Open Entity" opens HA entity grid filtered to entity
- [x] "Open Entity's Device" opens HA device page
- [x] "Open Entity's History" opens HA history filtered to entity
- [ ] "Show Entity Details" displays formatted YAML viewer
- [ ] "View History" shows last hour of state changes as event log
- [x] "Advanced Action Call" shows stub placeholder
- [ ] `ha restart` → shows confirmation → HA restarts
- [ ] `ha logs` → shows recent error log
- [ ] After using entities, empty `ha` query shows recently used entities first
