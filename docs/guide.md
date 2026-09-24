# User guide

This guide explains how to find and control Home Assistant entities from Alfred. For a one-page summary, see the [cheatsheet](cheatsheet.md).

The examples use entities from Home Assistant's built-in demo, such as Kitchen Lights, Ceiling Lights, Front Door and Garage Door. Your own entity names will differ.

- [Install and configure](#install-and-configure)
- [Searching](#searching)
- [Running actions](#running-actions)
- [The action menu](#the-action-menu)
- [Parameters](#parameters)
- [System commands](#system-commands)
- [Troubleshooting](#troubleshooting)

---

## Install and configure

### Requirements

- macOS, on Intel or Apple Silicon
- [Alfred 5](https://www.alfredapp.com/) with a Powerpack license, which Alfred requires for workflows
- A Home Assistant instance that your Mac can reach
- `/usr/bin/python3`, the Python that ships with macOS. The workflow uses only the standard library, so you don't need to install any packages.

### Install

1. Download `ay-alfred-homeassistant.alfredworkflow` from the [latest release](https://github.com/AYapejian/ay-alfred-homeassistant/releases/latest).
2. Double-click the file. Alfred opens and asks you to import it.

> [!NOTE]
> This guide describes the current `main` branch. The latest published release (v0.1.0) is older and doesn't have several features described here. Until a new release is published, you can run it from source: clone the repository and run `./scripts/dev-install.sh`, which links the `workflow/` folder into Alfred.

### Create a long-lived access token

The workflow signs in to Home Assistant with a long-lived access token.

1. In Home Assistant, click your user name in the lower-left corner to open your profile.
2. Open the **Security** tab.
3. Under **Long-lived access tokens**, click **Create token**, give it a name such as `Alfred`, and copy the token.

Home Assistant shows the token only once. If you lose it, delete it and create a new one.

### Configure the workflow

Alfred asks for these values when you import the workflow. To change them later, go to **Alfred Preferences → Workflows → Home Assistant** and click **Configure Workflow…**.

| Variable | Required | Default | What it does |
|----------|----------|---------|--------------|
| `HA_URL` | yes | — | The base URL of your Home Assistant, such as `http://homeassistant.local:8123`. Don't add `/api` to the end. |
| `HA_TOKEN` | yes | — | The long-lived access token from the previous step. |
| `CACHE_TTL` | no | `60` | How many seconds the entity list can age before the workflow refreshes it in the background. Use a whole number of 0 or more. |
| `HA_PREFERRED_LABEL` | no | `alfred_preferred` | The label ID that lifts tagged entities in the results. See [Ranking](#ranking). |

The workflow stores its entity list and your usage history separately for each `HA_URL`. If you point it at a different Home Assistant, the first server's data stays intact.

<!-- server profiles: see #47 -->

### First run

Type `ha` and a space. The first time, Alfred shows **Loading entities…** while the workflow fetches your entities from Home Assistant. The results appear on their own after a moment. After that, the workflow searches its local copy of your entities, so results come back quickly.

---

## Searching

Type `ha`, a space, and then your query. The query can take four forms.

| Form | Example | Finds |
|------|---------|-------|
| Plain words | `ha kitchen` | Entities that fuzzy-match every word |
| Domain filter | `ha light:living` | Only entities in the `light` domain |
| Regular expression | `ha /door/` | Entities whose entity ID or name matches the pattern |
| System commands | `ha system` | Workflow and Home Assistant commands |

Entity searches show at most 50 results.

### What a result shows

Each result shows the entity's friendly name, with a subtitle that starts with the domain and then the state. Some domains add more detail:

| Domain | Subtitle on the demo | Detail added |
|--------|----------------------|--------------|
| light | `light · On · 71% · 2631K` | Brightness and color temperature |
| sensor | `sensor · 15.6 °C` | Value and unit |
| climate | `climate · Cool · Current: 22° · Target: 21°` | Current and target temperature |
| media_player | `media_player · Playing · <title>` | Media title, or else the source |
| cover | `cover · Open · 70%` | Position |
| update | `update · Update: 1.0.0 → 1.0.1` | Installed and latest version |

The workflow is also designed to show the entity's area in place of the domain. That doesn't work yet: see [#50](https://github.com/AYapejian/ay-alfred-homeassistant/issues/50).

States come from the local copy of your entities. The workflow refreshes that copy in the background once it is older than `CACHE_TTL` seconds, and Alfred updates the list when the refresh finishes.

### Empty query

`ha` on its own lists the entities you use most, then the rest in alphabetical order. At the bottom are **Filter by domain** rows for common domains. Select one and press <kbd>↵</kbd> or <kbd>⇥</kbd> to fill in its `domain:` prefix.

![The ha keyword with no query](images/search-empty.png)

### Fuzzy search

Plain words match against an entity's friendly name, its entity ID and its device class. Matching ignores case. With more than one word, **every** word has to match something, in any field.

A result ranks higher when a word matches the whole field, the start of the field, or the start of a word in it. A word can also match its letters in order, so `kl` finds Kitchen Lights.

| Query | Result on the demo, with no usage history |
|-------|-------------------------------------------|
| `ha kitchen` | Kitchen (a media player), Kitchen Window, Kitchen Lights, Kitchen Door |
| `ha kitch lig` | Kitchen Lights |
| `ha ceiling` | Ceiling Fan, Ceiling Lights |
| `ha front door` | Front Door |

![Fuzzy search for kitchen](images/search-fuzzy.png)

Tab (<kbd>⇥</kbd>) on an entity replaces your query with its friendly name.

### Domain filter

Put a domain name and a colon before your words to search only that domain. With nothing after the colon, you get every entity in the domain.

| Query | Result on the demo |
|-------|--------------------|
| `ha light:` | All 6 lights |
| `ha light:living` | Living Room RGBWW Lights |
| `ha lock:door` | Front Door, Kitchen Door, Poorly Installed Door |
| `ha cover:garage` | Garage Door |

![All lights](images/domain-filter.png)

![Lights matching "living"](images/domain-filter-text.png)

If you type part of a domain name as a single word, such as `ha li`, a row like **Filter: light (6 entities)** appears at the top. Press <kbd>⇥</kbd> or <kbd>↵</kbd> on it to switch to `light:`.

The filter only works for the domains the workflow knows about. For any other prefix, `ha valve:` for example, the whole text is treated as a plain search and usually finds nothing. For those domains, use a plain search (`ha valve`) or a regular expression (`ha /^valve\./`).

<details>
<summary>Domains the filter accepts</summary>

`automation`, `binary_sensor`, `button`, `camera`, `climate`, `counter`, `cover`, `fan`, `group`, `humidifier`, `input_boolean`, `input_datetime`, `input_number`, `input_select`, `input_text`, `light`, `lock`, `media_player`, `number`, `person`, `scene`, `script`, `select`, `sensor`, `siren`, `switch`, `timer`, `update`, `vacuum`, `water_heater`, `weather`, `zone`

</details>

### Regular expressions

Wrap a pattern in slashes to match it against each entity's entity ID and friendly name. The pattern uses Python regular-expression syntax, ignores case, and can match anywhere in the text. Results appear in Home Assistant's order, without ranking.

| Query | Result on the demo |
|-------|--------------------|
| `ha /door/` | Garage Door, Front Door, Kitchen Door, Poorly Installed Door |
| `ha /^light\./` | All 6 lights |
| `ha /_door$/` | The same four doors, matched by entity ID |

![Regex search for door](images/regex.png)

A pattern that doesn't compile, such as `ha /[bad/`, shows **Invalid regex pattern** along with the reason.

### Ranking

Plain searches and domain-filter searches sort results into three groups, in this order:

1. **Entities you have used**, meaning ones you ran an action on from this workflow. Entities you use often or recently rank higher. Recency counts for less as the days go by.
2. **Entities with the preferred label** that you haven't used yet.
3. **Everything else.**

Within each group, better matches come first, with a boost for entities you use. With an empty query, used entities are sorted by how much you use them, and the other two groups are sorted alphabetically.

To clear your usage history, use `ha system history`. See [System commands](#system-commands).

#### Promoting entities with a label

1. In Home Assistant, go to **Settings → Areas, labels & zones → Labels** and create a label named **Alfred Preferred**. Home Assistant gives it the ID `alfred_preferred`.
2. Add the label to any entity, or to a device. A device's label applies to every entity on that device. A label on an area does not.
3. To use a different label, set `HA_PREFERRED_LABEL` to its ID.

> [!NOTE]
> Labels have no effect at the moment, because the workflow can't read them from Home Assistant yet. See [#50](https://github.com/AYapejian/ay-alfred-homeassistant/issues/50).

---

## Running actions

### What Enter does

Pressing <kbd>↵</kbd> on a result runs the default action for its domain. A notification tells you what happened, such as **Toggled Kitchen Lights**.

| Domains | <kbd>↵</kbd> runs | Notes |
|---------|-------------------|-------|
| `light`, `switch`, `fan`, `humidifier`, `siren`, `input_boolean`, `group`, `cover`, `media_player`, `climate` | `toggle` | |
| `automation` | `toggle` | Turns the automation **on or off**. To run it, use **Trigger** in the action menu. |
| `script`, `scene` | `turn_on` | Runs the script or activates the scene |
| `lock` | `lock` | Always locks. To unlock, use the action menu. |
| `button` | `press` | |
| `vacuum`, `timer` | `start` | |
| `counter` | `increment` | |
| `update` | `install` | **Installs the update** |
| `water_heater` | `toggle` | Home Assistant rejects this with *HTTP 400*, so water heaters can't be controlled yet |
| `number`, `input_number`, `input_text` | `set_value` | Needs a value, so use the action menu. Pressing <kbd>↵</kbd> fails with *HTTP 400*. |
| `select`, `input_select` | `select_option` | Needs an option, so use the action menu. Pressing <kbd>↵</kbd> fails with *HTTP 400*. |
| `sensor`, `binary_sensor`, `weather`, `camera`, `person`, `zone`, `input_datetime` and any domain not listed here | *(nothing)* | Display only. <kbd>↵</kbd> just fills the name into the search bar. The modifier keys still work. |

### Modifier keys

These work on every entity result, including display-only ones.

| Keys | Does |
|------|------|
| <kbd>⌘</kbd><kbd>↵</kbd> | Opens the [action menu](#the-action-menu) |
| <kbd>⌥</kbd><kbd>↵</kbd> | Copies the entity ID, such as `light.kitchen_lights`, to the clipboard |
| <kbd>⌃</kbd><kbd>↵</kbd> | Opens Home Assistant's entity settings list, filtered to this entity, in your browser |

---

## The action menu

Press <kbd>⌘</kbd><kbd>↵</kbd> on an entity to see everything you can do with it. The first row shows the entity ID and how long ago its state changed. Below it are the domain's actions, and then the copy and open actions. Typing doesn't filter this list: move through it with the arrow keys and press <kbd>↵</kbd>.

![Action menu for Kitchen Lights](images/action-menu.png)

For Kitchen Lights, the menu shows:

| Row | Does |
|-----|------|
| **Toggle** · **Turn On** · **Turn Off** | Runs that action. Turn On's subtitle says *supports: brightness, color temp, …* because it takes [parameters](#parameters). |
| **Copy Entity ID** | Copies `light.kitchen_lights` |
| **Copy Entity Details** | Copies the entity's full state and attributes as YAML |
| **Open Entity** | Opens the entity in Home Assistant's entity settings |
| **Open History** | Opens Home Assistant's history page for the entity |

Each domain has its own actions: **Lock** and **Unlock** for locks, **Open Cover**, **Close Cover** and **Stop Cover** for covers, **Trigger** for automations, **Media Play**, **Media Pause**, **Media Stop** and **Volume Set** for media players, and so on. A display-only entity such as a sensor shows only the copy and open rows.

The menu is also designed to include **Copy Device Details**, **Open Device** and **Open Area** for entities that belong to a device or an area. Those rows don't appear yet: see [#50](https://github.com/AYapejian/ay-alfred-homeassistant/issues/50).

---

## Parameters

Some actions take parameters, such as a light's brightness or a cover's position. In the action menu, those actions have **supports: …** in their subtitle.

1. Search for the entity and press <kbd>⌘</kbd><kbd>↵</kbd>.
2. Select the action, such as **Turn On**, and press <kbd>↵</kbd>.
3. Alfred lists the parameters that action accepts. Press <kbd>⇥</kbd> on one to start typing it.

   ![Parameter entry for Turn On](images/set-params.png)

4. Type one or more `key:value` pairs, separated by commas. The top row changes to a confirmation, **↵ Turn On Kitchen Lights**, that shows how the workflow read your values. Rows beneath it list each parameter.

   ![Parameters ready to send](images/set-params-confirm.png)

5. Press <kbd>↵</kbd> to send the command.

### Syntax

- Separate each key from its value with `:` and each pair from the next with `,`. For example: `brightness:50%,transition:2`.
- `brightness` takes 0–255, or a percentage with `%`. `brightness:50%` becomes 128.
- `color` is short for `color_name`. The workflow knows more than 1,000 color names, including `red`, `warm_white` and `eggshell`, and sends them as RGB values. Spaces, dashes and underscores in names are treated the same. An unknown name is passed to Home Assistant as it is.
- `rgb_color` takes three numbers from 0 to 255: `rgb_color:255,0,0`. You can add more pairs after it.
- Values outside a documented range are rejected before anything is sent. For example, `position:150` shows *'position' must be <= 100*.
- Keys that aren't in the table below are passed to Home Assistant as text.

| Domain | Action | Key | Accepts | Example |
|--------|--------|-----|---------|---------|
| light | Turn On | `brightness` | 0–255, or 0–100% | `brightness:50%` |
| | | `color_temp_kelvin` | Kelvin, 2000–6500 | `color_temp_kelvin:3000` |
| | | `color` / `color_name` | A color name | `color:red` |
| | | `rgb_color` | `R,G,B` | `rgb_color:255,0,0` |
| | | `effect` | The name of an effect the light supports | `effect:colorloop` |
| | | `transition` | Seconds | `transition:2` |
| fan | Turn On | `percentage` | 0–100 | `percentage:40` |
| cover | Open Cover, Close Cover | `position` | 0–100 | `position:50` |
| media_player | Volume Set | `volume_level` | 0.0–1.0 | `volume_level:0.3` |
| climate | Set Temperature | `temperature` (required) | A number | `temperature:21` |
| | | `hvac_mode` | `heat`, `cool`, `auto`, `off`, … | `hvac_mode:heat` |
| number, input_number | Set Value | `value` (required) | A number | `value:42` |
| input_text | Set Value | `value` (required) | Text | `value:hello` |
| select, input_select | Select Option | `option` (required) | One of the entity's options | `option:<name>` |

Errors appear in place of the confirmation row, and nothing is sent. For example:

| You type | You see |
|----------|---------|
| `brightness:150%` | Brightness percentage must be 0-100, got 150.0 |
| `brightness:abc` | Expected integer for 'brightness', got 'abc' |
| `brightness:50%,oops` | Invalid parameter (expected key:value): 'oops' |

---

## System commands

Type `ha system` to see the system commands. They appear only when your query starts with the word `system`. Any words after it narrow the list: each word has to match the start of one of the command's keywords.

![System commands](images/system-commands.png)

| Row | Try | Does |
|-----|-----|------|
| **History: Clear usage data** | `ha system history` | Deletes your usage history for the current server, which resets the ranking |
| **Cache: Refresh entities** | `ha system cache` | Fetches all entities from Home Assistant again |
| **System: Restart Home Assistant** | `ha system restart` | **Restarts Home Assistant as soon as you press <kbd>↵</kbd>, with no confirmation** |
| **System: Check config** | `ha system config` | Asks Home Assistant to validate its configuration, then shows *Configuration is valid* or the errors |
| **System: View error log** | `ha system log` | Copies Home Assistant's error log to the clipboard |

---

## Troubleshooting

Errors appear either as a row in Alfred's results or as a notification after you press <kbd>↵</kbd>.

| You see | Likely cause | Fix |
|---------|--------------|-----|
| **Configuration Error** · *HA_URL is not set…* or *HA_TOKEN is not set…* | The variable is empty | Fill it in under **Configure Workflow…** |
| **Configuration Error** · *CACHE_TTL must be a non-negative integer* | `CACHE_TTL` isn't a whole number | Use a number such as `60`, or clear the field to use the default |
| *Auth error: Authentication failed (HTTP 401)* | The token is wrong, expired or deleted | [Create a new token](#create-a-long-lived-access-token) and paste it into `HA_TOKEN` |
| *Connection error: … Connection refused* | Nothing is listening at that address and port. Home Assistant may be down, or the port is wrong. | Check the port. Home Assistant's default is `8123`. |
| *Connection error: … nodename nor servname provided, or not known* | The host name doesn't resolve. For example, `homeassistant.local` doesn't work away from your home network. | Use an address that your Mac can resolve from where it is |
| *Connection error: HTTP 404: Not Found* | `HA_URL` points somewhere Home Assistant isn't served, often because it ends in `/api` | Use the address you open Home Assistant at in a browser, such as `http://homeassistant.local:8123` |
| *Connection error: HTTP 400: Bad Request* after <kbd>↵</kbd> on a number, select or input helper | These actions need a value | Use <kbd>⌘</kbd><kbd>↵</kbd>, choose **Set Value** or **Select Option**, and enter a value |
| **Loading entities…** doesn't go away | The first fetch keeps failing. A macOS notification that starts *Cache refresh failed:* gives the reason. | Fix the cause, usually `HA_URL` or `HA_TOKEN`. While the entity list is empty, system commands are hidden too. |
| A state in the results is out of date | The results come from the local copy of your entities | Wait for the background refresh, or run `ha system cache` |
| *Error log not available (endpoint returned 404)…* | Home Assistant doesn't serve the error log through Nabu Casa's cloud URL | Point `HA_URL` at a local address |
| <kbd>↵</kbd> on a sensor only fills its name into the search bar | Sensors are display-only | Use <kbd>⌘</kbd><kbd>↵</kbd> for the copy and open actions |
| `ha valve:` finds nothing | The domain filter works only for [domains the workflow knows about](#domain-filter) | Use `ha valve` or `ha /^valve\./` |
| Areas don't appear, the preferred label has no effect, and the action menu has no device or area rows | A known bug: the workflow can't read Home Assistant's registries yet | See [#50](https://github.com/AYapejian/ay-alfred-homeassistant/issues/50) |

### Getting more detail

- The background refresh writes a log to `~/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/com.ayapejian.alfred-homeassistant/servers/<id>/refresh.log`. Each server you have used gets its own `<id>` folder.
- To see debug output, add a workflow environment variable `HA_DEBUG` with the value `1`. Then open the workflow in Alfred Preferences and click the bug icon to open Alfred's debugger.
