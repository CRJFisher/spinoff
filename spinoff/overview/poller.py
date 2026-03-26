"""Overview poller: monitors agent screens and dispatches notifications."""

import json
import logging
import os
import signal
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType
from typing import Optional

from spinoff.backends import get_backend
from spinoff.config import NotificationConfig, SpinoffConfig, load_config
from spinoff.screen import AgentState, AgentStatus, PollScheduler, ScreenSnapshot, classify
from spinoff.state import WorktreeEntry, WorktreeState, load_state, save_state
from spinoff.terminal import TerminalBackend

from spinoff.overview import get_cache_dir
from spinoff.overview.actions import poll_and_dispatch_action
from spinoff.overview.renderer import AgentSnapshot, OverviewData, render_overview
from spinoff.overview.security import redact_secrets

logger = logging.getLogger("spinoff.overview.poller")


@dataclass
class NotificationCooldown:
    """Per-workspace notification rate limiting."""
    last_urgent: float = 0.0
    last_info: float = 0.0

    def can_send_urgent(self, now: float, cooldown_secs: int) -> bool:
        return (now - self.last_urgent) >= cooldown_secs

    def can_send_info(self, now: float, cooldown_secs: int) -> bool:
        return (now - self.last_info) >= cooldown_secs


@dataclass
class DoneBatch:
    """Accumulates DONE transitions for batched notification."""
    names: list[str] = field(default_factory=list)
    first_seen: float = 0.0
    BATCH_WINDOW: float = 5.0

    def is_ready(self, now: float) -> bool:
        return bool(self.names) and (now - self.first_seen) >= self.BATCH_WINDOW


