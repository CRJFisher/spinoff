"""Tests for spinoff.coordination."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from spinoff.coordination import (
    DependencyError,
    FileOverlap,
    detect_file_overlaps,
    extract_completion_summary,
    get_dependents,
    topological_sort,
    validate_dependencies,
    write_dependency_context,
)
from spinoff.state import WorktreeEntry, WorktreeState


def _entry(name: str, depends_on: list[str] | None = None, status: str = "active") -> WorktreeEntry:
    return WorktreeEntry(
        name=name, path=f".claude/worktrees/{name}", branch=f"worktree/{name}",
        base_branch="main", terminal_id=f"s-{name}", status=status,
        depends_on=depends_on or [],
    )


class TestDetectFileOverlaps:
    @patch("spinoff.coordination._get_changed_files")
    def test_no_overlap(self, mock_get: MagicMock) -> None:
        state = WorktreeState(worktrees=[_entry("a"), _entry("b")])
        mock_get.side_effect = [{"src/a.py"}, {"src/b.py"}]
        result = detect_file_overlaps(Path("/repo"), state)
        assert result == []

    @patch("spinoff.coordination._get_changed_files")
    def test_overlap_detected(self, mock_get: MagicMock) -> None:
        state = WorktreeState(worktrees=[_entry("a"), _entry("b")])
        mock_get.side_effect = [{"src/shared.py", "src/a.py"}, {"src/shared.py"}]
        result = detect_file_overlaps(Path("/repo"), state)
        assert len(result) == 1
        assert result[0].file_path == "src/shared.py"
        assert sorted(result[0].worktree_names) == ["a", "b"]

    @patch("spinoff.coordination._get_changed_files")
    def test_three_agents_overlap(self, mock_get: MagicMock) -> None:
        state = WorktreeState(worktrees=[_entry("a"), _entry("b"), _entry("c")])
        mock_get.side_effect = [{"f.py"}, {"f.py"}, {"f.py"}]
        result = detect_file_overlaps(Path("/repo"), state)
        assert len(result) == 1
        assert len(result[0].worktree_names) == 3

    @patch("spinoff.coordination._get_changed_files")
    def test_skips_non_active(self, mock_get: MagicMock) -> None:
        state = WorktreeState(worktrees=[_entry("a"), _entry("b", status="done")])
        mock_get.side_effect = [{"f.py"}]
        result = detect_file_overlaps(Path("/repo"), state)
        assert result == []


class TestExtractCompletionSummary:
    @patch("spinoff.coordination.subprocess.run")
    def test_extracts_summary(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = [
            MagicMock(stdout="abc123 Add feature\ndef456 Fix bug\n", returncode=0),
            MagicMock(stdout=" src/main.py | 10 ++++\n 1 file changed\n", returncode=0),
        ]
        result = extract_completion_summary(Path("/wt"), "main")
        assert "abc123" in result
        assert "src/main.py" in result

    @patch("spinoff.coordination.subprocess.run")
    def test_handles_failure(self, mock_run: MagicMock) -> None:
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "git")
        result = extract_completion_summary(Path("/wt"), "main")
        assert result == ""


class TestGetDependents:
    def test_finds_dependents(self) -> None:
        state = WorktreeState(worktrees=[
            _entry("a"),
            _entry("b", depends_on=["a"]),
            _entry("c", depends_on=["a"]),
            _entry("d"),
        ])
        deps = get_dependents(state, "a")
        assert {d.name for d in deps} == {"b", "c"}

    def test_no_dependents(self) -> None:
        state = WorktreeState(worktrees=[_entry("a"), _entry("b")])
        assert get_dependents(state, "a") == []


class TestWriteDependencyContext:
    def test_writes_file(self, tmp_path: Path) -> None:
        dep = _entry("consumer")
        dep.path = str(tmp_path / "consumer")
        (tmp_path / "consumer").mkdir()
        result = write_dependency_context(Path("/"), "producer", "Summary text", dep)
        assert result is not None
        assert result.exists()
        assert "producer" in result.read_text()
        assert "Summary text" in result.read_text()


class TestDependencyValidation:
    def test_valid_deps(self) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
            WorktreeEntry(name="b", path="p", branch="b"),
        ])
        validate_dependencies(state, "c", ["a", "b"])  # Should not raise

    def test_missing_dep(self) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
        ])
        with pytest.raises(DependencyError, match="not found"):
            validate_dependencies(state, "c", ["a", "missing"])

    def test_self_dep(self) -> None:
        state = WorktreeState(worktrees=[])
        with pytest.raises(DependencyError, match="itself"):
            validate_dependencies(state, "a", ["a"])

    def test_direct_cycle(self) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", depends_on=["b"]),
            WorktreeEntry(name="b", path="p", branch="b"),
        ])
        with pytest.raises(DependencyError, match="cycle"):
            validate_dependencies(state, "b", ["a"])

    def test_indirect_cycle(self) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b", depends_on=["c"]),
            WorktreeEntry(name="b", path="p", branch="b", depends_on=["a"]),
            WorktreeEntry(name="c", path="p", branch="b"),
        ])
        with pytest.raises(DependencyError, match="cycle"):
            validate_dependencies(state, "c", ["b"])

    def test_diamond_no_cycle(self) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
            WorktreeEntry(name="b", path="p", branch="b", depends_on=["a"]),
            WorktreeEntry(name="c", path="p", branch="b", depends_on=["a"]),
        ])
        validate_dependencies(state, "d", ["b", "c"])  # Should not raise


class TestTopologicalSort:
    def test_no_deps(self) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
            WorktreeEntry(name="b", path="p", branch="b"),
        ])
        layers = topological_sort(state)
        assert len(layers) == 1
        assert sorted(layers[0]) == ["a", "b"]

    def test_linear_chain(self) -> None:
        state = WorktreeState(worktrees=[
            WorktreeEntry(name="a", path="p", branch="b"),
            WorktreeEntry(name="b", path="p", branch="b", depends_on=["a"]),
            WorktreeEntry(name="c", path="p", branch="b", depends_on=["b"]),
        ])
        layers = topological_sort(state)
        assert layers == [["a"], ["b"], ["c"]]

    def test_diamond(self) -> None:
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

    def test_empty(self) -> None:
        state = WorktreeState()
        assert topological_sort(state) == []


