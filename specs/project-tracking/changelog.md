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
