"""
Spinoff Overview Panel

Manages the overview dashboard: a cmux workspace with a poller that monitors
agent status via read-screen, updates sidebar metadata, sends desktop
notifications, and generates an HTML dashboard.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from spinoff.backends import get_backend
from spinoff.config import load_config
from spinoff.screen import AgentState, ScreenSnapshot, classify
from spinoff.state import OverviewInfo, WorktreeState, load_state, save_state


def get_cache_dir(project_name: str) -> Path:
    """Return the cache directory for overview files, creating if needed."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    cache_dir = base / "spinoff" / project_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def open_overview(project_path: Path) -> tuple[bool, str]:
    """Open or focus the overview panel. Idempotent."""
    config = load_config(project_path)
    backend = get_backend(config)

    if not backend.available():
        return False, "Terminal backend not available"

    state = load_state(project_path)

    # Check if overview is already running
    if state.overview is not None:
        if backend.workspace_exists(state.overview.workspace_id):
            backend.focus_workspace(state.overview.workspace_id)
            return True, "Overview panel focused"

    # Create new overview workspace with poller
    poller_cmd = [
        sys.executable, "-m", "spinoff.overview", "watch",
        "--project", str(project_path),
    ]
    success, workspace_id, msg = backend.create_workspace(
        title=f"spinoff-overview-{config.project_name}",
        cwd=project_path,
        command=poller_cmd,
        project_name=config.project_name,
    )
    if not success or workspace_id is None:
        return False, f"Failed to create overview workspace: {msg}"

    state.overview = OverviewInfo(
        workspace_id=workspace_id,
        surface_id=workspace_id,  # cmux uses same ID
        pid=os.getpid(),
    )
    save_state(project_path, state)

    return True, f"Overview panel started ({workspace_id})"


def close_overview(project_path: Path) -> tuple[bool, str]:
    """Stop the overview poller and close its workspace."""
    config = load_config(project_path)
    backend = get_backend(config)
    state = load_state(project_path)

    if state.overview is None:
        return True, "Overview not running"

    backend.close_workspace(state.overview.workspace_id)
    state.overview = None
    save_state(project_path, state)

    return True, "Overview panel closed"


def cmd_status(project_path: Path) -> None:
    """Print a text-based status table to stdout."""
    config = load_config(project_path)
    state = load_state(project_path)

    if not state.worktrees:
        print("No worktrees tracked.")
        return

    backend = get_backend(config)

    rows: list[tuple[str, str, str, str]] = []
    for wt in state.worktrees:
        if wt.terminal_id and backend.available():
            screen_text = backend.read_screen(wt.terminal_id)
            if screen_text is not None:
                snap = ScreenSnapshot(
                    surface_id=wt.terminal_id,
                    text=screen_text,
                    captured_at=time.monotonic(),
                )
                status = classify(snap)
                state_label = _format_state_label(status.state)
                rows.append((wt.name, state_label, wt.last_status or "-", status.summary[:60]))
            else:
                rows.append((wt.name, "offline", wt.last_status or "-", "Surface unreachable"))
        else:
            rows.append((wt.name, "offline", wt.last_status or "-", "No terminal session"))

    # Calculate column widths
    headers = ("Agent", "State", "Last", "Activity")
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]

    # Print header
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("  ".join("-" * w for w in widths))

    # Print rows
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(row))))


def cmd_approve(project_path: Path, name: str) -> None:
    """Approve a pending permission prompt for a named agent."""
    from spinoff.overview.security import is_safe_to_approve

    config = load_config(project_path)
    state = load_state(project_path)
    entry = state.find(name)

    if entry is None:
        names = [wt.name for wt in state.worktrees]
        print(f"Agent '{name}' not found. Available: {', '.join(names) or '(none)'}", file=sys.stderr)
        sys.exit(1)

    if entry.terminal_id is None:
        print(f"Agent '{name}' has no terminal session.", file=sys.stderr)
        sys.exit(1)

    backend = get_backend(config)
    screen_text = backend.read_screen(entry.terminal_id)
    if screen_text is None:
        print(f"Cannot read screen for '{name}'.", file=sys.stderr)
        sys.exit(1)

    snap = ScreenSnapshot(
        surface_id=entry.terminal_id,
        text=screen_text,
        captured_at=time.monotonic(),
    )
    status = classify(snap)

    if status.state != AgentState.WAITING_APPROVAL:
        print(f"Agent '{name}' is not waiting for approval (state: {status.state.value})")
        print(f"Last activity: {status.summary}")
        sys.exit(1)

    # Safety check
    safe, reason = is_safe_to_approve(screen_text)
    if not safe:
        print(f"Cannot auto-approve: {reason}", file=sys.stderr)
        print("Review the prompt manually and approve in the terminal.", file=sys.stderr)
        sys.exit(1)

    # Send approval
    backend.send_keys(entry.terminal_id, "y")
    backend.send_keys(entry.terminal_id, "enter")

    print(f"Approved: {name} -- {status.summary}")


def _format_state_label(state: AgentState) -> str:
    """Format state for display, uppercase for attention states."""
    labels = {
        AgentState.INITIALIZING: "starting",
        AgentState.WORKING: "working",
        AgentState.WAITING_INPUT: "idle",
        AgentState.WAITING_APPROVAL: "WAITING",
        AgentState.ERRORED: "ERRORED",
        AgentState.DONE: "done",
        AgentState.SHELL: "shell",
        AgentState.UNKNOWN: "unknown",
    }
    return labels.get(state, state.value)
