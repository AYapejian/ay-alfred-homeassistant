# Phase 2: Entity Cache & Search

**Goal:** Core user experience — type a query in Alfred, see matching HA entities.
**Status:** Planned
**Branch:** TBD
**Depends on:** Phase 1

---

## Tasks

### 2.1 — Entity data model (`src/ha_workflow/entities.py`)
- [ ] **Pending**
- `Entity` dataclass: `entity_id`, `domain`, `state`, `friendly_name`, `attributes` (dict), `last_updated`
- `DomainConfig`: `default_action`, `available_actions`, `icon_name`, `subtitle_formatter`
- `DOMAIN_REGISTRY` covering all common HA domains (light, switch, sensor, binary_sensor, automation, script, scene, climate, media_player, cover, fan, lock, vacuum, camera, weather, person, zone, input_boolean, input_number, input_select, input_text, group, timer, counter, input_datetime, number, select, button, humidifier, water_heater, siren, update, etc.)
- **Tests:** `tests/test_entities.py`
- **Depends on:** 0.1

### 2.2 — SQLite entity cache (`src/ha_workflow/cache.py`)
- [ ] **Pending**
- Create/open SQLite DB in Alfred cache directory. WAL mode.
- Methods: `refresh(entities)`, `get_all()`, `search(query)` (basic LIKE), `get_cache_age()`, `is_stale(ttl)`
- Schema: `entities` table (entity_id PK, domain, state, friendly_name, attributes_json, last_changed, last_updated), `cache_meta` table, indexes on domain and friendly_name
- **Tests:** `tests/test_cache.py` — in-memory SQLite
- **Depends on:** 1.1, 2.1

### 2.3 — Fuzzy search (`src/ha_workflow/search.py`)
- [ ] **Pending**
- Scoring: exact > prefix > word-boundary > substring > character-sequence
- Fields: `friendly_name` (highest weight), `entity_id` (medium), `device_class`/attributes (lower)
- Cap at 50 results. Sorted by score.
- **Tests:** `tests/test_search.py` — diverse match types, edge cases, scoring order
- **Depends on:** 2.1

### 2.4 — Search command end-to-end
- [ ] **Pending**
- Wire `search` in `cli.py`: config -> cache check -> refresh if needed -> fuzzy search -> Alfred JSON
- Each result: friendly name as title, domain + state subtitle, domain icon, entity_id + default_action as variables
- **Depends on:** 1.3, 1.4, 2.2, 2.3

### 2.5 — Background cache refresh
- [ ] **Pending**
- Stale cache: return cached results immediately, spawn detached `subprocess.Popen` to refresh
- Set Alfred `rerun: 1.0` for re-execution with fresh data
- PID-based lock file prevents concurrent refreshes
- **Depends on:** 2.4

---

## Acceptance Criteria

- [ ] `make lint && make typecheck && make test && make build` all pass
- [ ] Manual: `ha living` in Alfred shows matching entities with correct subtitles
- [ ] Cache file exists in Alfred cache directory after first search
- [ ] Stale cache returns fast + refreshes in background
