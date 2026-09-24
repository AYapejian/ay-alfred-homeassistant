# Phase 4: Polish & Usability

**Goal:** Improve visual quality, onboarding, and documentation.
**Status:** Planned
**Branch:** TBD
**Depends on:** Phases 2-3

---

## Pre-existing Work (from earlier phases)

Several Phase 4 tasks were partially or fully addressed in earlier phases:
- **Rich subtitles** (4.2): Already implemented in Phase 2 — light brightness/color_temp, climate current/target temp, media player source, sensor value+unit, cover position, update version. Only refinements needed.
- **Empty state & onboarding** (4.3): Partially done — "Loading entities..." with `rerun` (Phase 2), system commands on empty query (Phase 1.5). Missing: config error guidance.
- **`autocomplete`** (4.4): Already set to `friendly_name` on entity items (Phase 2), domain filter autocomplete (Phase 1.5). `uid` intentionally removed to prevent Alfred learning from overriding usage-based ranking (Phase 1.5 key decision).

---

## Tasks

### 4.1 — Entity icons per domain
- [ ] **Pending**
- Source/create icons for each domain (light, switch, sensor, climate, etc.)
- Place in `workflow/icons/`
- Update `DOMAIN_REGISTRY` icon_path entries (currently all `icon.png`)
- System commands already use macOS system icon (`System Settings.app` fileicon)

### 4.2 — Subtitle refinements
- [ ] **Pending** (scope reduced — basics already done in Phase 2)
- Review and refine existing subtitle formatters for edge cases
- Consider: automations showing enabled/disabled, locks showing locked/unlocked more clearly
- Add `match` field to items to improve Alfred's built-in filtering (includes entity_id + friendly_name)

### 4.3 — Onboarding & error UX
- [ ] **Pending** (scope reduced — loading state done in Phase 2)
- Missing config: "Configure Home Assistant connection in Alfred Preferences" with guidance
- Connection failure: diagnostic info (URL, timeout, auth error distinction)
- Config check accessible via system command (Phase 3.4 may cover this)

### 4.4 — Entity item ux improvements
- [ ] **Pending** Entities should...
- [ ] If state is open/closed, on/off, locked/unlocked, motion,no-motion (cleared)... These type of entities should have a visibly informative way to display the different states.
- [ ] If entities are unavailable they should be visually distinct (e.g. grayed out, "unavailable" subtitle), font smaller and italicized, default action will be opening submenu
- [ ] If entities are sensors then display the state and unit of measurement in the subtitle, and the default action will be opening the submenu
- [ ] If entities are media players then display the source in the subtitle, and the default will be play/pause toggle
- [ ] If entities are lights then display the brightness in subtitle.  Also render the light color temp or color in the subtitle line as a rectangular box. Default action will be toggle on/off
- [ ] ( Continue adding to this list and think as if you were the end user and what would be the most useful information to display for each type of entity, and what would be the most useful default action for each type of entity. )


### 4.5 — User onboarding and workflow preference ha system commands
- [ ] **Pending**
- [ ] System commands to fill in workflow configuration. Only required should be auto prompted on first install for HA url and API key, if auth fails then prompt user to re-enter credentials, and provide diagnostic info on what went wrong (e.g. timeout, auth error, etc).
- [ ] System command to check HA connection and config validity, with diagnostic info on failure
- [ ] System command to reset workflow configuration (clear saved url and API key)
- [ ] system command to open workflow documentation (README)


### 4.6 — Documentation
- [ ] **Pending** Check all documentation is up to date with the latest features and changes, and is clear and comprehensive for new users.
- README: installation, configuration, usage, supported entities, action reference, troubleshooting
- Search syntax reference: plain text, `domain:text`, `/regex/`, system commands

## Removed Tasks

- **`uid` for Alfred's learned ordering** — intentionally removed in Phase 1.5. Our usage-based ranking controls ordering; Alfred's built-in learning would conflict. This is a key decision, not a TODO.
