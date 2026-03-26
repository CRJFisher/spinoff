"""Tests for spinoff.overview.actions."""

import json
import time

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
from tests.unit.helpers.backends import SpyBackend


@pytest.fixture
def spy() -> SpyBackend:
    return SpyBackend()


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
    def test_reads_valid_json(self, tmp_path: object) -> None:
        from pathlib import Path
        p = Path(str(tmp_path)) / "action.json"
        p.write_text(json.dumps({
            "action": "approve", "surface_id": "s1", "timestamp": time.time(),
        }))
        req = read_action(p)
        assert req is not None
        assert req.action == "approve"
        assert req.surface_id == "s1"

    def test_returns_none_for_missing_file(self, tmp_path: object) -> None:
        from pathlib import Path
        p = Path(str(tmp_path)) / "missing.json"
        assert read_action(p) is None

    def test_returns_none_for_invalid_json(self, tmp_path: object) -> None:
        from pathlib import Path
        p = Path(str(tmp_path)) / "bad.json"
        p.write_text("not json{")
        assert read_action(p) is None

    def test_returns_none_for_missing_fields(self, tmp_path: object) -> None:
        from pathlib import Path
        p = Path(str(tmp_path)) / "partial.json"
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
    def test_deletes_file(self, tmp_path: object) -> None:
        from pathlib import Path
        p = Path(str(tmp_path)) / "action.json"
        p.write_text("{}")
        consume_action(p)
        assert not p.exists()

    def test_idempotent_on_missing(self, tmp_path: object) -> None:
        from pathlib import Path
        p = Path(str(tmp_path)) / "missing.json"
        consume_action(p)  # Should not raise


class TestDispatchAction:
    def test_focus_calls_focus_workspace(self, spy: SpyBackend, state_with_agents: WorktreeState, config: SpinoffConfig) -> None:
        req = ActionRequest("focus", "s1", time.time())
        result = dispatch_action(req, spy, state_with_agents, None, config)  # type: ignore[arg-type]
        assert result.success
        calls = spy.get_calls("focus_workspace")
        assert len(calls) == 1
        assert calls[0].args == ("s1",)

    def test_approve_with_safe_screen(self, spy: SpyBackend, state_with_agents: WorktreeState, config: SpinoffConfig) -> None:
        spy.set_current_screen("s1", "Do you want to proceed?\n> Yes\n  No\n")
        req = ActionRequest("approve", "s1", time.time())
        result = dispatch_action(req, spy, state_with_agents, None, config)  # type: ignore[arg-type]
        assert result.success
        send_calls = spy.get_calls("send_keys")
        assert len(send_calls) == 2
        assert send_calls[0].args == ("s1", "y")
        assert send_calls[1].args == ("s1", "enter")

    def test_approve_blocked_by_safety(self, spy: SpyBackend, state_with_agents: WorktreeState, config: SpinoffConfig) -> None:
        spy.set_current_screen("s1", "git push --force origin main\n> Yes\n")
        req = ActionRequest("approve", "s1", time.time())
        result = dispatch_action(req, spy, state_with_agents, None, config)  # type: ignore[arg-type]
        assert not result.success
        assert "Blocked" in result.message

    def test_reject_sends_n(self, spy: SpyBackend, state_with_agents: WorktreeState, config: SpinoffConfig) -> None:
        req = ActionRequest("reject", "s1", time.time())
        result = dispatch_action(req, spy, state_with_agents, None, config)  # type: ignore[arg-type]
        assert result.success
        send_calls = spy.get_calls("send_keys")
        assert send_calls[0].args == ("s1", "n")

    def test_interrupt_sends_ctrl_c(self, spy: SpyBackend, state_with_agents: WorktreeState, config: SpinoffConfig) -> None:
        req = ActionRequest("interrupt", "s1", time.time())
        dispatch_action(req, spy, state_with_agents, None, config)  # type: ignore[arg-type]
        send_calls = spy.get_calls("send_keys")
        assert send_calls[0].args == ("s1", "ctrl-c")

    def test_kill_closes_workspace(self, spy: SpyBackend, state_with_agents: WorktreeState, config: SpinoffConfig) -> None:
        req = ActionRequest("kill", "s1", time.time())
        result = dispatch_action(req, spy, state_with_agents, None, config)  # type: ignore[arg-type]
        assert result.success
        assert len(spy.get_calls("close_workspace")) == 1


class TestPollAndDispatch:
    def test_no_action_returns_none(self, tmp_path: object, spy: SpyBackend, state_with_agents: WorktreeState, config: SpinoffConfig) -> None:
        from pathlib import Path
        config_copy = SpinoffConfig(project_name="test", worktree_dir=str(tmp_path))
        result = poll_and_dispatch_action(Path(str(tmp_path)), config_copy, spy, state_with_agents)
        assert result is None

    def test_valid_action_dispatched_and_file_consumed(self, tmp_path: object, spy: SpyBackend, state_with_agents: WorktreeState) -> None:
        from pathlib import Path
        project = Path(str(tmp_path))
        wt_dir = project / ".claude" / "worktrees"
        wt_dir.mkdir(parents=True, exist_ok=True)
        actions_file = wt_dir / ".overview-actions.json"
        actions_file.write_text(json.dumps({
            "action": "focus", "surface_id": "s1", "timestamp": time.time(),
        }))
        config = SpinoffConfig(project_name="test", worktree_dir=".claude/worktrees")
        result = poll_and_dispatch_action(project, config, spy, state_with_agents)
        assert result is not None
        assert result.success
        assert not actions_file.exists()
