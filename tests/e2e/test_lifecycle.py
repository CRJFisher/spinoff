"""E2E tests for the full spinoff lifecycle."""

import json
import subprocess

import pytest

from worktree_state import load_state

from .conftest import run_create_worktree, run_merge_worktree


pytestmark = pytest.mark.e2e


class TestLifecycle:
    def test_full_cycle(self, test_project, spinoff_scripts):
        """Create → verify state/dir/branch/pane → commit in worktree → merge → verify cleanup."""
        project = test_project

        # Create
        result = run_create_worktree(project, "cycle-test", spinoff_scripts)
        assert result.returncode == 0, result.stderr

        # Verify state
        state = load_state(project)
        entry = state.find("cycle-test")
        assert entry is not None
        assert entry.branch == "worktree/cycle-test"
        assert entry.base_branch == "main"

        # Verify dir and branch exist
        wt_path = project / ".worktrees" / "cycle-test"
        assert wt_path.exists()
        branches = subprocess.run(
            ["git", "branch"], cwd=project, capture_output=True, text=True
        ).stdout
        assert "worktree/cycle-test" in branches

        # Make a commit in the worktree
        (wt_path / "new_file.txt").write_text("hello\n")
        subprocess.run(["git", "add", "new_file.txt"], cwd=wt_path, check=True,
                        capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add new file"], cwd=wt_path, check=True,
                        capture_output=True)

        # Merge
        merge_result = run_merge_worktree(project, "cycle-test", spinoff_scripts)
        assert merge_result.returncode == 0, merge_result.stderr + merge_result.stdout

        # Verify cleanup
        assert not wt_path.exists()
        state = load_state(project)
        assert state.find("cycle-test") is None

        # Verify file made it to main
        assert (project / "new_file.txt").exists()

    def test_create_with_task(self, test_project, spinoff_scripts):
        """Verify startup script contains the task."""
        result = run_create_worktree(
            test_project, "task-test", spinoff_scripts,
            task="fix the auth bug",
        )
        assert result.returncode == 0, result.stderr

        script = test_project / ".worktrees" / "task-test.start.sh"
        assert script.exists()
        content = script.read_text()
        assert "fix the auth bug" in content

    def test_create_plan_mode(self, test_project, spinoff_scripts):
        """Verify plan mode uses --permission-mode plan in startup script."""
        result = run_create_worktree(
            test_project, "plan-test", spinoff_scripts,
            mode="plan",
        )
        assert result.returncode == 0, result.stderr

        script = test_project / ".worktrees" / "plan-test.start.sh"
        content = script.read_text()
        assert "--permission-mode" in content
        assert "plan" in content

    def test_create_with_base(self, test_project, spinoff_scripts):
        """Verify --base stores base_branch and merge targets it."""
        project = test_project

        # Create develop branch
        subprocess.run(["git", "checkout", "-b", "develop"], cwd=project, check=True,
                        capture_output=True)
        (project / "dev.txt").write_text("dev\n")
        subprocess.run(["git", "add", "dev.txt"], cwd=project, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Dev commit"], cwd=project, check=True,
                        capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=project, check=True, capture_output=True)

        result = run_create_worktree(
            project, "base-test", spinoff_scripts,
            base="develop",
        )
        assert result.returncode == 0, result.stderr

        state = load_state(project)
        entry = state.find("base-test")
        assert entry.base_branch == "develop"

    def test_list_shows_active(self, test_project, spinoff_scripts):
        """List shows active worktrees."""
        run_create_worktree(test_project, "list-test", spinoff_scripts)

        result = subprocess.run(
            ["python", str(spinoff_scripts / "worktree_state.py"),
             "-p", str(test_project), "list"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "list-test" in result.stdout
