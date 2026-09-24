# Spec 001 — Server profiles

**Status:** Draft, for review. Design only; no code yet.
**Date:** 2026-09-24
**Depends on:** #46, "Isolate cache and usage storage per HA server": the `Config.server_key` seam plus per-server dirs.
**Related:** #30, "Support both local and cloud HA URLs with automatic fallback".

---

## 1. Goal

Let a user configure more than one Home Assistant server (for example home, a second house, or a local demo instance) and switch the active one from Alfred with `ha server:`. Switching must never send an action to the wrong house.

**Hard constraints**

- **Zero-action upgrade.** An existing `HA_URL` / `HA_TOKEN` configuration keeps working unchanged, as the implicit **default** profile.
- **One seam.** Every entry point resolves its server through `Config.from_env()`. No call site learns about profiles.
- **Python 3.9 stdlib only** at runtime. No 3.10+ syntax.
- **Fail closed.** When the chosen server cannot be resolved, show an error. Never fall back silently to a *different* server.

---

## 2. Research findings

Each finding is marked **[doc]** (stated in the cited source), **[obs]** (seen in this repo) or **[unverified]** (inferred, still to be confirmed on a device).

### 2.1 Alfred User Configuration

- **[doc]** User Configuration arrived in Alfred 5.0 ("New configurable 'User Configuration' for workflows"). Creators get "text fields, checkboxes, selection lists, and file pickers", with default values and required fields, and "a slider control". Sources: [What's new](https://www.alfredapp.com/whats-new/), [Changelog](https://www.alfredapp.com/changelog/), [Workflow Configuration](https://www.alfredapp.com/help/workflows/workflow-configuration/).
- **[doc]** "Workflow Configuration defaults are stored in `info.plist`, but changed values are saved to `prefs.plist`". The same page advises adding `prefs.plist` to `.gitignore`. ([Workflow Configuration](https://www.alfredapp.com/help/workflows/workflow-configuration/))
- **[doc]** Alfred "automatically migrates user values when workflows are updated". ([What's new](https://www.alfredapp.com/whats-new/))
- **[doc]** Workflows are synced along with the rest of the preferences through Alfred's sync folder ("workflows, snippets, themes, etc"). ([Sync](https://www.alfredapp.com/help/advanced/sync/))
- **[unverified]** `prefs.plist` sits inside the workflow folder, so a synced setup copies `HA_TOKEN` in plaintext to Dropbox or iCloud. This is inferred from the `.gitignore` advice together with the sync page.
- **[unverified]** Alfred's help pages never list the field-type identifiers. This repo's `info.plist` uses `textfield` **[obs]**. A multi-line "text view" (`textarea`) type is widely used but not documented on the pages fetched.
- **No field type holds a list.** None of the documented types (text field, checkbox, selection list, file picker, slider) is list-valued. A "list of tokens, the way Alfred does it" can only be built as **numbered fields** or a **serialized blob in one text field**.
- **[unverified]** Whether a User Configuration value is written into an exported `.alfredworkflow`. The export and sharing help page doesn't say. Our exports are built by `scripts/build.sh`, which never copies `prefs.plist` **[obs]**.

### 2.2 Can a script change its own configuration?

- **[doc]** Alfred 5.0.4 / 5.1: "Workflow user configuration values can now be set and removed via AppleScript". ([Changelog](https://www.alfredapp.com/changelog/))
- **[doc]** The syntax, from the Alfred 4+ era: `tell application id "com.runningwithcrayons.Alfred" to set configuration "<var>" to value "<v>" in workflow "<bundleid>" [with exportable]`, and `remove configuration "<var>" in workflow "<bundleid>"`. Without `with exportable`, the variable defaults to "Don't Export". ([deanishe: environment variables in Alfred](https://www.deanishe.net/post/2018/10/workflow/environment-variables-in-alfred/))
- **[unverified]** Exactly which store `set configuration` writes on Alfred 5: the Environment Variables in `info.plist`, or the User Configuration values in `prefs.plist`. Also unverified: whether a Script Filter that runs next sees the new value without a `reload workflow`. The relevant forum thread ([#19324](https://www.alfredforum.com/topic/19324-modifying-user-configuration-variable-from-within-the-workflow/)) returned 403.
- **[unverified]** `reload workflow` and `run trigger` exist in the dictionary. Neither Alfred help page fetched shows their syntax.
- **Conclusion.** Driving the active server through `set configuration` would build on the least-documented surface available. It would also cost an `osascript` round trip on every switch and rewrite a file that syncs. This spec does not depend on it (see D7).

### 2.3 macOS Keychain from a script (`man security`, macOS 27)

- **[doc]** `add-generic-password … -w password`: "Put at end of command to be prompted (recommended)". `-U` updates an existing item. "By default, the application which creates an item is trusted to access its data without warning."
- **[doc]** `find-generic-password -s <service> -a <account> -w` prints only the password, to stdout. Reading a token therefore never puts it in argv.
- **[doc]** `security -i` "will enter interactive mode and allow the user to enter multiple commands on stdin". Sending `add-generic-password … -w <token>` **on stdin** keeps the token out of argv; `ps` shows only `security -i`.
- **Writing with `-w <token>` as an argument exposes the token in `ps`** for as long as the process runs. So does `-X <hex>`. Both are rejected.
- **[unverified]** The "prompt when `-w` is last" path needs a TTY. Alfred's Run Script has none, so it is not usable here.
- **[unverified]** An item created by `/usr/bin/security` and read back by `/usr/bin/security` produces no access prompt (the creator is trusted). The flip side: **any process running as the user** can read the item by calling `security find-generic-password`. The Keychain protects against plaintext on disk, sync, backups and exports, not against local malware. `prefs.plist` protects against none of these.
- **[unverified]** Login-keychain items created this way stay local and don't go to iCloud Keychain.

### 2.4 Secure text entry without a terminal

- **[doc]** AppleScript `display dialog "…" default answer "" with hidden answer` shows bullets and returns `text returned`. Apple's guide warns that "hidden text is returned as plain, unencrypted text". ([Mac Automation Scripting Guide: Prompting for text](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/PromptforText.html))
- **[unverified]** Whether a dialog launched by `osascript` from an Alfred Run Script comes to the front, and whether it triggers an Automation permission prompt. A plain `display dialog` with no `tell` block should need none.

### 2.5 Repo facts that shape the design

- **[obs]** Two parallel config modules exist: `packages/ha_lib/config.py` (imported by every shipped entry script under `src/ha_workflow/scripts/`) and `src/ha_workflow/config.py` (imported by `cli.py`). #46 already applies to both, and so does this spec.
- **[obs]** Right now `search_filter.py` calls `Config.from_env()` and opens the cache **before** it checks for `system` commands, and an empty cache returns "Loading entities…" early. If `server:` were routed that way, it would be unreachable exactly when it's needed: when the active server is down or not yet cached.
- **[obs]** `server` is not in `DOMAIN_REGISTRY`, so `parse_query("server:…")` falls through to fuzzy search. `server:` has to be intercepted before `parse_query`.
- **[obs]** `cli.py` records a known Alfred issue: variables from a Script Filter item don't reliably reach a downstream Action, while the action string always does (params are encoded as `action::params` for that reason). This affects how the server id travels with an item (see D5).
- **[obs]** #46 keys storage as `sha256(normalized HA_URL)[:12]` (12 hex characters), under `<cache|data>/servers/<key>/`, with a non-secret `server.json` in each data dir.

---

## 3. Decisions

### D1 — Profile data model

**Recommendation.**

```python
@dataclass(frozen=True)
class Profile:
    id: str                 # stable; "default" or "p-<8 hex>" (random at creation, never changes)
    name: str               # display name, unique case-insensitively, e.g. "Lake House"
    urls: tuple[str, ...]   # ordered; v1 requires exactly 1. #30 defines semantics for >1
    token_source: str       # "env" (default profile) | "keychain"
    preferred_label: Optional[str] = None  # overrides HA_PREFERRED_LABEL for this server
    badge: Optional[str] = None            # short prefix for subtitles, e.g. "🏠" or "LAKE"
```

- `storage_key` is a derived property, never user-editable (see D6).
- `CACHE_TTL` stays global. A per-server TTL has no use case yet.
- The on-disk format carries `"schema_version": 1`. Unknown keys are preserved when rewriting, so a newer build's fields survive an older build's write.
- `urls` is a list now so #30 adds a second URL **without** a schema change and without touching storage keying.

**Alternatives.**
- A single `url` plus a future `local_url`. Rejected: it hard-codes #30's shape before #30 is designed.
- `name` as the id. Rejected: a rename would orphan the Keychain item and the storage dir.

### D2 — Where profiles and tokens live

**Recommendation: (d) hybrid.**

- The **default profile** comes from Alfred User Configuration, exactly as today. `HA_URL` and `HA_TOKEN` stay in `prefs.plist`, which is the existing baseline, unchanged.
- **Additional profiles** live in `<alfred_workflow_data>/profiles.json`. It holds no secrets.
- Their **tokens** live in the login Keychain: service `com.ayapejian.alfred-homeassistant` (the workflow bundle id), account = profile id.

| Option | Token exposure vs today | Add a server from Alfred | Slots | Code cost | Verdict |
|---|---|---|---|---|---|
| (a) Numbered config fields: `HA_NAME_2`, `HA_URL_2`, `HA_TOKEN_2`, … | Same as today: plaintext in `prefs.plist`, which syncs | No, only through the config sheet | Fixed N. Each slot is 3 permanent fields shown to every user, most of whom have one server | Lowest | **Viable fallback.** It's the only "Alfred-native list". Shares D1, D5, D6 and D7 unchanged: only the profile *source* differs. |
| (b) One JSON text-view field | Same as today, plus every token shown in cleartext in a multi-line box | No | Unlimited | Low | Rejected. Hand-edited JSON with tokens inside, errors that only surface at runtime, and a `textarea` type that is not in the docs. |
| (c) Everything in `profiles.json` + Keychain, including the default | Better | Yes | Unlimited | Medium | Rejected **for v1**. It breaks the zero-action upgrade: the default token would have to move. |
| **(d) Hybrid** | Default: same as today. New servers: better than today (not on disk, not synced, not exported) | Yes | Unlimited | Medium | **Recommended.** |

**Why not simply follow "however Alfred does it".** Alfred has no list field (see 2.1), so the Alfred-native answer is option (a). That puts every extra token in the same plaintext, synced file, with a fixed slot count. Option (d) keeps today's behaviour for the default server and makes every *new* token strictly safer.

**Trade-off to accept.** `profiles.json` and the Keychain are per-Mac. A second Mac that syncs Alfred preferences gets the default profile only. See open question Q2.

A later issue could offer a "move the default token to the Keychain" action; it is out of scope here.

### D3 — Adding, editing, removing and switching

| Operation | Recommendation |
|---|---|
| **Add** | `ha server:` → **"Add server…"** item → Run Script → three native dialogs: name, URL (default `http://`), token (`with hidden answer`). Then validate with `GET /api/` using the new token, write the token to the Keychain through `security -i` on stdin, and write `profiles.json` atomically. The notification reads "Added Lake House (HA 2026.9). Use `ha server:` to switch." |
| **Switch** | Enter on a server item writes the active pointer (see D7) and kicks a background refresh when the target cache is stale. |
| **Test** | ⌘-Enter on a server item runs `GET /api/config` and reports the version and location, or the error. |
| **Edit** | **"Edit servers file…"** item opens `profiles.json` in the default editor. Name, URL, badge and label are editable; the file never holds tokens. **Re-enter token** is the ⌥ modifier on a Keychain server, using the same hidden dialog. |
| **Remove** | ⌃-Enter on a Keychain server opens a confirmation dialog ("Remove Lake House? Its cached entities and usage history on this Mac are deleted.", with Cancel as the default button). It then deletes the Keychain item, the profile and both storage dirs. The default profile can't be removed there; its subtitle says "From workflow configuration". |

- **No auto-switch after Add.** Switching is always a deliberate act.
- **Adding does not contact any server before validation** beyond the one `GET /api/` call. A failed validation offers "Save anyway" (useful for a server that's offline right now) or "Cancel".
- Name and URL must be unique. A URL that normalizes (using #46's normalization) to an existing profile's URL is rejected: two profiles for the same house means two diverging caches and histories, which is itself a wrong-house trap.

**Token-entry alternatives rejected.**
- **Typing the token into Alfred's bar.** It shows on screen, becomes Script Filter **argv** (visible in `ps`), is logged by Alfred's debugger, and may be recalled as the "previous query" (**[unverified]**).
- **Reading it from the clipboard.** The user would copy it from HA's one-time dialog, which also records it in any clipboard history, Alfred's own included.
- **The hidden dialog.** It avoids all of the above; its one weakness (plain text in memory; see 2.4) applies to every option.

### D4 — `ha server:` in Script Filter JSON terms

**Routing.** The search filter checks for a leading `server:` (also `server` alone, case-insensitive) **before** `Config.from_env()`, before opening the cache, and before `parse_query`. The server list must render when the active server is unreachable, has an empty cache, or is misconfigured.

**Items, in order.**
1. One item per profile. The active one comes first, then the others alphabetically. Text after `server:` fuzzy-filters by name or host.
   - `title`: `Lake House`. The active item gets a `✓ ` prefix and the check icon; the others get the server icon.
   - `subtitle` for the active server: `Active · lake.example.net · 412 entities · refreshed 3m ago`.
   - `subtitle` for another server: `lake.example.net · 412 entities cached · ↵ switch`.
   - When the last background refresh failed: `… · last refresh failed 5m ago: connection timed out`. This comes from the per-server status that #46's refresh log / `server.json` already records. **The Script Filter never contacts a server**; everything shown is cached state.
   - `arg`: the profile id. `variables`: `{"entity_id": "__server__", "action": "server_switch::<id>", "domain": "__server__"}`. This follows the existing `__system__` dispatch pattern and the `action::payload` encoding, because action strings propagate reliably.
   - `mods`:
     - ⌘ → `server_test::<id>`
     - ⌥ → `server_token::<id>` (Keychain servers only)
     - ⌃ → `server_remove::<id>` (Keychain servers only)
     - On the default profile, ⌥ and ⌃ return `valid: false` with the subtitle "Configured in Alfred → Workflows → Configure".
   - No `uid`, consistent with the decision not to let Alfred's learning reorder items.
2. **Add server…**: `server_add`, always present.
3. **Edit servers file…**: `server_edit`, present once `profiles.json` exists.

**Empty state.** Only the default profile exists: it is listed as active, followed by "Add server…". No profile at all (a fresh install with `HA_URL` unset): "No servers configured", then "Add server…" and an item that says to fill in the workflow configuration.

**Error states.**
- `profiles.json` fails to parse or validate: the first item reads "Servers file is invalid: `<reason>`" and Enter opens the file. The default profile is still listed and switchable.
- The active pointer names a profile that no longer exists: every entry point *except* `server:` raises `ConfigError("Active server 'p-…' is not configured. Use 'ha server:' to choose one.")`. This fails closed; there is **no** silent fallback to the default.
- A Keychain lookup fails for the active profile: same fail-closed error, naming the server.
- Switching to an unreachable server is allowed. The notification says "Switched to Lake House (unreachable: …; showing cached entities)".

### D5 — Showing which server is active, so the wrong house is never touched

**Recommendation.** Only when **more than one profile exists**:

- Every entity item's subtitle is prefixed with the active server's badge, or its name when it has no badge: `Lake House · Light · on · Kitchen`.
- Titles of HA system commands name the server: `System: Restart Home Assistant (Lake House)`.
- Every notification after an action is prefixed with the server name: `Lake House: Front door locked`.
- **Each item carries its server id** as part of the action payload (`<action>@@<server id>`, parsed before `::` params), and the runner resolves config for *that* id through the `HA_SERVER` override (see D7). An action therefore always goes to the server whose cache produced the item, even when a switch happened in between.
  - Encoding the id in the action string rather than an item variable follows the propagation issue noted in 2.5. If on-device checking shows item variables *do* propagate for this path, a variable is cleaner. This choice is made during implementation, with a test either way.

With exactly one profile, nothing changes, so single-server users see no extra text.

**Alternatives.**
- A non-actionable header item. Rejected: Alfred has no unselectable header row, so it would take the top slot and break "Enter runs the top result".
- The badge only on system commands. Rejected: the risky actions are entity actions (locks, garage covers), not restarts.
- A per-domain confirmation step for locks and covers. Deferred (Q4).

### D6 — Storage keying and mapping from #46's dirs

**Recommendation.** `Config.server_key` (the #46 seam) comes from **profile identity, never from the URL in use**:

| Profile | `server_key` | Why |
|---|---|---|
| Default (from `HA_URL`) | #46's `sha256(normalized HA_URL)[:12]`, unchanged | The dirs #46 creates and migrates stay valid. **No second migration.** |
| Keychain profile | its `id`, e.g. `p-1a2b3c4d` | Stable across URL edits and across #30's second URL: one profile, one cache. |

- The `p-` prefix cannot collide with #46's 12-hex keys. Validate ids against `^p-[0-9a-f]{8}$`.
- When #30 adds a second URL to the **default** profile, the key still hashes the *primary* `HA_URL` only. Reachability fallback never changes the key.
- Editing `HA_URL` itself still starts a fresh cache and usage history. That is #46's behaviour and correct: it is a different server. Documented in the README.
- #46's `server.json` gains `profile_id` and `profile_name`, still with no token, to make it easier to debug.
- Removing a profile deletes `<cache>/servers/<key>/` and `<data>/servers/<key>/`.

**Alternative rejected.** Rekeying the default profile to `"default"` and moving the hash dir. It adds a second migration with its own failure modes, and it would silently reattach history if the user later pointed `HA_URL` at a different house.

### D7 — Persisting the active profile, with one seam

**Recommendation.** The pointer is `<alfred_workflow_data>/active_server`, containing one line with a profile id. It lives at the data-dir root, not per server, and is written atomically (temp file + `os.replace`). When it's missing, the default is active.

**Resolution order** in `Config.from_env()`, the single seam, in both `ha_lib` and `ha_workflow`:
1. The `HA_SERVER` environment variable (a profile id): set by the action runner from the item's encoded server id, by the background-refresh child, and by developers or tests.
2. The `active_server` file.
3. `default`.

- `Config` gains `server_id`, `server_name`, `server_count` and `server_key`, and **resolves the token lazily**. A Script Filter keystroke served from cache never runs `security`; only HTTP calls do. Tests check this.
- The background refresh spawned by `search_filter.py` passes `HA_SERVER=<resolved id>` to its child, so a switch between spawning the child and the child running can't send one server's entities to another's cache.
- `open_in_ha.py` and `copy_entity.py` use the same resolution, so "open in HA" opens the right house.
- `notify` stays config-free; callers prefix the server name (D5).

**Alternatives.**
- The active server as an Alfred config value set through AppleScript `set configuration`. Rejected: its semantics are unverified (2.2), it adds an `osascript` round trip per switch, and it writes a synced file, so two Macs would fight over one pointer.
- An env var in `info.plist`. Rejected: it can't be changed at runtime without the same AppleScript path.

### D8 — Testing strategy

- **Unit tests (pytest, `tmp_path`, env dicts; no network, no real Keychain):**
  - Profile loader: file absent, valid, invalid JSON, unknown keys preserved on rewrite, duplicate name or URL rejected.
  - Resolution order (`HA_SERVER` > file > default); fail-closed when the pointer is stale or the Keychain misses.
  - `server_key`: the default keeps #46's hash; a Keychain profile keeps its id when the URL changes.
- **`TokenStore` protocol** with a `SecurityCliTokenStore` and an in-memory fake.
  - A test patches `subprocess` and **asserts the token string never appears in any argv** and does appear on stdin.
  - A test asserts a cached search never calls `find-generic-password`.
- **`Prompter` protocol** wrapping `osascript display dialog`, faked in tests for the add, re-token and remove flows, including Cancel at every step.
- **Script Filter JSON snapshot tests** for `server:`: one profile, several, filtered, invalid file, stale pointer, no profiles. Also a test that `server:` renders with an empty or absent cache and **without** `HA_URL` set.
- **Safety tests:**
  - Subtitle and notification prefixes appear only when `server_count > 1`.
  - The action payload round-trips `@@<id>` together with `::params`.
  - The background child env carries `HA_SERVER`.
- **Manual QA on a device** (added to `scripts/QA_CHEATSHEET.md`):
  - The dialog appears in front; hidden entry shows bullets.
  - The first Keychain write and read cause no prompt.
  - With two servers, toggle an entity, switch, and confirm the toggle landed on the right server.
  - Confirm how item variables propagate (settles the D5 encoding choice).

### D9 — Task breakdown (one PR, in order, each task independently testable)

1. **Profile model and loader**: `ha_lib/profiles.py`, covering `Profile`, schema v1, atomic read and write, validation, and the implicit default from env.
2. **`TokenStore`**: `security -i` over stdin for writes, `find-generic-password -w` for reads, delete; the fake; the argv-leak test.
3. **Active pointer and resolution in `Config.from_env()`** (both config modules): `HA_SERVER` > file > default, lazy token, new fields, fail-closed errors.
4. **`server_key` from the profile**, replacing #46's URL-only input; `server.json` gains profile fields.
5. **`server:` listing** in `search_filter.py` (and `cli.py`), routed before config and cache; covers the empty, invalid and stale states.
6. **Server actions in `action_runner.py`**: switch, test, re-token, remove, plus the `Prompter` protocol.
7. **Add-server flow**: dialogs, validation, Keychain write, profile write.
8. **Server id on every item plus runner resolution**: the `@@<id>` payload, background-refresh `HA_SERVER` passthrough, `open_in_ha` and `copy_entity`.
9. **Wrong-house signals**: subtitle badge, system-command titles and notification prefixes when `server_count > 1`.
10. **Wiring and docs**: `info.plist` graph changes where needed, a README section, the QA cheatsheet, and tracking updates (a phase file, a `status.md` Key Decision, the changelog).

---

## 4. Out of scope

- #30 itself: local/cloud URL fallback and reachability checks. The model only leaves room for it (`urls` list, identity-based key).
- WebSocket listener (#10, #11, #12).
- Moving the default profile's token out of `prefs.plist`.
- Searching across all servers at once, or mixing servers in one result list.
- Per-server `CACHE_TTL`.
- Syncing profiles or tokens across Macs.
- `ha server:add <name> <url>` typed into the bar. Dialogs only in v1.
- Confirmation prompts for lock, cover or alarm domains (Q4).
- Editing profiles from Alfred's configuration sheet.

## 5. Open questions for the owner

- **Q1 — Hybrid, or the Alfred-native slots?** The spec recommends the hybrid (D2). If you prefer everything in Alfred's configuration sheet, option (a) with 2 extra slots (6 fields) is the fallback, and everything else in this spec still applies.
- **Q2 — Profiles stay per-Mac.** Extra servers and their tokens don't follow Alfred's preference sync. Is that acceptable, given it's also why the tokens stay off Dropbox/iCloud?
- **Q3 — Auto-revert.** Should a non-default active server revert to the default after some idle period (e.g. 12 h)? It's a guard against "still pointed at the lake house a week later". Default in this spec: no.
- **Q4 — Confirm risky actions.** With more than one server configured, should lock, cover and alarm actions ask for confirmation that names the server? Default in this spec: no. The subtitle prefix is the guard.
- **Q5 — What Remove deletes.** Should removing a server delete its usage history, or keep it so re-adding the server restores the rankings? Default in this spec: delete, with the confirmation dialog saying so.
