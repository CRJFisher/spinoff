"""Cross-agent coordination: conflict detection, summary extraction, context sharing."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from spinoff.state import WorktreeEntry, WorktreeState


@dataclass
class FileOverlap:
    """A file touched by multiple active worktrees."""
    file_path: str
    worktree_names: list[str]


def detect_file_overlaps(
    project_path: Path,
    state: WorktreeState,
) -> list[FileOverlap]:
    """Detect files modified by 2+ active worktrees."""
    file_to_agents: dict[str, list[str]] = {}

    for wt in state.worktrees:
        if wt.status != "active" or not wt.base_branch:
            continue
        worktree_path = project_path / wt.path
        changed = _get_changed_files(worktree_path, wt.base_branch)
        for f in changed:
            file_to_agents.setdefault(f, []).append(wt.name)

    overlaps = [
        FileOverlap(file_path=f, worktree_names=sorted(agents))
        for f, agents in sorted(file_to_agents.items())
        if len(agents) > 1
    ]
    return overlaps


def _get_changed_files(worktree_path: Path, base_branch: str) -> set[str]:
    """Get files changed in a worktree relative to its base branch."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_branch}...HEAD"],
            capture_output=True, text=True, check=True,
            cwd=worktree_path,
        )
        return {f.strip() for f in result.stdout.splitlines() if f.strip()}
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return set()


def extract_completion_summary(
    worktree_path: Path,
    base_branch: str,
) -> str:
    """Extract a completion summary from a finished worktree."""
    parts: list[str] = []

    try:
        log_result = subprocess.run(
            ["git", "log", "--oneline", f"{base_branch}..HEAD"],
            capture_output=True, text=True, check=True,
            cwd=worktree_path,
        )
        if log_result.stdout.strip():
            parts.append("Commits:")
            for line in log_result.stdout.strip().splitlines()[:20]:
                parts.append(f"  {line}")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    try:
        stat_result = subprocess.run(
            ["git", "diff", "--stat", f"{base_branch}..HEAD"],
            capture_output=True, text=True, check=True,
            cwd=worktree_path,
        )
        if stat_result.stdout.strip():
            parts.append("")
            parts.append("Changes:")
            for line in stat_result.stdout.strip().splitlines()[-5:]:
                parts.append(f"  {line}")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    return "\n".join(parts)[:500]


def get_dependents(state: WorktreeState, name: str) -> list[WorktreeEntry]:
    """Return all worktrees that depend on the given name."""
    return [wt for wt in state.worktrees if name in wt.depends_on]


def write_dependency_context(
    project_path: Path,
    completed_name: str,
    completed_summary: str,
    dependent: WorktreeEntry,
) -> Optional[Path]:
    """Write completion context to a dependent worktree's context directory."""
    dep_path = project_path / dependent.path / ".claude" / "dependency-context"
    try:
        dep_path.mkdir(parents=True, exist_ok=True)
        context_file = dep_path / f"{completed_name}.md"
        context_file.write_text(f"# {completed_name} completed\n\n{completed_summary}\n")
        return context_file
    except OSError:
        return None


def propagate_error(state: WorktreeState, errored_name: str) -> list[str]:
    """Mark dependents of an errored worktree as paused. Returns paused names."""
    paused: list[str] = []
    to_visit = [errored_name]
    visited: set[str] = set()

    while to_visit:
        current = to_visit.pop()
        if current in visited:
            continue
        visited.add(current)
        for wt in state.worktrees:
            if current in wt.depends_on and wt.status == "active":
                wt.status = "paused"
                paused.append(wt.name)
                to_visit.append(wt.name)

    return paused


def propagate_recovery(state: WorktreeState, recovered_name: str) -> list[str]:
    """Resume dependents when a previously-errored worktree recovers."""
    resumed: list[str] = []
    active_or_done = {
        wt.name for wt in state.worktrees
        if wt.status in ("active", "done")
    }
    active_or_done.add(recovered_name)

    for wt in state.worktrees:
        if wt.status != "paused":
            continue
        if all(dep in active_or_done for dep in wt.depends_on):
            wt.status = "active"
            resumed.append(wt.name)

    return resumed
