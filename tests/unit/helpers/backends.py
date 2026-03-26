"""Test doubles for TerminalBackend."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class FakeBackend:
    """Deterministic TerminalBackend that replays canned screen content."""

    def __init__(self) -> None:
        self._screens: dict[str, list[str]] = {}
        self._workspaces: dict[str, dict[str, str]] = {}
        self.notifications: list[tuple[str, str]] = []
        self.sidebar_status: dict[str, str] = {}
        self.sidebar_progress: dict[str, int] = {}
        self._next_id = 1

    def set_screen_sequence(self, surface_id: str, screens: list[str]) -> None:
        """Queue screen responses for read_screen calls."""
        self._screens[surface_id] = list(screens)

    def add_workspace(self, terminal_id: str, title: str = "", selected: bool = False) -> None:
        self._workspaces[terminal_id] = {
            "terminal_id": terminal_id,
            "title": title,
            "selected": str(selected),
        }

    def available(self) -> bool:
        return True

    def create_workspace(
        self, title: str, cwd: Path | None,
        command: list[str] | None, project_name: str | None,
    ) -> tuple[bool, str | None, str]:
        ws_id = f"ws-{self._next_id}"
        self._next_id += 1
        self._workspaces[ws_id] = {"terminal_id": ws_id, "title": title, "selected": "false"}
        return True, ws_id, f"Created {ws_id}"

    def close_workspace(self, terminal_id: str) -> tuple[bool, str]:
        self._workspaces.pop(terminal_id, None)
        return True, f"Closed {terminal_id}"

    def workspace_exists(self, terminal_id: str) -> bool:
        return terminal_id in self._workspaces

    def set_title(self, terminal_id: str, title: str) -> tuple[bool, str]:
        if terminal_id in self._workspaces:
            self._workspaces[terminal_id]["title"] = title
        return True, "ok"

    def focus_workspace(self, terminal_id: str) -> tuple[bool, str]:
        return True, f"Focused {terminal_id}"

    def list_workspaces(self) -> list[dict[str, str]]:
        return list(self._workspaces.values())

    def read_screen(self, terminal_id: str, scrollback: bool = False) -> str | None:
        queue = self._screens.get(terminal_id)
        if not queue:
            return None
        if len(queue) > 1:
            return queue.pop(0)
        return queue[0]  # Repeat last

    def send_keys(self, terminal_id: str, keys: str) -> tuple[bool, str]:
        return True, f"Sent {keys}"

    def notify(self, title: str, body: str) -> tuple[bool, str]:
        self.notifications.append((title, body))
        return True, "Notified"

    def set_sidebar_status(self, terminal_id: str, status: str) -> tuple[bool, str]:
        self.sidebar_status[terminal_id] = status
        return True, "ok"

    def set_sidebar_progress(self, terminal_id: str, progress: int) -> tuple[bool, str]:
        self.sidebar_progress[terminal_id] = progress
        return True, "ok"


@dataclass
class BackendCall:
    method: str
    args: tuple[object, ...]
    kwargs: dict[str, object] = field(default_factory=dict)


class SpyBackend:
    """TerminalBackend that records all calls for assertion."""

    def __init__(self) -> None:
        self.calls: list[BackendCall] = []
        self._screens: dict[str, str] = {}
        self._workspaces: dict[str, dict[str, str]] = {}

    def set_current_screen(self, surface_id: str, text: str) -> None:
        self._screens[surface_id] = text

    def get_calls(self, method: str) -> list[BackendCall]:
        return [c for c in self.calls if c.method == method]

    def available(self) -> bool:
        return True

    def create_workspace(
        self, title: str, cwd: Path | None,
        command: list[str] | None, project_name: str | None,
    ) -> tuple[bool, str | None, str]:
        self.calls.append(BackendCall("create_workspace", (title, cwd, command, project_name)))
        return True, "ws-new", "Created"

    def close_workspace(self, terminal_id: str) -> tuple[bool, str]:
        self.calls.append(BackendCall("close_workspace", (terminal_id,)))
        return True, "Closed"

    def workspace_exists(self, terminal_id: str) -> bool:
        return terminal_id in self._workspaces

    def set_title(self, terminal_id: str, title: str) -> tuple[bool, str]:
        self.calls.append(BackendCall("set_title", (terminal_id, title)))
        return True, "ok"

    def focus_workspace(self, terminal_id: str) -> tuple[bool, str]:
        self.calls.append(BackendCall("focus_workspace", (terminal_id,)))
        return True, "ok"

    def list_workspaces(self) -> list[dict[str, str]]:
        return list(self._workspaces.values())

    def read_screen(self, terminal_id: str, scrollback: bool = False) -> str | None:
        self.calls.append(BackendCall("read_screen", (terminal_id,)))
        return self._screens.get(terminal_id)

    def send_keys(self, terminal_id: str, keys: str) -> tuple[bool, str]:
        self.calls.append(BackendCall("send_keys", (terminal_id, keys)))
        return True, "ok"

    def notify(self, title: str, body: str) -> tuple[bool, str]:
        self.calls.append(BackendCall("notify", (title, body)))
        return True, "ok"

    def set_sidebar_status(self, terminal_id: str, status: str) -> tuple[bool, str]:
        self.calls.append(BackendCall("set_sidebar_status", (terminal_id, status)))
        return True, "ok"

    def set_sidebar_progress(self, terminal_id: str, progress: int) -> tuple[bool, str]:
        self.calls.append(BackendCall("set_sidebar_progress", (terminal_id, progress)))
        return True, "ok"
