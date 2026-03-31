"""HTML renderer for the overview dashboard."""

import json
from dataclasses import dataclass, field
from typing import Final

from spinoff.coordination import FileOverlap
from spinoff.screen import AgentSnapshot, AgentState

from spinoff.overview.security import sanitize_html
from spinoff.overview.template import TEMPLATE


@dataclass
class OverviewData:
    """Rendering context for the dashboard."""
    project_name: str
    agents: list[AgentSnapshot]
    generated_at: str
    actions_file_path: str
    file_overlaps: list[FileOverlap] = field(default_factory=list)
    refresh_interval: int = 5


# --- Shared display helpers (used by poller and __init__ too) ---

STATE_LABELS_SIDEBAR: Final[dict[AgentState, str]] = {
    AgentState.INITIALIZING: "starting",
    AgentState.WORKING: "working",
    AgentState.WAITING_INPUT: "idle",
    AgentState.WAITING_APPROVAL: "NEEDS APPROVAL",
    AgentState.ERRORED: "ERRORED",
    AgentState.DONE: "done",
    AgentState.SHELL: "shell",
    AgentState.UNKNOWN: "unknown",
}

STATE_LABELS_DISPLAY: Final[dict[AgentState, str]] = {
    AgentState.INITIALIZING: "Starting",
    AgentState.WORKING: "Working",
    AgentState.WAITING_INPUT: "Idle",
    AgentState.WAITING_APPROVAL: "Needs Approval",
    AgentState.ERRORED: "Errored",
    AgentState.DONE: "Done",
    AgentState.SHELL: "Shell",
    AgentState.UNKNOWN: "Unknown",
}


def format_duration(secs: int) -> str:
    """Format seconds as human-readable duration."""
    if secs < 60:
        return f"{secs}s"
    minutes = secs // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining = minutes % 60
    return f"{hours}h{remaining}m"


def render_overview(data: OverviewData) -> str:
    """Render the complete HTML dashboard."""
    stats = _build_stats(data.agents)
    stats_badges = _build_stats_badges(stats)

    has_waiting = stats.get("waiting_approval", 0) > 0
    approve_all_btn = (
        '<button class="btn btn-approve-all" onclick="approveAll()">Approve All</button>'
        if has_waiting else ""
    )

    if data.agents:
        table_content = _build_table(data.agents)
    else:
        table_content = '<p class="empty">No agents running. Use /spinoff:new to create one.</p>'

    overlaps_section = _build_overlaps(data.file_overlaps)

    return TEMPLATE.safe_substitute(
        project_name=sanitize_html(data.project_name),
        refresh_interval=str(data.refresh_interval),
        total_count=str(len(data.agents)),
        stats_badges=stats_badges,
        approve_all_btn=approve_all_btn,
        generated_at=sanitize_html(data.generated_at),
        table_content=table_content,
        overlaps_section=overlaps_section,
        actions_file_path=json.dumps(data.actions_file_path),
    )


def _build_stats(agents: list[AgentSnapshot]) -> dict[str, int]:
    """Count agents in each state."""
    counts: dict[str, int] = {}
    for agent in agents:
        key = agent.phase.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def _build_stats_badges(stats: dict[str, int]) -> str:
    """Build stats badge HTML for non-zero states."""
    parts: list[str] = []
    for state_val, css, label in [
        ("working", "working", "working"),
        ("waiting_approval", "waiting", "waiting"),
        ("errored", "errored", "errored"),
        ("done", "done", "done"),
    ]:
        count = stats.get(state_val, 0)
        if count > 0:
            parts.append(f'<span class="stat {css}">{count} {label}</span>')
    return "\n        ".join(parts)


def _build_table(agents: list[AgentSnapshot]) -> str:
    """Build the agent table HTML."""
    rows: list[str] = []
    for agent in agents:
        badge_class = f"badge-{agent.phase.value}"
        label = STATE_LABELS_DISPLAY.get(agent.phase, agent.phase.value)
        snippet = sanitize_html(agent.snippet[:80]) if agent.snippet else "-"
        duration = format_duration(int(agent.duration_secs))
        deps = ", ".join(sanitize_html(d) for d in agent.depends_on) if agent.depends_on else "-"
        sid = sanitize_html(agent.surface_id or "")
        name = sanitize_html(agent.worktree_name)

        actions: list[str] = []
        if agent.surface_id:
            actions.append(f'<button class="btn" data-action="focus" data-sid="{sid}">Focus</button>')
            if agent.phase == AgentState.WAITING_APPROVAL:
                actions.append(f'<button class="btn btn-approve" data-action="approve" data-sid="{sid}">Approve</button>')
                actions.append(f'<button class="btn" data-action="reject" data-sid="{sid}">Reject</button>')
            actions.append(f'<button class="btn" data-action="interrupt" data-sid="{sid}">Interrupt</button>')
            actions.append(f'<button class="btn btn-kill" data-action="kill" data-sid="{sid}" data-name="{name}">Kill</button>')

        rows.append(
            f'<tr data-sid="{sid}">'
            f'<td>{name}</td>'
            f'<td><span class="badge {badge_class}">{label}</span></td>'
            f'<td class="snippet" title="{sanitize_html(agent.snippet)}">{snippet}</td>'
            f'<td>{duration}</td>'
            f'<td>{deps}</td>'
            f'<td class="actions">{"".join(actions)}</td>'
            f'</tr>'
        )

    return (
        '<table role="grid" aria-label="Agent status">'
        '<thead><tr>'
        '<th>Agent</th><th>State</th><th>Activity</th>'
        '<th>Duration</th><th>Dependencies</th><th>Actions</th>'
        '</tr></thead>'
        '<tbody>' + "\n".join(rows) + '</tbody></table>'
    )


def _build_overlaps(overlaps: list[FileOverlap]) -> str:
    """Build file overlaps section HTML."""
    if not overlaps:
        return ""
    items: list[str] = []
    for overlap in overlaps:
        agents = ", ".join(sanitize_html(name) for name in overlap.worktree_names)
        items.append(
            f'<li><span class="overlap-file">{sanitize_html(overlap.file_path)}</span> '
            f'<span class="overlap-agents">({agents})</span></li>'
        )
    return (
        f'<section class="overlaps" aria-label="File conflicts">'
        f'<h2>File Overlaps ({len(overlaps)})</h2>'
        f'<ul>{"".join(items)}</ul></section>'
    )
