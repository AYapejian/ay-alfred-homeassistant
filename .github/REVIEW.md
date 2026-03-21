# Code Review Guidelines

## Critical — Always Flag

### Python 3.9 Compatibility

This project targets Python 3.9+ (system Python on macOS). The following
3.10+ syntax MUST NOT appear in any file under `src/`:

- `match` / `case` statements (3.10+)
- `X | Y` union type syntax in annotations — use `Union[X, Y]` or `Optional[X]` (3.10+)
- `except*` exception groups (3.11+)
- `type` statement aliases (3.12+)

Files under `tests/` may use 3.12+ syntax since dev tooling runs on 3.12.

### Security

- No hardcoded API keys, tokens, passwords, or credentials anywhere
- No secrets in log output or Alfred JSON responses
- `HA_TOKEN` and `HA_URL` must only be read from environment variables via the config module
- Validate and sanitize any user input before passing to HA API calls

### Type Safety

- All public functions must have complete type annotations
- Code must pass `mypy --strict` (configured in pyproject.toml)
- Use `Optional[X]` not `X | None`; use `Union[X, Y]` not `X | Y`

## Important — Flag if Missing

### Tests

- New public functions and classes should have corresponding unit tests
- Bug fixes should include a regression test
- Test files go in `tests/` and follow the `test_<module>.py` naming pattern

### Error Handling

- Use the project's error hierarchy from `src/ha_workflow/errors.py`
- Do not catch broad `Exception` unless re-raising or logging
- User-facing errors should produce meaningful Alfred feedback items

### Imports and Dependencies

- No new runtime dependencies without discussion — the workflow must run on
  system Python 3.9 with only stdlib + bundled packages
- Dev dependencies go in `[project.optional-dependencies] dev`

## Informational — Mention but Don't Block

### Code Style

- ruff handles formatting and most lint rules; do not duplicate ruff's job
- Flag structural issues: overly complex functions, poor naming, missing
  docstrings on public APIs
- Flag violations of existing patterns (e.g., inconsistent use of dataclasses
  vs dicts, inconsistent error handling)

### Documentation

- Public modules and classes should have docstrings
- Complex logic should have inline comments explaining "why"
- CLAUDE.md and spec docs should be updated if behavior changes

## Review Tone

- Be constructive and specific — cite line numbers and suggest fixes
- Distinguish between blockers ("must fix") and suggestions ("consider")
- Acknowledge good patterns and clean code — reviews are not only about problems
- If everything looks good, say so concisely rather than inventing issues
