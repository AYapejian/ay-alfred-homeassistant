"""Tests for ha_workflow.errors."""

from __future__ import annotations

import json

from ha_workflow.errors import (
    ConfigError,
    HAAuthError,
    HAConnectionError,
    HAWorkflowError,
    handle_error,
)


class TestExceptionHierarchy:
    def test_config_error_is_workflow_error(self) -> None:
        assert issubclass(ConfigError, HAWorkflowError)

    def test_connection_error_is_workflow_error(self) -> None:
        assert issubclass(HAConnectionError, HAWorkflowError)

    def test_auth_error_is_workflow_error(self) -> None:
        assert issubclass(HAAuthError, HAWorkflowError)


class TestHandleError:
    def _capture(self, exc: BaseException, capsys: object) -> dict[str, object]:
        # capsys typed loosely to satisfy mypy without pytest stubs
        handle_error(exc)

        out = capsys.readouterr().out
        return json.loads(out)  # type: ignore[no-any-return]

    def test_config_error_output(self, capsys: object) -> None:
        data = self._capture(ConfigError("bad token"), capsys)
        assert len(data["items"]) == 1  # type: ignore[arg-type]
        item = data["items"][0]  # type: ignore[index]
        assert item["title"] == "Configuration Error"
        assert "bad token" in item["subtitle"]
        assert item["valid"] is False

    def test_auth_error_output(self, capsys: object) -> None:
        data = self._capture(HAAuthError(), capsys)
        assert data["items"][0]["title"] == "Authentication Failed"  # type: ignore[index]

    def test_connection_error_output(self, capsys: object) -> None:
        data = self._capture(HAConnectionError("timeout"), capsys)
        assert data["items"][0]["title"] == "Connection Error"  # type: ignore[index]

    def test_generic_error_output(self, capsys: object) -> None:
        data = self._capture(RuntimeError("boom"), capsys)
        assert data["items"][0]["title"] == "Unexpected Error"  # type: ignore[index]
