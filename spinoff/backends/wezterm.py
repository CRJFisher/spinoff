"""WezTerm terminal backend.

Implements TerminalBackend using WezTerm's CLI. Each project gets its
own WezTerm workspace, with worktrees as tabs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


class WezTermBackend:
    """WezTerm implementation of the TerminalBackend protocol."""

    # ── Protocol: availability ───────────────────────────────────────

    def available(self) -> bool:
        """Check if WezTerm CLI is in PATH and a GUI instance is running."""
        if not self._cli_exists():
            return False
        result = subprocess.run(
            ["wezterm", "cli", "list-clients"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    # ── Protocol: workspace lifecycle ────────────────────────────────

    def create_workspace(
        self,
        title: str,
        cwd: Path | None = None,
        command: list[str] | None = None,
        project_name: str | None = None,
    ) -> tuple[bool, str | None, str]:
        """Create a new WezTerm tab with optional command.

        If project_name is specified (maps to WezTerm workspace):
        - If a window exists for that workspace, adds a tab to it
        - If no window exists, creates a new window with that workspace name
        """
        if not self._cli_exists():
            return False, None, "Error: WezTerm CLI not available"

        # If WezTerm is not running, start it with our command directly
        if not self.available():
            success, terminal_id, msg = self._start_with_command(
                cwd, command, project_name,
            )
            if success and terminal_id:
                self.set_title(terminal_id, title)
            return success, terminal_id, msg

        # WezTerm is running -- spawn a new tab/window
        window_id: str | None = None
        if project_name:
            window_id = self._get_project_window_id(project_name)

        spawn_cmd = ["wezterm", "cli", "spawn"]

        if window_id:
            spawn_cmd.extend(["--window-id", window_id])
        elif project_name:
            spawn_cmd.extend(["--new-window", "--workspace", project_name])

        if cwd:
            spawn_cmd.extend(["--cwd", str(cwd.resolve())])

        if command:
            spawn_cmd.append("--")
            spawn_cmd.extend(command)

        result = subprocess.run(spawn_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return False, None, f"Error creating tab: {result.stderr}"

        terminal_id = result.stdout.strip()

        if terminal_id:
            self.set_title(terminal_id, title)

            if not self._verify_pane_alive(terminal_id):
                return (
                    False,
                    None,
                    "Tab died shortly after creation"
                    " \u2014 check the startup script for errors",
                )

            ok, msg = self.focus_workspace(terminal_id)
            if not ok:
                print(f"  {msg}", file=sys.stderr)

        return True, terminal_id, f"Created tab '{title}' (pane {terminal_id})"

    def close_workspace(self, terminal_id: str) -> tuple[bool, str]:
        """Close a WezTerm tab/pane by its ID."""
        if not self.available():
            return False, "Error: WezTerm is not running or CLI not available"

        result = subprocess.run(
            ["wezterm", "cli", "kill-pane", "--pane-id", terminal_id],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            if (
                "no pane" in result.stderr.lower()
                or "invalid" in result.stderr.lower()
            ):
                return True, f"Pane {terminal_id} already closed"
            return False, f"Error closing tab: {result.stderr}"

        return True, f"Closed tab (pane {terminal_id})"

    def workspace_exists(self, terminal_id: str) -> bool:
        """Check if a pane with the given ID exists."""
        workspaces = self.list_workspaces()
        return any(
            w.get("terminal_id") == str(terminal_id) for w in workspaces
        )

    # ── Protocol: metadata ───────────────────────────────────────────

    def set_title(self, terminal_id: str, title: str) -> tuple[bool, str]:
        """Set the title of a WezTerm tab."""
        if not self.available():
            return False, "Error: WezTerm is not running or CLI not available"

        result = subprocess.run(
            ["wezterm", "cli", "set-tab-title", "--pane-id", terminal_id, title],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return False, f"Error setting title: {result.stderr}"

        return True, f"Set tab title to '{title}'"

    def focus_workspace(self, terminal_id: str) -> tuple[bool, str]:
        """Activate (focus) a WezTerm pane."""
        result = subprocess.run(
            ["wezterm", "cli", "activate-pane", "--pane-id", str(terminal_id)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return (
                False,
                f"Warning: Could not activate pane {terminal_id}:"
                f" {result.stderr.strip()}",
            )
        return True, f"Activated pane {terminal_id}"

    def list_workspaces(self) -> list[dict[str, str]]:
        """List all WezTerm panes, normalized to backend-neutral keys."""
        if not self.available():
            return []

        result = subprocess.run(
            ["wezterm", "cli", "list", "--format", "json"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return []

        try:
            raw_panes: list[dict[str, object]] = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return []

        normalized: list[dict[str, str]] = []
        for pane in raw_panes:
            normalized.append(
                {
                    "terminal_id": str(pane.get("pane_id", "")),
                    "title": str(pane.get("title", "")),
                    "cwd": str(pane.get("cwd", "")),
                    "workspace": str(pane.get("workspace", "")),
                    "window_id": str(pane.get("window_id", "")),
                }
            )
        return normalized

    # ── Protocol: cmux-only (no-ops) ─────────────────────────────────

    def read_screen(
        self, terminal_id: str, scrollback: bool = False,
    ) -> str | None:
        """Not supported by WezTerm backend."""
        return None

    def send_keys(self, terminal_id: str, keys: str) -> tuple[bool, str]:
        """Not supported by WezTerm backend."""
        return False, "Not supported by WezTerm backend"

    def notify(self, title: str, body: str) -> tuple[bool, str]:
        """Not supported by WezTerm backend."""
        return False, "Not supported by WezTerm backend"

    def set_sidebar_status(
        self, workspace_id: str, status: str,
    ) -> tuple[bool, str]:
        """Not supported by WezTerm backend."""
        return False, "Not supported by WezTerm backend"

    def set_sidebar_progress(
        self, workspace_id: str, progress: int,
    ) -> tuple[bool, str]:
        """Not supported by WezTerm backend."""
        return False, "Not supported by WezTerm backend"

    # ── Private helpers ──────────────────────────────────────────────

    def _cli_exists(self) -> bool:
        """Check if the wezterm binary is in PATH."""
        return shutil.which("wezterm") is not None

    def _start_with_command(
        self,
        cwd: Path | None = None,
        command: list[str] | None = None,
        workspace: str | None = None,
    ) -> tuple[bool, str | None, str]:
        """Start WezTerm with a specific command (when not running)."""
        start_cmd = ["wezterm", "start"]

        if workspace:
            start_cmd.extend(["--workspace", workspace])

        if cwd:
            start_cmd.extend(["--cwd", str(cwd.resolve())])

        if command:
            start_cmd.append("--")
            start_cmd.extend(command)

        subprocess.Popen(
            start_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for WezTerm to be ready and get pane ID
        for _ in range(50):  # Wait up to 5 seconds
            time.sleep(0.1)
            list_result = subprocess.run(
                ["wezterm", "cli", "list", "--format", "json"],
                capture_output=True,
                text=True,
            )
            if list_result.returncode == 0:
                try:
                    panes = json.loads(list_result.stdout)
                    if panes:
                        terminal_id = str(panes[0].get("pane_id"))

                        if not self._verify_pane_alive(terminal_id):
                            return (
                                False,
                                None,
                                "Tab died shortly after creation"
                                " \u2014 check the startup script for errors",
                            )

                        ok, msg = self.focus_workspace(terminal_id)
                        if not ok:
                            print(f"  {msg}", file=sys.stderr)

                        return (
                            True,
                            terminal_id,
                            f"Started WezTerm (pane {terminal_id})",
                        )
                except (json.JSONDecodeError, ValueError):
                    pass

        return True, None, "Started WezTerm but couldn't get pane ID"

    def _get_project_window_id(self, workspace_name: str) -> str | None:
        """Get the window ID for a project's workspace, if it exists."""
        result = subprocess.run(
            ["wezterm", "cli", "list", "--format", "json"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None

        try:
            panes: list[dict[str, object]] = json.loads(result.stdout)
            for pane in panes:
                if pane.get("workspace") == workspace_name:
                    return str(pane.get("window_id"))
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    def _verify_pane_alive(self, terminal_id: str, delay: float = 1.5) -> bool:
        """Wait briefly then check if a pane is still alive."""
        time.sleep(delay)
        return self.workspace_exists(terminal_id)
