"""Tests for spinoff.backends.cmux — CmuxBackend."""

import json
from unittest.mock import patch, MagicMock

from spinoff.backends.cmux import CmuxBackend


class TestAvailable:
    @patch("spinoff.backends.cmux.subprocess.run")
    @patch("spinoff.backends.cmux.shutil.which", return_value="/usr/local/bin/cmux")
    def test_available(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        assert CmuxBackend().available() is True

    @patch("spinoff.backends.cmux.shutil.which", return_value=None)
    def test_no_binary(self, mock_which: MagicMock) -> None:
        assert CmuxBackend().available() is False

    @patch("spinoff.backends.cmux.subprocess.run")
    @patch("spinoff.backends.cmux.shutil.which", return_value="/usr/local/bin/cmux")
    def test_ping_fails(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1)
        assert CmuxBackend().available() is False


class TestCloseWorkspace:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = CmuxBackend().close_workspace("surface-uuid")
        assert success is True

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_already_closed(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="not found")
        success, msg = CmuxBackend().close_workspace("gone-id")
        assert success is True
        assert "already" in msg.lower()

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="internal error")
        success, msg = CmuxBackend().close_workspace("bad-id")
        assert success is False


class TestSetTitle:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = CmuxBackend().set_title("ws-1", "new title")
        assert success is True

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="workspace not found")
        success, msg = CmuxBackend().set_title("ws-bad", "title")
        assert success is False


class TestFocusWorkspace:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = CmuxBackend().focus_workspace("ws-1")
        assert success is True

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="not found")
        success, msg = CmuxBackend().focus_workspace("ws-bad")
        assert success is False


class TestListWorkspaces:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_returns_normalized_workspaces(self, mock_run: MagicMock) -> None:
        raw_workspaces = [
            {"id": "ws-1", "title": "fix-auth", "selected": True, "current_directory": "/tmp"},
            {"id": "ws-2", "title": "overview", "selected": False, "current_directory": "/home"},
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(raw_workspaces))
        result = CmuxBackend().list_workspaces()
        assert len(result) == 2
        assert result[0]["terminal_id"] == "ws-1"
        assert result[0]["title"] == "fix-auth"
        assert result[1]["terminal_id"] == "ws-2"

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_empty_on_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert CmuxBackend().list_workspaces() == []

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_invalid_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        assert CmuxBackend().list_workspaces() == []


class TestWorkspaceExists:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_exists(self, mock_run: MagicMock) -> None:
        raw = [{"id": "ws-1", "title": "a"}, {"id": "ws-2", "title": "b"}]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(raw))
        assert CmuxBackend().workspace_exists("ws-1") is True

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_not_exists(self, mock_run: MagicMock) -> None:
        raw = [{"id": "ws-2", "title": "b"}]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(raw))
        assert CmuxBackend().workspace_exists("ws-99") is False


class TestReadScreen:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="terminal content")
        result = CmuxBackend().read_screen("surface-1")
        assert result == "terminal content"

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_with_scrollback(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="scrollback content")
        result = CmuxBackend().read_screen("surface-1", scrollback=True)
        assert result == "scrollback content"
        mock_run.assert_called_once_with(
            ["cmux", "read-screen", "--surface", "surface-1", "--scrollback"],
            capture_output=True, text=True, check=False,
        )

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_failure_returns_none(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert CmuxBackend().read_screen("bad-surface") is None


class TestSendKeys:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = CmuxBackend().send_keys("surface-1", "enter")
        assert success is True

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="surface not found")
        success, msg = CmuxBackend().send_keys("bad-surface", "enter")
        assert success is False


class TestNotify:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = CmuxBackend().notify("Build Done", "All tests passed")
        assert success is True

    @patch("spinoff.backends.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        success, msg = CmuxBackend().notify("title", "body")
        assert success is False


class TestSetSidebarStatus:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = CmuxBackend().set_sidebar_status("ws-1", "running")
        assert success is True


class TestSetSidebarProgress:
    @patch("spinoff.backends.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = CmuxBackend().set_sidebar_progress("ws-1", 75)
        assert success is True
