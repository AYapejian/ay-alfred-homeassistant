# Phase 4: Polish & Usability

**Goal:** Improve visual quality, onboarding, and documentation.
**Status:** Planned
**Branch:** TBD
**Depends on:** Phases 2-3

---

## Tasks

### 4.1 — Entity icons per domain
- [ ] **Pending**
- Source/create icons for each domain (light, switch, sensor, etc.)
- Place in `workflow/icons/`
- Implement `src/ha_workflow/icons.py` for icon path resolution

### 4.2 — Rich subtitles
- [ ] **Pending**
- Lights: brightness %, color
- Climate: current/target temperature
- Media player: currently playing media
- Sensors: value + unit of measurement
- Automations: enabled/disabled

### 4.3 — Empty state & onboarding
- [ ] **Pending**
- Missing config: "Configure Home Assistant connection in Alfred Preferences"
- Connection failure: diagnostic info
- Empty cache: "Loading entities..." with `rerun`

### 4.4 — Alfred `autocomplete`/`match`/`uid`
- [ ] **Pending**
- Tab completion via `autocomplete`
- `match` includes entity_id + friendly_name
- `uid` for Alfred's learned ordering

### 4.5 — Documentation
- [ ] **Pending**
- README: installation, configuration, usage, supported entities, action reference, troubleshooting
