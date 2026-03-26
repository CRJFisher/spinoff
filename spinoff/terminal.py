"""Protocol definition for terminal multiplexer backends."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TerminalBackend(Protocol):
    """Protocol for terminal multiplexer backends.

    Defines the interface that concrete backends (WezTerm, cmux) must
    implement to manage terminal workspaces. Each workspace is identified
    by a backend-specific ``terminal_id`` string (a WezTerm pane ID or
    a cmux workspace UUID).

    Methods fall into two categories:
    - Core workspace management (available, create, close, exists, title, focus, list)
    - Extended capabilities (read_screen, send_keys, notify, sidebar status/progress)

    Extended methods are fully supported by cmux. The WezTerm backend returns
    harmless no-op values (None or (False, "not supported")) so callers never
    need isinstance checks.
    """

    def available(self) -> bool:
        """Check whether the backend is installed and reachable."""
        ...

    def create_workspace(
        self,
        title: str,
        cwd: Path | None,
        command: list[str] | None,
        project_name: str | None,
    ) -> tuple[bool, str | None, str]:
        """Create a new terminal workspace.

        Args:
            title: Human-readable title for the workspace.
            cwd: Working directory, or None for the default.
            command: Initial command to execute, or None for a shell.
            project_name: Project name for grouping workspaces.

        Returns:
            (success, terminal_id or None on failure, message).
        """
        ...

    def close_workspace(self, terminal_id: str) -> tuple[bool, str]:
        """Close an existing workspace.

        Closing an already-closed workspace succeeds silently.
        """
        ...

    def workspace_exists(self, terminal_id: str) -> bool:
        """Check whether a workspace with the given id still exists."""
        ...

    def set_title(self, terminal_id: str, title: str) -> tuple[bool, str]:
        """Set the display title of a workspace."""
        ...

    def focus_workspace(self, terminal_id: str) -> tuple[bool, str]:
        """Bring a workspace into focus (select/activate it)."""
        ...

    def list_workspaces(self) -> list[dict[str, str]]:
        """List all workspaces managed by the backend.

        Returns a list of dicts with at least ``"terminal_id"`` and
        ``"title"`` keys. Backends may include additional keys.
        """
        ...

    # ------------------------------------------------------------------
    # Extended capabilities (cmux-only)
    # ------------------------------------------------------------------

    def read_screen(
        self, terminal_id: str, scrollback: bool = False,
    ) -> str | None:
        """Capture screen content. Returns None if unsupported."""
        ...

    def send_keys(self, terminal_id: str, keys: str) -> tuple[bool, str]:
        """Send keystrokes to a workspace."""
        ...

    def notify(self, title: str, body: str) -> tuple[bool, str]:
        """Display a desktop notification via the terminal backend."""
        ...

    def set_sidebar_status(
        self, terminal_id: str, status: str,
    ) -> tuple[bool, str]:
        """Update the sidebar status indicator for a workspace."""
        ...

    def set_sidebar_progress(
        self, terminal_id: str, progress: int,
    ) -> tuple[bool, str]:
        """Update the sidebar progress indicator for a workspace."""
        ...
