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

### 3.4 — HA system commands
- [ ] **Pending**
- Add to `_SYSTEM_COMMANDS` registry and `_cmd_system_action()` handler (Phase 1.5 infrastructure):
  - "System: Restart Home Assistant" — call `homeassistant/restart` with confirmation step
  - "System: Check config" — validate config, show result
  - "System: View logs" — fetch error log, display in Large Type / copy to clipboard
- Keywords should match natural queries like "restart", "logs", "check config"
- **Depends on:** 1.4 (HA client), 1.5.7 (system commands infrastructure)

---

## Acceptance Criteria

- [ ] Enter on a light -> toggles it, shows notification, records usage
- [ ] Cmd on a light -> shows action menu (Toggle, Turn On, Turn Off)
- [ ] `ha restart` -> shows "System: Restart Home Assistant", Enter -> confirmation -> HA restarts
- [ ] `ha logs` -> shows "System: View logs", Enter -> shows recent error log
- [ ] After using entities, empty `ha` query shows recently used entities first (usage tracking end-to-end)
