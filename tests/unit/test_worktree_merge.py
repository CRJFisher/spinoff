"""Tests for worktree_merge.py."""

from unittest.mock import patch, MagicMock

import pytest

from worktree_merge import MergeResult, merge_worktree


class TestMergeResultStr:
    def test_no_warnings(self):
        r = MergeResult(success=True, message="Merged OK", warnings=[])
        assert str(r) == "Merged OK"

    def test_one_warning(self):
        r = MergeResult(success=True, message="Merged OK", warnings=["pane gone"])
        s = str(r)
        assert "Merged OK" in s
        assert "Warnings:" in s
        assert "pane gone" in s

    def test_multiple_warnings(self):
        r = MergeResult(success=True, message="Done", warnings=["w1", "w2"])
        s = str(r)
        assert "w1" in s
        assert "w2" in s
        assert s.count("  - ") == 2


class TestMergeWorktree:
    @patch("worktree_merge.load_config")
    def test_missing_worktree_dir(self, mock_load_config, tmp_path):
        mock_config = MagicMock()
        mock_config.worktree_dir = ".worktrees"
        mock_load_config.return_value = mock_config

        result = merge_worktree("nonexistent", project_path=tmp_path)
        assert result.success is False
        assert "not found" in result.message

    @patch("worktree_merge.load_config")
    def test_unknown_strategy(self, mock_load_config, tmp_path):
        mock_config = MagicMock()
        mock_config.worktree_dir = ".worktrees"
        mock_load_config.return_value = mock_config

        # Create the worktree dir so it passes the exists check
        wt_dir = tmp_path / ".worktrees" / "test-wt"
        wt_dir.mkdir(parents=True)

        # Mock load_state and has_uncommitted_changes and target branch check
        with patch("worktree_merge.load_state") as mock_state, \
             patch("worktree_merge.has_uncommitted_changes", return_value=(False, "")), \
             patch("worktree_merge.subprocess") as mock_subprocess:
            mock_state.return_value = MagicMock(find=MagicMock(return_value=None))
            # Target branch validation passes
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_subprocess.run.return_value = mock_result

            result = merge_worktree("test-wt", strategy="invalid", project_path=tmp_path)
            assert result.success is False
            assert "Unknown merge strategy" in result.message