class OverviewPoller:
    """Polls agent screens and dispatches notifications + sidebar updates."""

    def __init__(
        self,
        project_path: Path,
        config: SpinoffConfig,
        backend: TerminalBackend,
    ) -> None:
        self._project_path = project_path
        self._config = config
        self._backend = backend
        self._scheduler = PollScheduler(
            override_interval=config.overview_poll_interval,
        )
        self._snapshots: dict[str, AgentSnapshot] = {}
        self._previous_states: dict[str, AgentState] = {}
        self._state_entered_at: dict[str, float] = {}
        self._cooldowns: dict[str, NotificationCooldown] = {}
        self._done_batch = DoneBatch()
        self._shutdown_requested = False
        self._focused_workspace: Optional[str] = None

        cache_dir = get_cache_dir(config.project_name)
        self._html_path = cache_dir / "overview.html"
        self._log_path = cache_dir / "overview.log"

    def run(self) -> None:
        """Main poll loop. Blocks until SIGTERM/SIGINT."""
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._log_event("poller_started", pid=os.getpid())
        logger.info("Overview poller started (pid=%d)", os.getpid())

        while not self._shutdown_requested:
            try:
                self._poll_cycle()
            except Exception:
                logger.exception("Error in poll cycle")
                self._log_event("cycle_error", error=traceback.format_exc()[:500])

            try:
                sleep_time = self._compute_sleep()
            except Exception:
                sleep_time = 1.0
            deadline = time.monotonic() + sleep_time
            while time.monotonic() < deadline and not self._shutdown_requested:
                time.sleep(min(0.25, deadline - time.monotonic()))

        self._flush_done_batch(force=True)
        self._log_event("poller_stopped")
        logger.info("Overview poller stopped")

    def _handle_signal(self, signum: int, frame: Optional[FrameType]) -> None:
        self._shutdown_requested = True

    def _poll_cycle(self) -> None:
        """One iteration of the poll loop."""
        state = self._load_agents()
        if state is None:
            return

        agents = [wt for wt in state.worktrees if wt.status == "active"]

        # Detect focused workspace
        self._update_focused_workspace()

        # Determine due surfaces
        surface_ids = [a.terminal_id for a in agents if a.terminal_id]
        due = set(self._scheduler.surfaces_due(surface_ids))

        # Prune removed worktrees
        active_names = {a.name for a in agents}
        for name in list(self._snapshots):
            if name not in active_names:
                snap = self._snapshots.pop(name)
                self._previous_states.pop(name, None)
                self._state_entered_at.pop(name, None)
                self._cooldowns.pop(name, None)
                if snap.surface_id:
                    self._scheduler.remove(snap.surface_id)

        # Read + classify due agents
        state_changed = False
        for entry in agents:
            if not entry.terminal_id or entry.terminal_id not in due:
                continue

            prev_state = self._previous_states.get(entry.name, AgentState.UNKNOWN)
            snapshot = self._read_and_classify(entry)
            if snapshot is not None:
                self._scheduler.record(entry.terminal_id, snapshot.phase)
                self._update_sidebar(snapshot)
                self._dispatch_notification(snapshot, prev_state)

                # Update last_status in state
                if entry.last_status != snapshot.phase.value:
                    entry.last_status = snapshot.phase.value
                    state_changed = True

        # Flush done batch
        self._flush_done_batch()

        # Write HTML
        self._write_html(list(self._snapshots.values()))

        # Process actions
        poll_and_dispatch_action(
            self._project_path, self._config, self._backend, state,
        )

        # Save state if last_status changed
        if state_changed:
            save_state(self._project_path, state)

    def _load_agents(self) -> Optional[WorktreeState]:
        """Load state, returning None on failure."""
        try:
            return load_state(self._project_path)
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            logger.warning("Failed to load state: %s", exc)
            return None

    def _read_and_classify(self, entry: WorktreeEntry) -> Optional[AgentSnapshot]:
        """Read screen and classify agent state."""
        assert entry.terminal_id is not None
        now = time.monotonic()

        screen_text = self._backend.read_screen(entry.terminal_id)
        if screen_text is None:
            prev = self._previous_states.get(entry.name, AgentState.UNKNOWN)
            snap = AgentSnapshot(
                worktree_name=entry.name,
                phase=AgentState.SHELL,
                surface_id=entry.terminal_id,
                snippet="Surface unreachable",
                error_message="",
                duration_secs=now - self._state_entered_at.get(entry.name, now),
                depends_on=entry.depends_on,
            )
            self._snapshots[entry.name] = snap
            self._track_state(entry.name, AgentState.SHELL, now)
            return snap

        status: AgentStatus = classify(ScreenSnapshot(
            surface_id=entry.terminal_id,
            text=screen_text,
            captured_at=now,
        ))

        entered = self._state_entered_at.get(entry.name, now)
        if self._previous_states.get(entry.name) != status.state:
            entered = now

        snap = AgentSnapshot(
            worktree_name=entry.name,
            phase=status.state,
            surface_id=entry.terminal_id,
            snippet=redact_secrets(status.summary),
            error_message=status.summary if status.state == AgentState.ERRORED else "",
            duration_secs=now - entered,
            depends_on=entry.depends_on,
        )
        self._snapshots[entry.name] = snap
        self._track_state(entry.name, status.state, now)
        return snap

    def _track_state(self, name: str, state: AgentState, now: float) -> None:
        """Track state transitions for notifications."""
        if self._previous_states.get(name) != state:
            self._state_entered_at[name] = now
        self._previous_states[name] = state

    def _update_focused_workspace(self) -> None:
        """Cache the currently focused workspace ID."""
        try:
            workspaces = self._backend.list_workspaces()
            for ws in workspaces:
                if ws.get("selected") in ("True", "true", "1"):
                    self._focused_workspace = ws.get("terminal_id")
                    return
            self._focused_workspace = None
        except Exception:
            self._focused_workspace = None

    def _update_sidebar(self, snapshot: AgentSnapshot) -> None:
        """Update sidebar status and progress for an agent."""
        label = _state_label(snapshot.phase)
        duration_str = _format_duration(int(snapshot.duration_secs))
        status_text = f"{label} [{duration_str}]"

        self._backend.set_sidebar_status(snapshot.surface_id or "", status_text)

        sid = snapshot.surface_id or ""
        if snapshot.phase in (AgentState.WORKING, AgentState.INITIALIZING, AgentState.WAITING_APPROVAL):
            self._backend.set_sidebar_progress(sid, -1)
        elif snapshot.phase in (AgentState.DONE, AgentState.SHELL, AgentState.ERRORED):
            self._backend.set_sidebar_progress(sid, 100)
        else:
            self._backend.set_sidebar_progress(sid, 0)

    def _dispatch_notification(self, snapshot: AgentSnapshot, prev_state: AgentState) -> None:
        """Send desktop notification on state transitions."""
        if prev_state == snapshot.phase:
            return

        now = time.monotonic()
        notif_config = self._config.notifications
        cooldown = self._cooldowns.setdefault(
            snapshot.worktree_name, NotificationCooldown(),
        )

        # Focus suppression
        if snapshot.surface_id == self._focused_workspace:
            return

        if snapshot.phase in (AgentState.WAITING_APPROVAL, AgentState.ERRORED):
            if not cooldown.can_send_urgent(now, notif_config.cooldown_urgent_secs):
                return
            if snapshot.phase == AgentState.WAITING_APPROVAL and not notif_config.on_waiting:
                return
            if snapshot.phase == AgentState.ERRORED and not notif_config.on_error:
                return
            if notif_config.desktop:
                title = f"spinoff: {snapshot.worktree_name}"
                body = snapshot.snippet[:100]
                self._backend.notify(title, body)
                cooldown.last_urgent = now
                self._log_event(
                    "notification_sent", name=snapshot.worktree_name,
                    tier="urgent", state=snapshot.phase.value,
                )

        elif snapshot.phase == AgentState.DONE:
            if notif_config.on_done:
                if not self._done_batch.names:
                    self._done_batch.first_seen = now
                self._done_batch.names.append(snapshot.worktree_name)

    def _flush_done_batch(self, force: bool = False) -> None:
        """Send batched DONE notification if the window has elapsed."""
        now = time.monotonic()
        if not self._done_batch.names:
            return
        if not force and not self._done_batch.is_ready(now):
            return

        names = list(self._done_batch.names)
        self._done_batch.names.clear()

        notif_config = self._config.notifications
        if not notif_config.desktop:
            return

        if len(names) == 1:
            body = f"{names[0]}: completed"
        else:
            body = f"{len(names)} agents done: {', '.join(names)}"

        self._backend.notify("Spinoff: Completed", body)

        for name in names:
            cd = self._cooldowns.setdefault(name, NotificationCooldown())
            cd.last_info = now

        self._log_event("notification_sent", tier="info", names=names)

    def _write_html(self, snapshots: list[AgentSnapshot]) -> None:
        """Generate and write the HTML dashboard."""
        try:
            data = OverviewData(
                project_name=self._config.project_name,
                agents=snapshots,
                generated_at=time.strftime("%H:%M:%S"),
                actions_file_path=str(
                    self._project_path / self._config.worktree_dir / ".overview-actions.json"
                ),
            )
            html_content = render_overview(data)
            temp = self._html_path.with_suffix(".tmp")
            temp.write_text(html_content)
            temp.rename(self._html_path)
        except OSError as exc:
            logger.warning("Failed to write HTML: %s", exc)

    def _compute_sleep(self) -> float:
        """Compute sleep duration before next cycle."""
        if not self._snapshots:
            return 1.0

        now = time.monotonic()
        min_wait = float("inf")
        for snap in self._snapshots.values():
            if snap.surface_id:
                timing = self._scheduler.get_timing(snap.surface_id)
                next_due = timing.last_poll + timing.interval()
                min_wait = min(min_wait, max(0.0, next_due - now))

        if self._done_batch.names:
            batch_due = self._done_batch.first_seen + self._done_batch.BATCH_WINDOW
            min_wait = min(min_wait, max(0.0, batch_due - now))

        return max(0.25, min(min_wait, 2.0))

    def _log_event(self, event: str, **fields: object) -> None:
        """Append a JSONL line to the audit log."""
        record = {"ts": time.time(), "event": event, **fields}
        try:
            with self._log_path.open("a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass


def _state_label(state: AgentState) -> str:
    """Map state to sidebar label."""
    labels = {
        AgentState.INITIALIZING: "starting",
        AgentState.WORKING: "working",
        AgentState.WAITING_INPUT: "idle",
        AgentState.WAITING_APPROVAL: "NEEDS APPROVAL",
        AgentState.ERRORED: "ERRORED",
        AgentState.DONE: "done",
        AgentState.SHELL: "shell",
        AgentState.UNKNOWN: "unknown",
    }
    return labels.get(state, state.value)


def _format_duration(secs: int) -> str:
    """Format seconds as human-readable duration."""
    if secs < 60:
        return f"{secs}s"
    minutes = secs // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining = minutes % 60
    return f"{hours}h{remaining}m"


def watch(project_path: Path) -> None:
    """Entry point for the overview poll loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = load_config(project_path)
    backend = get_backend(config)

    if not backend.available():
        logger.error("Terminal backend not available")
        sys.exit(1)

    poller = OverviewPoller(project_path, config, backend)
    poller.run()
