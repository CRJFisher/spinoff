"""HTML renderer for the overview dashboard."""

from dataclasses import dataclass, field

from spinoff.screen import AgentState

import json

from spinoff.overview.security import safe_html
from spinoff.overview.template import TEMPLATE


@dataclass
class AgentSnapshot:
    """In-memory ephemeral state for one agent."""
    worktree_name: str
    phase: AgentState
    surface_id: str | None
    snippet: str
    error_message: str = ""
    cost_usd: float | None = None
    token_count: int | None = None
    duration_secs: float = 0.0
    depends_on: list[str] = field(default_factory=list)


@dataclass
class FileOverlap:
    """A file touched by multiple active worktrees."""
    file_path: str
    agents: list[str]


@dataclass
class OverviewData:
    """Rendering context for the dashboard."""
    project_name: str
    agents: list[AgentSnapshot]
    generated_at: str
    actions_file_path: str
    file_overlaps: list[FileOverlap] = field(default_factory=list)
    refresh_interval: int = 5


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
        project_name=safe_html(data.project_name),
        refresh_interval=str(data.refresh_interval),
        total_count=str(len(data.agents)),
        stats_badges=stats_badges,
        approve_all_btn=approve_all_btn,
        generated_at=safe_html(data.generated_at),
        table_content=table_content,
        overlaps_section=overlaps_section,
        actions_file_path=json.dumps(data.actions_file_path),
    )


def _build_stats(agents: list[AgentSnapshot]) -> dict[str, int]:
    """Count agents in each state."""
    counts: dict[str, int] = {}
    for a in agents:
        key = a.phase.value
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
    for a in agents:
        badge_class = f"badge-{a.phase.value}"
        label = _state_display_label(a.phase)
        snippet = safe_html(a.snippet[:80]) if a.snippet else "-"
        duration = _format_duration(int(a.duration_secs))
        deps = ", ".join(safe_html(d) for d in a.depends_on) if a.depends_on else "-"
        sid = safe_html(a.surface_id or "")
        name = safe_html(a.worktree_name)

        actions: list[str] = []
        if a.surface_id:
            actions.append(f'<button class="btn" data-action="focus" data-sid="{sid}">Focus</button>')
            if a.phase == AgentState.WAITING_APPROVAL:
                actions.append(f'<button class="btn btn-approve" data-action="approve" data-sid="{sid}">Approve</button>')
                actions.append(f'<button class="btn" data-action="reject" data-sid="{sid}">Reject</button>')
            actions.append(f'<button class="btn" data-action="interrupt" data-sid="{sid}">Interrupt</button>')
            actions.append(f'<button class="btn btn-kill" data-action="kill" data-sid="{sid}" data-name="{name}">Kill</button>')

        rows.append(
            f'<tr data-sid="{sid}">'
            f'<td>{name}</td>'
            f'<td><span class="badge {badge_class}">{label}</span></td>'
            f'<td class="snippet" title="{safe_html(a.snippet)}">{snippet}</td>'
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
    for o in overlaps:
        agents = ", ".join(safe_html(a) for a in o.agents)
        items.append(
            f'<li><span class="overlap-file">{safe_html(o.file_path)}</span> '
            f'<span class="overlap-agents">({agents})</span></li>'
        )
    return (
        f'<section class="overlaps" aria-label="File conflicts">'
        f'<h2>File Overlaps ({len(overlaps)})</h2>'
        f'<ul>{"".join(items)}</ul></section>'
    )


def _state_display_label(state: AgentState) -> str:
    """Map AgentState to human-readable label."""
    labels = {
        AgentState.INITIALIZING: "Starting",
        AgentState.WORKING: "Working",
        AgentState.WAITING_INPUT: "Idle",
        AgentState.WAITING_APPROVAL: "Needs Approval",
        AgentState.ERRORED: "Errored",
        AgentState.DONE: "Done",
        AgentState.SHELL: "Shell",
        AgentState.UNKNOWN: "Unknown",
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
