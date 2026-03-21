# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Description

**Project:** ay-alfred-homeassistant
**Owner:** AYapejian

An Alfred Workflow for macOS that integrates with Home Assistant. Users invoke Alfred to search HA entities (by ID, friendly name, or attributes), execute service calls, toggle automations, fetch logs, validate config, and restart HA — all from the Alfred search bar. The workflow ships as an importable `.alfredworkflow` artifact.

This is **not** a Home Assistant add-on. There is no Docker container or HA supervisor component. The workflow runs entirely on the user's Mac and communicates with HA over its REST and WebSocket APIs.

---

## Project Status

See `specs/project-tracking/status.md` for current phase, task progress, and key decisions.

**Stack:** Python 3.9+ runtime, `uv` + ruff/mypy/pytest dev tooling.
**Action UX:** Enter = smart default action per entity domain. Cmd modifier = action sub-menu.
**Cache:** Pull-based REST with SQLite. WebSocket listener deferred.
**Config:** Alfred 5 Workflow Environment Variables (`HA_URL`, `HA_TOKEN`).

---

## Target Platform

- **Alfred 5** (latest: 5.7.x) — requires Powerpack license for workflows
- **macOS** — Intel and Apple Silicon
- **Home Assistant** — communicates via REST API and WebSocket API

---

## Planned Capabilities

- Fuzzy search / discovery across HA entities (entity IDs, friendly names, attributes)
- Cached entity index kept fresh via HA WebSocket state-change events
- Action execution from Alfred: service calls, automation control, log fetching, config validation, HA restart
- Background listener for real-time state updates
- User-extensible via custom scripts/actions/hooks
- Distributable as a single `.alfredworkflow` file with configurable HA URL, token, and defaults

---

## Project Tracking

All task planning, progress, and completion is tracked in `specs/project-tracking/`. This is the source of truth for project state — do not rely solely on agentic memory or conversation context.

- **Entry point:** `specs/project-tracking/status.md` — current phase, key decisions, phase overview
- **Per-phase files:** `specs/project-tracking/phase-N-*.md` — task breakdowns, acceptance criteria, status checkboxes
- **Changelog:** `specs/project-tracking/changelog.md` — chronological log of completed work

### Tracking rules

- **When planning tasks:** update the relevant `phase-N-*.md` with task breakdowns
- **When starting a task:** note the date in the phase file
- **When completing a task:** check the box `[x]`, note the date and commit hash
- **When a task errors or is blocked:** mark with `[!]` and log the issue inline
- **When a phase completes:** update `status.md` current state table and add a `changelog.md` entry
- **When key decisions are made:** add to the "Key Decisions" table in `status.md`

---

## Git Workflow

This project uses a GitHub Issues + PR workflow under the **AYapejian** account.
Repository: `AYapejian/ay-alfred-homeassistant`

### Branches & Commits

- Each PR represents one coherent, reviewable unit of work
- **Branch naming:** `feat/<issue-N>-short-description`, `fix/<issue-N>-short-description`, `chore/<issue-N>-short-description`
- **Commit message prefixes:** `feat:`, `fix:`, `chore:`, `docs:`, etc.
- **Merge strategy:** Squash and merge for PRs. Fast-forward merge for local-only work.

### Issues & PRs

- **All work is tracked via GitHub Issues.** Each issue maps to one PR.
- **PR body must reference its issue:** use `Closes #N` to auto-close the issue on merge.
- **Issues cross-reference dependencies:** use `Depends on #N` in issue bodies.
- **Issues link to spec docs and source files** in the repo for full context.
- **Milestones** group issues by phase. Issues can move between milestones freely.

### Labels

| Category | Labels | Purpose |
|----------|--------|---------|
| Type | `feature`, `bug`, `chore`, `docs`, `idea` | What kind of work |
| Area | `area/search`, `area/actions`, `area/cache`, `area/cli`, `area/config`, `area/infra` | What part of the codebase |
| Priority | `P1-high`, `P2-medium`, `P3-low` | Triage ordering |
| Status | `blocked` | Exceptional states only |

### CI & Releases

- **CI:** GitHub Actions runs lint, format check, type check, tests, and build on every push to `main` and every PR. See `.github/workflows/ci.yml`.
- **Releases:** Tag with `vX.Y.Z` to trigger the release workflow, which builds the `.alfredworkflow` and creates a GitHub Release. See `.github/workflows/release.yml`.
- **Code Review:** Claude Code reviews PRs automatically on open/reopen. Use `@claude` in any PR comment for interactive follow-up. See `.github/REVIEW.md` for review guidelines.

---

## Conventions

### Specs

- All spec documents live in `specs/` as Markdown (`.md`) files
- Naming: `spec-NNN-short-description.md`

### YAML (if used in workflow config)

- 2-space indentation (enforced by `.editorconfig`)
- Quote ambiguous strings (e.g., version numbers: `"1.0"`)

### Python

- **Runtime target:** Python 3.9+ (system `/usr/bin/python3` on macOS)
- **Dev tooling:** Python 3.12+ locally
- `uv` for dependency management (`uv add`, `uv sync`, `uv run`)
- Formatter: `ruff format` (line length 88)
- Linter: `ruff check`
- Type checker: `mypy` strict mode
- Tests: `pytest`
- **No 3.10+ syntax in shipped code** — no `match` statements, no `X | Y` union types, no `except*`

---

## References

- [Alfred Workflows Documentation](https://www.alfredapp.com/help/workflows/)
- [Alfred Script Filter JSON Format](https://www.alfredapp.com/help/workflows/inputs/script-filter/json/)
- [Alfred Script Environment Variables](https://www.alfredapp.com/help/workflows/script-environment-variables/)
- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest)
- [Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket)
