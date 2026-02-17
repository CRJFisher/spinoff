"""Tests for spinoff.state."""

import json

import pytest

from spinoff.state import (
    WorktreeEntry,
    WorktreeState,
    get_state_file_path,
    load_state,
    save_state,
    _get_legacy_state_file_path,
    _migrate_legacy_state,
)


class TestWorktreeEntry:
    def test_to_dict_required_fields(self):
        entry = WorktreeEntry(name="fix", path=".worktrees/fix", branch="worktree/fix")
        d = entry.to_dict()
        assert d["name"] == "fix"
        assert d["path"] == ".worktrees/fix"
        assert d["branch"] == "worktree/fix"
        assert d["status"] == "active"
        assert "base_branch" not in d
        assert "pane_id" not in d

    def test_to_dict_with_optional_fields(self):
        entry = WorktreeEntry(
            name="fix", path=".worktrees/fix", branch="worktree/fix",
            base_branch="main", pane_id="42",
        )
        d = entry.to_dict()
        assert d["base_branch"] == "main"
        assert d["pane_id"] == "42"

    def test_to_dict_base_branch_none_omitted(self):
        entry = WorktreeEntry(name="a", path="p", branch="b", base_branch=None)
        assert "base_branch" not in entry.to_dict()

    def test_to_dict_pane_id_none_omitted(self):
        entry = WorktreeEntry(name="a", path="p", branch="b", pane_id=None)
        assert "pane_id" not in entry.to_dict()

    def test_default_values(self):
        entry = WorktreeEntry(name="x", path="p", branch="b")
        assert entry.base_branch is None
        assert entry.pane_id is None
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
        assert state.find("fix").path == "new-path"

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
            WorktreeEntry(name="a", path=".worktrees/a", branch="worktree/a",
                          base_branch="main", pane_id="1"),
            WorktreeEntry(name="b", path=".worktrees/b", branch="worktree/b"),
        ])
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert len(loaded.worktrees) == 2
        assert loaded.worktrees[0].name == "a"
        assert loaded.worktrees[0].base_branch == "main"
        assert loaded.worktrees[0].pane_id == "1"
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
        assert (tmp_path / ".worktrees").is_dir()
        assert get_state_file_path(tmp_path).exists()


class TestLegacyMigration:
    def test_migrates_legacy_file(self, tmp_path):
        legacy = _get_legacy_state_file_path(tmp_path)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        data = {"worktrees": [{"name": "old", "path": "p", "branch": "b"}]}
        legacy.write_text(json.dumps(data))

        state = load_state(tmp_path)
        assert len(state.worktrees) == 1
        assert state.worktrees[0].name == "old"
        assert not legacy.exists()
        assert get_state_file_path(tmp_path).exists()

    def test_noop_when_new_file_exists(self, tmp_path):
        legacy = _get_legacy_state_file_path(tmp_path)
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps({"worktrees": [{"name": "old", "path": "p", "branch": "b"}]}))

        new = get_state_file_path(tmp_path)
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_text(json.dumps({"worktrees": [{"name": "new", "path": "p2", "branch": "b2"}]}))

        _migrate_legacy_state(tmp_path)
        # Legacy file still exists (not migrated because new file exists)
        assert legacy.exists()
        state = load_state(tmp_path)
        assert state.worktrees[0].name == "new"

    def test_noop_when_no_legacy_file(self, tmp_path):
        _migrate_legacy_state(tmp_path)
        assert not get_state_file_path(tmp_path).exists()
