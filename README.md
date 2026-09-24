# ay-alfred-homeassistant

[![CI](https://github.com/AYapejian/ay-alfred-homeassistant/actions/workflows/ci.yml/badge.svg)](https://github.com/AYapejian/ay-alfred-homeassistant/actions/workflows/ci.yml)
[![Release](https://github.com/AYapejian/ay-alfred-homeassistant/actions/workflows/release.yml/badge.svg)](https://github.com/AYapejian/ay-alfred-homeassistant/actions/workflows/release.yml)
[![GitHub Release](https://img.shields.io/github/v/release/AYapejian/ay-alfred-homeassistant?include_prereleases&sort=semver)](https://github.com/AYapejian/ay-alfred-homeassistant/releases/latest)
[![License: MIT](https://img.shields.io/github/license/AYapejian/ay-alfred-homeassistant)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Alfred 5](https://img.shields.io/badge/Alfred-5-blueviolet?logo=alfred)](https://www.alfredapp.com/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-REST%20API-41BDF5?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64?logo=ruff&logoColor=D7FF64)](https://docs.astral.sh/ruff/)

An [Alfred](https://www.alfredapp.com/) workflow for macOS that brings [Home Assistant](https://www.home-assistant.io/) to your fingertips. Search entities, call services, toggle automations, and more — all from Alfred's search bar.

> **Note:** This is an active personal project, built largely with AI-assisted development. It works well for my setup, but it is not production-grade software. APIs and behavior may change between versions. If you find it useful, great — just know what you're getting into.

## What It Does

This is a native macOS Alfred workflow — not a Home Assistant add-on. It runs entirely on your Mac and talks to HA over its REST API.

**Features:**

- Fuzzy search across all HA entities (by entity ID, friendly name, or attributes)
- Domain filtering (e.g., `light:bedroom` to search only lights)
- Regex search (e.g., `/.*kitchen.*/` for pattern matching)
- Usage-based ranking — frequently used entities float to the top
- Action execution — toggle lights, activate scenes, call services directly from Alfred
- Action sub-menu via Cmd modifier with domain-aware actions
- Parameterized actions — set brightness, color temp, etc. with inline `key:value` syntax
- Copy entity ID/details, open entity or history in HA
- HA system commands — restart, check config, view error log
- System commands (cache refresh, clear usage data) accessible from search
- Cached entity index in SQLite for fast, offline-capable lookups
- Per-server storage — the entity cache and usage history are kept separately for each `HA_URL`, so pointing the workflow at another Home Assistant never mixes or clears the first one's data (existing data moves into the current server's folder on upgrade)
- Several servers — add more Home Assistant instances and switch between them with `ha server:`; tokens for added servers live in the macOS Keychain

**Planned:**

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
   - `HA_PREFERRED_LABEL` *(optional)* — HA label slug that floats tagged entities to the top of search results. Defaults to `alfred_preferred`.
4. Type `ha` in Alfred followed by your search query

## Usage

- `ha <query>` — search entities. **Enter** runs the default action (toggle, turn on/off, etc.)
- **Cmd + Enter** — open the action sub-menu for the selected entity
- In the action sub-menu, select **Set Params...** to enter parameters like `brightness:100` or `color_temp_kelvin:3000`

### Promoting entities to the top

Create a label in Home Assistant (Settings → Areas & zones → Labels) named **Alfred Preferred** — HA stores it with the slug `alfred_preferred`. Tag any entity *or device* with it and those entities float above unlabeled ones in search results. Device-level labels propagate to every entity on that device. Your own usage history still takes priority over labeled entities. Override the slug with `HA_PREFERRED_LABEL` if you prefer a different label name.

### Several Home Assistant servers

The server in the workflow configuration (`HA_URL` / `HA_TOKEN`) is the **default** server; nothing changes if it is the only one. To add another (a second house, a demo instance):

1. Type `ha server:` and choose **Add server…**
2. Enter a name, the URL, and a long-lived access token. The token field is hidden, and the token is stored in your login Keychain (service `com.ayapejian.alfred-homeassistant`), not in Alfred's preferences.
3. The workflow checks the token with the server once. If the server is offline you can **Save anyway**.

Adding a server does not switch to it. In `ha server:`:

| Key | On a server |
|-----|-------------|
| **Enter** | Switch to it. Search and actions now use this server. |
| **⌘ Enter** | Server actions: switch, test connection, re-enter token, remove |

- `ha server:<text>` filters the list by name or host. The active server has a ✓ and shows its entity count and last refresh. A server whose last background refresh failed says so.
- **Remove server…** asks first. It deletes that server's token, cached entities and usage history on this Mac. The default server can only be changed in the workflow configuration.
- **Edit servers file…** opens `profiles.json` in Alfred's workflow data folder. It holds names, URLs, an optional `badge` (a short label such as `LAKE`) and an optional `preferred_label` per server, and never tokens. A `"default": {"name": "Home", "badge": "🏠"}` entry renames the default server.

**Which server an action hits.** Each result remembers the server it came from. Enter always acts on that server, even if you switched in between. With more than one server configured:

- every entity subtitle starts with the server's badge or name (`Lake House · Kitchen · on`)
- system commands name the server: `System: Restart Home Assistant (Lake House)`
- notifications start with the server name: `Lake House: Toggled Front Door`

**Things to know**

- Added servers and their tokens stay on this Mac. They do not follow Alfred's preference sync; on a second Mac, add them again.
- There is no automatic switch back to the default server.
- Changing `HA_URL` itself still starts a fresh cache and usage history, because it is a different server. Editing an added server's URL in `profiles.json` keeps its history.
- If the active server is removed, or `profiles.json` cannot be read, `ha` shows an error that points to `ha server:`. It never falls back to another server on its own.

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
