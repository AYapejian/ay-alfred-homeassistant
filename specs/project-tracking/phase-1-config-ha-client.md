# Phase 1: Configuration & HA Client

**Goal:** Establish the HA connection and all core plumbing that Phases 2-4 build on.
**Status:** In Progress
**Branch:** `feat/phase-1-config-ha-client`
**Depends on:** Phase 0

---

## Tasks

### 1.1 — Config module (`src/ha_workflow/config.py`)
- [ ] **Pending**
- Read `HA_URL`, `HA_TOKEN`, `CACHE_TTL` from environment variables (set by Alfred)
- Detect Alfred cache/data directories from `alfred_workflow_cache` / `alfred_workflow_data` env vars
- Provide sensible dev fallbacks when not running inside Alfred (e.g., `~/.cache/ha-workflow/`)
- `Config` dataclass with validated fields
- Clear error message when required vars (`HA_URL`, `HA_TOKEN`) are missing
- `CACHE_TTL` defaults to `60` seconds
- **Tests:** `tests/test_config.py` — missing vars, defaults, validation
- **Depends on:** 0.1
- **Blocks:** 1.4, 1.5, 2.2

### 1.2 — Error handling (`src/ha_workflow/errors.py`)
- [ ] **Pending**
- Custom exception hierarchy:
  - `HAWorkflowError` (base)
  - `ConfigError` — missing/invalid configuration
  - `HAConnectionError` — network/connection failures
  - `HAAuthError` — 401/403 from HA
- Top-level error handler that catches exceptions and outputs a single Alfred Script Filter item with the error message (so Alfred shows the error, not silent failure)
- **Tests:** `tests/test_errors.py`
- **Depends on:** 0.1
- **Blocks:** 1.5

### 1.3 — Alfred JSON builder (`src/ha_workflow/alfred.py`)
- [ ] **Pending**
- Classes: `AlfredItem`, `AlfredMod`, `AlfredIcon`, `AlfredOutput`
- `AlfredOutput.to_json()` produces complete Script Filter JSON
- Supported fields: `title`, `subtitle`, `arg`, `icon` (with `type`), `valid`, `match`, `autocomplete`, `mods` (cmd, alt, ctrl, shift, fn), `variables`, `uid`
- Top-level fields: `rerun` (seconds), `cache` (`seconds`, `loosereload`)
- **Tests:** `tests/test_alfred.py` — build items, verify JSON matches Alfred spec exactly
- **Depends on:** 0.1
- **Blocks:** 1.5, 2.4, 3.4

### 1.4 — HA REST API client (`src/ha_workflow/ha_client.py`)
- [ ] **Pending**
- Built on `urllib.request` (stdlib, no deps)
- Methods:
  - `get_states() -> list[dict]` — `GET /api/states`
  - `get_state(entity_id) -> dict` — `GET /api/states/{entity_id}`
  - `call_service(domain, service, data) -> dict` — `POST /api/services/{domain}/{service}`
  - `get_config() -> dict` — `GET /api/config`
  - `get_error_log() -> str` — `GET /api/error_log`
  - `check_config() -> dict` — `POST /api/config/core/check_config`
- Auth: `Authorization: Bearer {token}` header
- Timeout: 10s default
- Error handling: raise `HAConnectionError` on network failure, `HAAuthError` on 401/403
- **Tests:** `tests/test_ha_client.py` — mock `urllib.request.urlopen`, test success/error/timeout paths
- **Depends on:** 1.1
- **Blocks:** 1.5, 2.4, 3.1, 3.4

### 1.5 — CLI entry point + connection test (`src/ha_workflow/cli.py`)
- [ ] **Pending**
- Entry point: `/usr/bin/python3 ha_workflow/cli.py <command> [args]`
- Argument dispatch via `sys.argv`:
  - `search <query>` — (stub, wired in Phase 2)
  - `action <entity_id> <action>` — (stub, wired in Phase 3)
  - `actions <entity_id>` — (stub, wired in Phase 3)
  - `cache refresh` / `cache status` — (stub, wired in Phase 2)
  - `config validate` — **implement now**: calls `ha_client.get_config()`, outputs Alfred item "Connected to HA {version}" or error
- Top-level `try/except` wrapping all commands, using error handler from 1.2
- **Tests:** `tests/test_cli.py` — test argument parsing, test config validate with mocked client
- **Depends on:** 1.2, 1.3, 1.4
- **Delivers:** First end-to-end testable workflow command. User types `haconfig` and sees connection status.

---

## Parallelism

Tasks 1.1, 1.2, and 1.3 have no dependencies on each other and can be implemented in parallel.
Task 1.4 requires 1.1 (Config). Task 1.5 requires 1.2 + 1.3 + 1.4.

```
1.1 (config) ────────┐
1.2 (errors) ────────┤── 1.5 (CLI + connection test)
1.3 (alfred JSON) ───┤
         └── 1.4 (HA client, needs 1.1) ──┘
```

---

## Acceptance Criteria

- [ ] `make lint` passes
- [ ] `make typecheck` passes
- [ ] `make test` passes (all new tests green)
- [ ] `make build` produces valid `.alfredworkflow`
- [ ] Manual test: `HA_URL=... HA_TOKEN=... python3 src/ha_workflow/cli.py config validate` outputs valid Alfred JSON
