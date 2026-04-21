"""Tests for ha_workflow.colors."""

from __future__ import annotations

from ha_workflow.colors import palette_size, resolve_color


class TestResolveColor:
    def test_css4_red(self) -> None:
        assert resolve_color("red") == (255, 0, 0)

    def test_css4_white(self) -> None:
        assert resolve_color("white") == (255, 255, 255)

    def test_xkcd_eggshell(self) -> None:
        # XKCD: eggshell -> #ffffd4
        assert resolve_color("eggshell") == (255, 255, 212)

    def test_ha_extra_warm_white(self) -> None:
        rgb = resolve_color("warm_white")
        assert rgb is not None and len(rgb) == 3

    def test_case_insensitive(self) -> None:
        assert resolve_color("RED") == resolve_color("red")
        assert resolve_color("Eggshell") == resolve_color("eggshell")

    def test_space_dash_underscore_equivalence(self) -> None:
        a = resolve_color("warm white")
        b = resolve_color("warm-white")
        c = resolve_color("warm_white")
        assert a is not None
        assert a == b == c

    def test_unknown_color(self) -> None:
        assert resolve_color("not_a_real_color_xyz") is None

    def test_empty_string(self) -> None:
        assert resolve_color("") is None

    def test_whitespace_stripped(self) -> None:
        assert resolve_color("  red  ") == (255, 0, 0)

    def test_palette_is_substantial(self) -> None:
        # Should comfortably exceed 1000 once CSS4 + XKCD + HA extras are merged.
        assert palette_size() > 900
