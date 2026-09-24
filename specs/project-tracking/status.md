# Project Status

**Project:** ay-alfred-homeassistant
**Last updated:** 2026-09-24

---

## Current State

| Item | Value |
|------|-------|
| **Current phase** | None active — see Phase Overview |
| **Active branch** | — |
| **Last completed phase** | Phase 1.6 — Preferred-label prioritization |
| **Last commit on main** | `e19a291` — dev-install symlink fix (#41) |
| **Blockers** | None |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-20 | **Python** as implementation language | Strongest Alfred ecosystem (429+ repos), zero-friction distribution via system Python, user-extensible scripts. Go was runner-up. |
| 2026-03-20 | **Python 3.9+** runtime target | macOS system `/usr/bin/python3` is 3.9. Zero install friction. Dev tooling uses 3.12+. No 3.10+ syntax in shipped code. |
| 2026-03-20 | **Enter = default action, Cmd = sub-menu** | Power-user friendly. Enter toggles/activates. Cmd opens action list. |
| 2026-03-20 | **Pull-based cache (SQLite)** | Start simple with REST API polling + SQLite. WebSocket listener deferred to Phase 5. |
| 2026-03-20 | **Alfred Workflow Environment Variables** | Standard Alfred pattern for `HA_URL`, `HA_TOKEN`, `CACHE_TTL`. No separate config file. |
| 2026-03-20 | **All entity domains from day one** | No domain subset filtering. Index everything HA exposes. |
| 2026-03-20 | **CI/packaging early (Phase 0)** | Every phase produces a testable `.alfredworkflow` artifact. |
| 2026-03-21 | **No `uid` on entity items** | Prevents Alfred's built-in learning from overriding our usage-based ranking. Our fuzzy search + usage boost has full control over ordering. |
| 2026-03-21 | **System commands via search** | System actions (cache refresh, usage clear) surface as search results with `__system__` entity_id, distinct icon, and "System" subtitle. Dispatched through `_cmd_action` → `_cmd_system_action`. |
| 2026-04-21 | **Preferred-label tiering (not weight)** | Search results are grouped into explicit tiers: usage history → labeled (`HA_PREFERRED_LABEL`, default `alfred_preferred`) → everything else. Device-level labels propagate to child entities; area labels do not. Keeps the "usage wins" contract explicit instead of tuning weights. |
| 2026-09-24 | **Per-server storage keyed by normalized URL hash** | Entity cache, usage history, and refresh state live under `servers/<key>/` in Alfred's cache/data dirs, where `<key>` is a 12-char sha256 of the normalized `HA_URL`. Switching servers can never mix or clear another server's data; `Config.server_key` is the single seam a server-profiles feature can override. Legacy flat files migrate once into the server configured at upgrade. |

---

## Phase Overview

| Phase | Name | Status | Branch | Merged |
|-------|------|--------|--------|--------|
| 0 | Foundation & CI/Packaging | **Done** | `feat/planning-phase` | `81a8c4e` on main |
| 1 | Configuration & HA Client | **Done** | `feat/phase-1-config-ha-client` | `48462ac` on main |
| 2 | Entity Cache & Search | **Done** | `feat/phase-2-cache-search` | `1a48cc8` on main |
| 1.5 | Enhanced Search | **Done** | `feat/phase-1.5-enhanced-search` | `bae99ed` on main |
| 1.6 | Preferred-label prioritization | **Done** | `feat/38-preferred-label` | `80df1c5` on main |
| 1.7 | Multi-server support | **In progress** | `feat/46-per-server-storage` | — |
| 3 | Actions & Entity Interaction | **Next** | — | — |
| 4 | Polish & Usability | Planned | — | — |
| 5 | WebSocket Listener | Deferred | — | — |

---

## Known Bugs

| ID | Description | Phase | Status |
|----|-------------|-------|--------|
| BUG-001 | Usage-based auto-suggest/prioritization may not order correctly | 1.5 | Open — needs investigation. `record-usage` is not yet called from the workflow; Phase 3 will wire it into the action flow. |

---

## Architecture Reference

Spec: `specs/spec-000-init.md`

```
Alfred "ha" keyword -> Script Filter -> /usr/bin/python3 ha_workflow/cli.py search "{query}"
                                          -> Config (Alfred env vars)
                                          -> Cache check (SQLite)
                                          -> Query parser (domain filter, regex, fuzzy)
                                          -> System command matching
                                          -> Fuzzy search + usage boost
                                          -> Domain suggestions
                                          -> Alfred JSON output

Enter  -> Run Script -> cli.py action {entity_id} {action}  -> Notification
                        (handles __system__ dispatch + entity actions)
Cmd    -> Script Filter -> cli.py actions {entity_id}        -> action sub-menu
```
