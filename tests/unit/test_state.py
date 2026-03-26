"""Tests for spinoff.state."""

import json

import pytest

from spinoff.state import (
    WorktreeEntry,
    WorktreeState,
    get_state_file_path,
    load_state,
    save_state,
)


class TestWorktreeEntry:
    def test_to_dict_required_fields(self):
        entry = WorktreeEntry(name="fix", path=".claude/worktrees/fix", branch="worktree/fix")
        d = entry.to_dict()
        assert d["name"] == "fix"
        assert d["path"] == ".claude/worktrees/fix"
        assert d["branch"] == "worktree/fix"
        assert d["status"] == "active"
        assert "base_branch" not in d
        assert "terminal_id" not in d

    def test_to_dict_with_optional_fields(self):
        entry = WorktreeEntry(
            name="fix", path=".claude/worktrees/fix", branch="worktree/fix",
            base_branch="main", terminal_id="42",
        )
        d = entry.to_dict()
        assert d["base_branch"] == "main"
        assert d["terminal_id"] == "42"

    def test_to_dict_base_branch_none_omitted(self):
        entry = WorktreeEntry(name="a", path="p", branch="b", base_branch=None)
        assert "base_branch" not in entry.to_dict()

    def test_to_dict_terminal_id_none_omitted(self):
        entry = WorktreeEntry(name="a", path="p", branch="b", terminal_id=None)
        assert "terminal_id" not in entry.to_dict()

    def test_default_values(self):
        entry = WorktreeEntry(name="x", path="p", branch="b")
        assert entry.base_branch is None
        assert entry.terminal_id is None
        assert entry.status == "active"


class TestWorktreeState:
    def test_empty_default(self):
        state = WorktreeState()
        assert state.worktrees == []

    def test_find_existing(self):
        entry = WorktreeEntry(name="fix", path="p", branch="b")
        state = WorktreeState(worktrees=[entry])
        assert state.find("fix") is entry

    def test_find_missing(self):
        state = WorktreeState()
        assert state.find("nope") is None

    def test_add_new(self):
        state = WorktreeState()
        entry = WorktreeEntry(name="fix", path="p", branch="b")
        state.add(entry)
        assert len(state.worktrees) == 1
        assert state.find("fix") is entry

    def test_add_replace_duplicate(self):
        state = WorktreeState()
        old = WorktreeEntry(name="fix", path="old-path", branch="b")
        new = WorktreeEntry(name="fix", path="new-path", branch="b2")
        state.add(old)
        state.add(new)
        assert len(state.worktrees) == 1
        result = state.find("fix")
        assert result is not None
        assert result.path == "new-path"

    def test_remove_existing(self):
        entry = WorktreeEntry(name="fix", path="p", branch="b")
        state = WorktreeState(worktrees=[entry])
        assert state.remove("fix") is True
        assert state.worktrees == []

    def test_remove_missing(self):
        state = WorktreeState()
        assert state.remove("nope") is False


class TestFileIO:
    def test_save_load_roundtrip(self, tmp_path):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path=".claude/worktrees/a", branch="worktree/a",
                          base_branch="main", terminal_id="1"),
            WorktreeEntry(name="b", path=".claude/worktrees/b", branch="worktree/b"),
        ])
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert len(loaded.worktrees) == 2
        assert loaded.worktrees[0].name == "a"
        assert loaded.worktrees[0].base_branch == "main"
        assert loaded.worktrees[0].terminal_id == "1"
        assert loaded.worktrees[1].name == "b"
        assert loaded.worktrees[1].base_branch is None

    def test_load_missing_file_returns_empty(self, tmp_path):
        state = load_state(tmp_path)
        assert state.worktrees == []

    def test_load_empty_file_returns_empty(self, tmp_path):
        state_file = get_state_file_path(tmp_path)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("")
        state = load_state(tmp_path)
        assert state.worktrees == []

    def test_save_creates_worktrees_dir(self, tmp_path):
        state = WorktreeState()
        save_state(tmp_path, state)
        assert (tmp_path / ".claude" / "worktrees").is_dir()
        assert get_state_file_path(tmp_path).exists()

    def test_legacy_pane_id_fallback(self, tmp_path):
        """Loading a state file with old pane_id key populates terminal_id."""
        state_file = get_state_file_path(tmp_path)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_data = {
            "worktrees": [{
                "name": "old-wt", "path": "p", "branch": "b",
                "pane_id": "77", "status": "active",
            }]
        }
        state_file.write_text(json.dumps(legacy_data))
        loaded = load_state(tmp_path)
        assert loaded.worktrees[0].terminal_id == "77"

    def test_terminal_id_takes_precedence_over_pane_id(self, tmp_path):
        """When both keys exist, terminal_id wins."""
        state_file = get_state_file_path(tmp_path)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "worktrees": [{
                "name": "wt", "path": "p", "branch": "b",
                "terminal_id": "new-99", "pane_id": "old-77",
            }]
        }
        state_file.write_text(json.dumps(data))
        loaded = load_state(tmp_path)
        assert loaded.worktrees[0].terminal_id == "new-99"


class TestProjectLevelFields:
    def test_window_id_roundtrip(self, tmp_path):
        state = WorktreeState(window_id="cmux-win-uuid")
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.window_id == "cmux-win-uuid"

    def test_overview_workspace_id_roundtrip(self, tmp_path):
        state = WorktreeState(overview_workspace_id="cmux-overview-uuid")
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.overview_workspace_id == "cmux-overview-uuid"

    def test_none_fields_omitted_from_json(self, tmp_path):
        state = WorktreeState()
        save_state(tmp_path, state)
        raw = json.loads(get_state_file_path(tmp_path).read_text())
        assert "window_id" not in raw
        assert "overview_workspace_id" not in raw

    def test_defaults_are_none(self):
        state = WorktreeState()
        assert state.window_id is None
        assert state.overview_workspace_id is None
