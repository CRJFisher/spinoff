"""
Spinoff Overview Panel

Manages the overview dashboard: a cmux workspace with a poller that monitors
agent status via read-screen, updates sidebar metadata, sends desktop
notifications, and generates an HTML dashboard.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import spinoff.cmux as cmux
from spinoff.config import SpinoffConfig, load_config
from spinoff.state import OverviewInfo, load_state, save_state


def ensure_cache_dir(project_name: str) -> Path:
    """Return the cache directory for overview files, creating if needed.

    Sanitizes project_name to prevent path traversal.
    """
    safe_name = project_name.replace("/", "-").replace("..", "-").replace("\\", "-")
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    cache_dir = base / "spinoff" / safe_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def open_overview(project_path: Path, config: Optional[SpinoffConfig] = None) -> tuple[bool, str]:
    """Open or focus the overview panel. Idempotent."""
    if config is None:
        config = load_config(project_path)

    if not cmux.available():
        return False, "cmux not available"

    state = load_state(project_path)

    if state.overview is not None:
        if cmux.workspace_exists(state.overview.workspace_id):
            cmux.focus_workspace(state.overview.workspace_id)
            return True, "Overview panel focused"

    poller_cmd = [
        sys.executable, "-m", "spinoff.overview", "watch",
        "--project", str(project_path),
    ]
    success, workspace_id, msg = cmux.create_workspace(
        title=f"spinoff-overview-{config.project_name}",
        cwd=project_path,
        command=poller_cmd,
    )
    if not success or workspace_id is None:
        return False, f"Failed to create overview workspace: {msg}"

    state.overview = OverviewInfo(
        workspace_id=workspace_id,
        surface_id=workspace_id,
    )
    save_state(project_path, state)

    return True, f"Overview panel started ({workspace_id})"


def close_overview(project_path: Path) -> tuple[bool, str]:
    """Stop the overview poller and close its workspace."""
    state = load_state(project_path)

    if state.overview is None:
        return True, "Overview not running"

    ok, msg = cmux.close_workspace(state.overview.workspace_id)
    state.overview = None
    save_state(project_path, state)

    if not ok:
        return False, f"Overview state cleared but workspace close failed: {msg}"
    return True, "Overview panel closed"
