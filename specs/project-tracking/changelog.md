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

### Repository published to GitHub

**Commits:** `06edc0c`, `518013f` (direct to `main`)

- MIT LICENSE, README rewrite, `.claude/` ignored
- `CLAUDE.md` documents the issue → branch → PR workflow, branch naming, labels and milestones

### CI and release workflows improved (#15)

**Commit:** `7416591` · Closes #14

- CI moved to `ubuntu-latest`; exposed as a reusable `workflow_call` so the release job runs the same checks
- Release reuses the CI-built artifact instead of rebuilding; `beta`/`rc`/`alpha` tags are marked prerelease
- `.github/release.yml` groups release notes by label
- `a38d608`: Claude review `max-turns` raised from 5 to 10 (reviews of large PRs were hitting the limit)

### Domain icons and area subtitles (#16, #17, #19)

**Commits:** `aa65ad3` (#16), `0e844d3` (direct), `e253049` (#17), `287f5d1` (#19)

- 34 domain-specific MDI icons on coloured rounded squares; `scripts/generate_icons.py` regenerates them
- Subtitles show the area name instead of the domain (domain fallback when no area)
- Areas are fetched from the entity, device and area registries during cache refresh — an entity's area falls back to its device's area, since HA usually assigns areas to devices
- Search scores `area_name` (weight 1.5); `area_name` and `device_id` added to the SQLite cache with migrations
- `uv.lock` regenerated after dev dependencies moved to `[project.optional-dependencies]`

**Verification:** 239 passed, 4 skipped (#17).

---

## 2026-03-22

### README status badges (#18)

**Commit:** `edb840f`

- CI, release, version, license, Python, Alfred, Home Assistant and ruff badges

### Action dispatcher — Enter and Cmd (#20)

**Commit:** `bb4cd4a` · Closes #1, #2, #3 · Phase 3 tasks 3.1–3.3

- `actions.py` `dispatch_action()` maps action names to HA service calls, validated against the domain registry
- Enter runs the entity's default action and records usage on success
- Cmd opens a per-domain action sub-menu

**Verification:** 272 passed, 4 skipped.

### Cmd modifier fix (#28)

**Commit:** `f28ff36` · Closes #27

- Cmd+Enter did not open the sub-menu: search items had no `mods.cmd`, so display-only entities blocked it and `$entity_id` was not passed through
- Every search item now carries `mods.cmd` with `valid=true` and explicit variables

**Verification:** 276 passed, 4 skipped.

### HA system commands (#23)

**Commit:** `1d58ebf` · Closes #4 · Phase 3 task 3.4

- Restart Home Assistant, Check config, View error log (copied to clipboard)
- System keyword matching changed from substring to word-prefix ("li" no longer matches "validate")

**Verification:** 286 passed, 4 skipped.

### Entity details and history (#25)

**Commit:** `c86f4a6` · Closes #24 · Phase 3 tasks 3.8, 3.9

- Show Entity Details: full state as YAML to the clipboard
- View History: last hour of state changes to the clipboard, via new `HAClient.get_history()`

**Verification:** 292 passed, 4 skipped.

### Enhanced entity sub-menu (#29)

**Commit:** `a7fbe6c` · Closes #21

- Re-application of #22, which was closed after rebase conflicts
- Header shows friendly name, entity_id and relative last-changed time (UTC-correct via `calendar.timegm`)
- Copy actions (entity ID, entity YAML, device YAML) and Open in HA (entity, device, area, history)
- Display-only entities get copy/open actions instead of "No actions available"

**Verification:** 314 passed, 4 skipped.

---

## 2026-03-24

### Phase 3 QA validation (#31)

**Commit:** `e6f6d31`

- Native macOS notifications (`notify.py`) replace print-based feedback, one channel per context
- `scripts/qa_smoke_test.py` and `scripts/QA_CHEATSHEET.md` for end-to-end manual checks against a live instance
- Nabu Casa 404 on the error-log endpoint now produces an actionable message

---

## 2026-04-07

### Parameterized actions (#32)

**Commits:** `54a71eb`, `8950523`, merged via `ff6f3b1`

- `params.py` parses short syntax (`brightness:50%,transition:2,color_name:blue`) with type coercion, validation, percent conversion and RGB
- Inline params on the CLI and an interactive param-entry flow in Alfred
- Input helpers gain `set_value` / `select_option`; `media_player` gains `volume_set`

**Verification:** 366 passed, 4 skipped.

- `1ed28b4` (direct): `.github/copilot-instructions.md`

---

## 2026-04-08

### Advanced-action param fixes (direct to `main`)

**Commits:** `15fc069`, `2dc1aa0`, `e62fa30`, `50f0eda`

- `$params` pre-declared in `info.plist` and cleared on every action item so a stale value can't leak into a plain toggle; "Advanced Action Call…" renamed "Set Params…"
- Params encoded into `$action` with a `::` separator, because Alfred did not reliably pass `$params` to the action node (removed again in #34)
- Actions Script Filter switched to inline `{query}` substitution — in argv mode it received the literal text `{query}`, so param entry could never trigger
- README moved actions, params and system commands from Planned to Features

---

## 2026-04-10

### Workflow UX redesign (#34)

**Commit:** `db94b13` · Closes #33

- Business logic extracted into `packages/ha_lib/`, a standalone package with no Alfred dependency
- Six thin Alfred scripts in `src/ha_workflow/scripts/`: search, actions, params, action runner, copy entity, open in HA
- `info.plist` redesigned: ⌥ Enter copies the entity ID, ⌃ Enter opens it in HA, a dedicated params Script Filter node, all variables declared
- The `::` encoding hack removed — params travel as a clean `$params` variable
- Empty search shows domain hint items; entities autocomplete to their friendly name; modifier subtitles on every result

### Claude Code GitHub workflow (#35)

**Commits:** `bb85357`, `82ec2a2`

- `@claude` mentions in PRs and issues run Claude Code in Actions
- Automatic review restricted to `ready_for_review`

---

## 2026-04-20

### Quick-exec from the search bar (#37)

**Commit:** `19a441a` · Closes #36

- `<entity_id> [params]` in the search bar becomes one item that fires on Enter, e.g. `light.foo brightness:80%,color:eggshell,transition:10`
- Action inferred from domain and param keys; named colours resolved to `rgb_color` from a bundled 1,052-entry palette
- An unknown entity_id falls back to fuzzy search

**Verification:** 416 passed, 4 skipped.

### System commands moved behind `ha system`

**Commit:** `66a9e62` (direct to `main`)

- System commands no longer appear in the default entity search; `ha system [filter]` shows only system items
- Supersedes the 2026-03-21 "System commands via search" decision in `status.md`

### Quick-exec in the actions submenu — reverted

**Commits:** `69b63a5`, reverted by `8cb0e7b` the same day (direct to `main`)

- Would have accepted `<entity_id> [params]` inside the actions submenu via a shared `ha_workflow.quick_exec` module. The revert records no reason.

---

## 2026-09-23

### Phase 1.6 — Preferred-label prioritization (#39)

**Commit:** `80df1c5` · Closes #38

- Search ranks in three tiers: usage history → entities with the preferred label → everything else, for both empty and typed queries
- Label set by `HA_PREFERRED_LABEL` (default `alfred_preferred`); device labels propagate to their entities, area labels do not
- Cache migration adds `labels_json`

**Verification:** 436 passed, 4 skipped.

### Dev-install symlink fix (#41)

**Commit:** `e19a291` · Closes #40

- The repo moved into `git-personal/`, leaving the dev-install symlinks dangling; Alfred dropped the workflow without an error
- `workflow/ha_workflow` is now a relative link; re-running `scripts/dev-install.sh` repairs stale or dangling links
- Previously stashed Phase 4 ideas (entity display, onboarding system commands) added to `phase-4-polish.md`
