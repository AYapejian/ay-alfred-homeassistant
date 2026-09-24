# Demo Home Assistant

A throwaway Home Assistant in Docker, filled with fake devices from HA's
built-in [`demo` integration](https://www.home-assistant.io/integrations/demo/)
(lights, switches, locks, covers, climate, media players, sensors, vacuums…).
Use it to develop and test the workflow without touching a real house, and for
documentation screenshots — nothing in it is real.

- Listens on **`127.0.0.1:8124` only** (not reachable from the network, and no
  clash with a real HA on 8123).
- Login: **`demo` / `demo-password`** — demo-only credentials, never reuse them.
- Requires Docker and [`uv`](https://docs.astral.sh/uv/).

## Commands

```bash
scripts/demo-ha.sh up      # start, finish onboarding, create a token, seed
scripts/demo-ha.sh status  # container, API and token status
scripts/demo-ha.sh token   # create/replace the long-lived token
scripts/demo-ha.sh seed    # re-apply demo areas + the alfred_preferred label
scripts/demo-ha.sh down    # stop (state is kept)
scripts/demo-ha.sh reset   # stop and wipe all state; next `up` starts fresh
```

Make targets wrap the same: `make demo-ha-up`, `demo-ha-down`, `demo-ha-reset`,
`demo-ha-token`, `demo-ha-status`.

`up` is idempotent. It completes every onboarding step, so the web UI at
<http://127.0.0.1:8124> opens straight to the dashboard. The seed step adds a
few areas and an **Alfred Preferred** label (`alfred_preferred`) on some demo
entities. Onboarding also sets up HA's default integrations (Met.no weather,
Radio Browser, Google Translate TTS, Shopping List), which make outbound
internet requests.

## Point the workflow CLI at it

```bash
eval "$(scripts/demo-ha.sh env)"   # exports HA_URL and HA_TOKEN
alfred_workflow_cache=/tmp/demo-c alfred_workflow_data=/tmp/demo-d \
  uv run python src/ha_workflow/cli.py cache refresh
alfred_workflow_cache=/tmp/demo-c alfred_workflow_data=/tmp/demo-d \
  uv run python src/ha_workflow/cli.py search kitchen
```

Setting the two `alfred_workflow_*` variables keeps the demo's cache and usage
history apart from your real workflow data.

## Files

- `docker-compose.yml` — the pinned image; to upgrade, bump the tag, then
  `scripts/demo-ha.sh reset && scripts/demo-ha.sh up`.
- `config/configuration.yaml` — the only committed config. Everything else in
  `config/` is runtime state, and `.demo-token` holds the token (mode 600).
  Both are gitignored.
