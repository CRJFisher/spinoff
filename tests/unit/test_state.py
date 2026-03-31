"""Tests for spinoff.state."""

import json
from pathlib import Path

from spinoff.state import (
    OverviewInfo,
    WorktreeEntry,
    WorktreeState,
    add_worktree,
    get_state_file_path,
    load_state,
    remove_worktree,
    save_state,
)


class TestWorktreeEntry:
    def test_to_dict_required_fields(self) -> None:
        entry = WorktreeEntry(name="fix", path=".claude/worktrees/fix", branch="worktree/fix")
        d = entry.to_dict()
        assert d["name"] == "fix"
        assert d["path"] == ".claude/worktrees/fix"
        assert d["branch"] == "worktree/fix"
        assert d["status"] == "active"
        assert "base_branch" not in d
        assert "terminal_id" not in d

    def test_to_dict_with_optional_fields(self) -> None:
        entry = WorktreeEntry(
            name="fix", path=".claude/worktrees/fix", branch="worktree/fix",
            base_branch="main", terminal_id="42",
        )
        d = entry.to_dict()
        assert d["base_branch"] == "main"
        assert d["terminal_id"] == "42"

    def test_to_dict_base_branch_none_omitted(self) -> None:
        entry = WorktreeEntry(name="a", path="p", branch="b", base_branch=None)
        assert "base_branch" not in entry.to_dict()

    def test_to_dict_terminal_id_none_omitted(self) -> None:
        entry = WorktreeEntry(name="a", path="p", branch="b", terminal_id=None)
        assert "terminal_id" not in entry.to_dict()

    def test_default_values(self) -> None:
        entry = WorktreeEntry(name="x", path="p", branch="b")
        assert entry.base_branch is None
        assert entry.terminal_id is None
        assert entry.status == "active"
        assert entry.depends_on == []
        assert entry.summary == ""
        assert entry.last_status == ""

    def test_to_dict_with_depends_on(self) -> None:
        entry = WorktreeEntry(name="a", path="p", branch="b", depends_on=["x", "y"])
        d = entry.to_dict()
        assert d["depends_on"] == ["x", "y"]

    def test_to_dict_empty_depends_on_omitted(self) -> None:
        entry = WorktreeEntry(name="a", path="p", branch="b")
        assert "depends_on" not in entry.to_dict()

    def test_to_dict_with_summary(self) -> None:
        entry = WorktreeEntry(name="a", path="p", branch="b", summary="done stuff")
        assert entry.to_dict()["summary"] == "done stuff"

    def test_to_dict_empty_summary_omitted(self) -> None:
        entry = WorktreeEntry(name="a", path="p", branch="b")
        assert "summary" not in entry.to_dict()

    def test_to_dict_with_last_status(self) -> None:
        entry = WorktreeEntry(name="a", path="p", branch="b", last_status="working")
        assert entry.to_dict()["last_status"] == "working"

    def test_to_dict_empty_last_status_omitted(self) -> None:
        entry = WorktreeEntry(name="a", path="p", branch="b")
        assert "last_status" not in entry.to_dict()


class TestWorktreeState:
    def test_empty_default(self) -> None:
        state = WorktreeState()
        assert state.worktrees == []

    def test_find_existing(self) -> None:
        entry = WorktreeEntry(name="fix", path="p", branch="b")
        state = WorktreeState(worktrees=[entry])
        assert state.find("fix") is entry

    def test_find_missing(self) -> None:
        state = WorktreeState()
        assert state.find("nope") is None

    def test_add_new(self) -> None:
        state = WorktreeState()
        entry = WorktreeEntry(name="fix", path="p", branch="b")
        state.add(entry)
        assert len(state.worktrees) == 1
        assert state.find("fix") is entry

    def test_add_replace_duplicate(self) -> None:
        state = WorktreeState()
        old = WorktreeEntry(name="fix", path="old-path", branch="b")
        new = WorktreeEntry(name="fix", path="new-path", branch="b2")
        state.add(old)
        state.add(new)
        assert len(state.worktrees) == 1
        result = state.find("fix")
        assert result is not None
        assert result.path == "new-path"

    def test_remove_existing(self) -> None:
        entry = WorktreeEntry(name="fix", path="p", branch="b")
        state = WorktreeState(worktrees=[entry])
        assert state.remove("fix") is True
        assert state.worktrees == []

    def test_remove_missing(self) -> None:
        state = WorktreeState()
        assert state.remove("nope") is False


