"""Smoke test to verify the package is importable."""

from ha_workflow import __version__


def test_version() -> None:
    assert __version__ == "0.1.0"
