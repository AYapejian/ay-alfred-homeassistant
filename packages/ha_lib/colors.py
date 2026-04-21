"""Named-color resolution.

Maps human-friendly color names (CSS4 + X11 + XKCD + HA extras) to RGB
triplets.  The bundled JSON is built by ``scripts/build_colors.py``.

Resolution is permissive: names are lowercased and spaces, dashes, and
underscores are all treated as the same separator, so ``"warm white"``,
``"warm-white"``, and ``"warm_white"`` all resolve to the same color.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent / "data" / "colors.json"


def _normalize(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


@lru_cache(maxsize=1)
def _palette() -> dict[str, tuple[int, int, int]]:
    with _DATA_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return {name: (r, g, b) for name, (r, g, b) in raw.items()}


def resolve_color(name: str) -> Optional[tuple[int, int, int]]:
    """Return ``(r, g, b)`` for *name*, or ``None`` if unknown."""
    if not name:
        return None
    return _palette().get(_normalize(name))


def palette_size() -> int:
    """Number of known color names (useful in tests)."""
    return len(_palette())