class TestFileIO:
    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
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

    def test_load_missing_file_returns_empty(self, tmp_path: Path) -> None:
        state = load_state(tmp_path)
        assert state.worktrees == []

    def test_load_empty_file_returns_empty(self, tmp_path: Path) -> None:
        state_file = get_state_file_path(tmp_path)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("")
        state = load_state(tmp_path)
        assert state.worktrees == []

    def test_save_creates_worktrees_dir(self, tmp_path: Path) -> None:
        state = WorktreeState()
        save_state(tmp_path, state)
        assert (tmp_path / ".claude" / "worktrees").is_dir()
        assert get_state_file_path(tmp_path).exists()



class TestProjectLevelFields:
    def test_window_id_roundtrip(self, tmp_path: Path) -> None:
        state = WorktreeState(window_id="cmux-win-uuid")
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.window_id == "cmux-win-uuid"

    def test_overview_roundtrip(self, tmp_path: Path) -> None:
        info = OverviewInfo(workspace_id="ws-1", surface_id="sf-2")
        state = WorktreeState(overview=info)
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.overview is not None
        assert loaded.overview.workspace_id == "ws-1"
        assert loaded.overview.surface_id == "sf-2"

    def test_none_fields_omitted_from_json(self, tmp_path: Path) -> None:
        state = WorktreeState()
        save_state(tmp_path, state)
        raw = json.loads(get_state_file_path(tmp_path).read_text())
        assert "window_id" not in raw
        assert "overview" not in raw

    def test_defaults_are_none(self) -> None:
        state = WorktreeState()
        assert state.window_id is None
        assert state.overview is None


class TestOverviewInfo:
    def test_to_dict(self) -> None:
        info = OverviewInfo(workspace_id="ws", surface_id="sf")
        d = info.to_dict()
        assert d == {"workspace_id": "ws", "surface_id": "sf"}


class TestNewFieldsRoundtrip:
    def test_depends_on_roundtrip(self, tmp_path: Path) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", depends_on=["x", "y"]),
        ])
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.worktrees[0].depends_on == ["x", "y"]

    def test_summary_roundtrip(self, tmp_path: Path) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", summary="done stuff"),
        ])
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.worktrees[0].summary == "done stuff"

    def test_last_status_roundtrip(self, tmp_path: Path) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", last_status="working"),
        ])
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.worktrees[0].last_status == "working"

    def test_backward_compat_no_new_fields(self, tmp_path: Path) -> None:
        """Old state files without new fields load with defaults."""
        state_file = get_state_file_path(tmp_path)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({
            "worktrees": [{"name": "old", "path": "p", "branch": "b"}]
        }))
        loaded = load_state(tmp_path)
        assert loaded.worktrees[0].depends_on == []
        assert loaded.worktrees[0].summary == ""
        assert loaded.worktrees[0].last_status == ""


class TestRemoveWorktree:
    def test_remove_existing(self, tmp_path: Path) -> None:
        add_worktree(tmp_path, "fix", ".claude/worktrees/fix", "worktree/fix")
        found, state = remove_worktree(tmp_path, "fix")
        assert found is True
        assert state.find("fix") is None
        # Verify persisted
        reloaded = load_state(tmp_path)
        assert reloaded.find("fix") is None

    def test_remove_missing(self, tmp_path: Path) -> None:
        add_worktree(tmp_path, "fix", ".claude/worktrees/fix", "worktree/fix")
        found, state = remove_worktree(tmp_path, "nonexistent")
        assert found is False
        assert state.find("fix") is not None

    def test_remove_preserves_others(self, tmp_path: Path) -> None:
        add_worktree(tmp_path, "a", "pa", "ba")
        add_worktree(tmp_path, "b", "pb", "bb")
        found, state = remove_worktree(tmp_path, "a")
        assert found is True
        assert state.find("b") is not None
        assert len(state.worktrees) == 1
