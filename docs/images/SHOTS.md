# Shot list

<!--
Machine-readable. One line per image under "## Shots":
  filename | query typed after "ha " | keystrokes after results appear | what must be visible
Query "<empty>" means type "ha " and nothing else.
Keystrokes: comma-separated. "none", "enter", "cmd+enter", "tab", "down", or type:<text> to type into
the Alfred box of the current step. Wait for the results to settle between steps.
Captured against the demo Home Assistant (scripts/demo-ha.sh), never a real house.
-->

## Setup (before any shot)

- `HA_URL` / `HA_TOKEN` point at the demo (`scripts/demo-ha.sh env`); `CACHE_TTL` left at its default.
- Clean usage history: `ha system history` → enter.
- Give Kitchen Lights usage history, so it ranks first: `ha kitchen lights` → enter, twice. It ends in its original state.
- Wait for **Loading entities…** to clear before the first shot.

## Shots

search-empty.png | <empty> | none | Kitchen Lights first (used), then entities A–Z (AC, All lights off at midnight, …) with "domain · state" subtitles
search-fuzzy.png | kitchen | none | 4 rows: Kitchen Lights (used, so first), Kitchen (media_player · Playing · …), Kitchen Window, Kitchen Door
domain-filter.png | light: | none | exactly 6 lights: Kitchen Lights first, then Bed Light, Ceiling Lights (subtitle shows 2631K), Entrance Color + White Lights, Living Room RGBWW Lights, Office RGBW Lights
domain-filter-text.png | light:living | none | one row: Living Room RGBWW Lights, subtitle "light · <state>"
regex.png | /door/ | none | Garage Door (cover), Front Door, Kitchen Door, Poorly Installed Door (locks). "Filter by domain" rows below them are expected (known quirk)
action-menu.png | kitchen lights | cmd+enter | header "Kitchen Lights · light.kitchen_lights · Changed …", then Toggle, Turn On (supports: brightness, color temp, …), Turn Off, Copy Entity ID, Copy Entity Details, Open Entity, Open History
set-params.png | kitchen lights | cmd+enter, down, down, enter | "Set parameters for Turn On" header, then Brightness, Color Temp, RGB Color, Color Name, Effect, Transition hint rows
set-params-confirm.png | kitchen lights | cmd+enter, down, down, enter, type:brightness:50%,color:red | top row "↵ Turn On Kitchen Lights" with subtitle "brightness=128/255 (≈50%) …, rgb_color=[255, 0, 0]", then rows "brightness: 128" and "rgb_color: [255, 0, 0]"
system-commands.png | system | none | 5 rows: History: Clear usage data, Cache: Refresh entities, System: Restart Home Assistant, System: Check config, System: View error log (subtitles name 127.0.0.1:8124)

## Hero GIF (docs/images/hero.gif) frame plan

Alt text: "Searching and toggling a light". Run after Setup. Type one character per frame group, and hold each marked frame for about 1 s.

1. `ha ` (empty query), hold
2. `ha k` → `ha ki` → `ha kit` → `ha kitchen`, hold (4 kitchen rows, Kitchen Lights on top)
3. `ha kitchen l` → `ha kitchen li` → … → `ha kitchen lights`, hold (single row, "light · On · …")
4. enter. Hold on the notification "Toggled Kitchen Lights"
5. Reopen Alfred and type `ha kitchen lights`, hold (the subtitle may show the old state until the background refresh lands)
6. cmd+enter. Hold on the action menu (Toggle, Turn On, Turn Off, Copy…, Open…). End.

Leave Kitchen Lights on at the end: add a final unrecorded `ha kitchen lights` → enter if the GIF left it off.
