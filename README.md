# ay-alfred-homeassistant

An [Alfred](https://www.alfredapp.com/) workflow for macOS that brings [Home Assistant](https://www.home-assistant.io/) to your fingertips. Search entities, call services, toggle automations, and more — all from Alfred's search bar.

## Status

**Early planning** — the implementation stack has not been chosen yet. See [`specs/spec-000-init.md`](specs/spec-000-init.md) for the initial requirements.

## Planned Features

- **Entity search** — fuzzy search across entity IDs, friendly names, and attributes
- **Action execution** — service calls, automation toggling, log fetching, config validation, HA restart
- **Live cache** — entity index kept fresh via Home Assistant WebSocket state-change events
- **Extensible** — custom scripts, actions, and hooks
- **Single artifact** — ships as an importable `.alfredworkflow` file

## Requirements

- [Alfred 5](https://www.alfredapp.com/) with Powerpack
- macOS (Intel or Apple Silicon)
- A running Home Assistant instance with a [long-lived access token](https://www.home-assistant.io/docs/authentication/#your-account-profile)

## License

TBD
