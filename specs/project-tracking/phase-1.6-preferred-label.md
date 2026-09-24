# Phase 1.6: Preferred-Label Prioritization

**Goal:** Let users tag entities (or devices) in Home Assistant with a label so those entities float above unlabeled ones in Alfred search results, without disturbing usage-history-based ranking.
**Status:** Done — merged as `80df1c5` (#39)
**Branch:** `feat/38-preferred-label`
**Issue:** [#38](https://github.com/AYapejian/ay-alfred-homeassistant/issues/38)
**Depends on:** Phase 1.5

---

## Tasks

### 1.6.1 — Labels on `Entity`
- [x] **Done** — 2026-04-21
- Add `labels: tuple[str, ...] = ()` to `Entity` in `src/ha_workflow/entities.py` and `packages/ha_lib/entities.py`
- `Entity.from_state_dict` takes a `labels` kwarg
- **Tests:** `tests/test_entities.py` — default-empty + passed-through cases

### 1.6.2 — Cache schema migration
- [x] **Done** — 2026-04-21
- Add `labels_json TEXT NOT NULL DEFAULT '[]'` column in `src/ha_workflow/cache.py` and `packages/ha_lib/cache.py`
- Runtime migration handles legacy DBs created before the column existed
- **Tests:** `tests/test_cache.py::TestLabels` — round-trip + legacy migration

### 1.6.3 — Registry lookup for labels
- [x] **Done** — 2026-04-21
- Extend `_RegistryInfo` in `src/ha_workflow/cli.py` with `labels`
- `_build_registry_lookup` reads `labels` from entity-registry entries and unions in the owning device's labels (device tags propagate to child entities, mirroring area resolution)
- Area labels do **not** propagate (scope kept targeted to v1)
- Labels normalized to lowercase, deduped

### 1.6.4 — `HA_PREFERRED_LABEL` config
- [x] **Done** — 2026-04-21
- Add `preferred_label: str` to `Config` in both packages
- Sourced from env var `HA_PREFERRED_LABEL`, default `alfred_preferred`, lowercased and stripped
- Empty-string override falls back to the default
- **Tests:** 4 new tests in `tests/test_config.py`

### 1.6.5 — Tier-based search ordering
- [x] **Done** — 2026-04-21
- `fuzzy_search(..., preferred_label=None)` in both packages
- Three-tier sort key: (0) entities with a usage record → (1) labeled entities → (2) the rest
- Within each tier the existing combined `fuzzy_score + usage_boost` ordering applies
- Empty-query path uses the same tiers, falling back to alphabetical within each tier
- **Tests:** `tests/test_search.py::TestPreferredLabel` — 7 cases covering tier ordering, case-insensitive match, usage-still-wins, inclusion gating

### 1.6.6 — Wire through CLI + script entry points
- [x] **Done** — 2026-04-21
- `src/ha_workflow/cli.py`: pass `config.preferred_label` into `_search_fuzzy` / `_search_domain_filtered`
- `src/ha_workflow/scripts/search_filter.py`: same for the `_lib_search.fuzzy_search` paths plus `_quick_exec` fallback

### 1.6.7 — Expose `HA_PREFERRED_LABEL` in Alfred
- [x] **Done** — 2026-04-21
- New `textfield` workflow variable in `workflow/info.plist` with default `alfred_preferred`
- Updated workflow description comment block with the new variable

### 1.6.8 — Docs
- [x] **Done** — 2026-04-21
- README: documented the label + override under the "Promoting entities to the top" section

### 1.6.9 — Merge & changelog
- [x] **Done** — 2026-09-23 · squash-merged as `80df1c5` (#39); changelog and `status.md` updated in #42

---

## Key decisions

| Decision | Rationale |
|----------|-----------|
| **Tier-based sort, not additive weight** | Users asked for history-first, then labeled, then rest. Additive weights drift with tuning; explicit tiers make the contract obvious. |
| **Device labels propagate, area labels do not** | Mirrors the existing area-resolution pattern. Device tags are targeted enough that "every entity on this device" is usually the user's intent; area-wide promotion would be too broad. |
| **Default slug `alfred_preferred`** | HA normalizes "Alfred Preferred" → `alfred_preferred`. Matches HA's conventions so setup is copy/paste from the UI. |
| **Single label only (v1)** | Multiple labels / weighted priorities can come later; start with one clear signal. |

---

## Follow-ups

- Visual hint in the Alfred row when an entity is preferred (icon badge or subtitle prefix)
- Multi-label support (comma-separated) with ordered priority
- Area-label propagation behind a second env var (if requested)
