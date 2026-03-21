# Phase 2: Entity Cache & Search

**Goal:** Core user experience — type a query in Alfred, see matching HA entities.
**Status:** Done
**Branch:** `feat/phase-2-cache-search`
**Depends on:** Phase 1

---

## Tasks

### 2.1 — Entity data model (`src/ha_workflow/entities.py`)
- [x] **Done** — 2026-03-20
- `Entity` frozen dataclass: `entity_id`, `domain`, `state`, `friendly_name`, `attributes` (dict), `last_changed`, `last_updated`
- `Entity.from_state_dict()` classmethod converts HA REST API state dicts
- `DomainConfig`: `default_action`, `available_actions`, `icon_path`, `subtitle_formatter`
- `DOMAIN_REGISTRY` covering 31 HA domains with domain-specific subtitle formatters (light, sensor, climate, media_player, cover, update, etc.)
- `get_domain_config(domain)` with unknown-domain fallback
- **Tests:** `tests/test_entities.py` — 29 tests

### 2.2 — SQLite entity cache (`src/ha_workflow/cache.py`)
- [x] **Done** — 2026-03-20
- `EntityCache` class: SQLite DB in Alfred cache directory, WAL mode
- Methods: `refresh(entities)`, `get_all()`, `search(query)` (LIKE), `get_cache_age()`, `is_stale(ttl)`, `close()`
- Schema: `entities` table (entity_id PK, domain, state, friendly_name, attributes_json, last_changed, last_updated), `cache_meta` table (key/value), indexes on domain and friendly_name
- `open_cache(config)` factory function
- **Tests:** `tests/test_cache.py` — 17 tests (in-memory SQLite)

### 2.3 — Fuzzy search (`src/ha_workflow/search.py`)
- [x] **Done** — 2026-03-20
- 5-tier scoring: exact(100) > prefix(80) > word-boundary(60) > substring(40) > char-sequence(20)
- Field weights: friendly_name(3.0) > entity_id(2.0) > device_class(1.0) > area attrs(0.5)
- Multi-word queries: each word must match, scores summed
- Cap at 50 results, sorted by descending score
- **Tests:** `tests/test_search.py` — 31 tests (scoring tiers, multi-word, edge cases)

### 2.4 — Search command end-to-end
- [x] **Done** — 2026-03-20
- `search <query>` wired in `cli.py`: config → open cache → sync refresh on first run → fuzzy search → Alfred JSON
- Each result: friendly_name title, "domain · state" subtitle, domain icon, entity_id/action/domain variables
- `cache refresh` and `cache status` subcommands implemented
- **Tests:** `tests/test_cli.py` updated — 22 tests total

### 2.5 — Background cache refresh
- [x] **Done** — 2026-03-20
- Stale cache: returns cached results immediately, spawns detached `subprocess.Popen` to refresh
- Alfred `rerun: 1.0` triggers re-execution with fresh data
- PID-based lock file (`.refresh.lock`) prevents concurrent refreshes; stale locks cleaned up
- Lock file removed after `cache refresh` completes
- **Tests:** background refresh tests in `tests/test_cli.py`

---

## Acceptance Criteria

- [x] `make lint && make typecheck && make test && make build` all pass
- [x] 143 tests passing (4 skipped — live HA integration tests)
- [x] `.alfredworkflow` artifact builds (14.6 KB)
- [ ] Manual: `ha living` in Alfred shows matching entities with correct subtitles
- [ ] Cache file exists in Alfred cache directory after first search
- [ ] Stale cache returns fast + refreshes in background
