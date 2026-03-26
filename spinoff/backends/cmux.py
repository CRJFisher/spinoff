"""cmux terminal backend.

Implements TerminalBackend for cmux, a native macOS terminal with
agent-specific features: read-screen, notifications, sidebar metadata.

Terminology mapping (WezTerm -> cmux):
  Window    -> Window     (top-level OS window)
  Tab       -> Workspace  (sidebar entry)
  Pane      -> Surface    (individual terminal session)

All operations go through the cmux CLI.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path


class CmuxBackend:
    """TerminalBackend implementation using the cmux CLI."""

    def _run(
        self,
        args: list[str],
        *,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Run a cmux CLI command and return the CompletedProcess."""
        return subprocess.run(
            ["cmux", *args],
            capture_output=True,
            text=True,
            check=check,
        )

    def _get_window_id(self) -> str | None:
        """Resolve the cmux window ID for the calling terminal.

        Uses ``cmux identify --json`` which returns the caller's context
        including window_id. Returns None if called from outside cmux.
        """
        result = self._run(["identify", "--json"])
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

    # ------------------------------------------------------------------
    # TerminalBackend protocol
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Check if cmux CLI is in PATH and a cmux instance is running."""
        if shutil.which("cmux") is None:
            return False
        result = self._run(["ping"])
        return result.returncode == 0

    def create_workspace(
        self,
        title: str,
        cwd: Path | None,
        command: list[str] | None,
        project_name: str | None,
    ) -> tuple[bool, str | None, str]:
        """Create a new cmux workspace.

        Flow:
        1. ``cmux identify --json`` to get caller.window_id
        2. ``cmux [--window <id>] new-workspace [--cwd <path>]``
        3. ``cmux rename-workspace --workspace <new_id> <title>``
        4. If command: ``cmux send --workspace <new_id> <command>``
        """
        window_id = self._get_window_id()

        # Build new-workspace command
        new_cmd: list[str] = []
        if window_id is not None:
            new_cmd.extend(["--window", window_id])
        new_cmd.append("new-workspace")
        if cwd is not None:
            new_cmd.extend(["--cwd", str(cwd.resolve())])

        result = self._run(new_cmd)
        if result.returncode != 0:
            return False, None, f"Error creating workspace: {result.stderr.strip()}"

        # Parse workspace ID from output
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

        # Rename the workspace
        self._run(["rename-workspace", "--workspace", workspace_id, title])

        # Send startup command if provided
        if command:
            command_str = " ".join(shlex.quote(c) for c in command)
            self._run(["send", "--workspace", workspace_id, command_str])

        return True, workspace_id, f"Created workspace '{title}' ({workspace_id})"

    def close_workspace(self, terminal_id: str) -> tuple[bool, str]:
        """Close a cmux workspace by closing its surface."""
        result = self._run(["close-surface", "--surface", terminal_id])
        if result.returncode != 0:
            stderr = result.stderr.strip().lower()
            if "not found" in stderr or "invalid" in stderr or "no surface" in stderr:
                return True, f"Surface {terminal_id} already closed"
            return False, f"Error closing workspace: {result.stderr.strip()}"
        return True, f"Closed workspace (surface {terminal_id})"

    def workspace_exists(self, terminal_id: str) -> bool:
        """Check if a workspace with the given ID exists."""
        workspaces = self.list_workspaces()
        return any(ws.get("terminal_id") == terminal_id for ws in workspaces)

    def set_title(self, terminal_id: str, title: str) -> tuple[bool, str]:
        """Set the sidebar title of a cmux workspace."""
        result = self._run([
            "rename-workspace", "--workspace", terminal_id, title,
        ])
        if result.returncode != 0:
            return False, f"Error setting title: {result.stderr.strip()}"
        return True, f"Set workspace title to '{title}'"

    def focus_workspace(self, terminal_id: str) -> tuple[bool, str]:
        """Focus (select) a cmux workspace in the sidebar."""
        result = self._run(["select-workspace", "--workspace", terminal_id])
        if result.returncode != 0:
            return False, f"Error focusing workspace: {result.stderr.strip()}"
        return True, f"Focused workspace {terminal_id}"

    def list_workspaces(self) -> list[dict[str, str]]:
        """List all cmux workspaces in the current window, normalized."""
        cmd: list[str] = ["--json", "list-workspaces"]
        window_id = self._get_window_id()
        if window_id is not None:
            cmd = ["--json", "--window", window_id, "list-workspaces"]
        result = self._run(cmd)
        if result.returncode != 0:
            return []
        try:
            data = json.loads(result.stdout)
            if isinstance(data, list):
                normalized: list[dict[str, str]] = []
                for ws in data:
                    normalized.append({
                        "terminal_id": str(ws.get("id", "")),
                        "title": str(ws.get("title", "")),
                        "selected": str(ws.get("selected", "")),
                        "cwd": str(ws.get("current_directory", "")),
                    })
                return normalized
        except (json.JSONDecodeError, ValueError):
            pass
        return []

    def read_screen(
        self, terminal_id: str, scrollback: bool = False,
    ) -> str | None:
        """Read the visible terminal content of a cmux surface."""
        cmd = ["read-screen", "--surface", terminal_id]
        if scrollback:
            cmd.append("--scrollback")
        result = self._run(cmd)
        if result.returncode != 0:
            return None
        return result.stdout

    def send_keys(self, terminal_id: str, keys: str) -> tuple[bool, str]:
        """Send a keystroke to a cmux surface."""
        result = self._run(["send-key", "--surface", terminal_id, keys])
        if result.returncode != 0:
            return False, f"Error sending keys: {result.stderr.strip()}"
        return True, f"Sent key '{keys}' to surface {terminal_id}"

    def notify(self, title: str, body: str) -> tuple[bool, str]:
        """Show a desktop notification via cmux."""
        result = self._run(["notify", "--title", title, "--body", body])
        if result.returncode != 0:
            return False, f"Error sending notification: {result.stderr.strip()}"
        return True, "Notification sent"

    def set_sidebar_status(
        self, terminal_id: str, status: str,
    ) -> tuple[bool, str]:
        """Set the sidebar status text for a cmux workspace."""
        result = self._run([
            "set-status", "--workspace", terminal_id, status,
        ])
        if result.returncode != 0:
            return False, f"Error setting status: {result.stderr.strip()}"
        return True, f"Set status to '{status}'"

    def set_sidebar_progress(
        self, terminal_id: str, progress: int,
    ) -> tuple[bool, str]:
        """Set the sidebar progress bar for a cmux workspace."""
        result = self._run([
            "set-progress", "--workspace", terminal_id, str(progress),
        ])
        if result.returncode != 0:
            return False, f"Error setting progress: {result.stderr.strip()}"
        return True, f"Set progress to {progress}"
