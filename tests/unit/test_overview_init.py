"""Tests for spinoff.overview.__init__."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spinoff.config import SpinoffConfig
from spinoff.overview import close_overview, ensure_cache_dir, open_overview
from spinoff.state import OverviewInfo, WorktreeState, load_state, save_state


class TestEnsureCacheDir:
    def test_creates_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        result = ensure_cache_dir("my-project")
        assert result.exists()
        assert result == tmp_path / "cache" / "spinoff" / "my-project"

    def test_xdg_cache_home_used(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        custom_cache = tmp_path / "custom-cache"
        monkeypatch.setenv("XDG_CACHE_HOME", str(custom_cache))
        result = ensure_cache_dir("proj")
        assert str(result).startswith(str(custom_cache))

    def test_sanitizes_path_traversal(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        result = ensure_cache_dir("../../../tmp/evil")
        assert ".." not in result.name
        assert result.exists()

    def test_sanitizes_slashes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        result = ensure_cache_dir("org/repo")
        assert "/" not in result.name
        assert result.exists()

    def test_idempotent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        r1 = ensure_cache_dir("proj")
        r2 = ensure_cache_dir("proj")
        assert r1 == r2


class TestOpenOverview:
    @patch("spinoff.overview.cmux")
    def test_returns_false_when_cmux_unavailable(self, mock_cmux: MagicMock, tmp_path: Path) -> None:
        mock_cmux.available.return_value = False
        config = SpinoffConfig(project_name="test")
        ok, msg = open_overview(tmp_path, config=config)
        assert not ok
        assert "cmux not available" in msg

    @patch("spinoff.overview.cmux")
    def test_focuses_existing_overview(self, mock_cmux: MagicMock, tmp_path: Path) -> None:
        mock_cmux.available.return_value = True
        mock_cmux.workspace_exists.return_value = True
        mock_cmux.focus_workspace.return_value = (True, "ok")

        state = WorktreeState(overview=OverviewInfo(workspace_id="ws-1", surface_id="ws-1"))
        save_state(tmp_path, state)

        config = SpinoffConfig(project_name="test")
        ok, msg = open_overview(tmp_path, config=config)
        assert ok
        assert "focused" in msg.lower()
        mock_cmux.focus_workspace.assert_called_once_with("ws-1")

    @patch("spinoff.overview.cmux")
    def test_creates_new_workspace(self, mock_cmux: MagicMock, tmp_path: Path) -> None:
        mock_cmux.available.return_value = True
        mock_cmux.create_workspace.return_value = (True, "ws-new", "ok")

        config = SpinoffConfig(project_name="test")
        ok, msg = open_overview(tmp_path, config=config)
        assert ok
        assert "ws-new" in msg

        reloaded = load_state(tmp_path)
        assert reloaded.overview is not None
        assert reloaded.overview.workspace_id == "ws-new"

    @patch("spinoff.overview.cmux")
    def test_returns_false_on_create_failure(self, mock_cmux: MagicMock, tmp_path: Path) -> None:
        mock_cmux.available.return_value = True
        mock_cmux.create_workspace.return_value = (False, None, "cmux error")

        config = SpinoffConfig(project_name="test")
        ok, msg = open_overview(tmp_path, config=config)
        assert not ok
        assert "Failed" in msg

    @patch("spinoff.overview.cmux")
    def test_uses_passed_config(self, mock_cmux: MagicMock, tmp_path: Path) -> None:
        mock_cmux.available.return_value = True
        mock_cmux.create_workspace.return_value = (True, "ws-1", "ok")

        config = SpinoffConfig(project_name="my-app")
        open_overview(tmp_path, config=config)

        call_kwargs = mock_cmux.create_workspace.call_args
        assert "my-app" in call_kwargs.kwargs.get("title", "") or "my-app" in str(call_kwargs)


class TestCloseOverview:
    @patch("spinoff.overview.cmux")
    def test_noop_when_not_running(self, mock_cmux: MagicMock, tmp_path: Path) -> None:
        save_state(tmp_path, WorktreeState())
        ok, msg = close_overview(tmp_path)
        assert ok
        assert "not running" in msg.lower()

    @patch("spinoff.overview.cmux")
    def test_closes_and_clears_state(self, mock_cmux: MagicMock, tmp_path: Path) -> None:
        mock_cmux.close_workspace.return_value = (True, "ok")
        state = WorktreeState(overview=OverviewInfo(workspace_id="ws-1", surface_id="ws-1"))
        save_state(tmp_path, state)

        ok, msg = close_overview(tmp_path)
        assert ok
        assert "closed" in msg.lower()
        mock_cmux.close_workspace.assert_called_once_with("ws-1")

        reloaded = load_state(tmp_path)
        assert reloaded.overview is None

    @patch("spinoff.overview.cmux")
    def test_clears_state_even_on_close_failure(self, mock_cmux: MagicMock, tmp_path: Path) -> None:
        mock_cmux.close_workspace.return_value = (False, "workspace not found")
        state = WorktreeState(overview=OverviewInfo(workspace_id="ws-1", surface_id="ws-1"))
        save_state(tmp_path, state)

        ok, msg = close_overview(tmp_path)
        assert not ok
        assert "failed" in msg.lower()

        reloaded = load_state(tmp_path)
        assert reloaded.overview is None
