"""Tests for worktree_sandbox.py."""

import json
from unittest.mock import patch

import pytest

from worktree_sandbox import get_claude_command, claude_available, COMMIT_INSTRUCTIONS


class TestGetClaudeCommand:
    def test_implement_mode_no_task(self):
        cmd = get_claude_command(mode="implement")
        assert cmd[0] == "claude"
        assert "--dangerously-skip-permissions" in cmd
        # Find --settings and parse JSON
        idx = cmd.index("--settings")
        settings = json.loads(cmd[idx + 1])
        assert settings["sandbox"]["enabled"] is True
        assert settings["sandbox"]["autoAllowBashIfSandboxed"] is True

    def test_plan_mode_no_task(self):
        cmd = get_claude_command(mode="plan")
        assert cmd == ["claude", "--permission-mode", "plan"]

    def test_implement_mode_with_task(self):
        cmd = get_claude_command(task="fix the bug", mode="implement")
        # Task should have COMMIT_INSTRUCTIONS appended
        assert cmd[-1] == "fix the bug" + COMMIT_INSTRUCTIONS
        assert "--dangerously-skip-permissions" in cmd

    def test_plan_mode_with_task(self):
        cmd = get_claude_command(task="analyze auth", mode="plan")
        assert cmd[-1] == "analyze auth"
        # Should NOT have COMMIT_INSTRUCTIONS
        assert COMMIT_INSTRUCTIONS not in cmd[-1]
        assert "--permission-mode" in cmd
        assert "plan" in cmd

    def test_implement_appends_commit_instructions(self):
        cmd = get_claude_command(task="do stuff", mode="implement")
        assert cmd[-1].endswith(COMMIT_INSTRUCTIONS)

    def test_plan_does_not_append_commit_instructions(self):
        cmd = get_claude_command(task="do stuff", mode="plan")
        assert not cmd[-1].endswith(COMMIT_INSTRUCTIONS)

    def test_settings_json_valid(self):
        cmd = get_claude_command(mode="implement")
        idx = cmd.index("--settings")
        settings = json.loads(cmd[idx + 1])
        assert isinstance(settings, dict)
        assert "sandbox" in settings


class TestModelSelection:
    def test_implement_with_model(self):
        cmd = get_claude_command(mode="implement", model="haiku")
        idx = cmd.index("--settings")
        settings = json.loads(cmd[idx + 1])
        assert settings["model"] == "haiku"
        assert settings["sandbox"]["enabled"] is True

    def test_plan_with_model(self):
        cmd = get_claude_command(mode="plan", model="sonnet")
        assert "--permission-mode" in cmd
        assert "plan" in cmd
        idx = cmd.index("--settings")
        settings = json.loads(cmd[idx + 1])
        assert settings["model"] == "sonnet"

    def test_no_model_default(self):
        cmd = get_claude_command(mode="implement")
        idx = cmd.index("--settings")
        settings = json.loads(cmd[idx + 1])
        assert "model" not in settings

    def test_plan_no_model_no_task_no_settings(self):
        cmd = get_claude_command(mode="plan")
        assert "--settings" not in cmd
        assert cmd == ["claude", "--permission-mode", "plan"]


class TestClaudeAvailable:
    @patch("worktree_sandbox.shutil.which", return_value="/usr/local/bin/claude")
    def test_available(self, mock_which):
        assert claude_available() is True

    @patch("worktree_sandbox.shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert claude_available() is False
