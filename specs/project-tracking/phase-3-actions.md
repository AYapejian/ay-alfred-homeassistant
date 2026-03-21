# Phase 3: Actions & Entity Interaction

**Goal:** Users can act on entities, not just search them.
**Status:** Planned
**Branch:** TBD
**Depends on:** Phase 2

---

## Tasks

### 3.1 — Action dispatcher (`src/ha_workflow/actions.py`)
- [ ] **Pending**
- Map action names to HA service calls: `toggle` -> `{domain}/toggle`, `turn_on`, `turn_off`, `activate` (scenes/scripts), `lock`/`unlock`, `open`/`close` (covers), etc.
- Execute via `ha_client.call_service()`. Return success/failure.
- **Tests:** `tests/test_actions.py` — mocked HA client
- **Depends on:** 1.4, 2.1

### 3.2 — Default action on Enter
- [ ] **Pending**
- Wire Run Script in `info.plist`: `cli.py action {entity_id} {action}`
- Action determined by domain default from `DOMAIN_REGISTRY`
- Alfred Post Notification showing success/failure
- **Depends on:** 3.1, 2.4

### 3.3 — Action sub-menu (Cmd modifier)
- [ ] **Pending**
- Cmd on a result -> second Script Filter listing available actions for that entity's domain
- Each action item triggers Run Script with specific action name
- **Depends on:** 2.1, 3.1

### 3.4 — HA system commands
- [ ] **Pending**
- `ha logs` — fetch error log, display in Large Type / copy to clipboard
- `ha restart` — call `homeassistant/restart` with confirmation step
- `ha check-config` — validate config, show result
- Surface these when search query matches "log", "restart", "config"
- **Depends on:** 1.4, 1.3

---

## Acceptance Criteria

- [ ] Enter on a light -> toggles it
- [ ] Cmd on a light -> shows action menu (Toggle, Turn On, Turn Off)
- [ ] `ha restart` -> confirmation -> HA restarts
- [ ] `ha logs` -> shows recent error log
