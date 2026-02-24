"""E2E tests for merge strategies."""

import subprocess

import pytest

from spinoff.state import load_state

from .conftest import run_create_worktree, run_merge_worktree


pytestmark = pytest.mark.e2e


def _make_commit_in_worktree(project, name):
    """Helper to make a commit in a worktree."""
    wt = project / ".claude" / "worktrees" / name
    (wt / f"{name}.txt").write_text(f"content for {name}\n")
    subprocess.run(["git", "add", "."], cwd=wt, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"Work on {name}"], cwd=wt, check=True,
                    capture_output=True)


class TestMergeStrategies:
    def test_default_merge(self, test_project, plugin_root):
        """Default merge creates a merge commit with --no-ff."""
        project = test_project
        run_create_worktree(project, "merge-default", plugin_root)
        _make_commit_in_worktree(project, "merge-default")

        result = run_merge_worktree(project, "merge-default", plugin_root)
        assert result.returncode == 0, result.stdout + result.stderr

        # Check for merge commit
        log = subprocess.run(
            ["git", "log", "--oneline", "-5"], cwd=project,
            capture_output=True, text=True,
        ).stdout
        assert "Merge worktree: merge-default" in log

    def test_squash_merge(self, test_project, plugin_root):
        """Squash merge creates a single commit."""
        project = test_project
        run_create_worktree(project, "merge-squash", plugin_root)
        _make_commit_in_worktree(project, "merge-squash")

        result = run_merge_worktree(
            project, "merge-squash", plugin_root, strategy="squash",
        )
        assert result.returncode == 0, result.stdout + result.stderr

        log = subprocess.run(
            ["git", "log", "--oneline", "-5"], cwd=project,
            capture_output=True, text=True,
        ).stdout
        assert "Complete: merge-squash" in log

    def test_rebase_merge(self, test_project, plugin_root):
        """Rebase produces linear history."""
        project = test_project
        run_create_worktree(project, "merge-rebase", plugin_root)
        _make_commit_in_worktree(project, "merge-rebase")

        result = run_merge_worktree(
            project, "merge-rebase", plugin_root, strategy="rebase",
        )
        assert result.returncode == 0, result.stdout + result.stderr

        # Verify linear history (no merge commits)
        log = subprocess.run(
            ["git", "log", "--oneline", "--merges", "-5"], cwd=project,
            capture_output=True, text=True,
        ).stdout
        assert "Merge" not in log

    def test_keep_branch(self, test_project, plugin_root):
        """--keep-branch preserves branch after merge."""
        project = test_project
        run_create_worktree(project, "merge-keep", plugin_root)
        _make_commit_in_worktree(project, "merge-keep")

        result = run_merge_worktree(
            project, "merge-keep", plugin_root, keep_branch=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

        # Branch should still exist
        branches = subprocess.run(
            ["git", "branch"], cwd=project, capture_output=True, text=True,
        ).stdout
        assert "worktree/merge-keep" in branches
