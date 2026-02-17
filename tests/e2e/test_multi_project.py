"""E2E tests for multi-project workspace isolation."""

import json

import pytest

from worktree_state import load_state
from worktree_wezterm import list_panes

from .conftest import run_create_worktree


pytestmark = pytest.mark.e2e


class TestMultiProject:
    def test_separate_workspaces(self, test_project_pair, spinoff_scripts):
        """Create spinoff in two projects, verify separate WezTerm windows."""
        project_a, project_b = test_project_pair

        config_a = json.loads((project_a / ".claude" / "spinoff.json").read_text())
        config_b = json.loads((project_b / ".claude" / "spinoff.json").read_text())

        panes_before = list_panes()
        pane_ids_before = {str(p.get("pane_id")) for p in panes_before}

        # Create worktree in each project
        r1 = run_create_worktree(project_a, "task-a", spinoff_scripts)
        assert r1.returncode == 0, r1.stderr
        r2 = run_create_worktree(project_b, "task-b", spinoff_scripts)
        assert r2.returncode == 0, r2.stderr

        # Get new panes
        panes_after = list_panes()
        new_panes = [p for p in panes_after
                     if str(p.get("pane_id")) not in pane_ids_before]

        # Exactly 2 new panes created
        assert len(new_panes) == 2, (
            f"Expected 2 new panes, got {len(new_panes)}: {new_panes}"
        )

        # Each pane has the correct workspace
        new_workspaces = {p.get("workspace") for p in new_panes}
        assert config_a["project_name"] in new_workspaces
        assert config_b["project_name"] in new_workspaces

        # Different window_ids prove separate WezTerm windows
        window_ids = {str(p.get("window_id")) for p in new_panes}
        assert len(window_ids) == 2, (
            f"Expected 2 distinct windows, got {window_ids}"
        )

        # State files recorded valid pane_ids
        state_a = load_state(project_a)
        state_b = load_state(project_b)
        entry_a = state_a.find("task-a")
        entry_b = state_b.find("task-b")
        assert entry_a is not None and entry_a.pane_id is not None
        assert entry_b is not None and entry_b.pane_id is not None
        assert entry_a.pane_id != entry_b.pane_id

    def test_independent_state(self, test_project_pair, spinoff_scripts):
        """Each project's state file has no cross-contamination."""
        project_a, project_b = test_project_pair

        run_create_worktree(project_a, "task-aa", spinoff_scripts)
        run_create_worktree(project_b, "task-bb", spinoff_scripts)

        state_a = load_state(project_a)
        state_b = load_state(project_b)

        assert state_a.find("task-aa") is not None
        assert state_a.find("task-bb") is None

        assert state_b.find("task-bb") is not None
        assert state_b.find("task-aa") is None
