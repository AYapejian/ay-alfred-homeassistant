# Project Tracking

This directory is the single source of truth for project status, task breakdowns, and progress. It is maintained alongside implementation work so that anyone (human or agent) can pick up where things left off without relying on conversation context or agentic memory.

## Files

| File | Purpose |
|------|---------|
| `status.md` | High-level project status, current phase, key decisions, and blockers |
| `phase-0-foundation.md` | Phase 0 tasks, outcomes, and completion log |
| `phase-1-config-ha-client.md` | Phase 1 tasks, acceptance criteria, and progress |
| `phase-2-cache-search.md` | Phase 2 tasks (planned) |
| `phase-3-actions.md` | Phase 3 tasks (planned) |
| `phase-4-polish.md` | Phase 4 tasks (planned) |
| `phase-5-websocket.md` | Phase 5 tasks (deferred) |
| `changelog.md` | Chronological log of completed work, commits, and decisions |

## Conventions

- Tasks use checkbox format: `- [ ]` pending, `- [x]` done, `- [!]` blocked/errored
- Each task has an ID (e.g., `0.1`, `1.3`) matching the project plan
- When starting a task, note the date. When completing, note the date and commit hash.
- Blockers and errors are logged inline with the task, not in a separate file.
