"""cmux terminal interface.

All spinoff terminal operations (screen reading, notifications, sidebar
metadata, workspace lifecycle) go through the cmux CLI.

cmux terminology:
  Window    — top-level OS window
  Workspace — sidebar entry
  Surface   — individual terminal session
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path


def _run_cmux(
    args: list[str],
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a cmux CLI command and return the result."""
    return subprocess.run(
        ["cmux", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _get_window_id() -> str | None:
    """Resolve the cmux window ID for the calling terminal.

    Uses ``cmux identify --json`` which returns the caller's context
    including window_id. Returns None if called from outside cmux.
    """
    result = _run_cmux(["identify", "--json"])
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        caller = data.get("caller")
        if caller is not None:
            return caller.get("window_id")
    except (json.JSONDecodeError, ValueError, AttributeError):
        pass
    return None


def available() -> bool:
    """Check if cmux CLI is in PATH and a cmux instance is running."""
    if shutil.which("cmux") is None:
        return False
    result = _run_cmux(["ping"])
    return result.returncode == 0


def create_workspace(
    title: str,
    cwd: Path | None,
    command: list[str] | None,
) -> tuple[bool, str | None, str]:
    """Create a new cmux workspace.

    Flow:
    1. ``cmux identify --json`` to get caller.window_id
    2. ``cmux [--window <id>] new-workspace [--cwd <path>]``
    3. ``cmux rename-workspace --workspace <new_id> <title>``
    4. If command: ``cmux send --workspace <new_id> <command>``
    """
    window_id = _get_window_id()

    new_cmd: list[str] = []
    if window_id is not None:
        new_cmd.extend(["--window", window_id])
    new_cmd.append("new-workspace")
    if cwd is not None:
        new_cmd.extend(["--cwd", str(cwd.resolve())])

    result = _run_cmux(new_cmd)
    if result.returncode != 0:
        return False, None, f"Error creating workspace: {result.stderr.strip()}"

    workspace_id: str | None = None
    stdout = result.stdout.strip()
    try:
        data = json.loads(stdout)
        workspace_id = data.get("id") or data.get("workspace_id")
    except (json.JSONDecodeError, ValueError, AttributeError):
        if stdout:
            workspace_id = stdout

    if not workspace_id:
        return False, None, "Created workspace but could not determine its ID"

    rename_result = _run_cmux(["rename-workspace", "--workspace", workspace_id, title])
    if rename_result.returncode != 0:
        return False, workspace_id, f"Workspace created but rename failed: {rename_result.stderr.strip()}"

    if command:
        command_str = " ".join(shlex.quote(c) for c in command)
        send_result = _run_cmux(["send", "--workspace", workspace_id, command_str])
        if send_result.returncode != 0:
            return False, workspace_id, f"Workspace created but send failed: {send_result.stderr.strip()}"

    return True, workspace_id, f"Created workspace '{title}' ({workspace_id})"


def close_workspace(terminal_id: str) -> tuple[bool, str]:
    """Close a cmux workspace by closing its surface."""
    result = _run_cmux(["close-surface", "--surface", terminal_id])
    if result.returncode != 0:
        stderr = result.stderr.strip().lower()
        if "not found" in stderr or "invalid" in stderr or "no surface" in stderr:
            return True, f"Surface {terminal_id} already closed"
        return False, f"Error closing workspace: {result.stderr.strip()}"
    return True, f"Closed workspace (surface {terminal_id})"


def workspace_exists(terminal_id: str) -> bool:
    """Check if a workspace with the given ID exists."""
    workspaces = list_workspaces()
    return any(ws.get("terminal_id") == terminal_id for ws in workspaces)


def set_title(terminal_id: str, title: str) -> tuple[bool, str]:
    """Set the sidebar title of a cmux workspace."""
    result = _run_cmux([
        "rename-workspace", "--workspace", terminal_id, title,
    ])
    if result.returncode != 0:
        return False, f"Error setting title: {result.stderr.strip()}"
    return True, f"Set workspace title to '{title}'"


def focus_workspace(terminal_id: str) -> tuple[bool, str]:
    """Focus (select) a cmux workspace in the sidebar."""
    result = _run_cmux(["select-workspace", "--workspace", terminal_id])
    if result.returncode != 0:
        return False, f"Error focusing workspace: {result.stderr.strip()}"
    return True, f"Focused workspace {terminal_id}"


def list_workspaces() -> list[dict[str, object]]:
    """List all cmux workspaces in the current window, normalized."""
    cmd: list[str] = ["--json", "list-workspaces"]
    window_id = _get_window_id()
    if window_id is not None:
        cmd = ["--json", "--window", window_id, "list-workspaces"]
    result = _run_cmux(cmd)
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        if isinstance(data, list):
            normalized: list[dict[str, object]] = []
            for ws in data:
                raw_selected = ws.get("selected", "")
                normalized.append({
                    "terminal_id": str(ws.get("id", "")),
                    "title": str(ws.get("title", "")),
                    "selected": str(raw_selected).lower() in ("true", "1"),
                    "cwd": str(ws.get("current_directory", "")),
                })
            return normalized
    except (json.JSONDecodeError, ValueError):
        pass
    return []


def read_screen(
    terminal_id: str, scrollback: bool = False,
) -> str | None:
    """Read the visible terminal content of a cmux surface."""
    cmd = ["read-screen", "--surface", terminal_id]
    if scrollback:
        cmd.append("--scrollback")
    result = _run_cmux(cmd)
    if result.returncode != 0:
        return None
    return result.stdout


def send_keys(terminal_id: str, keys: str) -> tuple[bool, str]:
    """Send a keystroke to a cmux surface."""
    result = _run_cmux(["send-key", "--surface", terminal_id, keys])
    if result.returncode != 0:
        return False, f"Error sending keys: {result.stderr.strip()}"
    return True, f"Sent key '{keys}' to surface {terminal_id}"


def notify(title: str, body: str) -> tuple[bool, str]:
    """Show a desktop notification via cmux."""
    result = _run_cmux(["notify", "--title", title, "--body", body])
    if result.returncode != 0:
        return False, f"Error sending notification: {result.stderr.strip()}"
    return True, "Notification sent"


def set_sidebar_status(
    terminal_id: str, status: str,
) -> tuple[bool, str]:
    """Set the sidebar status text for a cmux workspace."""
    result = _run_cmux([
        "set-status", "--workspace", terminal_id, status,
    ])
    if result.returncode != 0:
        return False, f"Error setting status: {result.stderr.strip()}"
    return True, f"Set status to '{status}'"


def set_sidebar_progress(
    terminal_id: str, progress: int,
) -> tuple[bool, str]:
    """Set the sidebar progress bar for a cmux workspace."""
    result = _run_cmux([
        "set-progress", "--workspace", terminal_id, str(progress),
    ])
    if result.returncode != 0:
        return False, f"Error setting progress: {result.stderr.strip()}"
    return True, f"Set progress to {progress}"
