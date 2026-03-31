"""Cross-agent coordination: conflict detection, summary extraction, context sharing."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from spinoff.state import WorktreeEntry, WorktreeState


class DependencyError(ValueError):
    """Raised when dependency validation fails."""


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


def validate_dependencies(
    state: WorktreeState,
    new_name: str,
    depends_on: list[str],
) -> None:
    """Validate that dependencies exist and don't create cycles.

    Raises:
        DependencyError: If a referenced worktree doesn't exist or a cycle would form.
    """
    existing_names = {wt.name for wt in state.worktrees}
    for dep in depends_on:
        if dep == new_name:
            raise DependencyError(f"Worktree '{new_name}' cannot depend on itself")
        if dep not in existing_names:
            raise DependencyError(
                f"Dependency '{dep}' not found. "
                f"Available: {', '.join(sorted(existing_names)) or '(none)'}"
            )

    graph: dict[str, list[str]] = {}
    for wt in state.worktrees:
        graph[wt.name] = list(wt.depends_on)
    graph[new_name] = list(depends_on)

    if _has_cycle(graph):
        raise DependencyError(
            f"Adding dependencies {new_name} -> {depends_on} would create a cycle"
        )


def _has_cycle(graph: dict[str, list[str]]) -> bool:
    """Detect cycles via DFS with 3-color marking."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in graph}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for dep in graph.get(node, []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                return True
            if color[dep] == WHITE and dfs(dep):
                return True
        color[node] = BLACK
        return False

    for node in graph:
        if color[node] == WHITE:
            if dfs(node):
                return True
    return False


def topological_sort(state: WorktreeState) -> list[list[str]]:
    """Return worktrees in merge-order layers.

    Each layer contains worktrees whose dependencies are all in earlier layers.
    """
    all_names = {wt.name for wt in state.worktrees}
    graph = {wt.name: [d for d in wt.depends_on if d in all_names] for wt in state.worktrees}

    remaining = {name: len(deps) for name, deps in graph.items()}
    layers: list[list[str]] = []

    while remaining:
        layer = sorted(name for name, deg in remaining.items() if deg == 0)
        if not layer:
            break  # cycle
        layers.append(layer)
        for name in layer:
            del remaining[name]
        for name in remaining:
            remaining[name] = len([d for d in graph[name] if d in remaining])

    return layers
