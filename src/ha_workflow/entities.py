"""Entity data model and domain registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

SubtitleFormatter = Callable[["Entity"], str]


# ---------------------------------------------------------------------------
# Entity dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Entity:
    """A single Home Assistant entity."""

    entity_id: str
    domain: str
    state: str
    friendly_name: str
    attributes: dict[str, Any]
    last_changed: str
    last_updated: str
    area_name: str = ""
    device_id: str = ""
    labels: tuple[str, ...] = ()

    @classmethod
    def from_state_dict(
        cls,
        data: dict[str, Any],
        area_name: str = "",
        device_id: str = "",
        labels: tuple[str, ...] = (),
    ) -> Entity:
        """Convert an HA REST API state dict to an :class:`Entity`."""
        entity_id: str = data["entity_id"]
        domain = entity_id.split(".", 1)[0]
        attrs: dict[str, Any] = data.get("attributes") or {}
        return cls(
            entity_id=entity_id,
            domain=domain,
            state=data.get("state", "unknown"),
            friendly_name=attrs.get("friendly_name", entity_id),
            attributes=attrs,
            last_changed=data.get("last_changed", ""),
            last_updated=data.get("last_updated", ""),
            area_name=area_name,
            device_id=device_id,
            labels=labels,
        )

    @property
    def device_class(self) -> Optional[str]:
        """Return the ``device_class`` attribute, if present."""
        val = self.attributes.get("device_class")
        if isinstance(val, str):
            return val
        return None


# ---------------------------------------------------------------------------
# Domain configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DomainConfig:
    """Per-domain defaults for actions, icons, and subtitle formatting."""

    default_action: str
    available_actions: tuple[str, ...]
    icon_path: str
    subtitle_formatter: SubtitleFormatter


# ---------------------------------------------------------------------------
# Subtitle formatters
# ---------------------------------------------------------------------------


def _default_subtitle(entity: Entity) -> str:
    return entity.state.replace("_", " ").title()


def _light_subtitle(entity: Entity) -> str:
    parts = [entity.state.replace("_", " ").title()]
    brightness = entity.attributes.get("brightness")
    if brightness is not None:
        try:
            pct = round(int(brightness) / 255 * 100)
            parts.append(f"{pct}%")
        except (ValueError, TypeError):
            pass
    color_temp = entity.attributes.get("color_temp_kelvin")
    if color_temp is not None:
        parts.append(f"{color_temp}K")
    return " \u00b7 ".join(parts)


def _sensor_subtitle(entity: Entity) -> str:
    unit = entity.attributes.get("unit_of_measurement", "")
    if unit:
        return f"{entity.state} {unit}"
    return entity.state


def _climate_subtitle(entity: Entity) -> str:
    parts = [entity.state.replace("_", " ").title()]
    current = entity.attributes.get("current_temperature")
    target = entity.attributes.get("temperature")
    if current is not None:
        parts.append(f"Current: {current}\u00b0")
    if target is not None:
        parts.append(f"Target: {target}\u00b0")
    return " \u00b7 ".join(parts)


def _media_player_subtitle(entity: Entity) -> str:
    parts = [entity.state.replace("_", " ").title()]
    source = entity.attributes.get("media_title") or entity.attributes.get("source")
    if source:
        parts.append(str(source))
    return " \u00b7 ".join(parts)


def _cover_subtitle(entity: Entity) -> str:
    parts = [entity.state.replace("_", " ").title()]
    position = entity.attributes.get("current_position")
    if position is not None:
        parts.append(f"{position}%")
    return " \u00b7 ".join(parts)


def _update_subtitle(entity: Entity) -> str:
    installed = entity.attributes.get("installed_version", "")
    latest = entity.attributes.get("latest_version", "")
    if installed and latest and installed != latest:
        return f"Update: {installed} \u2192 {latest}"
    if installed:
        return f"v{installed} (up to date)"
    return entity.state.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Domain registry
# ---------------------------------------------------------------------------

_DC = DomainConfig  # shorthand

DOMAIN_REGISTRY: dict[str, DomainConfig] = {
    # Toggleable entities
    "light": _DC(
        "toggle", ("toggle", "turn_on", "turn_off"), "icons/light.png", _light_subtitle
    ),
    "switch": _DC(
        "toggle",
        ("toggle", "turn_on", "turn_off"),
        "icons/switch.png",
        _default_subtitle,
    ),
    "fan": _DC(
        "toggle", ("toggle", "turn_on", "turn_off"), "icons/fan.png", _default_subtitle
    ),
    "humidifier": _DC(
        "toggle",
        ("toggle", "turn_on", "turn_off"),
        "icons/humidifier.png",
        _default_subtitle,
    ),
    "water_heater": _DC(
        "toggle", ("toggle",), "icons/water_heater.png", _default_subtitle
    ),
    "siren": _DC(
        "toggle",
        ("toggle", "turn_on", "turn_off"),
        "icons/siren.png",
        _default_subtitle,
    ),
    "input_boolean": _DC(
        "toggle",
        ("toggle", "turn_on", "turn_off"),
        "icons/input_boolean.png",
        _default_subtitle,
    ),
    "group": _DC(
        "toggle",
        ("toggle", "turn_on", "turn_off"),
        "icons/group.png",
        _default_subtitle,
    ),
    # Sensors (display-only)
    "sensor": _DC("", (), "icons/sensor.png", _sensor_subtitle),
    "binary_sensor": _DC("", (), "icons/binary_sensor.png", _default_subtitle),
    "weather": _DC("", (), "icons/weather.png", _sensor_subtitle),
    # Automation / scripting
    "automation": _DC(
        "toggle",
        ("toggle", "trigger", "turn_on", "turn_off"),
        "icons/automation.png",
        _default_subtitle,
    ),
    "script": _DC("turn_on", ("turn_on",), "icons/script.png", _default_subtitle),
    "scene": _DC("turn_on", ("turn_on",), "icons/scene.png", _default_subtitle),
    # Complex entities
    "climate": _DC(
        "toggle",
        ("toggle", "set_temperature"),
        "icons/climate.png",
        _climate_subtitle,
    ),
    "media_player": _DC(
        "toggle",
        ("toggle", "media_play", "media_pause", "media_stop", "volume_set"),
        "icons/media_player.png",
        _media_player_subtitle,
    ),
    "cover": _DC(
        "toggle",
        ("toggle", "open_cover", "close_cover", "stop_cover"),
        "icons/cover.png",
        _cover_subtitle,
    ),
    "lock": _DC("lock", ("lock", "unlock"), "icons/lock.png", _default_subtitle),
    "vacuum": _DC(
        "start",
        ("start", "stop", "return_to_base"),
        "icons/vacuum.png",
        _default_subtitle,
    ),
    "camera": _DC("", (), "icons/camera.png", _default_subtitle),
    # People / zones
    "person": _DC("", (), "icons/person.png", _default_subtitle),
    "zone": _DC("", (), "icons/zone.png", _default_subtitle),
    # Input helpers
    "input_number": _DC(
        "set_value", ("set_value",), "icons/input_number.png", _sensor_subtitle
    ),
    "input_select": _DC(
        "select_option", ("select_option",), "icons/input_select.png", _default_subtitle
    ),
    "input_text": _DC(
        "set_value", ("set_value",), "icons/input_text.png", _default_subtitle
    ),
    "input_datetime": _DC("", (), "icons/input_datetime.png", _default_subtitle),
    "number": _DC("set_value", ("set_value",), "icons/number.png", _sensor_subtitle),
    "select": _DC(
        "select_option", ("select_option",), "icons/select.png", _default_subtitle
    ),
    # Action entities
    "button": _DC("press", ("press",), "icons/button.png", _default_subtitle),
    "timer": _DC(
        "start", ("start", "cancel", "pause"), "icons/timer.png", _default_subtitle
    ),
    "counter": _DC(
        "increment",
        ("increment", "decrement", "reset"),
        "icons/counter.png",
        _default_subtitle,
    ),
    # System
    "update": _DC("install", ("install", "skip"), "icons/update.png", _update_subtitle),
}

_UNKNOWN_DOMAIN = DomainConfig(
    default_action="",
    available_actions=(),
    icon_path="icons/_default.png",
    subtitle_formatter=_default_subtitle,
)


def get_domain_config(domain: str) -> DomainConfig:
    """Return the :class:`DomainConfig` for *domain*, with a safe fallback."""
    return DOMAIN_REGISTRY.get(domain, _UNKNOWN_DOMAIN)


# ---------------------------------------------------------------------------
# Action parameter definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionParam:
    """Describes a single parameter for a parameterized HA service call."""

    name: str  # HA service_data key (e.g. "brightness")
    label: str  # Human-readable label ("Brightness")
    type: str  # "int", "float", "str", "bool"
    required: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    hint: str = ""  # shown as Alfred subtitle ("0-255 or 0-100%")


_AP = ActionParam  # shorthand

ACTION_PARAMS: dict[tuple[str, str], tuple[ActionParam, ...]] = {
    # --- Lights ---
    ("light", "turn_on"): (
        _AP("brightness", "Brightness", "int", hint="0-255 or 0-100%"),
        _AP("color_temp_kelvin", "Color Temp", "int", hint="2000-6500 K"),
        _AP("rgb_color", "RGB Color", "str", hint="R,G,B (e.g. 255,0,0)"),
        _AP("color_name", "Color Name", "str", hint="e.g. red, blue, warm_white"),
        _AP("effect", "Effect", "str", hint="Effect name"),
        _AP("transition", "Transition", "float", hint="Seconds"),
    ),
    # --- Climate ---
    ("climate", "set_temperature"): (
        _AP("temperature", "Temperature", "float", required=True, hint="Target temp"),
        _AP("hvac_mode", "HVAC Mode", "str", hint="heat, cool, auto, off"),
    ),
    # --- Cover ---
    ("cover", "open_cover"): (
        _AP("position", "Position", "int", hint="0-100", min_value=0, max_value=100),
    ),
    ("cover", "close_cover"): (
        _AP("position", "Position", "int", hint="0-100", min_value=0, max_value=100),
    ),
    # --- Fan ---
    ("fan", "turn_on"): (
        _AP("percentage", "Speed", "int", hint="0-100", min_value=0, max_value=100),
    ),
    # --- Media player ---
    ("media_player", "volume_set"): (
        _AP(
            "volume_level",
            "Volume",
            "float",
            hint="0.0-1.0",
            min_value=0.0,
            max_value=1.0,
        ),
    ),
    # --- Input helpers ---
    ("input_number", "set_value"): (
        _AP("value", "Value", "float", required=True, hint="New value"),
    ),
    ("input_select", "select_option"): (
        _AP("option", "Option", "str", required=True, hint="Option to select"),
    ),
    ("input_text", "set_value"): (
        _AP("value", "Value", "str", required=True, hint="New text"),
    ),
    ("number", "set_value"): (
        _AP("value", "Value", "float", required=True, hint="New value"),
    ),
    ("select", "select_option"): (
        _AP("option", "Option", "str", required=True, hint="Option to select"),
    ),
}


def get_action_params(domain: str, action: str) -> tuple[ActionParam, ...]:
    """Return parameter definitions for a domain/action pair, or empty tuple."""
    return ACTION_PARAMS.get((domain, action), ())
