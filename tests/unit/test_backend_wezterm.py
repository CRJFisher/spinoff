"""Tests for spinoff.backends.wezterm — WezTermBackend."""

import json
from unittest.mock import patch, MagicMock

from spinoff.backends.wezterm import WezTermBackend


class TestAvailable:
    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_available(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        backend = WezTermBackend()
        assert backend.available() is True

    @patch("spinoff.backends.wezterm.shutil.which", return_value=None)
    def test_no_binary(self, mock_which: MagicMock) -> None:
        backend = WezTermBackend()
        assert backend.available() is False

    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_not_running(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1)
        backend = WezTermBackend()
        assert backend.available() is False


class TestWorkspaceExists:
    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_exists(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        avail_result = MagicMock(returncode=0)
        panes_data = [{"pane_id": 42}, {"pane_id": 99}]
        list_result = MagicMock(returncode=0, stdout=json.dumps(panes_data))
        mock_run.side_effect = [avail_result, list_result]
        backend = WezTermBackend()
        assert backend.workspace_exists("42") is True

    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_not_exists(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        avail_result = MagicMock(returncode=0)
        panes_data = [{"pane_id": 99}]
        list_result = MagicMock(returncode=0, stdout=json.dumps(panes_data))
        mock_run.side_effect = [avail_result, list_result]
        backend = WezTermBackend()
        assert backend.workspace_exists("42") is False


class TestCloseWorkspace:
    @patch("spinoff.backends.wezterm.shutil.which", return_value=None)
    def test_not_available(self, mock_which: MagicMock) -> None:
        backend = WezTermBackend()
        success, msg = backend.close_workspace("42")
        assert success is False

    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_already_closed(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        avail_result = MagicMock(returncode=0)
        kill_result = MagicMock(returncode=1, stderr="no pane with id")
        mock_run.side_effect = [avail_result, kill_result]
        backend = WezTermBackend()
        success, msg = backend.close_workspace("42")
        assert success is True
        assert "already" in msg.lower()

    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_success(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        avail_result = MagicMock(returncode=0)
        kill_result = MagicMock(returncode=0, stderr="")
        mock_run.side_effect = [avail_result, kill_result]
        backend = WezTermBackend()
        success, msg = backend.close_workspace("42")
        assert success is True


class TestListWorkspaces:
    @patch("spinoff.backends.wezterm.shutil.which", return_value=None)
    def test_empty_when_unavailable(self, mock_which: MagicMock) -> None:
        backend = WezTermBackend()
        assert backend.list_workspaces() == []

    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_json_parse_normalized(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        avail_result = MagicMock(returncode=0)
        panes_data = [{"pane_id": 1, "title": "test", "cwd": "/tmp", "workspace": "proj"}]
        list_result = MagicMock(returncode=0, stdout=json.dumps(panes_data))
        mock_run.side_effect = [avail_result, list_result]
        backend = WezTermBackend()
        result = backend.list_workspaces()
        assert len(result) == 1
        assert result[0]["terminal_id"] == "1"
        assert result[0]["title"] == "test"
        assert result[0]["workspace"] == "proj"

    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_invalid_json(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        avail_result = MagicMock(returncode=0)
        list_result = MagicMock(returncode=0, stdout="not json")
        mock_run.side_effect = [avail_result, list_result]
        backend = WezTermBackend()
        assert backend.list_workspaces() == []


class TestSetTitle:
    @patch("spinoff.backends.wezterm.shutil.which", return_value=None)
    def test_not_available(self, mock_which: MagicMock) -> None:
        backend = WezTermBackend()
        success, msg = backend.set_title("42", "new title")
        assert success is False

    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_success(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        avail_result = MagicMock(returncode=0)
        title_result = MagicMock(returncode=0, stderr="")
        mock_run.side_effect = [avail_result, title_result]
        backend = WezTermBackend()
        success, msg = backend.set_title("42", "new title")
        assert success is True


class TestFocusWorkspace:
    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_success(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        backend = WezTermBackend()
        success, msg = backend.focus_workspace("42")
        assert success is True

    @patch("spinoff.backends.wezterm.subprocess.run")
    @patch("spinoff.backends.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_failure(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="pane not found")
        backend = WezTermBackend()
        success, msg = backend.focus_workspace("42")
        assert success is False


class TestCmuxOnlyMethodsReturnNoOps:
    def test_read_screen_returns_none(self) -> None:
        assert WezTermBackend().read_screen("42") is None

    def test_send_keys_not_supported(self) -> None:
        success, msg = WezTermBackend().send_keys("42", "enter")
        assert success is False
        assert "not supported" in msg.lower()

    def test_notify_not_supported(self) -> None:
        success, msg = WezTermBackend().notify("title", "body")
        assert success is False

    def test_set_sidebar_status_not_supported(self) -> None:
        success, msg = WezTermBackend().set_sidebar_status("ws-1", "running")
        assert success is False

    def test_set_sidebar_progress_not_supported(self) -> None:
        success, msg = WezTermBackend().set_sidebar_progress("ws-1", 50)
        assert success is False
