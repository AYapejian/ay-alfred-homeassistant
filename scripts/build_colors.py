#!/usr/bin/env python3
"""One-off builder for packages/ha_lib/data/colors.json.

Combines:

* XKCD color survey names (CC0) — ~950 names from https://xkcd.com/color/rgb.txt
* CSS4 / X11 standard color names (public domain)
* Home Assistant ``light.color_name`` extras (``warm_white``, ``cool_white``,
  ``homeassistant_orange``, etc.) so HA-specific names resolve too.

Run this once when updating the palette::

    python3 scripts/build_colors.py

Output: ``packages/ha_lib/data/colors.json`` — a sorted ``{name: [r, g, b]}``
map with ``_``-joined lowercase keys.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

_XKCD_URL = "https://xkcd.com/color/rgb.txt"

# CSS4 / X11 standard colors (public domain). Mirrors matplotlib's CSS4_COLORS
# but bundled here so we have zero runtime dependencies.
_CSS4: dict[str, str] = {
    "aliceblue": "#f0f8ff",
    "antiquewhite": "#faebd7",
    "aqua": "#00ffff",
    "aquamarine": "#7fffd4",
    "azure": "#f0ffff",
    "beige": "#f5f5dc",
    "bisque": "#ffe4c4",
    "black": "#000000",
    "blanchedalmond": "#ffebcd",
    "blue": "#0000ff",
    "blueviolet": "#8a2be2",
    "brown": "#a52a2a",
    "burlywood": "#deb887",
    "cadetblue": "#5f9ea0",
    "chartreuse": "#7fff00",
    "chocolate": "#d2691e",
    "coral": "#ff7f50",
    "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc",
    "crimson": "#dc143c",
    "cyan": "#00ffff",
    "darkblue": "#00008b",
    "darkcyan": "#008b8b",
    "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9",
    "darkgreen": "#006400",
    "darkgrey": "#a9a9a9",
    "darkkhaki": "#bdb76b",
    "darkmagenta": "#8b008b",
    "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00",
    "darkorchid": "#9932cc",
    "darkred": "#8b0000",
    "darksalmon": "#e9967a",
    "darkseagreen": "#8fbc8f",
    "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f",
    "darkslategrey": "#2f4f4f",
    "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3",
    "deeppink": "#ff1493",
    "deepskyblue": "#00bfff",
    "dimgray": "#696969",
    "dimgrey": "#696969",
    "dodgerblue": "#1e90ff",
    "firebrick": "#b22222",
    "floralwhite": "#fffaf0",
    "forestgreen": "#228b22",
    "fuchsia": "#ff00ff",
    "gainsboro": "#dcdcdc",
    "ghostwhite": "#f8f8ff",
    "gold": "#ffd700",
    "goldenrod": "#daa520",
    "gray": "#808080",
    "green": "#008000",
    "greenyellow": "#adff2f",
    "grey": "#808080",
    "honeydew": "#f0fff0",
    "hotpink": "#ff69b4",
    "indianred": "#cd5c5c",
    "indigo": "#4b0082",
    "ivory": "#fffff0",
    "khaki": "#f0e68c",
    "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5",
    "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd",
    "lightblue": "#add8e6",
    "lightcoral": "#f08080",
    "lightcyan": "#e0ffff",
    "lightgoldenrodyellow": "#fafad2",
    "lightgray": "#d3d3d3",
    "lightgreen": "#90ee90",
    "lightgrey": "#d3d3d3",
    "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa",
    "lightskyblue": "#87cefa",
    "lightslategray": "#778899",
    "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0",
    "lime": "#00ff00",
    "limegreen": "#32cd32",
    "linen": "#faf0e6",
    "magenta": "#ff00ff",
    "maroon": "#800000",
    "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd",
    "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db",
    "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a",
    "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585",
    "midnightblue": "#191970",
    "mintcream": "#f5fffa",
    "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead",
    "navy": "#000080",
    "oldlace": "#fdf5e6",
    "olive": "#808000",
    "olivedrab": "#6b8e23",
    "orange": "#ffa500",
    "orangered": "#ff4500",
    "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98",
    "paleturquoise": "#afeeee",
    "palevioletred": "#db7093",
    "papayawhip": "#ffefd5",
    "peachpuff": "#ffdab9",
    "peru": "#cd853f",
    "pink": "#ffc0cb",
    "plum": "#dda0dd",
    "powderblue": "#b0e0e6",
    "purple": "#800080",
    "rebeccapurple": "#663399",
    "red": "#ff0000",
    "rosybrown": "#bc8f8f",
    "royalblue": "#4169e1",
    "saddlebrown": "#8b4513",
    "salmon": "#fa8072",
    "sandybrown": "#f4a460",
    "seagreen": "#2e8b57",
    "seashell": "#fff5ee",
    "sienna": "#a0522d",
    "silver": "#c0c0c0",
    "skyblue": "#87ceeb",
    "slateblue": "#6a5acd",
    "slategray": "#708090",
    "slategrey": "#708090",
    "snow": "#fffafa",
    "springgreen": "#00ff7f",
    "steelblue": "#4682b4",
    "tan": "#d2b48c",
    "teal": "#008080",
    "thistle": "#d8bfd8",
    "tomato": "#ff6347",
    "turquoise": "#40e0d0",
    "violet": "#ee82ee",
    "wheat": "#f5deb3",
    "white": "#ffffff",
    "whitesmoke": "#f5f5f5",
    "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
}

# Home Assistant ``light.color_name`` extras beyond CSS4.
_HA_EXTRAS: dict[str, str] = {
    "warm_white": "#ffa500",
    "cool_white": "#f5f5f5",
    "homeassistant_orange": "#18bcf2",
    "homeassistant_blue": "#18bcf2",
}


def _normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _hex_to_rgb(h: str) -> list[int]:
    h = h.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Bad hex: {h!r}")
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]


def main() -> int:
    print(f"Fetching {_XKCD_URL}...", file=sys.stderr)
    with urllib.request.urlopen(_XKCD_URL, timeout=30) as resp:
        body = resp.read().decode("utf-8")

    palette: dict[str, list[int]] = {}

    # Precedence matters: XKCD first for breadth (~950 names), then CSS4
    # overrides on collision so basics (``red`` → 255,0,0) match what users
    # expect from web colors rather than XKCD's slightly off-spec values
    # (``red`` → 229,0,0).  HA extras win last.
    xkcd_count = 0
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = _normalize(parts[0])
        if not name:
            continue
        try:
            palette[name] = _hex_to_rgb(parts[1])
            xkcd_count += 1
        except ValueError:
            continue

    for name, hex_val in _CSS4.items():
        palette[_normalize(name)] = _hex_to_rgb(hex_val)

    for name, hex_val in _HA_EXTRAS.items():
        palette[_normalize(name)] = _hex_to_rgb(hex_val)

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "packages",
        "ha_lib",
        "data",
        "colors.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    sorted_palette = dict(sorted(palette.items()))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sorted_palette, f, indent=2, sort_keys=True)
        f.write("\n")

    print(
        f"Wrote {len(sorted_palette)} colors to {out_path} "
        f"(CSS4: {len(_CSS4)}, HA extras: {len(_HA_EXTRAS)}, XKCD: {xkcd_count})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
