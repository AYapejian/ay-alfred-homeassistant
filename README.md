# ay-alfred-homeassistant

An [Alfred](https://www.alfredapp.com/) workflow for macOS that brings [Home Assistant](https://www.home-assistant.io/) to your fingertips. Search entities, call services, toggle automations, and more — all from Alfred's search bar.

> **Note:** This is an active personal project, built largely with AI-assisted development. It works well for my setup, but it is not production-grade software. APIs and behavior may change between versions. If you find it useful, great — just know what you're getting into.

## What It Does

This is a native macOS Alfred workflow — not a Home Assistant add-on. It runs entirely on your Mac and talks to HA over its REST API.

**Working today:**

- Fuzzy search across all HA entities (by entity ID, friendly name, or attributes)
- Domain filtering (e.g., `light:bedroom` to search only lights)
- Regex search (e.g., `/.*kitchen.*/` for pattern matching)
- Usage-based ranking — frequently used entities float to the top
- System commands (cache refresh, clear usage data) accessible from search
- Cached entity index in SQLite for fast, offline-capable lookups

**Planned:**

- Action execution — toggle lights, activate scenes, call services directly from Alfred
- Action sub-menu via Cmd modifier
- HA system commands — restart, check config, view logs
- Real-time cache updates via WebSocket (currently pull-based)

## Requirements

- [Alfred 5](https://www.alfredapp.com/) with Powerpack license
- macOS (Intel or Apple Silicon)
- A running Home Assistant instance
- A [long-lived access token](https://www.home-assistant.io/docs/authentication/#your-account-profile) from HA

## Quick Start

1. Download `ay-alfred-homeassistant.alfredworkflow` from the [latest release](https://github.com/AYapejian/ay-alfred-homeassistant/releases/latest)
2. Double-click to import into Alfred
3. Open the workflow's configuration in Alfred and set:
   - `HA_URL` — your Home Assistant URL (e.g., `http://homeassistant.local:8123`)
   - `HA_TOKEN` — your long-lived access token
4. Type `ha` in Alfred followed by your search query

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/) for development. The workflow itself targets Python 3.9+ (macOS system Python) and uses only the standard library at runtime.

```sh
git clone https://github.com/AYapejian/ay-alfred-homeassistant.git
cd ay-alfred-homeassistant
uv sync --extra dev
```

Run checks:

```sh
make lint          # ruff check
make format-check  # ruff format --check
make typecheck     # mypy (strict mode)
make test          # pytest
make build         # package .alfredworkflow artifact
```

For local development with live reloading in Alfred:

```sh
make dev-install   # symlinks into Alfred's workflow directory
```

## Project Structure

```
src/ha_workflow/    # Python source (the workflow logic)
tests/              # pytest test suite
workflow/           # Alfred workflow resources (info.plist, icons)
scripts/            # build and dev-install scripts
specs/              # project specs and tracking
.github/workflows/  # CI and release automation
```

## License

[MIT](LICENSE)
