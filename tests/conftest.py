"""Shared pytest fixtures for ha_workflow tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Where the Keychain token store looks for `security` during tests: a path
# that cannot exist, so no test can ever read or write the real Keychain.
_DISABLED_SECURITY_BIN = "/nonexistent/security-disabled-in-tests"
_DISABLED_OSASCRIPT_BIN = "/nonexistent/osascript-disabled-in-tests"


@pytest.fixture()
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture(autouse=True)
def _no_real_keychain(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    """Isolate every test from the real Keychain and the owner's server state.

    * ``security`` resolves to a path that does not exist.
    * ``HA_SERVER`` and Alfred's dir variables are cleared.
    * ``HOME`` points at a scratch dir, so the dev-fallback data dir
      (``~/.cache/ha-workflow``) — and any ``profiles.json`` /
      ``active_server`` in it — is never read.
    """
    import ha_lib.keychain
    import ha_lib.prompter
    import ha_workflow.keychain

    for mod in (ha_lib.keychain, ha_workflow.keychain):
        monkeypatch.setattr(mod, "SECURITY_BIN", _DISABLED_SECURITY_BIN)
    # No test may pop a real dialog either.
    monkeypatch.setattr(ha_lib.prompter, "OSASCRIPT_BIN", _DISABLED_OSASCRIPT_BIN)
    for var in ("HA_SERVER", "alfred_workflow_cache", "alfred_workflow_data"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    yield
