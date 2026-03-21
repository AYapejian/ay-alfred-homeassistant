# Phase 0: Foundation & CI/Packaging

**Goal:** Establish project scaffold so every subsequent phase produces a testable `.alfredworkflow` artifact.
**Status:** Done
**Branch:** `feat/planning-phase` (merged to main)
**Commit:** `81a8c4e`
**Date completed:** 2026-03-20

---

## Tasks

### 0.1 — Python project setup
- [x] **Completed 2026-03-20**
- Created `pyproject.toml` with metadata, ruff/mypy/pytest config, hatchling build backend
- Created `src/ha_workflow/__init__.py`, `tests/__init__.py`, `tests/conftest.py`
- Created `Makefile` with targets: `lint`, `format`, `format-check`, `typecheck`, `test`, `build`, `clean`
- Set up `uv` dev environment (`uv sync --extra dev`)
- Added smoke test `tests/test_version.py`
- **Note:** Had to add `[tool.hatch.build.targets.wheel] packages = ["src/ha_workflow"]` because hatchling couldn't auto-discover the package under `src/`.
- **Files:** `pyproject.toml`, `Makefile`, `uv.lock`, `src/ha_workflow/__init__.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_version.py`

### 0.2 — Alfred workflow skeleton (`info.plist`)
- [x] **Completed 2026-03-20**
- Created `workflow/info.plist` with:
  - Bundle ID: `com.ayapejian.alfred-homeassistant`
  - User Configuration: `HA_URL` (required), `HA_TOKEN` (required), `CACHE_TTL` (optional, default 60)
  - Object 0: Script Filter — keyword `ha`, invokes `/usr/bin/python3 ha_workflow/cli.py search "{query}"`
  - Object 1: Run Script — invokes `cli.py action "$entity_id" "$action"`
  - Object 2: Post Notification — shows action result
  - Object 3: Script Filter — action sub-menu via `cli.py actions "$entity_id"`
  - Connections: search->action (Enter), search->actions (Cmd/1048576), actions->action, action->notification
- Created placeholder `workflow/icon.png` (64x64 blue square)
- Validated with `plutil -lint`
- **Files:** `workflow/info.plist`, `workflow/icon.png`

### 0.3 — Build script & packaging
- [x] **Completed 2026-03-20**
- Created `scripts/build.sh`: stages files, zips to `dist/ay-alfred-homeassistant.alfredworkflow`
- Created `scripts/dev-install.sh`: symlinks repo into Alfred's workflow directory for live dev
- Added `make build` and `make dev-install` targets
- Verified: `make build` produces 2345-byte `.alfredworkflow` containing `info.plist`, `icon.png`, `ha_workflow/__init__.py`
- **Files:** `scripts/build.sh`, `scripts/dev-install.sh`

### 0.4 — GitHub Actions CI pipeline
- [x] **Completed 2026-03-20**
- Created `.github/workflows/ci.yml`: runs on push/PR to main
- Steps: checkout -> install uv -> python 3.12 -> uv sync -> lint -> format-check -> typecheck -> test -> build -> upload artifact
- Runs on `macos-latest`
- **Note:** Cannot test until GitHub remote is created.
- **Files:** `.github/workflows/ci.yml`

### 0.5 — GitHub Actions release pipeline
- [x] **Completed 2026-03-20**
- Created `.github/workflows/release.yml`: triggered on `v*` tag push
- Runs full CI suite, then creates GitHub Release with `.alfredworkflow` attached via `softprops/action-gh-release@v2`
- **Note:** Cannot test until GitHub remote is created.
- **Files:** `.github/workflows/release.yml`

---

## Verification

All passing as of 2026-03-20:
- `make lint` — All checks passed
- `make format-check` — 4 files formatted
- `make typecheck` — Success, no issues
- `make test` — 1 passed
- `make build` — Produces valid `.alfredworkflow` (2345 bytes)
