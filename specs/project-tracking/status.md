# Project Status

**Project:** ay-alfred-homeassistant
**Last updated:** 2026-03-20

---

## Current State

| Item | Value |
|------|-------|
| **Current phase** | Phase 1 — Configuration & HA Client |
| **Active branch** | `feat/phase-1-config-ha-client` |
| **Last completed phase** | Phase 0 — Foundation & CI/Packaging |
| **Last commit on main** | `81a8c4e` — Phase 0 merged |
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

---

## Phase Overview

| Phase | Name | Status | Branch | Merged |
|-------|------|--------|--------|--------|
| 0 | Foundation & CI/Packaging | **Done** | `feat/planning-phase` | `81a8c4e` on main |
| 1 | Configuration & HA Client | **In Progress** | `feat/phase-1-config-ha-client` | — |
| 2 | Entity Cache & Search | Planned | — | — |
| 3 | Actions & Entity Interaction | Planned | — | — |
| 4 | Polish & Usability | Planned | — | — |
| 5 | WebSocket Listener | Deferred | — | — |

---

## Architecture Reference

Full plan: `.claude/plans/tidy-shimmying-marble.md`
Spec: `specs/spec-000-init.md`

```
Alfred "ha" keyword -> Script Filter -> /usr/bin/python3 ha_workflow/cli.py search "{query}"
                                          -> Config (Alfred env vars)
                                          -> Cache check (SQLite)
                                          -> Fuzzy search
                                          -> Alfred JSON output

Enter  -> Run Script -> cli.py action {entity_id} {action}  -> Notification
Cmd    -> Script Filter -> cli.py actions {entity_id}        -> action sub-menu
```
