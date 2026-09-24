# Cheatsheet

Keyword **`ha`**. The full explanations are in the [user guide](guide.md).

### Search

| Type | Does | Example |
|------|------|---------|
| `ha` | Your most-used entities first, then A–Z | `ha` |
| `ha <words>` | Fuzzy search on name, entity ID and device class. Every word must match | `ha kitchen`, `ha kitch lig` |
| `ha <domain>:` | Show only one domain | `ha light:` |
| `ha <domain>:<words>` | Fuzzy search within one domain | `ha light:living` |
| `ha /<regex>/` | Case-insensitive regex on entity ID and name | `ha /door/`, `ha /^light\./` |
| `ha system [word]` | System commands | `ha system`, `ha system log` |

### Keys on an entity result

| Key | Does |
|-----|------|
| <kbd>↵</kbd> | Runs the default action for the entity's domain ([table](guide.md#what-enter-does)) |
| <kbd>⌘</kbd><kbd>↵</kbd> | Opens the action menu |
| <kbd>⌥</kbd><kbd>↵</kbd> | Copies the entity ID |
| <kbd>⌃</kbd><kbd>↵</kbd> | Opens the entity in Home Assistant |
| <kbd>⇥</kbd> | Autocompletes the name, or `domain:` on a "Filter:" row |

### Parameters

Press <kbd>⌘</kbd><kbd>↵</kbd>, then pick an action whose subtitle says **supports: …**, then type `key:value,key:value`.

| Domain | Action | Keys | Example |
|--------|--------|------|---------|
| light | Turn On | `brightness`, `color_temp_kelvin`, `color`, `rgb_color`, `effect`, `transition` | `brightness:50%,color:red,transition:2` |
| fan | Turn On | `percentage` (0–100) | `percentage:40` |
| cover | Open Cover / Close Cover | `position` (0–100) | `position:50` |
| media_player | Volume Set | `volume_level` (0.0–1.0) | `volume_level:0.3` |
| climate | Set Temperature | `temperature`, `hvac_mode` | `temperature:21,hvac_mode:heat` |
| number, input_number, input_text | Set Value | `value` | `value:42` |
| select, input_select | Select Option | `option` | `option:<name>` |

### System commands

| Row | Filter words | Does |
|-----|--------------|------|
| History: Clear usage data | `history`, `clear`, `usage` | Resets usage-based ranking |
| Cache: Refresh entities | `cache`, `refresh`, `reload` | Fetches all entities again |
| System: Restart Home Assistant | `restart`, `reboot` | **Restarts HA right away, with no confirmation** |
| System: Check config | `check`, `config`, `validate` | Validates HA's configuration |
| System: View error log | `log`, `error` | Copies the HA error log to the clipboard |

### Configuration variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `HA_URL` | *(required)* | Base URL, e.g. `http://homeassistant.local:8123` |
| `HA_TOKEN` | *(required)* | Long-lived access token |
| `CACHE_TTL` | `60` | Seconds before the entity list is refreshed in the background |
| `HA_PREFERRED_LABEL` | `alfred_preferred` | Label ID that lifts tagged entities in the results |
