"""Tests for ha_workflow.alfred — Alfred 5 Script Filter JSON builder."""

from __future__ import annotations

import json

from ha_workflow.alfred import AlfredIcon, AlfredItem, AlfredMod, AlfredOutput


class TestAlfredIcon:
    def test_path_only(self) -> None:
        assert AlfredIcon(path="icon.png").to_dict() == {"path": "icon.png"}

    def test_with_type(self) -> None:
        icon = AlfredIcon(path="icon.png", type="fileicon")
        assert icon.to_dict() == {"path": "icon.png", "type": "fileicon"}


class TestAlfredMod:
    def test_empty(self) -> None:
        assert AlfredMod().to_dict() == {}

    def test_full(self) -> None:
        mod = AlfredMod(
            subtitle="Hold cmd",
            arg="alt-action",
            valid=True,
            icon=AlfredIcon(path="cmd.png"),
            variables={"mode": "cmd"},
        )
        d = mod.to_dict()
        assert d["subtitle"] == "Hold cmd"
        assert d["arg"] == "alt-action"
        assert d["valid"] is True
        assert d["icon"] == {"path": "cmd.png"}
        assert d["variables"] == {"mode": "cmd"}


class TestAlfredItem:
    def test_title_only(self) -> None:
        d = AlfredItem(title="Hello").to_dict()
        assert d == {"title": "Hello"}

    def test_full_item(self) -> None:
        item = AlfredItem(
            title="Living Room Light",
            subtitle="On",
            arg="light.living_room",
            icon=AlfredIcon(path="icons/light.png"),
            valid=True,
            match="living room light",
            autocomplete="Living Room",
            uid="light.living_room",
            mods={"cmd": AlfredMod(subtitle="Toggle", arg="toggle")},
            variables={"entity_id": "light.living_room"},
        )
        d = item.to_dict()
        assert d["title"] == "Living Room Light"
        assert d["subtitle"] == "On"
        assert d["arg"] == "light.living_room"
        assert d["icon"] == {"path": "icons/light.png"}
        assert d["valid"] is True
        assert d["match"] == "living room light"
        assert d["autocomplete"] == "Living Room"
        assert d["uid"] == "light.living_room"
        assert d["mods"]["cmd"]["subtitle"] == "Toggle"
        assert d["variables"]["entity_id"] == "light.living_room"


class TestAlfredOutput:
    def test_empty_items(self) -> None:
        out = AlfredOutput()
        assert out.to_dict() == {"items": []}
        assert json.loads(out.to_json()) == {"items": []}

    def test_with_items(self) -> None:
        out = AlfredOutput(items=[AlfredItem(title="A"), AlfredItem(title="B")])
        data = json.loads(out.to_json())
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "A"
        assert data["items"][1]["title"] == "B"

    def test_rerun(self) -> None:
        out = AlfredOutput(rerun=0.5)
        assert out.to_dict()["rerun"] == 0.5

    def test_cache(self) -> None:
        out = AlfredOutput(cache_seconds=30, cache_loosereload=True)
        data = out.to_dict()
        assert data["cache"] == {"seconds": 30, "loosereload": True}

    def test_cache_seconds_only(self) -> None:
        out = AlfredOutput(cache_seconds=10)
        assert out.to_dict()["cache"] == {"seconds": 10}

    def test_to_json_is_valid_json(self) -> None:
        out = AlfredOutput(
            items=[AlfredItem(title="Test", subtitle="sub")],
            rerun=1.0,
            cache_seconds=60,
        )
        parsed = json.loads(out.to_json())
        assert "items" in parsed
        assert "rerun" in parsed
        assert "cache" in parsed
