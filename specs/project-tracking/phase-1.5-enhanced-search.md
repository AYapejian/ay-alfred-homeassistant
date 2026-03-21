# Phase 1.5: Enhanced Search

**Goal:** Smart search with domain filtering, usage-based ranking, regex support, system commands, and domain autocomplete — making the search feel like VS Code's command palette.
**Status:** Done
**Branch:** `feat/phase-1.5-enhanced-search`
**Merged:** `bae99ed` on main
**Depends on:** Phase 2

---

## Tasks

### 1.5.1 — Query parser module (`src/ha_workflow/query_parser.py`)
- [x] **Done** — 2026-03-21
- `ParsedQuery` frozen dataclass: `mode` (fuzzy/regex/domain_browse), `text`, `domain_filter`, `regex_pattern`
- `parse_query(raw)`: regex detection (`/pattern/`), domain filter extraction (`light:bedroom`), fallback to plain fuzzy
- Validates domain prefixes against `DOMAIN_REGISTRY` — invalid prefixes treated as plain text
- **Tests:** `tests/test_query_parser.py` — 21 tests

### 1.5.2 — Domain filtering in cache (`src/ha_workflow/cache.py`)
- [x] **Done** — 2026-03-21
- `get_by_domain(domain)` — SQL query using existing `idx_entities_domain` index
- `get_domain_counts()` — `GROUP BY domain` for suggestion display
- **Tests:** 6 new tests in `tests/test_cache.py`

### 1.5.3 — Usage tracking module (`src/ha_workflow/usage.py`)
- [x] **Done** — 2026-03-21
- Separate SQLite DB at `config.data_dir/usage.db` (survives cache clears)
- `usage_stats` table: `entity_id` PK, `use_count` INT, `last_used_at` REAL
- `UsageTracker` class: `record_usage()`, `get_usage_stats()`, `get_usage_record()`, `count()`, `clear()`
- `UsageRecord` frozen dataclass, `open_usage_tracker(config)` factory
- **Tests:** `tests/test_usage.py` — 15 tests

### 1.5.4 — Usage-based ranking boost (`src/ha_workflow/search.py`)
- [x] **Done** — 2026-03-21
- Scoring: `(0.7 * log(count+1) + 0.3 * 2^(-age/24h)) * USAGE_WEIGHT`
- `fuzzy_search()` gains optional `usage_stats` + `now` params (default None = backward compatible)
- Non-empty query: fuzzy_score + usage_boost for ranking
- Empty query: sort by usage score descending, then alphabetically
- **Tests:** 8 new tests in `tests/test_search.py`

### 1.5.5 — Regex search (`src/ha_workflow/search.py`)
- [x] **Done** — 2026-03-21
- `regex_search(entities, pattern, max_results=50)` — `re.search()` against entity_id and friendly_name
- Case insensitive, binary match (no scoring), results in cache order
- Raises `re.error` for invalid patterns (CLI shows Alfred error item)
- **Tests:** 8 new tests in `tests/test_search.py`

### 1.5.6 — Domain suggestions and smart empty state (`src/ha_workflow/suggestions.py`)
- [x] **Done** — 2026-03-21
- `build_domain_suggestions(query, domain_counts)` — prefix-match query against domain names
- Triggers only when query is a single `[a-z_]+` token (≥2 chars)
- Returns AlfredItems with `autocomplete="light:"`, `valid=False`, sorted by count desc
- `sort_by_usage(entities, usage_stats)` — sort entities by usage score for empty-query display
- **Tests:** `tests/test_suggestions.py` — 18 tests

### 1.5.7 — CLI integration, system commands, and action dispatch (`src/ha_workflow/cli.py`)
- [x] **Done** — 2026-03-21
- `_cmd_search()` rewritten: parse query → route to fuzzy/regex/domain-browse → load usage stats → prepend system commands → prepend domain suggestions
- System commands: `_SYSTEM_COMMANDS` registry with keyword matching, macOS system icon, "System" subtitle prefix. Always shown at top. Displayed on empty query too.
- `_cmd_action()`: dispatches `__system__` entity actions via `_cmd_system_action()`, stubs entity actions for Phase 3
- Current system commands: "History: Clear usage data" (`usage_clear`), "Cache: Refresh entities" (`cache_refresh`)
- `record-usage {entity_id}` CLI command for Phase 3 to call after action execution
- Removed `uid` from entity items — prevents Alfred's built-in learning from overriding our ranking
- **Tests:** 32 tests in `tests/test_cli.py` (was 19)

---

## Known Issues

- [!] **Usage-based ranking may not work as expected** — needs investigation. `record-usage` is never called from the Alfred workflow yet (Phase 3 will wire it). Ordering on empty query may not reflect actual usage until Phase 3 integrates the recording hook.

---

## Acceptance Criteria

- [x] `make lint && make typecheck && make test && make build` all pass
- [x] All existing tests still pass (no regressions) — 232 pass, 4 skipped
- [x] `ha bedroom` — fuzzy search works as before
- [x] `ha light:` — shows all light entities
- [x] `ha light:bed` — shows only lights matching "bed"
- [x] `ha /.*room$/` — regex matches entities ending in "room"
- [x] `ha li` — shows "Filter: light" suggestion at top, Tab fills `light:`
- [x] `ha` (empty) — system commands appear at top before entity results
- [x] `ha history clear` — "History: Clear usage data" appears as actionable item
- [x] Invalid regex (`ha /[bad/`) shows error item, not a crash
- [ ] After repeated entity selections, empty `ha` query shows recently/frequently used first — **blocked on Phase 3 wiring `record-usage`**
