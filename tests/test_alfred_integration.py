"""Integration tests — invoke cli.py via subprocess, the way Alfred does.

These tests simulate Alfred's execution model:
  1. Set cwd to the workflow root (the directory containing ha_workflow/)
  2. Run ``/usr/bin/python3 ha_workflow/cli.py <args>``
  3. Parse stdout as Alfred Script Filter JSON

This catches import-path and packaging issues that unit tests miss.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# The "workflow root" in dev is src/, which contains ha_workflow/.
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
CLI_PATH = SRC_DIR / "ha_workflow" / "cli.py"


def _run_cli(
    *args: str,
    env_override: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke cli.py in a subprocess, mimicking Alfred's execution model."""
    env = {
        # Minimal clean env — avoids inheriting HA_URL/HA_TOKEN from dev shell
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    if env_override:
        env.update(env_override)

    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True,
        text=True,
        cwd=str(SRC_DIR),
        env=env,
        timeout=10,
    )


def _parse_output(proc: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """Assert the process succeeded and return parsed JSON."""
    assert proc.returncode == 0, (
        f"cli.py exited {proc.returncode}\nstderr: {proc.stderr}"
    )
    return json.loads(proc.stdout)  # type: ignore[no-any-return]


class TestSubprocessImport:
    """Verify ha_workflow is importable when run the way Alfred does it."""

    def test_no_args_outputs_valid_json(self) -> None:
        proc = _run_cli()
        data = _parse_output(proc)
        assert "items" in data
        assert len(data["items"]) >= 1  # type: ignore[arg-type]

    def test_search_stub(self) -> None:
        data = _parse_output(_run_cli("search", "test"))
        assert "not yet implemented" in data["items"][0]["title"]  # type: ignore[index]

    def test_config_validate_missing_env(self) -> None:
        """Without HA_URL/HA_TOKEN, config validate should output an error item."""
        proc = _run_cli("config", "validate")
        # The top-level error handler catches ConfigError and writes JSON
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        item = data["items"][0]
        assert item["valid"] is False
        assert "HA_URL" in item["subtitle"] or "Configuration" in item["title"]


@pytest.mark.integration
class TestLiveHAConnection:
    """Tests requiring a real HA instance (``HA_URL`` + ``HA_TOKEN`` in env).

    Skipped unless both env vars are set.  Run with::

        HA_URL=... HA_TOKEN=... pytest -m integration
    """

    @pytest.fixture(autouse=True)
    def _require_ha_env(self) -> None:
        if not os.environ.get("HA_URL") or not os.environ.get("HA_TOKEN"):
            pytest.skip("HA_URL and HA_TOKEN not set")

    def _live_env(self) -> dict[str, str]:
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "HA_URL": os.environ["HA_URL"],
            "HA_TOKEN": os.environ["HA_TOKEN"],
        }

    def test_config_validate_live(self) -> None:
        data = _parse_output(
            _run_cli("config", "validate", env_override=self._live_env())
        )
        item = data["items"][0]  # type: ignore[index]
        assert item["title"] == "Connected to Home Assistant"
        assert "v" in item["subtitle"]
