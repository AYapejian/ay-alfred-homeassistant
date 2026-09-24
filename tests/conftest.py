"""Shared pytest fixtures for ha_workflow tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Where the Keychain token store looks for `security` during tests: a path
# that cannot exist, so no test can ever read or write the real Keychain.
_DISABLED_SECURITY_BIN = "/nonexistent/security-disabled-in-tests"


@pytest.fixture()
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture(autouse=True)
def _no_real_keychain(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Block the real Keychain and the owner's server selection in every test."""
    import ha_lib.keychain
    import ha_workflow.keychain

    for mod in (ha_lib.keychain, ha_workflow.keychain):
        monkeypatch.setattr(mod, "SECURITY_BIN", _DISABLED_SECURITY_BIN)
    monkeypatch.delenv("HA_SERVER", raising=False)
    yield
