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
