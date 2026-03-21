# Changelog

Chronological log of completed work, decisions, and notable events.

---

## 2026-03-20

### Phase 0 completed and merged to main

**Commit:** `81a8c4e`
**Branch:** `feat/planning-phase` -> merged to `main`

**What was done:**
- Stack decision: Python (3.9+ runtime, 3.12+ dev tooling)
- `pyproject.toml` with ruff, mypy (strict, py39 target), pytest, hatchling
- `Makefile` with lint/format/typecheck/test/build/clean/dev-install targets
- `workflow/info.plist` — full Alfred 5 workflow skeleton with Script Filter, Run Script, action sub-menu, notification, user config vars
- `scripts/build.sh` — assembles `.alfredworkflow` zip artifact
- `scripts/dev-install.sh` — symlinks into Alfred for live dev
- `.github/workflows/ci.yml` — CI pipeline (untested, no remote)
- `.github/workflows/release.yml` — release pipeline (untested, no remote)
- Updated `CLAUDE.md` with stack decision and Python conventions

**Verification:** All `make` targets pass. `.alfredworkflow` artifact builds successfully (2345 bytes).

### Project tracking system created

- Created `specs/project-tracking/` with status, per-phase tracking, and changelog
- Backfilled Phase 0 completion and Phase 1-5 task breakdowns

### Phase 1 branch created

- Branch `feat/phase-1-config-ha-client` created off main
- Phase 1 tasks: config (1.1), errors (1.2), alfred JSON (1.3), HA client (1.4), CLI (1.5)

### Phase 1 completed and merged to main

**Commit:** `48462ac`
**Branch:** `feat/phase-1-config-ha-client` -> merged to `main`

**What was done:**
- Config module (`config.py`): reads `HA_URL`, `HA_TOKEN`, `CACHE_TTL` from env vars, Alfred dir detection, dev fallbacks
- Error handling (`errors.py`): `HAWorkflowError` hierarchy — `ConfigError`, `HAConnectionError`, `HAAuthError`
- Alfred JSON builder (`alfred.py`): `AlfredItem`, `AlfredMod`, `AlfredIcon`, `AlfredOutput` with full Script Filter JSON support
- HA REST client (`ha_client.py`): stdlib `urllib.request`, `get_states`, `get_config`, `call_service`, proper error mapping
- CLI entry point (`cli.py`): argument dispatch, `config validate` command, stub commands for Phase 2–3
- Ruff rule ignores for UP007/UP045 to preserve `Union`/`Optional` syntax (3.9 compat)
- Updated `dev-install.sh` with symlink support for source package
- Added `workflow/prefs.plist` to `.gitignore` (contains secrets)

**Verification:** 55 tests passing (1 skipped — integration test needs live HA), lint/typecheck clean, `.alfredworkflow` builds (7.7 KB). Manual test verified against HA v2026.3.2 with 2778 entities.

### Phase 2 completed on feat/phase-2-cache-search

**Branch:** `feat/phase-2-cache-search`

**What was done:**
- Entity data model (`entities.py`): `Entity` frozen dataclass with `from_state_dict()`, `DomainConfig` with subtitle formatters, `DOMAIN_REGISTRY` for 31 HA domains
- SQLite entity cache (`cache.py`): `EntityCache` class with WAL mode, full-replace refresh, staleness detection via `cache_meta` timestamps, `open_cache()` factory
- Fuzzy search (`search.py`): 5-tier scoring (exact/prefix/word-boundary/substring/char-sequence), weighted fields (friendly_name > entity_id > device_class > area), multi-word query support, capped at 50 results
- CLI wiring (`cli.py`): `search <query>` command with sync-on-first-run, `cache refresh` and `cache status` subcommands, background refresh with PID lock file and Alfred `rerun: 1.0`
- Updated integration tests for new search behavior

**Verification:** 143 tests passing (4 skipped — live HA), lint/typecheck clean, `.alfredworkflow` builds (14.6 KB).

---

## 2026-03-21

### Phase 1.5 completed and merged to main

**Commit:** `bae99ed`
**Branch:** `feat/phase-1.5-enhanced-search` -> merged to `main`

**What was done:**
- Query parser (`query_parser.py`): decomposes raw input into domain filter (`light:bedroom`), regex (`/pattern/`), or plain fuzzy search
- Domain filtering: `get_by_domain()` and `get_domain_counts()` on EntityCache using existing SQLite index
- Usage tracking (`usage.py`): separate SQLite DB in `data_dir` with `UsageTracker` class (record, count, clear, get stats)
- Usage-based ranking boost: `log(freq) + exponential recency decay` integrated into `fuzzy_search()` as optional parameter
- Regex search: `regex_search()` with case-insensitive `re.search()` against entity_id and friendly_name
- Domain suggestions (`suggestions.py`): Tab-completable domain filter items for partial domain queries
- System commands: `_SYSTEM_COMMANDS` registry with keyword matching, macOS system icon, "System" subtitle prefix. "History: Clear usage data" and "Cache: Refresh entities" — always shown at top, including on empty query
- Action handler: `_cmd_action()` dispatches `__system__` entity actions, stubs entity actions for Phase 3
- `record-usage` CLI command ready for Phase 3 integration
- Removed `uid` from entity items to prevent Alfred learning from overriding our ranking

**Verification:** 232 tests passing (4 skipped — live HA), lint/typecheck clean, `.alfredworkflow` builds (21.4 KB).

**Known issue:** Usage-based auto-suggest not yet end-to-end functional — `record-usage` is not called from the workflow until Phase 3 wires it into the action flow (BUG-001).
