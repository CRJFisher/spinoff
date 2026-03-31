"""Tests for spinoff.overview.renderer."""

import re

from spinoff.screen import AgentSnapshot, AgentState
from spinoff.coordination import FileOverlap
from spinoff.overview.renderer import (
    OverviewData,
    format_duration,
    render_overview,
)


def _snap(name: str, phase: AgentState, snippet: str = "working...", sid: str = "s1") -> AgentSnapshot:
    return AgentSnapshot(
        worktree_name=name,
        phase=phase,
        surface_id=sid,
        snippet=snippet,
        duration_secs=300,
    )


def _data(agents: list[AgentSnapshot] | None = None, overlaps: list[FileOverlap] | None = None) -> OverviewData:
    return OverviewData(
        project_name="test-project",
        agents=agents or [],
        generated_at="14:32:07",
        actions_file_path="/tmp/actions.json",
        file_overlaps=overlaps or [],
    )


class TestHTMLGeneration:
    def test_renders_basic_structure(self) -> None:
        html = render_overview(_data())
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "test-project" in html
        assert 'http-equiv="refresh"' in html

    def test_renders_agent_rows(self) -> None:
        agents = [
            _snap("fix-auth", AgentState.WORKING, sid="s1"),
            _snap("feat-mode", AgentState.DONE, sid="s2"),
        ]
        html = render_overview(_data(agents))
        assert "fix-auth" in html
        assert "feat-mode" in html
        assert html.count("<tr") >= 3  # header + 2 data rows

    def test_working_has_badge_class(self) -> None:
        html = render_overview(_data([_snap("a", AgentState.WORKING)]))
        assert "badge-working" in html

    def test_done_has_badge_class(self) -> None:
        html = render_overview(_data([_snap("a", AgentState.DONE)]))
        assert "badge-done" in html

    def test_waiting_has_approve_button(self) -> None:
        html = render_overview(_data([_snap("a", AgentState.WAITING_APPROVAL)]))
        assert "Approve" in html
        assert "Reject" in html

    def test_working_has_no_approve_button(self) -> None:
        html = render_overview(_data([_snap("a", AgentState.WORKING)]))
        # Approve action button should not appear for WORKING state
        assert 'data-action="approve"' not in html

    def test_errored_has_badge_class(self) -> None:
        html = render_overview(_data([_snap("a", AgentState.ERRORED)]))
        assert "badge-errored" in html


class TestEmptyState:
    def test_no_agents_shows_message(self) -> None:
        html = render_overview(_data([]))
        assert "No agents running" in html


class TestSnippetRendering:
    def test_snippet_html_escaped(self) -> None:
        agents = [_snap("a", AgentState.WORKING, snippet="<b>bold</b>")]
        html = render_overview(_data(agents))
        assert "&lt;b&gt;bold&lt;/b&gt;" in html
        # The raw snippet should not appear unescaped in the table
        assert "<b>bold</b>" not in html.split("<tbody>")[1]

    def test_long_snippet_truncated(self) -> None:
        long_snippet = "x" * 200
        agents = [_snap("a", AgentState.WORKING, snippet=long_snippet)]
        html = render_overview(_data(agents))
        # The cell content truncates to 80 chars, but title attr has full text
        cell_match = re.search(r'class="snippet"[^>]*>([^<]+)</td>', html)
        assert cell_match is not None
        assert len(cell_match.group(1)) <= 80


class TestStatsBar:
    def test_stats_show_working_count(self) -> None:
        agents = [
            _snap("a", AgentState.WORKING, sid="s1"),
            _snap("b", AgentState.WORKING, sid="s2"),
        ]
        html = render_overview(_data(agents))
        assert "2 working" in html

    def test_stats_show_waiting_count(self) -> None:
        agents = [_snap("a", AgentState.WAITING_APPROVAL)]
        html = render_overview(_data(agents))
        assert "1 waiting" in html

    def test_approve_all_visible_when_waiting(self) -> None:
        agents = [_snap("a", AgentState.WAITING_APPROVAL)]
        html = render_overview(_data(agents))
        assert "Approve All" in html

    def test_approve_all_hidden_when_no_waiting(self) -> None:
        agents = [_snap("a", AgentState.WORKING)]
        html = render_overview(_data(agents))
        assert "Approve All" not in html


class TestFileOverlaps:
    def test_overlaps_shown(self) -> None:
        overlaps = [FileOverlap(file_path="src/main.py", worktree_names=["a", "b"])]
        html = render_overview(_data(overlaps=overlaps))
        assert "File Overlaps" in html
        assert "src/main.py" in html

    def test_no_overlaps_section_when_empty(self) -> None:
        html = render_overview(_data())
        assert "File Overlaps" not in html


class TestFormatDuration:
    def test_seconds(self) -> None:
        assert format_duration(0) == "0s"
        assert format_duration(30) == "30s"
        assert format_duration(59) == "59s"

    def test_minutes(self) -> None:
        assert format_duration(60) == "1m"
        assert format_duration(120) == "2m"
        assert format_duration(3599) == "59m"

    def test_hours(self) -> None:
        assert format_duration(3600) == "1h0m"
        assert format_duration(3660) == "1h1m"
        assert format_duration(7200) == "2h0m"
        assert format_duration(7290) == "2h1m"

    def test_boundary_60_seconds(self) -> None:
        assert format_duration(59) == "59s"
        assert format_duration(60) == "1m"

    def test_boundary_60_minutes(self) -> None:
        assert format_duration(3599) == "59m"
        assert format_duration(3600) == "1h0m"
