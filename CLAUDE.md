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

**Phase:** Implementation — Phase 0 (Foundation & CI/Packaging)

**Stack decision:** Python, targeting 3.9+ runtime (system `/usr/bin/python3` on macOS) for zero-friction distribution. Dev tooling (ruff, mypy, pytest) runs under local Python 3.12+. See `specs/spec-000-init.md` for original requirements and the plan file for full architecture.

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

## GitHub Workflow

This project follows a GitHub Issues + PR workflow under the **AYapejian** account.

- Every piece of work starts with a GitHub Issue
- Each PR represents one coherent, reviewable unit of work
- **Branch naming:** `feat/<issue-number>-short-description`, `fix/<issue-number>-short-description`
- **PR title format:** `feat:`, `fix:`, `chore:`, `docs:`, etc.
- **Merge strategy:** Squash and merge

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
