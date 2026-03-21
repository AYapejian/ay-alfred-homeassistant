# Agentic Handoff Doc
**Project:** Alfred Workflow extension for Home Assistant
**Status:** Planning and architecture-decision phase only; implementation intentionally not started

---

## 1. What this project is

Build an **importable Alfred workflow** for **Home Assistant** that supports:

- discovery mode and live search across:
  - entity IDs
  - friendly names
  - attributes
- cached entity index with **state change updates**
- action execution from Alfred, including:
  - service calls
  - automation control
  - log fetching
  - config validation
  - Home Assistant restart
- background listening for Home Assistant events/state changes
- a way for users to extend behavior with **custom scripts/actions/hooks**
- developer-friendly repo with:
  - CI
  - tests
  - linting
  - formatting
  - packaging
  - README and contribution guidance

The workflow output must be an **importable `.alfredworkflow` artifact** with configurable options such as:

- Home Assistant URL
- API token / key
- optional defaults and runtime settings
- sane defaults for performance and error handling

---

## 2. Current status

This project is still in the **planning / architecture decision** phase.

A previous session created a planning-only scaffold and a planning-only Alfred workflow artifact, but **no final implementation stack has been chosen** and **real runtime implementation has not started**.

### Important rule for future agent sessions

**Do not assume Python is chosen.**
A prior session explored Python as a possible direction, but that choice should be treated as **discarded** for future implementation work.

The next implementation/planning agent must:

1. review the product requirements
2. present viable stack and architecture options
3. compare them on maintainability, Alfred compatibility, packaging, debugging, extensibility, CI/CD, and long-term support
4. recommend one
5. **ask the user to choose before generating the real scaffold or implementation**

---

## 3. Research and known facts already established
