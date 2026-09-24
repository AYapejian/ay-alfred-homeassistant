# Phase 1.7: Multi-Server Support

**Goal:** Support multiple HA servers safely, a demo HA instance for development, and screenshot-backed user docs.
**Status:** In progress
**Branch:** `feat/46-per-server-storage` (1.7.1)
**Issue:** [#46](https://github.com/AYapejian/ay-alfred-homeassistant/issues/46) (1.7.1), [#9](https://github.com/AYapejian/ay-alfred-homeassistant/issues/9) (1.7.3)
**Depends on:** Phase 1.6

---

## Tasks

### 1.7.1 — Per-server storage isolation
- [x] **Done** — 2026-09-24 · this PR (#46)
- `Config.server_key` — 12-char sha256 of the normalized `HA_URL` (lowercase scheme/host, no user-info, default ports 80/443 dropped, no trailing slash); `server_key_override` is the seam for server profiles
- `Config.server_cache_dir` / `server_data_dir` = `<cache_dir|data_dir>/servers/<key>/`; `Config.server_label` for UI text
- New `storage.py` in `src/ha_workflow/` and `packages/ha_lib/`: `prepare_server_storage` (dirs + non-secret `server.json`) and `migrate_legacy_storage`
- Per-server: `entities.db`, `usage.db` (+ SQLite `-wal`/`-shm`/`-journal`), `.refresh.lock`, `refresh.log`, `server.json`
- One-time migration moves legacy flat files into the current server's dirs: `flock`-serialized, `os.replace`, never overwrites, marker `<data_dir>/servers/.legacy-migrated` stops a later stray file being attributed to another server
- "Clear usage" and cache refresh act on the current server and name it in their subtitles
- **Tests:** `tests/test_storage.py` — key normalization, per-server dirs, `server.json` has no token, isolation when switching `HA_URL`, migration (once, idempotent, sidecars, no clobber, concurrent threads), scoped clear, per-server refresh lock/log; runs against both library copies

### 1.7.2 — Demo HA instance in Docker
- [ ] Not started
- `make demo-ha-*` targets to run a throwaway Home Assistant with demo entities for development and screenshots
- Relies on 1.7.1 so pointing the workflow at the demo never touches real usage history

### 1.7.3 — Screenshot script + cheatsheet / user guide
- [ ] Not started — closes #9
- Scripted screenshots against the demo instance; cheatsheet and user guide built on them

### 1.7.4 — Server profiles + `ha server:` switcher
- [ ] In progress — started 2026-09-24 · branch `feat/47-server-profiles` ([#47](https://github.com/AYapejian/ay-alfred-homeassistant/issues/47)) · spec: `specs/spec-001-server-profiles.md`
- Multiple configured servers, switchable from Alfred; profile supplies `Config.server_key_override`
- Default server = `HA_URL`/`HA_TOKEN` (unchanged); added servers in `<data>/profiles.json` (no secrets), tokens in the login Keychain via `security -i` on stdin (never argv)
- Active server: `HA_SERVER` env > `<data>/active_server` > `default`, resolved only in `Config.from_env()`; lazy Keychain read; fails closed (stale pointer, invalid file, missing token)
- `ha server:` listing routed before config/cache; Enter switches; ⌘ opens a server sub-menu (test, re-enter token, remove) in the existing actions Script Filter — no `info.plist` change
- Every item carries `<action>@@<server id>`; runner / open-in-HA / background refresh pin `HA_SERVER` to it
- Wrong-house signals when >1 server: subtitle badge/name, system-command titles, notification prefix
- **Tests:** `test_profiles.py`, `test_keychain.py` (argv-leak), `test_server_resolution.py`, `test_server_menu.py`, `test_server_actions.py`, `test_server_add.py`, `test_server_routing.py`, `test_wrong_house.py`; `conftest.py` blocks the real Keychain, real dialogs and `HOME`
- **Manual QA still needed on a Mac:** `scripts/QA_CHEATSHEET.md` → "Server profiles"

---

## Key decisions

| Decision | Rationale |
|----------|-----------|
| **Storage keyed by normalized URL hash** | Stable, filesystem-safe, and equivalent URLs (`/`, case, default port) share one folder. No token or raw URL in the path. |
| **Single seam (`Config.server_key`)** | Profiles can supply the key later without touching storage code; no hashing scattered across modules. |
| **Migrate legacy files once, to the server configured at upgrade** | Preserves existing users' usage history. The marker prevents a later stray legacy file from being misattributed to a different server. |
| **Never overwrite during migration** | If the server dir already has a file, the legacy copy is left in place rather than risk losing either. |
