"""Tests for spinoff.state."""

import json

import pytest

from spinoff.state import (
    DependencyError,
    OverviewInfo,
    WorktreeEntry,
    WorktreeState,
    get_state_file_path,
    load_state,
    save_state,
    topological_sort,
    validate_dependencies,
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
        assert entry.depends_on == []
        assert entry.summary == ""
        assert entry.last_status == ""

    def test_to_dict_with_depends_on(self):
        entry = WorktreeEntry(name="a", path="p", branch="b", depends_on=["x", "y"])
        d = entry.to_dict()
        assert d["depends_on"] == ["x", "y"]

    def test_to_dict_empty_depends_on_omitted(self):
        entry = WorktreeEntry(name="a", path="p", branch="b")
        assert "depends_on" not in entry.to_dict()

    def test_to_dict_with_summary(self):
        entry = WorktreeEntry(name="a", path="p", branch="b", summary="done stuff")
        assert entry.to_dict()["summary"] == "done stuff"

    def test_to_dict_empty_summary_omitted(self):
        entry = WorktreeEntry(name="a", path="p", branch="b")
        assert "summary" not in entry.to_dict()

    def test_to_dict_with_last_status(self):
        entry = WorktreeEntry(name="a", path="p", branch="b", last_status="working")
        assert entry.to_dict()["last_status"] == "working"

    def test_to_dict_empty_last_status_omitted(self):
        entry = WorktreeEntry(name="a", path="p", branch="b")
        assert "last_status" not in entry.to_dict()


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

    def test_overview_roundtrip(self, tmp_path):
        info = OverviewInfo(workspace_id="ws-1", surface_id="sf-2", pid=1234)
        state = WorktreeState(overview=info)
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.overview is not None
        assert loaded.overview.workspace_id == "ws-1"
        assert loaded.overview.surface_id == "sf-2"
        assert loaded.overview.pid == 1234

    def test_none_fields_omitted_from_json(self, tmp_path):
        state = WorktreeState()
        save_state(tmp_path, state)
        raw = json.loads(get_state_file_path(tmp_path).read_text())
        assert "window_id" not in raw
        assert "overview" not in raw

    def test_defaults_are_none(self):
        state = WorktreeState()
        assert state.window_id is None
        assert state.overview is None


class TestOverviewInfo:
    def test_to_dict(self):
        info = OverviewInfo(workspace_id="ws", surface_id="sf", pid=42)
        d = info.to_dict()
        assert d == {"workspace_id": "ws", "surface_id": "sf", "pid": 42}


class TestNewFieldsRoundtrip:
    def test_depends_on_roundtrip(self, tmp_path):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", depends_on=["x", "y"]),
        ])
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.worktrees[0].depends_on == ["x", "y"]

    def test_summary_roundtrip(self, tmp_path):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", summary="done stuff"),
        ])
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.worktrees[0].summary == "done stuff"

    def test_last_status_roundtrip(self, tmp_path):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", last_status="working"),
        ])
        save_state(tmp_path, state)
        loaded = load_state(tmp_path)
        assert loaded.worktrees[0].last_status == "working"

    def test_backward_compat_no_new_fields(self, tmp_path):
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


class TestDependencyValidation:
    def test_valid_deps(self):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
            WorktreeEntry(name="b", path="p", branch="b"),
        ])
        validate_dependencies(state, "c", ["a", "b"])  # Should not raise

    def test_missing_dep(self):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
        ])
        with pytest.raises(DependencyError, match="not found"):
            validate_dependencies(state, "c", ["a", "missing"])

    def test_self_dep(self):
        state = WorktreeState(worktrees=[])
        with pytest.raises(DependencyError, match="itself"):
            validate_dependencies(state, "a", ["a"])

    def test_direct_cycle(self):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", depends_on=["b"]),
            WorktreeEntry(name="b", path="p", branch="b"),
        ])
        with pytest.raises(DependencyError, match="cycle"):
            validate_dependencies(state, "b", ["a"])

    def test_indirect_cycle(self):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", depends_on=["c"]),
            WorktreeEntry(name="b", path="p", branch="b", depends_on=["a"]),
            WorktreeEntry(name="c", path="p", branch="b"),
        ])
        with pytest.raises(DependencyError, match="cycle"):
            validate_dependencies(state, "c", ["b"])

    def test_diamond_no_cycle(self):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
            WorktreeEntry(name="b", path="p", branch="b", depends_on=["a"]),
            WorktreeEntry(name="c", path="p", branch="b", depends_on=["a"]),
        ])
        validate_dependencies(state, "d", ["b", "c"])  # Should not raise


class TestTopologicalSort:
    def test_no_deps(self):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
            WorktreeEntry(name="b", path="p", branch="b"),
        ])
        layers = topological_sort(state)
        assert len(layers) == 1
        assert sorted(layers[0]) == ["a", "b"]

    def test_linear_chain(self):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
            WorktreeEntry(name="b", path="p", branch="b", depends_on=["a"]),
            WorktreeEntry(name="c", path="p", branch="b", depends_on=["b"]),
        ])
        layers = topological_sort(state)
        assert layers == [["a"], ["b"], ["c"]]

    def test_diamond(self):
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
            WorktreeEntry(name="b", path="p", branch="b", depends_on=["a"]),
            WorktreeEntry(name="c", path="p", branch="b", depends_on=["a"]),
            WorktreeEntry(name="d", path="p", branch="b", depends_on=["b", "c"]),
        ])
        layers = topological_sort(state)
        assert layers[0] == ["a"]
        assert sorted(layers[1]) == ["b", "c"]
        assert layers[2] == ["d"]

    def test_empty(self):
        state = WorktreeState()
        assert topological_sort(state) == []
