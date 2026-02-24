"""E2E tests for error handling."""

import subprocess

import pytest

from .conftest import run_create_worktree, run_merge_worktree


pytestmark = pytest.mark.e2e


class TestErrorCases:
    def test_merge_uncommitted_changes(self, test_project, plugin_root):
        """Merge fails when worktree has uncommitted changes."""
        project = test_project
        run_create_worktree(project, "dirty-wt", plugin_root)

        # Create uncommitted change
        wt = project / ".claude" / "worktrees" / "dirty-wt"
        (wt / "dirty.txt").write_text("uncommitted\n")

        result = run_merge_worktree(project, "dirty-wt", plugin_root)
        assert result.returncode != 0
        assert "uncommitted" in result.stdout.lower()

    def test_merge_nonexistent_target(self, test_project, plugin_root):
        """Merge fails when target branch doesn't exist."""
        project = test_project
        run_create_worktree(project, "bad-target", plugin_root)

        # Make a commit so it passes the uncommitted check
        wt = project / ".claude" / "worktrees" / "bad-target"
        (wt / "file.txt").write_text("content\n")
        subprocess.run(["git", "add", "."], cwd=wt, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "work"], cwd=wt, check=True, capture_output=True)

        result = run_merge_worktree(
            project, "bad-target", plugin_root, target="nonexistent-branch",
        )
        assert result.returncode != 0
        assert "does not exist" in result.stdout.lower()

    def test_create_duplicate_name(self, test_project, plugin_root):
        """Creating a worktree with an existing name fails."""
        r1 = run_create_worktree(test_project, "dup-test", plugin_root)
        assert r1.returncode == 0, r1.stderr

        r2 = run_create_worktree(test_project, "dup-test", plugin_root)
        assert r2.returncode != 0

    def test_merge_nonexistent_worktree(self, test_project, plugin_root):
        """Merging a worktree that doesn't exist fails."""
        result = run_merge_worktree(test_project, "ghost", plugin_root)
        assert result.returncode != 0
        assert "not found" in result.stdout.lower()
