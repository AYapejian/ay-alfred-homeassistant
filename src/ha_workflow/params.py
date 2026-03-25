"""Parse short-syntax service parameters (e.g. ``brightness:50,transition:2``)."""

from __future__ import annotations

import math
from typing import Optional, Union

from ha_workflow.entities import get_action_params

# Type produced by the parser — values are coerced to their declared types.
ParamValue = Union[int, float, str, bool]


def parse_service_params(
    raw: str,
    domain: str,
    action: str,
) -> dict[str, object]:
    """Parse ``key:value,key:value`` into a typed ``service_data`` dict.

    Type coercion uses :func:`get_action_params` for the *(domain, action)*
    pair.  Unknown keys are passed through as strings so power users can send
    arbitrary HA service data.

    Special handling:

    * **brightness** — a trailing ``%`` converts the percentage (0-100) to the
      HA 0-255 range.
    * **rgb_color** — ``"255,0,0"`` is converted to ``[255, 0, 0]``.

    Raises :class:`ValueError` on parse or validation failures.
    """
    if not raw or not raw.strip():
        return {}

    param_defs = {p.name: p for p in get_action_params(domain, action)}
    result: dict[str, object] = {}

    # Pre-extract rgb_color if present (its value contains commas)
    remaining = raw
    if "rgb_color:" in remaining:
        before, rgb_rest = remaining.split("rgb_color:", 1)
        rgb_val, after = _extract_rgb(rgb_rest)
        result["rgb_color"] = rgb_val
        # Reassemble remaining params without the rgb_color segment
        parts = [p.strip() for p in [before.rstrip(",").strip(), after] if p.strip()]
        remaining = ",".join(parts)

    if not remaining.strip():
        return result

    for pair in remaining.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            raise ValueError(f"Invalid parameter (expected key:value): {pair!r}")
        key, value = pair.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Empty parameter name in: {pair!r}")

        param_def = param_defs.get(key)
        if param_def is None:
            # Unknown key — pass through as string
            result[key] = value
            continue

        result[key] = _coerce(key, value, param_def.type)

        # Validate min/max
        if param_def.min_value is not None or param_def.max_value is not None:
            _validate_range(key, result[key], param_def.min_value, param_def.max_value)

    return result


def _coerce(key: str, value: str, type_name: str) -> ParamValue:
    """Coerce *value* to the declared *type_name*."""
    if type_name == "int":
        return _coerce_int(key, value)
    if type_name == "float":
        return _coerce_float(key, value)
    if type_name == "bool":
        return value.lower() in ("true", "1", "yes", "on")
    # str — pass through
    return value


def _coerce_int(key: str, value: str) -> int:
    """Coerce to int, with brightness percentage shorthand."""
    if key == "brightness" and value.endswith("%"):
        pct_str = value[:-1]
        try:
            pct = float(pct_str)
        except ValueError:
            raise ValueError(f"Invalid brightness percentage: {value!r}") from None
        if pct < 0 or pct > 100:
            raise ValueError(f"Brightness percentage must be 0-100, got {pct}")
        return math.ceil(pct / 100.0 * 255)
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Expected integer for '{key}', got {value!r}") from None


def _coerce_float(key: str, value: str) -> float:
    """Coerce to float."""
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Expected number for '{key}', got {value!r}") from None


def _validate_range(
    key: str,
    value: object,
    min_val: Optional[float],
    max_val: Optional[float],
) -> None:
    """Raise ValueError if *value* is outside [min_val, max_val]."""
    if not isinstance(value, (int, float)):
        return
    if min_val is not None and value < min_val:
        raise ValueError(f"'{key}' must be >= {min_val}, got {value}")
    if max_val is not None and value > max_val:
        raise ValueError(f"'{key}' must be <= {max_val}, got {value}")


def _extract_rgb(rgb_raw: str) -> tuple[list[int], str]:
    """Extract an RGB triplet and return ``(rgb_list, remaining_params)``.

    Consumes up to 3 comma-separated integer tokens from *rgb_raw*, stopping
    when a ``key:value`` pair is encountered.
    """
    rgb_parts: list[str] = []
    after_parts: list[str] = []
    hit_next = False
    for token in rgb_raw.split(","):
        token = token.strip()
        if hit_next or (":" in token and len(rgb_parts) >= 1):
            hit_next = True
            after_parts.append(token)
        else:
            rgb_parts.append(token)

    if len(rgb_parts) != 3:
        raise ValueError(
            f"Expected 3 RGB values (R,G,B), got {len(rgb_parts)}: "
            f"{','.join(rgb_parts)!r}"
        )
    try:
        rgb = [int(p) for p in rgb_parts]
    except ValueError:
        raise ValueError(
            f"RGB values must be integers, got: {','.join(rgb_parts)!r}"
        ) from None
    for i, v in enumerate(rgb):
        if v < 0 or v > 255:
            raise ValueError(f"RGB value {v} at position {i} must be 0-255")
    return rgb, ",".join(after_parts)
