"""Tests for spinoff.wezterm."""

import json
from unittest.mock import patch, MagicMock

import pytest

from spinoff.wezterm import (
    wezterm_available,
    ensure_wezterm_running,
    pane_exists,
    close_tab,
    list_panes,
    get_project_window_id,
)


class TestWeztermAvailable:
    @patch("spinoff.wezterm.subprocess.run")
    @patch("spinoff.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_available(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert wezterm_available() is True

    @patch("spinoff.wezterm.shutil.which", return_value=None)
    def test_no_binary(self, mock_which):
        assert wezterm_available() is False

    @patch("spinoff.wezterm.subprocess.run")
    @patch("spinoff.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_not_running(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert wezterm_available() is False


class TestEnsureWeztermRunning:
    @patch("spinoff.wezterm.shutil.which", return_value="/usr/local/bin/wezterm")
    def test_true(self, mock_which):
        assert ensure_wezterm_running() is True

    @patch("spinoff.wezterm.shutil.which", return_value=None)
    def test_false(self, mock_which):
        assert ensure_wezterm_running() is False


class TestPaneExists:
    @patch("spinoff.wezterm.list_panes")
    def test_exists(self, mock_list):
        mock_list.return_value = [{"pane_id": 42}, {"pane_id": 99}]
        assert pane_exists("42") is True

    @patch("spinoff.wezterm.list_panes")
    def test_not_exists(self, mock_list):
        mock_list.return_value = [{"pane_id": 99}]
        assert pane_exists("42") is False


class TestCloseTab:
    @patch("spinoff.wezterm.wezterm_available", return_value=False)
    def test_wezterm_not_available(self, mock_avail):
        success, msg = close_tab("42")
        assert success is False
        assert "not running" in msg.lower() or "not available" in msg.lower()

    @patch("spinoff.wezterm.subprocess.run")
    @patch("spinoff.wezterm.wezterm_available", return_value=True)
    def test_already_closed(self, mock_avail, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="no pane with id")
        success, msg = close_tab("42")
        assert success is True
        assert "already closed" in msg.lower()


class TestListPanes:
    @patch("spinoff.wezterm.wezterm_available", return_value=False)
    def test_empty_when_unavailable(self, mock_avail):
        assert list_panes() == []

    @patch("spinoff.wezterm.subprocess.run")
    @patch("spinoff.wezterm.wezterm_available", return_value=True)
    def test_json_parse(self, mock_avail, mock_run):
        panes_data = [{"pane_id": 1, "title": "test"}]
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(panes_data)
        )
        result = list_panes()
        assert result == panes_data

    @patch("spinoff.wezterm.subprocess.run")
    @patch("spinoff.wezterm.wezterm_available", return_value=True)
    def test_invalid_json(self, mock_avail, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        assert list_panes() == []


class TestGetProjectWindowId:
    @patch("spinoff.wezterm.subprocess.run")
    def test_found(self, mock_run):
        panes = [{"workspace": "my-project", "window_id": 7}]
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(panes)
        )
        assert get_project_window_id("my-project") == "7"

    @patch("spinoff.wezterm.subprocess.run")
    def test_not_found(self, mock_run):
        panes = [{"workspace": "other", "window_id": 7}]
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(panes)
        )
        assert get_project_window_id("my-project") is None
