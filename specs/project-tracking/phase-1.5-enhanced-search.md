# Phase 1.5: Enhanced Search

**Goal:** Smart search with domain filtering, usage-based ranking, regex support, and domain autocomplete — making the search feel like VS Code's command palette.
**Status:** Planned
**Branch:** TBD (`feat/phase-1.5-enhanced-search`)
**Depends on:** Phase 2

---

## Tasks

### 1.5.1 — Query parser module (`src/ha_workflow/query_parser.py`)
- [ ] **Pending**
- `ParsedQuery` frozen dataclass: `mode` (fuzzy/regex/domain_browse), `text`, `domain_filter`, `regex_pattern`
- `parse_query(raw)`: regex detection (`/pattern/`), domain filter extraction (`light:bedroom`), fallback to plain fuzzy
- Validates domain prefixes against `DOMAIN_REGISTRY` — invalid prefixes treated as plain text
- **Tests:** `tests/test_query_parser.py` — ~15 tests
- **Depends on:** 2.1 (DOMAIN_REGISTRY)

### 1.5.2 — Domain filtering in cache (`src/ha_workflow/cache.py`)
- [ ] **Pending**
- `get_by_domain(domain)` — SQL query using existing `idx_entities_domain` index
- `get_domain_counts()` — `GROUP BY domain` for suggestion display
- **Tests:** ~6 new tests in `tests/test_cache.py`
- **Depends on:** 2.2

### 1.5.3 — Usage tracking module (`src/ha_workflow/usage.py`)
- [ ] **Pending**
- Separate SQLite DB at `config.data_dir/usage.db` (survives cache clears)
- `usage_stats` table: `entity_id` PK, `use_count` INT, `last_used_at` REAL
- `UsageTracker` class: `record_usage()` (UPSERT), `get_usage_stats()`, `get_usage_record()`
- `UsageRecord` frozen dataclass, `open_usage_tracker(config)` factory
- **Tests:** `tests/test_usage.py` — ~10 tests

### 1.5.4 — Usage-based ranking boost (`src/ha_workflow/search.py`)
- [ ] **Pending**
- Scoring: `(0.7 * log(count+1) + 0.3 * 2^(-age/24h)) * USAGE_WEIGHT`
- `fuzzy_search()` gains optional `usage_stats` + `now` params (default None = backward compatible)
- Non-empty query: fuzzy_score + usage_boost for ranking
- Empty query: sort by usage score descending, then alphabetically
- **Tests:** ~10 new tests in `tests/test_search.py`
- **Depends on:** 1.5.3

### 1.5.5 — Regex search (`src/ha_workflow/search.py`)
- [ ] **Pending**
- `regex_search(entities, pattern, max_results=50)` — `re.search()` against entity_id and friendly_name
- Case insensitive, binary match (no scoring), results in cache order
- Raises `re.error` for invalid patterns (CLI shows Alfred error item)
- **Tests:** ~8 new tests in `tests/test_search.py`

### 1.5.6 — Domain suggestions and smart empty state (`src/ha_workflow/suggestions.py`)
- [ ] **Pending**
- `build_domain_suggestions(query, domain_counts)` — prefix-match query against domain names
- Triggers only when query is a single `[a-z_]+` token (≥2 chars)
- Returns AlfredItems with `autocomplete="light:"`, `valid=False`, sorted by count desc
- `build_usage_sorted_items(entities, usage_stats)` — sort entities by usage score for empty-query display
- **Tests:** `tests/test_suggestions.py` — ~10 tests
- **Depends on:** 1.5.2, 1.5.3

### 1.5.7 — CLI integration and end-to-end wiring (`src/ha_workflow/cli.py`)
- [ ] **Pending**
- Update `_cmd_search()`: parse query → route to fuzzy/regex/domain-browse → load usage stats → prepend domain suggestions
- New CLI command: `record-usage {entity_id}` — Phase 3 action dispatcher will call this
- Handle regex errors with Alfred error item
- **Tests:** ~12 new tests in `tests/test_cli.py`
- **Depends on:** 1.5.1–1.5.6

---

## Acceptance Criteria

- [ ] `make lint && make typecheck && make test && make build` all pass
- [ ] All existing tests still pass (no regressions)
- [ ] `ha bedroom` — fuzzy search works as before
- [ ] `ha light:` — shows all light entities
- [ ] `ha light:bed` — shows only lights matching "bed"
- [ ] `ha /.*room$/` — regex matches entities ending in "room"
- [ ] `ha li` — shows "Filter: light" suggestion at top, Tab fills `light:`
- [ ] After repeated entity selections, empty `ha` query shows recently/frequently used first
- [ ] Invalid regex (`ha /[bad/`) shows error item, not a crash
