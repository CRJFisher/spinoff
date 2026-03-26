"""Tests for spinoff.coordination."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from spinoff.coordination import (
    FileOverlap,
    detect_file_overlaps,
    extract_completion_summary,
    get_dependents,
    propagate_error,
    propagate_recovery,
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


class TestPropagateError:
    def test_pauses_direct_dependents(self) -> None:
        state = WorktreeState(worktrees=[
            _entry("a"),
            _entry("b", depends_on=["a"]),
            _entry("c"),
        ])
        paused = propagate_error(state, "a")
        assert "b" in paused
        assert state.find("b").status == "paused"
        assert state.find("c").status == "active"

    def test_pauses_transitive_dependents(self) -> None:
        state = WorktreeState(worktrees=[
            _entry("a"),
            _entry("b", depends_on=["a"]),
            _entry("c", depends_on=["b"]),
        ])
        paused = propagate_error(state, "a")
        assert "b" in paused
        assert "c" in paused

    def test_no_dependents(self) -> None:
        state = WorktreeState(worktrees=[_entry("a"), _entry("b")])
        assert propagate_error(state, "a") == []


class TestPropagateRecovery:
    def test_resumes_when_all_deps_active(self) -> None:
        state = WorktreeState(worktrees=[
            _entry("a"),
            _entry("b", depends_on=["a"], status="paused"),
        ])
        resumed = propagate_recovery(state, "a")
        assert "b" in resumed
        assert state.find("b").status == "active"

    def test_stays_paused_with_other_errored_dep(self) -> None:
        state = WorktreeState(worktrees=[
            _entry("a"),
            _entry("x", status="errored"),
            _entry("b", depends_on=["a", "x"], status="paused"),
        ])
        resumed = propagate_recovery(state, "a")
        assert "b" not in resumed
        assert state.find("b").status == "paused"
