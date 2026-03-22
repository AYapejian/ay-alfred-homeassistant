# Phase 3: Actions & Entity Interaction

**Goal:** Users can act on entities, not just search them.
**Status:** Planned
**Branch:** TBD
**Depends on:** Phase 2, Phase 1.5

---

## Pre-existing Infrastructure (from Phase 1.5)

Phase 1.5 already built the action dispatch skeleton:
- `cli.py action {entity_id} {action}` is wired in `info.plist` (Phase 0) and dispatches via `_cmd_action()` (Phase 1.5)
- `__system__` entity actions dispatch through `_cmd_system_action()` — system command pattern is established
- `record-usage {entity_id}` CLI command exists — Phase 3 must call it after successful entity actions
- `_SYSTEM_COMMANDS` registry in `cli.py` — new HA system commands (logs, restart, check-config) should be added here

Phase 3 builds on this: implement the entity action dispatcher and wire `record-usage` into the action flow.

---

## Tasks

### 3.1 — Action dispatcher (`src/ha_workflow/actions.py`)
- [ ] **Pending**
- Map action names to HA service calls: `toggle` -> `{domain}/toggle`, `turn_on`, `turn_off`, `activate` (scenes/scripts), `lock`/`unlock`, `open`/`close` (covers), etc.
- Execute via `ha_client.call_service()`. Return success/failure.
- **Tests:** `tests/test_actions.py` — mocked HA client
- **Depends on:** 1.4 (HA client), 2.1 (DOMAIN_REGISTRY)

### 3.2 — Default action on Enter
- [ ] **Pending**
- Update `_cmd_action()` in `cli.py` to call action dispatcher for non-`__system__` entities (currently stubs)
- Run Script already wired in `info.plist`: `cli.py action "$entity_id" "$action"` (Phase 0)
- After successful action: call `record-usage {entity_id}` to feed usage tracking (Phase 1.5)
- Alfred Post Notification showing success/failure (notification node exists in `info.plist`)
- **Depends on:** 3.1, 1.5.3 (usage tracking)

### 3.3 — Action sub-menu (Cmd modifier)
- [ ] **Pending**
- Implement `_cmd_actions()` in `cli.py` (currently stubs) — second Script Filter listing available actions for that entity's domain
- Each action item triggers Run Script with specific action name
- Script Filter node already wired in `info.plist`: `cli.py actions "$entity_id"` (Phase 0)
- **Depends on:** 2.1 (DOMAIN_REGISTRY), 3.1

### 3.4 — HA system commands ✅
- [x] **Done** — PR (2026-03-22)
- Added to `_SYSTEM_COMMANDS` registry and `_cmd_system_action()` handler:
  - "System: Restart Home Assistant" — calls `homeassistant/restart`
  - "System: Check config" — validates config, shows valid/invalid + error details
  - "System: View error log" — fetches error log, copies to clipboard via `pbcopy`
- Keywords: "restart", "reboot", "check config", "validate", "log", "error", "debug"
- Also improved keyword matching from substring to word-prefix (avoids false positives)

### 3.8 — "Show Entity Details" viewer ✅
- [x] **Done** — PR #24 (2026-03-22)
- Fetches full entity state via `ha_client.get_state()`, formats as YAML
- Copies to clipboard via `pbcopy`, shows notification with entity name + state
- Action name: `show_details`, routed in `_cmd_action()`

### 3.9 — "View History" action ✅
- [x] **Done** — PR #24 (2026-03-22)
- New `HAClient.get_history()` method — `GET /api/history/period` with `filter_entity_id`
- Fetches last hour of state changes, formats as chronological log
- Copies to clipboard via `pbcopy`, shows notification with change count
- Action name: `view_history`, routed in `_cmd_action()`
- Also added: `_format_as_yaml()`, `_format_relative_time()`, `_format_history_entry()` helpers

---

## Acceptance Criteria

- [ ] Enter on a light -> toggles it, shows notification, records usage
- [ ] Cmd on a light -> shows action menu (Toggle, Turn On, Turn Off)
- [x] `ha restart` -> shows "System: Restart Home Assistant", Enter -> HA restarts
- [x] `ha logs` -> shows "System: View error log", Enter -> copies error log to clipboard
- [x] `ha check config` -> shows "System: Check config", Enter -> validates config
- [x] "Show Entity Details" copies YAML to clipboard with notification
- [x] "View History" copies last hour of state changes to clipboard
- [ ] After using entities, empty `ha` query shows recently used entities first (usage tracking end-to-end)
