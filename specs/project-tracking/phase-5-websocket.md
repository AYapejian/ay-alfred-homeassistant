# Phase 5: WebSocket Listener

**Goal:** Real-time entity cache updates via HA WebSocket API.
**Status:** Deferred
**Branch:** TBD
**Depends on:** Phase 2

---

## Tasks

### 5.1 — WebSocket client module
- [ ] **Pending**
- Vendor `websockets` or `wsproto` library (pure Python, no C extensions)
- Auth handshake with HA WebSocket API
- Subscribe to `state_changed` events

### 5.2 — Background listener process
- [ ] **Pending**
- Long-running process maintaining WebSocket connection
- Updates SQLite cache in real-time
- Managed via Alfred workflow triggers or launchd

### 5.3 — Cache integration
- [ ] **Pending**
- WebSocket keeps cache hot
- Pull-based (REST) is fallback when listener is not running
- Graceful degradation

---

## Notes

- Architecture decision (launchd daemon vs on-demand) deferred to when this phase starts
- Will need to vendor a WebSocket library into the `.alfredworkflow` artifact
