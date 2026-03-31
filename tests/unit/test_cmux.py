"""Tests for spinoff.cmux module functions."""

import json
from unittest.mock import patch, MagicMock

import spinoff.cmux as cmux


class TestGetWindowId:
    @patch("spinoff.cmux.subprocess.run")
    def test_returns_window_id(self, mock_run: MagicMock) -> None:
        identify_json = json.dumps({"caller": {"window_id": "win-abc"}, "focused": {}})
        mock_run.return_value = MagicMock(returncode=0, stdout=identify_json)
        assert cmux.get_window_id() == "win-abc"

    @patch("spinoff.cmux.subprocess.run")
    def test_returns_none_on_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert cmux.get_window_id() is None

    @patch("spinoff.cmux.subprocess.run")
    def test_returns_none_when_caller_null(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"caller": None}))
        assert cmux.get_window_id() is None

    @patch("spinoff.cmux.subprocess.run")
    def test_returns_none_on_malformed_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        assert cmux.get_window_id() is None

    @patch("spinoff.cmux.subprocess.run")
    def test_returns_none_when_caller_missing_window_id(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"caller": {}}))
        assert cmux.get_window_id() is None


class TestAvailable:
    @patch("spinoff.cmux.subprocess.run")
    @patch("spinoff.cmux.shutil.which", return_value="/usr/local/bin/cmux")
    def test_available(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        assert cmux.available() is True

    @patch("spinoff.cmux.shutil.which", return_value=None)
    def test_no_binary(self, mock_which: MagicMock) -> None:
        assert cmux.available() is False

    @patch("spinoff.cmux.subprocess.run")
    @patch("spinoff.cmux.shutil.which", return_value="/usr/local/bin/cmux")
    def test_ping_fails(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1)
        assert cmux.available() is False


class TestCloseWorkspace:
    @patch("spinoff.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = cmux.close_workspace("surface-uuid")
        assert success is True

    @patch("spinoff.cmux.subprocess.run")
    def test_already_closed(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="not found")
        success, msg = cmux.close_workspace("gone-id")
        assert success is True
        assert "already" in msg.lower()

    @patch("spinoff.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="internal error")
        success, msg = cmux.close_workspace("bad-id")
        assert success is False


class TestSetTitle:
    @patch("spinoff.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = cmux.set_title("ws-1", "new title")
        assert success is True

    @patch("spinoff.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="workspace not found")
        success, msg = cmux.set_title("ws-bad", "title")
        assert success is False


class TestFocusWorkspace:
    @patch("spinoff.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = cmux.focus_workspace("ws-1")
        assert success is True

    @patch("spinoff.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="not found")
        success, msg = cmux.focus_workspace("ws-bad")
        assert success is False


class TestListWorkspaces:
    @patch("spinoff.cmux.subprocess.run")
    def test_returns_normalized_workspaces(self, mock_run: MagicMock) -> None:
        raw_workspaces = [
            {"id": "ws-1", "title": "fix-auth", "selected": True, "current_directory": "/tmp"},
            {"id": "ws-2", "title": "overview", "selected": False, "current_directory": "/home"},
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(raw_workspaces))
        result = cmux.list_workspaces()
        assert len(result) == 2
        assert result[0]["terminal_id"] == "ws-1"
        assert result[0]["title"] == "fix-auth"
        assert result[0]["selected"] is True
        assert result[1]["terminal_id"] == "ws-2"
        assert result[1]["selected"] is False

    @patch("spinoff.cmux.subprocess.run")
    def test_empty_on_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert cmux.list_workspaces() == []

    @patch("spinoff.cmux.subprocess.run")
    def test_invalid_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        assert cmux.list_workspaces() == []

    @patch("spinoff.cmux.subprocess.run")
    def test_passes_window_id(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        cmux.list_workspaces(window_id="win-123")
        call_args = mock_run.call_args[0][0]
        assert "--window" in call_args
        assert "win-123" in call_args

    @patch("spinoff.cmux.subprocess.run")
    def test_no_window_flag_when_none(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        cmux.list_workspaces()
        call_args = mock_run.call_args[0][0]
        assert "--window" not in call_args


class TestWorkspaceExists:
    @patch("spinoff.cmux.subprocess.run")
    def test_exists(self, mock_run: MagicMock) -> None:
        raw = [{"id": "ws-1", "title": "a"}, {"id": "ws-2", "title": "b"}]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(raw))
        assert cmux.workspace_exists("ws-1") is True

    @patch("spinoff.cmux.subprocess.run")
    def test_not_exists(self, mock_run: MagicMock) -> None:
        raw = [{"id": "ws-2", "title": "b"}]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(raw))
        assert cmux.workspace_exists("ws-99") is False


class TestReadScreen:
    @patch("spinoff.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="terminal content")
        result = cmux.read_screen("surface-1")
        assert result == "terminal content"

    @patch("spinoff.cmux.subprocess.run")
    def test_with_scrollback(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="scrollback content")
        result = cmux.read_screen("surface-1", scrollback=True)
        assert result == "scrollback content"
        mock_run.assert_called_once_with(
            ["cmux", "read-screen", "--surface", "surface-1", "--scrollback"],
            capture_output=True, text=True, check=False,
        )

    @patch("spinoff.cmux.subprocess.run")
    def test_failure_returns_none(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert cmux.read_screen("bad-surface") is None


class TestSendKeys:
    @patch("spinoff.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = cmux.send_keys("surface-1", "enter")
        assert success is True

    @patch("spinoff.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="surface not found")
        success, msg = cmux.send_keys("bad-surface", "enter")
        assert success is False


class TestNotify:
    @patch("spinoff.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = cmux.notify("Build Done", "All tests passed")
        assert success is True

    @patch("spinoff.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        success, msg = cmux.notify("title", "body")
        assert success is False


class TestCreateWorkspace:
    @patch("spinoff.cmux.subprocess.run")
    def test_passes_window_id(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout='{"id":"ws-new"}', stderr="")
        cmux.create_workspace(title="test", cwd=None, command=None, window_id="win-123")
        first_call_args = mock_run.call_args_list[0][0][0]
        assert "--window" in first_call_args
        assert "win-123" in first_call_args

    @patch("spinoff.cmux.subprocess.run")
    def test_no_window_flag_when_none(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout='{"id":"ws-new"}', stderr="")
        cmux.create_workspace(title="test", cwd=None, command=None)
        first_call_args = mock_run.call_args_list[0][0][0]
        assert "--window" not in first_call_args


class TestFindWorkspaceByTitle:
    @patch("spinoff.cmux.subprocess.run")
    def test_found(self, mock_run: MagicMock) -> None:
        raw = [
            {"id": "ws-1", "title": "myapp: Overview", "selected": False, "current_directory": "/tmp"},
            {"id": "ws-2", "title": "myapp: fix-auth", "selected": True, "current_directory": "/tmp"},
        ]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(raw))
        result = cmux.find_workspace_by_title("myapp: Overview")
        assert result == "ws-1"

    @patch("spinoff.cmux.subprocess.run")
    def test_not_found(self, mock_run: MagicMock) -> None:
        raw = [{"id": "ws-2", "title": "myapp: fix-auth", "selected": True, "current_directory": "/tmp"}]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(raw))
        result = cmux.find_workspace_by_title("myapp: Overview")
        assert result is None

    @patch("spinoff.cmux.subprocess.run")
    def test_passes_window_id(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        cmux.find_workspace_by_title("title", window_id="win-42")
        call_args = mock_run.call_args[0][0]
        assert "--window" in call_args
        assert "win-42" in call_args


class TestReorderWorkspace:
    @patch("spinoff.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = cmux.reorder_workspace("ws-1", 0)
        assert success is True
        call_args = mock_run.call_args[0][0]
        assert "rpc" in call_args
        assert "workspace.reorder" in call_args
        payload = json.loads(call_args[-1])
        assert payload == {"workspace_id": "ws-1", "index": 0}

    @patch("spinoff.cmux.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        success, msg = cmux.reorder_workspace("ws-bad", 0)
        assert success is False


class TestSetSidebarStatus:
    @patch("spinoff.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = cmux.set_sidebar_status("ws-1", "running")
        assert success is True


class TestSetSidebarProgress:
    @patch("spinoff.cmux.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        success, msg = cmux.set_sidebar_progress("ws-1", 75)
        assert success is True
