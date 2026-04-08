# Copilot Instructions

## Commands

```bash
# Install dev dependencies
uv sync --extra dev

# Lint, format, typecheck, test
make lint
make format
make format-check
make typecheck
make test

# Run a single test file
uv run pytest tests/test_search.py

# Run a single test by name
uv run pytest tests/test_search.py::test_fuzzy_search_empty_query

# Build the .alfredworkflow artifact
make build                   # → dist/ay-alfred-homeassistant.alfredworkflow
```

Set `HA_DEBUG=1` to enable debug output to stderr in the CLI.

## Architecture

Alfred triggers `cli.py` directly via `/usr/bin/python3 ha_workflow/cli.py <command> [args]`. There are two entry points:

- **`search "{query}"`** — Script Filter: parses query, hits cache, returns Alfred JSON to stdout
- **`action {entity_id} {action} [params]`** — action handler: dispatches HA service call, writes notification text to stdout; system commands (cache refresh, HA restart, etc.) use `entity_id = "__system__"`
- **`actions {entity_id}`** — Script Filter: returns action sub-menu items for a specific entity

Request flow for search:
```
Alfred keyword → cli.py search → Config (Alfred env vars)
                               → EntityCache (SQLite, cache_dir)
                               → parse_query() → domain filter / regex / fuzzy
                               → _match_system_commands()
                               → fuzzy_search() + UsageTracker boost
                               → build_domain_suggestions()
                               → AlfredOutput.to_json() → stdout
```

Module responsibilities:
| Module | Role |
|---|---|
| `cli.py` | Entry point; orchestrates all commands |
| `alfred.py` | `AlfredItem` / `AlfredOutput` dataclasses → Script Filter JSON |
| `config.py` | `Config.from_env()` — reads `HA_URL`, `HA_TOKEN`, `CACHE_TTL` |
| `ha_client.py` | Thin stdlib-only REST client (`urllib.request`); no third-party HTTP libs |
| `cache.py` | `EntityCache` — SQLite store in `alfred_workflow_cache` dir |
| `usage.py` | `UsageTracker` — SQLite store in `alfred_workflow_data` dir (survives cache clears) |
| `entities.py` | `Entity` dataclass, `DOMAIN_REGISTRY`, `ACTION_PARAMS` |
| `search.py` | `fuzzy_search()` and `regex_search()` with tiered scoring |
| `query_parser.py` | Parses `domain:text`, `/regex/`, and plain fuzzy queries |
| `params.py` | Parses `key:value,key:value` service param strings |
| `actions.py` | `dispatch_action()` — maps action names to HA service calls |
| `suggestions.py` | Domain filter autocomplete suggestions |
| `notify.py` | Two notification channels: stdout (Alfred pipeline) vs `osascript` (background) |
| `errors.py` | Exception hierarchy + `handle_error()` — always exits 0 (Alfred requirement) |

Two SQLite databases:
- `cache_dir/entities.db` — entity state cache (Alfred may wipe `cache_dir`)
- `data_dir/usage.db` — usage frequency/recency (persists across cache clears)

Both databases accept `":memory:"` for testing.

## Key Conventions

### Python 3.9 compatibility (enforced in `src/`)
- **No** `match`/`case`, `X | Y` union types, `except*`, or `type` aliases
- Use `Optional[X]` and `Union[X, Y]` — ruff rules `UP007`/`UP045` are explicitly ignored
- Use `from __future__ import annotations` at the top of every source file
- Tests (`tests/`) may use 3.12+ syntax freely

### No runtime dependencies
The workflow runs on system Python (`/usr/bin/python3`). Only stdlib is available at runtime. New runtime dependencies require explicit discussion and vendoring into `lib/`.

### Alfred output contract
- Script Filter commands must write valid JSON to **stdout** and exit 0 — even on errors
- Use `handle_error(exc)` from `errors.py` to output an Alfred error item instead of raising
- `AlfredOutput.to_json()` produces the required Script Filter JSON format
- Entity items must **not** have a `uid` field — this prevents Alfred's built-in learning from overriding the usage-based ranking

### Error hierarchy
All exceptions inherit from `HAWorkflowError` in `errors.py`: `ConfigError`, `HAConnectionError`, `HAAuthError`. Don't catch broad `Exception` unless re-raising.

### Domain registry
`DOMAIN_REGISTRY` in `entities.py` is the single source of truth for domain defaults (default action, available actions, icon path, subtitle formatter). Add new domains here. `get_domain_config(domain)` returns a safe fallback for unknown domains.

### Notification channels
- **Foreground** (`notify`, `notify_error`): write to stdout, flows to Alfred's Post Notification node
- **Background** (`notify_background`, `notify_background_error`): use `osascript` for macOS toast — never write to stdout from a detached subprocess

### System commands
Special non-entity actions (cache refresh, HA restart, etc.) use `entity_id = "__system__"` as a sentinel. They appear as search results with the `_SYSTEM_ICON` and a "System ·" subtitle prefix, and are dispatched through `_cmd_system_action()` in `cli.py`.

### Config
`Config.from_env()` reads `HA_URL`, `HA_TOKEN`, `CACHE_TTL`, `alfred_workflow_cache`, and `alfred_workflow_data`. For local dev, set these in `.env` (see `.env.example`). Never read env vars directly — always go through `Config`.

### Fuzzy search scoring
`search.py` uses tiered scores (exact=100, prefix=80, word-boundary=60, substring=40, char-sequence=20) weighted by field (friendly_name × 3.0, entity_id × 2.0, area_name × 1.5). Multi-word queries require all words to match. Usage boost uses log-frequency + exponential recency decay with a 24-hour half-life.

### Testing
- Use `":memory:"` for `EntityCache` and `UsageTracker` in tests — never write real DB files
- Integration tests that require a live HA instance are marked `@pytest.mark.integration` and excluded from CI
- Test fixtures (JSON, etc.) live in `tests/fixtures/`
