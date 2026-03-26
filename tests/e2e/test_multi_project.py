"""E2E tests for multi-project workspace isolation."""

import json

import pytest

from spinoff.backends import get_backend
from spinoff.state import load_state

from .conftest import run_create_worktree


pytestmark = pytest.mark.e2e


class TestMultiProject:
    def test_separate_workspaces(self, test_project_pair, plugin_root):
        """Create spinoff in two projects, verify separate terminal windows."""
        project_a, project_b = test_project_pair
        backend = get_backend()

        config_a = json.loads((project_a / ".claude" / "spinoff.json").read_text())
        config_b = json.loads((project_b / ".claude" / "spinoff.json").read_text())

        workspaces_before = backend.list_workspaces()
        ids_before = {w.get("terminal_id", "") for w in workspaces_before}

        # Create worktree in each project
        r1 = run_create_worktree(project_a, "task-a", plugin_root)
        assert r1.returncode == 0, r1.stderr
        r2 = run_create_worktree(project_b, "task-b", plugin_root)
        assert r2.returncode == 0, r2.stderr

        # Get new workspaces
        workspaces_after = backend.list_workspaces()
        new_workspaces = [w for w in workspaces_after
                         if w.get("terminal_id", "") not in ids_before]

        # Exactly 2 new workspaces created
        assert len(new_workspaces) == 2, (
            f"Expected 2 new workspaces, got {len(new_workspaces)}: {new_workspaces}"
        )

        # Each workspace belongs to the correct project
        new_projects = {w.get("workspace", w.get("title", "")) for w in new_workspaces}
        assert config_a["project_name"] in new_projects or any(
            config_a["project_name"] in str(w.values()) for w in new_workspaces
        )

        # Different window_ids prove separate terminal windows
        window_ids = {w.get("window_id", "") for w in new_workspaces}
        assert len(window_ids) == 2, (
            f"Expected 2 distinct windows, got {window_ids}"
        )

        # State files recorded valid terminal_ids
        state_a = load_state(project_a)
        state_b = load_state(project_b)
        entry_a = state_a.find("task-a")
        entry_b = state_b.find("task-b")
        assert entry_a is not None and entry_a.terminal_id is not None
        assert entry_b is not None and entry_b.terminal_id is not None
        assert entry_a.terminal_id != entry_b.terminal_id

    def test_independent_state(self, test_project_pair, plugin_root):
        """Each project's state file has no cross-contamination."""
        project_a, project_b = test_project_pair

        run_create_worktree(project_a, "task-aa", plugin_root)
        run_create_worktree(project_b, "task-bb", plugin_root)

        state_a = load_state(project_a)
        state_b = load_state(project_b)

        assert state_a.find("task-aa") is not None
        assert state_a.find("task-bb") is None

        assert state_b.find("task-bb") is not None
        assert state_b.find("task-aa") is None
