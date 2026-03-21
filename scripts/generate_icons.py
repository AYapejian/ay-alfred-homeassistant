#!/usr/bin/env python3
"""Generate domain-specific icons for the Alfred workflow.

Downloads MDI (Material Design Icons) SVGs from Pictogrammers and renders
them as white icons on colored rounded-square backgrounds (256x256 PNG).

Usage:
    uv run scripts/generate_icons.py

Requires dev dependencies: cairosvg, Pillow
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ICON_SIZE = 256
CORNER_RADIUS = 48
ICON_PADDING = 56  # padding from edge for the MDI icon
MDI_BASE_URL = (
    "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG"
    "/master/svg/{name}.svg"
)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "workflow" / "icons"

# Domain -> (mdi_icon_name, hex_color)
DOMAIN_ICONS: dict[str, tuple[str, str]] = {
    # Toggleable
    "light": ("lightbulb", "#FFC107"),
    "switch": ("toggle-switch", "#4CAF50"),
    "fan": ("fan", "#4CAF50"),
    "humidifier": ("air-humidifier", "#4CAF50"),
    "water_heater": ("water-boiler", "#FF9800"),
    "siren": ("alarm-light", "#F44336"),
    "input_boolean": ("toggle-switch-outline", "#4CAF50"),
    "group": ("google-circles-communities", "#607D8B"),
    # Sensors
    "sensor": ("eye", "#2196F3"),
    "binary_sensor": ("motion-sensor", "#607D8B"),
    "weather": ("weather-partly-cloudy", "#2196F3"),
    # Automation / scripting
    "automation": ("robot", "#00BCD4"),
    "script": ("script-text", "#00BCD4"),
    "scene": ("palette", "#9C27B0"),
    # Complex
    "climate": ("thermostat", "#FF9800"),
    "media_player": ("speaker", "#9C27B0"),
    "cover": ("window-shutter", "#3F51B5"),
    "lock": ("lock", "#009688"),
    "vacuum": ("robot-vacuum", "#607D8B"),
    "camera": ("camera", "#F44336"),
    # People / zones
    "person": ("account", "#795548"),
    "zone": ("map-marker-radius", "#795548"),
    # Input helpers
    "input_number": ("numeric", "#607D8B"),
    "input_select": ("form-dropdown", "#607D8B"),
    "input_text": ("form-textbox", "#607D8B"),
    "input_datetime": ("calendar-clock", "#607D8B"),
    "number": ("numeric", "#607D8B"),
    "select": ("form-dropdown", "#607D8B"),
    # Actions
    "button": ("gesture-tap-button", "#4CAF50"),
    "timer": ("timer-outline", "#FF9800"),
    "counter": ("counter", "#607D8B"),
    # System
    "update": ("package-up", "#2196F3"),
    # Fallback / unknown
    "_default": ("home-assistant", "#03A9F4"),
    # System commands icon
    "_system": ("cog", "#757575"),
}


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert '#RRGGBB' to (R, G, B) tuple."""
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def download_svg(icon_name: str) -> bytes:
    """Download an MDI SVG from the Pictogrammers GitHub repo."""
    url = MDI_BASE_URL.format(name=icon_name)
    print(f"  Downloading {icon_name}...")
    req = urllib.request.Request(url, headers={"User-Agent": "ay-alfred-ha/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def recolor_svg_white(svg_bytes: bytes) -> bytes:
    """Replace the SVG fill color with white."""
    svg_text = svg_bytes.decode("utf-8")
    # MDI SVGs use a single <path> — add white fill to the root <svg>
    svg_text = svg_text.replace("<svg ", '<svg fill="white" ', 1)
    return svg_text.encode("utf-8")


def render_icon(svg_bytes: bytes, bg_color: str) -> Image.Image:
    """Render an MDI SVG as a white icon on a colored rounded-square background."""
    rgb = hex_to_rgb(bg_color)

    # Create background with rounded corners
    bg = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bg)
    draw.rounded_rectangle(
        [(0, 0), (ICON_SIZE - 1, ICON_SIZE - 1)],
        radius=CORNER_RADIUS,
        fill=(*rgb, 255),
    )

    # Render SVG to PNG (white, with transparency)
    white_svg = recolor_svg_white(svg_bytes)
    icon_size = ICON_SIZE - (ICON_PADDING * 2)
    png_bytes = cairosvg.svg2png(
        bytestring=white_svg,
        output_width=icon_size,
        output_height=icon_size,
    )
    icon_img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    # Composite icon centered on background
    offset = ICON_PADDING
    bg.paste(icon_img, (offset, offset), icon_img)

    return bg


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating icons to {OUTPUT_DIR}/")

    failed: list[str] = []
    for domain, (icon_name, color) in DOMAIN_ICONS.items():
        try:
            svg_bytes = download_svg(icon_name)
            img = render_icon(svg_bytes, color)
            out_path = OUTPUT_DIR / f"{domain}.png"
            img.save(str(out_path), "PNG")
            print(f"  -> {out_path.name}")
        except Exception as exc:
            print(f"  FAILED {domain} ({icon_name}): {exc}")
            failed.append(domain)

    total = len(DOMAIN_ICONS)
    ok = total - len(failed)
    print(f"\nDone: {ok}/{total} icons generated.")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
