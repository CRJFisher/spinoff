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
from typing import ClassVar, Optional

import spinoff.cmux as cmux
from spinoff.config import SpinoffConfig, load_config
from spinoff.screen import AgentSnapshot, AgentState, AgentStatus, PollScheduler, ScreenSnapshot, classify
from spinoff.state import WorktreeEntry, WorktreeState, load_state, save_state

from spinoff.overview import ensure_cache_dir
from spinoff.overview.actions import get_actions_file_path, poll_and_dispatch_action
from spinoff.overview.renderer import (
    STATE_LABELS_SIDEBAR,
    OverviewData,
    format_duration,
    render_overview,
)
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
    BATCH_WINDOW: ClassVar[float] = 5.0

    def is_ready(self, now: float) -> bool:
        return bool(self.names) and (now - self.first_seen) >= self.BATCH_WINDOW


class OverviewPoller:
    """Polls agent screens and dispatches notifications + sidebar updates."""

    def __init__(
        self,
        project_path: Path,
        config: SpinoffConfig,
    ) -> None:
        self._project_path = project_path
        self._config = config
        self._scheduler = PollScheduler(
            override_interval=config.overview_poll_interval or None,
        )
        self._snapshots: dict[str, AgentSnapshot] = {}
        self._previous_states: dict[str, AgentState] = {}
        self._state_entered_at: dict[str, float] = {}
        self._cooldowns: dict[str, NotificationCooldown] = {}
        self._done_batch = DoneBatch()
        self._shutdown_requested = False
        self._focused_workspace: Optional[str] = None
        self._last_sidebar_progress: dict[str, int] = {}
        self._snapshots_changed = False
        self._window_id: Optional[str] = load_state(project_path).window_id

        cache_dir = ensure_cache_dir(config.project_name)
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

            sleep_time = self._compute_sleep()
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
        surface_ids = [a.terminal_id for a in agents if a.terminal_id]
        due = set(self._scheduler.surfaces_due(surface_ids))

        active_names = {a.name for a in agents}
        for name in list(self._snapshots):
            if name not in active_names:
                snap = self._snapshots.pop(name)
                self._previous_states.pop(name, None)
                self._state_entered_at.pop(name, None)
                self._cooldowns.pop(name, None)
                if snap.surface_id:
                    self._scheduler.remove(snap.surface_id)
                    self._last_sidebar_progress.pop(snap.surface_id, None)

        self._snapshots_changed = False
        has_transitions = False
        state_changed = False
        for entry in agents:
            if not entry.terminal_id or entry.terminal_id not in due:
                continue

            prev_state = self._previous_states.get(entry.name, AgentState.UNKNOWN)
            snapshot = self._read_and_classify(entry)
            if snapshot is not None:
                self._scheduler.record(entry.terminal_id, snapshot.phase)
                self._update_sidebar(snapshot)

                if prev_state != snapshot.phase:
                    has_transitions = True
                self._dispatch_notification(snapshot, prev_state)

                if entry.last_status != snapshot.phase.value:
                    entry.last_status = snapshot.phase.value
                    state_changed = True

        if has_transitions:
            self._update_focused_workspace()

        self._flush_done_batch()

        if self._snapshots_changed:
            self._write_html(list(self._snapshots.values()))

        poll_and_dispatch_action(
            self._project_path, self._config, state,
        )

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
        if entry.terminal_id is None:
            return None
        now = time.monotonic()

        screen_text = cmux.read_screen(entry.terminal_id)
        if screen_text is None:
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
            self._snapshots_changed = True
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
        self._snapshots_changed = True
        self._track_state(entry.name, status.state, now)
        return snap

    def _track_state(self, name: str, state: AgentState, now: float) -> None:
        """Track state transitions for notifications."""
        if self._previous_states.get(name) != state:
            self._state_entered_at[name] = now
        self._previous_states[name] = state

    def _update_focused_workspace(self) -> None:
        """Cache the currently focused workspace ID."""
        workspaces = cmux.list_workspaces(window_id=self._window_id)
        self._focused_workspace = None
        for ws in workspaces:
            if ws.get("selected"):
                self._focused_workspace = str(ws.get("terminal_id", ""))
                return

    def _update_sidebar(self, snapshot: AgentSnapshot) -> None:
        """Update sidebar status and progress for an agent."""
        sid = snapshot.surface_id or ""
        label = STATE_LABELS_SIDEBAR.get(snapshot.phase, snapshot.phase.value)
        duration_str = format_duration(int(snapshot.duration_secs))
        cmux.set_sidebar_status(sid, f"{label} [{duration_str}]")

        if snapshot.phase in (AgentState.WORKING, AgentState.INITIALIZING, AgentState.WAITING_APPROVAL):
            progress = -1
        elif snapshot.phase in (AgentState.DONE, AgentState.SHELL, AgentState.ERRORED):
            progress = 100
        else:
            progress = 0

        if self._last_sidebar_progress.get(sid) != progress:
            cmux.set_sidebar_progress(sid, progress)
            self._last_sidebar_progress[sid] = progress

    def _dispatch_notification(self, snapshot: AgentSnapshot, prev_state: AgentState) -> None:
        """Send desktop notification on state transitions."""
        if prev_state == snapshot.phase:
            return

        now = time.monotonic()
        notif_config = self._config.notifications
        cooldown = self._cooldowns.setdefault(
            snapshot.worktree_name, NotificationCooldown(),
        )

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
                cmux.notify(title, body)
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

        cmux.notify("Spinoff: Completed", body)

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
                    get_actions_file_path(self._project_path, self._config.worktree_dir)
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


def watch(project_path: Path) -> None:
    """Entry point for the overview poll loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = load_config(project_path)

    if not cmux.available():
        logger.error("cmux not available")
        sys.exit(1)

    poller = OverviewPoller(project_path, config)
    poller.run()
