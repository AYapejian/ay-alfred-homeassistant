"""Tests for ha_workflow.notify."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ha_workflow.notify import (
    _escape_applescript,
    notify,
    notify_background,
    notify_background_error,
    notify_error,
)


class TestEscapeApplescript:
    def test_plain_string(self) -> None:
        assert _escape_applescript("hello") == "hello"

    def test_quotes(self) -> None:
        assert _escape_applescript('say "hi"') == 'say \\"hi\\"'

    def test_backslash(self) -> None:
        assert _escape_applescript("path\\to") == "path\\\\to"

    def test_newline_replaced(self) -> None:
        assert _escape_applescript("line1\nline2") == "line1 line2"


class TestForegroundNotify:
    """Foreground functions write to stdout only — no macOS toast."""

    def test_notify_writes_stdout(self, capsys: object) -> None:
        notify("Toggled light")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert out == "Toggled light\n"

    def test_notify_error_writes_stdout(self, capsys: object) -> None:
        notify_error("Connection failed")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert out == "Connection failed\n"

    @patch("ha_workflow.notify._macos_notification")
    def test_notify_does_not_post_toast(
        self, mock_macos: MagicMock, capsys: object
    ) -> None:
        notify("Toggled light")
        capsys.readouterr()  # type: ignore[union-attr]
        mock_macos.assert_not_called()

    @patch("ha_workflow.notify._macos_notification")
    def test_notify_error_does_not_post_toast(
        self, mock_macos: MagicMock, capsys: object
    ) -> None:
        notify_error("Connection failed")
        capsys.readouterr()  # type: ignore[union-attr]
        mock_macos.assert_not_called()


class TestBackgroundNotify:
    """Background functions post macOS toast only — no stdout."""

    @patch("ha_workflow.notify._macos_notification")
    def test_background_no_stdout(self, mock_macos: MagicMock, capsys: object) -> None:
        notify_background("Cache refreshed")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert out == ""
        mock_macos.assert_called_once()

    @patch("ha_workflow.notify._macos_notification")
    def test_background_error_no_stdout_with_sound(
        self, mock_macos: MagicMock, capsys: object
    ) -> None:
        notify_background_error("Refresh failed")
        out = capsys.readouterr().out  # type: ignore[union-attr]
        assert out == ""
        mock_macos.assert_called_once_with("Refresh failed", subtitle="", sound="Funk")


class TestMacosNotification:
    @patch("ha_workflow.notify.subprocess.Popen")
    def test_posts_osascript(self, mock_popen: MagicMock) -> None:
        from ha_workflow.notify import _macos_notification

        _macos_notification("hello", subtitle="sub", sound="Pop")
        mock_popen.assert_called_once()
        script = mock_popen.call_args[0][0][2]
        assert 'display notification "hello"' in script
        assert 'with title "Home Assistant"' in script
        assert 'subtitle "sub"' in script
        assert 'sound name "Pop"' in script
