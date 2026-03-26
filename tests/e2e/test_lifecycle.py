"""E2E tests for the full spinoff lifecycle."""

import subprocess

import pytest

from spinoff.state import load_state

from .conftest import run_create_worktree


pytestmark = pytest.mark.e2e


class TestLifecycle:
    def test_full_cycle(self, test_project, plugin_root):
        """Create → verify state/dir/branch/pane."""
        project = test_project

        # Create
        result = run_create_worktree(project, "cycle-test", plugin_root)
        assert result.returncode == 0, result.stderr

        # Verify state
        state = load_state(project)
        entry = state.find("cycle-test")
        assert entry is not None
        assert entry.branch == "worktree/cycle-test"
        assert entry.base_branch == "main"

        # Verify dir and branch exist
        wt_path = project / ".claude" / "worktrees" / "cycle-test"
        assert wt_path.exists()
        branches = subprocess.run(
            ["git", "branch"], cwd=project, capture_output=True, text=True
        ).stdout
        assert "worktree/cycle-test" in branches

    def test_create_with_task(self, test_project, plugin_root):
        """Verify startup script contains the task."""
        result = run_create_worktree(
            test_project, "task-test", plugin_root,
            task="fix the auth bug",
        )
        assert result.returncode == 0, result.stderr

        script = test_project / ".claude" / "worktrees" / "task-test.start.sh"
        assert script.exists()
        content = script.read_text()
        assert "fix the auth bug" in content

    def test_create_plan_mode(self, test_project, plugin_root):
        """Verify plan mode uses --permission-mode plan in startup script."""
        result = run_create_worktree(
            test_project, "plan-test", plugin_root,
            mode="plan",
        )
        assert result.returncode == 0, result.stderr

        script = test_project / ".claude" / "worktrees" / "plan-test.start.sh"
        content = script.read_text()
        assert "--permission-mode" in content
        assert "plan" in content

    def test_create_with_base(self, test_project, plugin_root):
        """Verify --base stores base_branch correctly."""
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
            project, "base-test", plugin_root,
            base="develop",
        )
        assert result.returncode == 0, result.stderr

        state = load_state(project)
        entry = state.find("base-test")
        assert entry is not None
        assert entry.base_branch == "develop"

    def test_list_shows_active(self, test_project, plugin_root):
        """List shows active worktrees."""
        import os
        run_create_worktree(test_project, "list-test", plugin_root)

        env = {**os.environ, "PYTHONPATH": str(plugin_root)}
        result = subprocess.run(
            ["python", "-m", "spinoff.state",
             "-p", str(test_project), "list"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0
        assert "list-test" in result.stdout
