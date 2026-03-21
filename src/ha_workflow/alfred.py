"""Alfred 5 Script Filter JSON builder."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AlfredIcon:
    """Icon reference for an Alfred item."""

    path: str
    type: Optional[str] = None  # "fileicon" | "filetype" | None

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"path": self.path}
        if self.type is not None:
            d["type"] = self.type
        return d


@dataclass
class AlfredMod:
    """Modifier key overlay (cmd, alt, ctrl, shift, fn)."""

    subtitle: Optional[str] = None
    arg: Optional[str] = None
    valid: Optional[bool] = None
    icon: Optional[AlfredIcon] = None
    variables: Optional[dict[str, str]] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.subtitle is not None:
            d["subtitle"] = self.subtitle
        if self.arg is not None:
            d["arg"] = self.arg
        if self.valid is not None:
            d["valid"] = self.valid
        if self.icon is not None:
            d["icon"] = self.icon.to_dict()
        if self.variables is not None:
            d["variables"] = self.variables
        return d


@dataclass
class AlfredItem:
    """A single item in Alfred's Script Filter results."""

    title: str
    subtitle: Optional[str] = None
    arg: Optional[str] = None
    icon: Optional[AlfredIcon] = None
    valid: Optional[bool] = None
    match: Optional[str] = None
    autocomplete: Optional[str] = None
    uid: Optional[str] = None
    mods: Optional[dict[str, AlfredMod]] = None
    variables: Optional[dict[str, str]] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"title": self.title}
        if self.subtitle is not None:
            d["subtitle"] = self.subtitle
        if self.arg is not None:
            d["arg"] = self.arg
        if self.icon is not None:
            d["icon"] = self.icon.to_dict()
        if self.valid is not None:
            d["valid"] = self.valid
        if self.match is not None:
            d["match"] = self.match
        if self.autocomplete is not None:
            d["autocomplete"] = self.autocomplete
        if self.uid is not None:
            d["uid"] = self.uid
        if self.mods is not None:
            d["mods"] = {k: v.to_dict() for k, v in self.mods.items()}
        if self.variables is not None:
            d["variables"] = self.variables
        return d


@dataclass
class AlfredOutput:
    """Complete Alfred Script Filter response."""

    items: list[AlfredItem] = field(default_factory=list)
    rerun: Optional[float] = None
    cache_seconds: Optional[int] = None
    cache_loosereload: Optional[bool] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"items": [i.to_dict() for i in self.items]}
        if self.rerun is not None:
            d["rerun"] = self.rerun
        if self.cache_seconds is not None or self.cache_loosereload is not None:
            cache: dict[str, Any] = {}
            if self.cache_seconds is not None:
                cache["seconds"] = self.cache_seconds
            if self.cache_loosereload is not None:
                cache["loosereload"] = self.cache_loosereload
            d["cache"] = cache
        return d

    def to_json(self) -> str:
        """Serialize to Alfred Script Filter JSON."""
        return json.dumps(self.to_dict())
