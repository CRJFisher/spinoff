"""Tests for spinoff.overview.actions."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from spinoff.config import SpinoffConfig
from spinoff.state import WorktreeEntry, WorktreeState

from spinoff.overview.actions import (
    ActionRequest,
    consume_action,
    dispatch_action,
    poll_and_dispatch_action,
    read_action,
    validate_action,
)


@pytest.fixture
def state_with_agents() -> WorktreeState:
    return WorktreeState(worktrees=[
        WorktreeEntry(name="a", path="p/a", branch="b/a", terminal_id="s1"),
        WorktreeEntry(name="b", path="p/b", branch="b/b", terminal_id="s2"),
    ])


@pytest.fixture
def config() -> SpinoffConfig:
    return SpinoffConfig(project_name="test")


class TestReadAction:
    def test_reads_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "action.json"
        p.write_text(json.dumps({
            "action": "approve", "surface_id": "s1", "timestamp": time.time(),
        }))
        req = read_action(p)
        assert req is not None
        assert req.action == "approve"
        assert req.surface_id == "s1"

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.json"
        assert read_action(p) is None

    def test_returns_none_for_invalid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("not json{")
        assert read_action(p) is None

    def test_returns_none_for_missing_fields(self, tmp_path: Path) -> None:
        p = tmp_path / "partial.json"
        p.write_text(json.dumps({"action": "approve"}))
        assert read_action(p) is None


class TestValidateAction:
    def test_valid_action_accepted(self) -> None:
        req = ActionRequest("approve", "s1", time.time())
        ok, _ = validate_action(req, frozenset({"s1", "s2"}))
        assert ok

    def test_unknown_action_rejected(self) -> None:
        req = ActionRequest("hack", "s1", time.time())
        ok, reason = validate_action(req, frozenset({"s1"}))
        assert not ok
        assert "Unknown action" in reason

    def test_unknown_surface_rejected(self) -> None:
        req = ActionRequest("approve", "s99", time.time())
        ok, reason = validate_action(req, frozenset({"s1"}))
        assert not ok
        assert "Unknown surface" in reason

    def test_stale_action_rejected(self) -> None:
        req = ActionRequest("approve", "s1", time.time() - 60)
        ok, reason = validate_action(req, frozenset({"s1"}))
        assert not ok
        assert "Stale" in reason

    def test_approve_all_bypasses_surface_check(self) -> None:
        req = ActionRequest("approve_all", "", time.time())
        ok, _ = validate_action(req, frozenset({"s1"}))
        assert ok


class TestConsumeAction:
    def test_deletes_file(self, tmp_path: Path) -> None:
        p = tmp_path / "action.json"
        p.write_text("{}")
        consume_action(p)
        assert not p.exists()

    def test_idempotent_on_missing(self, tmp_path: Path) -> None:
        p = tmp_path / "missing.json"
        consume_action(p)  # Should not raise


class TestDispatchAction:
    @patch("spinoff.overview.actions.cmux")
    def test_focus_calls_focus_workspace(self, mock_cmux, state_with_agents: WorktreeState) -> None:
        mock_cmux.focus_workspace.return_value = (True, "ok")
        req = ActionRequest("focus", "s1", time.time())
        result = dispatch_action(req, state_with_agents)
        assert result.success
        mock_cmux.focus_workspace.assert_called_once_with("s1")

    @patch("spinoff.overview.actions.cmux")
    def test_approve_with_safe_screen(self, mock_cmux, state_with_agents: WorktreeState) -> None:
        mock_cmux.read_screen.return_value = "Do you want to proceed?\n❯ Yes\n  No\n"
        mock_cmux.send_keys.return_value = (True, "ok")
        req = ActionRequest("approve", "s1", time.time())
        result = dispatch_action(req, state_with_agents)
        assert result.success
        assert mock_cmux.send_keys.call_count == 2
        mock_cmux.send_keys.assert_any_call("s1", "y")
        mock_cmux.send_keys.assert_any_call("s1", "enter")

    @patch("spinoff.overview.actions.cmux")
    def test_approve_surface_unreachable(self, mock_cmux, state_with_agents: WorktreeState) -> None:
        mock_cmux.read_screen.return_value = None
        req = ActionRequest("approve", "s1", time.time())
        result = dispatch_action(req, state_with_agents)
        assert not result.success
        assert "unreachable" in result.message.lower()

    @patch("spinoff.overview.actions.cmux")
    def test_approve_not_waiting(self, mock_cmux, state_with_agents: WorktreeState) -> None:
        # Screen shows working state, not an approval prompt
        mock_cmux.read_screen.return_value = "Claude is working on something...\n⏳ Thinking..."
        req = ActionRequest("approve", "s1", time.time())
        result = dispatch_action(req, state_with_agents)
        assert not result.success
        assert "Not waiting" in result.message

    @patch("spinoff.overview.actions.cmux")
    def test_approve_blocked_by_safety(self, mock_cmux, state_with_agents: WorktreeState) -> None:
        mock_cmux.read_screen.return_value = "git push --force origin main\n❯ Yes\n  No\n"
        req = ActionRequest("approve", "s1", time.time())
        result = dispatch_action(req, state_with_agents)
        assert not result.success
        assert "Blocked" in result.message

    @patch("spinoff.overview.actions.cmux")
    def test_reject_sends_n(self, mock_cmux, state_with_agents: WorktreeState) -> None:
        mock_cmux.send_keys.return_value = (True, "ok")
        req = ActionRequest("reject", "s1", time.time())
        result = dispatch_action(req, state_with_agents)
        assert result.success
        mock_cmux.send_keys.assert_any_call("s1", "n")

    @patch("spinoff.overview.actions.cmux")
    def test_interrupt_sends_ctrl_c(self, mock_cmux, state_with_agents: WorktreeState) -> None:
        mock_cmux.send_keys.return_value = (True, "ok")
        req = ActionRequest("interrupt", "s1", time.time())
        dispatch_action(req, state_with_agents)
        mock_cmux.send_keys.assert_called_once_with("s1", "ctrl-c")

    @patch("spinoff.overview.actions.cmux")
    def test_kill_closes_workspace(self, mock_cmux, state_with_agents: WorktreeState) -> None:
        mock_cmux.close_workspace.return_value = (True, "ok")
        req = ActionRequest("kill", "s1", time.time())
        result = dispatch_action(req, state_with_agents)
        assert result.success
        mock_cmux.close_workspace.assert_called_once_with("s1")


class TestPollAndDispatch:
    def test_no_action_returns_none(self, tmp_path: Path, state_with_agents: WorktreeState) -> None:
        config_copy = SpinoffConfig(project_name="test", worktree_dir=str(tmp_path))
        result = poll_and_dispatch_action(tmp_path, config_copy, state_with_agents)
        assert result is None

    @patch("spinoff.overview.actions.cmux")
    def test_valid_action_dispatched_and_file_consumed(self, mock_cmux, tmp_path: Path, state_with_agents: WorktreeState) -> None:
        mock_cmux.focus_workspace.return_value = (True, "ok")
        project = tmp_path
        wt_dir = project / ".claude" / "worktrees"
        wt_dir.mkdir(parents=True, exist_ok=True)
        actions_file = wt_dir / ".overview-actions.json"
        actions_file.write_text(json.dumps({
            "action": "focus", "surface_id": "s1", "timestamp": time.time(),
        }))
        config = SpinoffConfig(project_name="test", worktree_dir=".claude/worktrees")
        result = poll_and_dispatch_action(project, config, state_with_agents)
        assert result is not None
        assert result.success
        assert not actions_file.exists()
