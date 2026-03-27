"""
Spinoff Overview Panel

Manages the overview dashboard: a cmux workspace with a poller that monitors
agent status via read-screen, updates sidebar metadata, sends desktop
notifications, and generates an HTML dashboard.
"""

import os
import sys
import time
from pathlib import Path

from spinoff.backends import get_backend
from spinoff.config import load_config
from spinoff.screen import AgentState, ScreenSnapshot, classify
from spinoff.state import OverviewInfo, load_state, save_state

from spinoff.overview.actions import ActionResult, _execute_approve
from spinoff.overview.renderer import STATE_LABELS_CLI, format_duration


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

    if state.overview is not None:
        if backend.workspace_exists(state.overview.workspace_id):
            backend.focus_workspace(state.overview.workspace_id)
            return True, "Overview panel focused"

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
        surface_id=workspace_id,
        pid=0,
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
    is_available = backend.available()

    rows: list[tuple[str, str, str, str]] = []
    for wt in state.worktrees:
        if wt.terminal_id and is_available:
            screen_text = backend.read_screen(wt.terminal_id)
            if screen_text is not None:
                snap = ScreenSnapshot(
                    surface_id=wt.terminal_id,
                    text=screen_text,
                    captured_at=time.monotonic(),
                )
                status = classify(snap)
                state_label = STATE_LABELS_CLI.get(status.state, status.state.value)
                rows.append((wt.name, state_label, wt.last_status or "-", status.summary[:60]))
            else:
                rows.append((wt.name, "offline", wt.last_status or "-", "Surface unreachable"))
        else:
            rows.append((wt.name, "offline", wt.last_status or "-", "No terminal session"))

    headers = ("Agent", "State", "Last", "Activity")
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]

    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("  ".join("-" * w for w in widths))

    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(row))))


def cmd_approve(project_path: Path, name: str) -> None:
    """Approve a pending permission prompt for a named agent."""
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
    result: ActionResult = _execute_approve(entry.terminal_id, backend)

    if not result.success:
        print(f"Cannot approve '{name}': {result.message}", file=sys.stderr)
        sys.exit(1)

    print(f"Approved: {name}")
