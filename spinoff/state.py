#!/usr/bin/env python3
"""
Worktree State Management

Manages the .claude/worktrees/.state.json state file for tracking active worktrees.

State file format (JSON):
{
  "window_id": "cmux-window-uuid",
  "overview_workspace_id": "cmux-workspace-uuid",
  "worktrees": [
    {
      "name": "fix-auth",
      "path": ".claude/worktrees/fix-auth",
      "branch": "worktree/fix-auth",
      "base_branch": "main",
      "terminal_id": "42",
      "status": "active"
    }
  ]
}
"""
# /// script
# requires-python = ">=3.11"
# ///

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class WorktreeEntry:
    """Represents a tracked worktree."""
    name: str
    path: str
    branch: str
    base_branch: Optional[str] = None  # Branch the worktree was created from
    terminal_id: Optional[str] = None   # Terminal backend ID (may be None if closed)
    status: str = "active"

    def to_dict(self) -> dict:
        """Convert to dict for JSON output."""
        d = {
            "name": self.name,
            "path": self.path,
            "branch": self.branch,
            "status": self.status,
        }
        if self.base_branch is not None:
            d["base_branch"] = self.base_branch
        if self.terminal_id is not None:
            d["terminal_id"] = self.terminal_id
        return d


@dataclass
class WorktreeState:
    """State of all tracked worktrees for a project."""
    worktrees: list[WorktreeEntry] = field(default_factory=list)
    window_id: Optional[str] = None              # cmux window ID
    overview_workspace_id: Optional[str] = None   # cmux overview workspace ID

    def find(self, name: str) -> Optional[WorktreeEntry]:
        """Find a worktree by name."""
        for wt in self.worktrees:
            if wt.name == name:
                return wt
        return None

    def add(self, entry: WorktreeEntry) -> None:
        """Add a worktree entry."""
        existing = self.find(entry.name)
        if existing:
            self.worktrees.remove(existing)
        self.worktrees.append(entry)

    def remove(self, name: str) -> bool:
        """Remove a worktree by name. Returns True if found and removed."""
        entry = self.find(name)
        if entry:
            self.worktrees.remove(entry)
            return True
        return False


def get_state_file_path(project_path: Path) -> Path:
    """Get the path to the state file for a project."""
    return project_path / ".claude" / "worktrees" / ".state.json"


def load_state(project_path: Path) -> WorktreeState:
    """Load worktree state from the project's state file."""
    state_file = get_state_file_path(project_path)
    state = WorktreeState()

    if not state_file.exists():
        return state

    content = state_file.read_text()
    if not content.strip():
        return state

    data = json.loads(content)

    state.window_id = data.get("window_id")
    state.overview_workspace_id = data.get("overview_workspace_id")

    for wt_data in data.get("worktrees", []):
        entry = WorktreeEntry(
            name=wt_data["name"],
            path=wt_data["path"],
            branch=wt_data["branch"],
            base_branch=wt_data.get("base_branch"),
            terminal_id=wt_data.get("terminal_id") or wt_data.get("pane_id"),
            status=wt_data.get("status", "active"),
        )
        state.worktrees.append(entry)

    return state


def save_state(project_path: Path, state: WorktreeState) -> None:
    """Save worktree state to the project's state file."""
    state_file = get_state_file_path(project_path)

    # Ensure worktrees directory exists
    state_file.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, object] = {
        "worktrees": [wt.to_dict() for wt in state.worktrees],
    }
    if state.window_id is not None:
        data["window_id"] = state.window_id
    if state.overview_workspace_id is not None:
        data["overview_workspace_id"] = state.overview_workspace_id

    # Write atomically via temp file
    temp_file = state_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(data, indent=2) + "\n")
    temp_file.rename(state_file)


def add_worktree(
    project_path: Path,
    name: str,
    worktree_path: str,
    branch: str,
    base_branch: Optional[str] = None,
    terminal_id: Optional[str] = None,
) -> WorktreeState:
    """Add a worktree to the state file."""
    state = load_state(project_path)

    entry = WorktreeEntry(
        name=name,
        path=worktree_path,
        branch=branch,
        base_branch=base_branch,
        terminal_id=terminal_id,
        status="active",
    )
    state.add(entry)
    save_state(project_path, state)
    return state


def remove_worktree(project_path: Path, name: str) -> tuple[bool, WorktreeState]:
    """Remove a worktree from the state file. Returns (found, updated_state)."""
    state = load_state(project_path)
    found = state.remove(name)
    if found:
        save_state(project_path, state)
    return found, state


def cmd_list(project_path: Path) -> None:
    """List all tracked worktrees."""
    state = load_state(project_path)

    if not state.worktrees:
        print("No worktrees tracked.")
        print(f"State file: {get_state_file_path(project_path)}")
        return

    print(f"Worktrees ({len(state.worktrees)}):")
    for wt in state.worktrees:
        flags = []
        if wt.terminal_id is not None:
            flags.append(f"terminal:{wt.terminal_id}")
        if wt.base_branch:
            flags.append(f"base:{wt.base_branch}")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"  {wt.name}: {wt.path}{flag_str}")


def cmd_show(project_path: Path, name: str) -> None:
    """Show details for a specific worktree."""
    state = load_state(project_path)
    entry = state.find(name)

    if not entry:
        print(f"Worktree '{name}' not found.")
        return

    print(f"Name:         {entry.name}")
    print(f"Path:         {entry.path}")
    print(f"Branch:       {entry.branch}")
    print(f"Base Branch:  {entry.base_branch or 'N/A'}")
    print(f"Status:       {entry.status}")
    print(f"Terminal ID:  {entry.terminal_id or 'N/A'}")


def cmd_path(project_path: Path) -> None:
    """Print the state file path."""
    print(get_state_file_path(project_path))


if __name__ == "__main__":
    import argparse
    import subprocess
    import sys

    # Try to detect project root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        default_project = Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        default_project = Path.cwd()

    parser = argparse.ArgumentParser(
        description="Manage worktree state tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m spinoff.state list              List all tracked worktrees
  python -m spinoff.state show fix-auth     Show details for 'fix-auth'
  python -m spinoff.state path              Print state file path
""",
    )
    parser.add_argument(
        "-p", "--project",
        type=Path,
        default=default_project,
        help=f"Project path (default: {default_project})",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list command
    subparsers.add_parser("list", help="List all tracked worktrees")

    # show command
    show_parser = subparsers.add_parser("show", help="Show details for a worktree")
    show_parser.add_argument("name", help="Worktree name")

    # path command
    subparsers.add_parser("path", help="Print the state file path")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args.project)
    elif args.command == "show":
        cmd_show(args.project, args.name)
    elif args.command == "path":
        cmd_path(args.project)
    else:
        parser.print_help()
        sys.exit(1)
