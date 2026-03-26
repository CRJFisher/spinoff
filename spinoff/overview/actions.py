"""Action dispatch: browser-to-Python bridge for the overview dashboard."""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from spinoff.config import SpinoffConfig
from spinoff.screen import AgentState, ScreenSnapshot, classify, strip_ansi
from spinoff.state import WorktreeState, save_state
from spinoff.terminal import TerminalBackend

from spinoff.overview.security import is_safe_to_approve

ACTIONS_FILENAME = ".overview-actions.json"
STALENESS_THRESHOLD_SECS: float = 30.0

ALLOWED_ACTIONS: frozenset[str] = frozenset({
    "focus", "approve", "reject", "interrupt", "kill", "approve_all",
})


@dataclass
class ActionRequest:
    """A parsed action from the browser bridge."""
    action: str
    surface_id: str
    timestamp: float


@dataclass
class ActionResult:
    """Outcome of executing an action."""
    success: bool
    action: str
    surface_id: str
    message: str


def get_actions_file_path(project_path: Path, worktree_dir: str) -> Path:
    """Return path to the action bridge file."""
    return project_path / worktree_dir / ACTIONS_FILENAME


def read_action(actions_path: Path) -> Optional[ActionRequest]:
    """Read and parse the action file. Returns None if absent or invalid."""
    if not actions_path.exists():
        return None
    try:
        raw = actions_path.read_text()
        if not raw.strip():
            return None
        data = json.loads(raw)
        return ActionRequest(
            action=data["action"],
            surface_id=data["surface_id"],
            timestamp=data["timestamp"],
        )
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def validate_action(
    request: ActionRequest,
    valid_surface_ids: frozenset[str],
) -> tuple[bool, str]:
    """Validate an action request. Returns (ok, reason)."""
    if request.action not in ALLOWED_ACTIONS:
        return False, f"Unknown action: {request.action}"

    if request.action != "approve_all" and request.surface_id not in valid_surface_ids:
        return False, f"Unknown surface: {request.surface_id}"

    age = time.time() - request.timestamp
    if age > STALENESS_THRESHOLD_SECS:
        return False, f"Stale action ({age:.0f}s old)"

    return True, ""


def consume_action(actions_path: Path) -> None:
    """Delete the action file."""
    actions_path.unlink(missing_ok=True)


def dispatch_action(
    request: ActionRequest,
    backend: TerminalBackend,
    state: WorktreeState,
    project_path: Path,
    config: SpinoffConfig,
) -> ActionResult:
    """Execute a validated action."""
    action = request.action
    sid = request.surface_id

    if action == "focus":
        ok, msg = backend.focus_workspace(sid)
        return ActionResult(ok, action, sid, msg)

    if action == "approve":
        return _execute_approve(sid, backend)

    if action == "reject":
        backend.send_keys(sid, "n")
        backend.send_keys(sid, "enter")
        return ActionResult(True, action, sid, "Rejected")

    if action == "interrupt":
        ok, msg = backend.send_keys(sid, "ctrl-c")
        return ActionResult(ok, action, sid, msg)

    if action == "kill":
        ok, msg = backend.close_workspace(sid)
        return ActionResult(ok, action, sid, msg)

    if action == "approve_all":
        return _execute_approve_all(backend, state)

    return ActionResult(False, action, sid, f"Unhandled action: {action}")


def _execute_approve(surface_id: str, backend: TerminalBackend) -> ActionResult:
    """Approve a single agent's permission prompt with safety check."""
    screen_text = backend.read_screen(surface_id)
    if screen_text is None:
        return ActionResult(False, "approve", surface_id, "Surface unreachable")

    safe, reason = is_safe_to_approve(screen_text)
    if not safe:
        return ActionResult(False, "approve", surface_id, f"Blocked: {reason}")

    backend.send_keys(surface_id, "y")
    backend.send_keys(surface_id, "enter")
    return ActionResult(True, "approve", surface_id, "Approved")


def _execute_approve_all(
    backend: TerminalBackend,
    state: WorktreeState,
) -> ActionResult:
    """Approve all WAITING agents that pass the safety filter."""
    approved: list[str] = []
    skipped: list[str] = []

    for wt in state.worktrees:
        if wt.terminal_id is None:
            continue

        screen_text = backend.read_screen(wt.terminal_id)
        if screen_text is None:
            continue

        snap = ScreenSnapshot(
            surface_id=wt.terminal_id,
            text=screen_text,
            captured_at=time.monotonic(),
        )
        status = classify(snap)
        if status.state != AgentState.WAITING_APPROVAL:
            continue

        safe, reason = is_safe_to_approve(screen_text)
        if not safe:
            skipped.append(f"{wt.name} ({reason})")
            continue

        backend.send_keys(wt.terminal_id, "y")
        backend.send_keys(wt.terminal_id, "enter")
        approved.append(wt.name)

    parts: list[str] = []
    if approved:
        parts.append(f"Approved: {', '.join(approved)}")
    if skipped:
        parts.append(f"Skipped: {', '.join(skipped)}")
    if not parts:
        parts.append("No agents waiting for approval")

    return ActionResult(True, "approve_all", "", ". ".join(parts))


def poll_and_dispatch_action(
    project_path: Path,
    config: SpinoffConfig,
    backend: TerminalBackend,
    state: WorktreeState,
) -> Optional[ActionResult]:
    """Read, validate, and dispatch one action. Returns None if no action pending."""
    actions_path = get_actions_file_path(project_path, config.worktree_dir)
    request = read_action(actions_path)
    if request is None:
        return None

    valid_surfaces = frozenset(
        wt.terminal_id for wt in state.worktrees if wt.terminal_id
    )
    ok, reason = validate_action(request, valid_surfaces)

    try:
        if not ok:
            return ActionResult(False, request.action, request.surface_id, reason)
        return dispatch_action(request, backend, state, project_path, config)
    finally:
        consume_action(actions_path)
