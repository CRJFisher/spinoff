"""Tests for spinoff.screen — Claude Code terminal output parser."""

import time


from spinoff.screen import (
    AgentState,
    PollScheduler,
    PollTiming,
    ScreenSnapshot,
    classify,
    strip_ansi,
    _extract_outside_tool_results,
)


def _snap(text: str, surface_id: str = "test-1") -> ScreenSnapshot:
    """Helper to create a ScreenSnapshot."""
    return ScreenSnapshot(
        surface_id=surface_id,
        text=text,
        captured_at=time.monotonic(),
    )


# ---------------------------------------------------------------------------
# ANSI stripping
# ---------------------------------------------------------------------------

class TestStripAnsi:
    def test_removes_color_codes(self) -> None:
        assert strip_ansi("\x1b[31mError\x1b[0m") == "Error"

    def test_removes_cursor_movement(self) -> None:
        assert strip_ansi("\x1b[2Jhello\x1b[H") == "hello"

    def test_removes_osc_sequences(self) -> None:
        assert strip_ansi("\x1b]0;title\x07content") == "content"

    def test_preserves_plain_text(self) -> None:
        text = "Just plain text with unicode: ╭─ Bash ─╮"
        assert strip_ansi(text) == text

    def test_preserves_box_drawing(self) -> None:
        text = "╭─ Edit ──────╮\n│ hello.py    │\n╰─────────────╯"
        assert strip_ansi(text) == text


# ---------------------------------------------------------------------------
# Tool result extraction
# ---------------------------------------------------------------------------

class TestExtractOutsideToolResults:
    def test_removes_result_box_content(self) -> None:
        text = (
            "Before\n"
            "╭─ Bash Result ──────────────────╮\n"
            "│ Error: file not found          │\n"
            "│ some other output              │\n"
            "╰────────────────────────────────╯\n"
            "After"
        )
        result = _extract_outside_tool_results(text)
        assert "Error: file not found" not in result
        assert "Before" in result
        assert "After" in result

    def test_preserves_non_result_boxes(self) -> None:
        text = (
            "╭─ Bash ─────────────────────────╮\n"
            "│ git status                     │\n"
            "╰────────────────────────────────╯\n"
            "Error: something broke"
        )
        result = _extract_outside_tool_results(text)
        # The tool-call box (not "Result") is preserved
        assert "git status" in result
        assert "Error: something broke" in result

    def test_handles_multiple_result_boxes(self) -> None:
        text = (
            "╭─ Bash Result ──────╮\n"
            "│ Error: x           │\n"
            "╰────────────────────╯\n"
            "middle text\n"
            "╭─ Read Result ──────╮\n"
            "│ Error: y           │\n"
            "╰────────────────────╯\n"
            "end text"
        )
        result = _extract_outside_tool_results(text)
        assert "Error: x" not in result
        assert "Error: y" not in result
        assert "middle text" in result
        assert "end text" in result


# ---------------------------------------------------------------------------
# State classification — SHELL
# ---------------------------------------------------------------------------

class TestShellState:
    def test_claude_exited_message(self) -> None:
        text = (
            "Some previous output\n"
            "Claude exited. Shell kept open.\n"
            "$ "
        )
        status = classify(_snap(text))
        assert status.state == AgentState.SHELL
        assert "exited" in status.summary.lower()

    def test_build_failed_message(self) -> None:
        text = (
            "npm ERR! code ELIFECYCLE\n"
            "Build failed. Shell kept open for debugging.\n"
            "$ "
        )
        status = classify(_snap(text))
        assert status.state == AgentState.SHELL

    def test_bare_shell_prompt(self) -> None:
        text = "some output\n$\n"
        status = classify(_snap(text))
        assert status.state == AgentState.SHELL


# ---------------------------------------------------------------------------
# State classification — INITIALIZING
# ---------------------------------------------------------------------------

class TestInitializingState:
    def test_version_banner(self) -> None:
        text = "Claude Code v2.1.84\nLoading project..."
        status = classify(_snap(text))
        assert status.state == AgentState.INITIALIZING

    def test_init_with_tool_calls_is_not_initializing(self) -> None:
        """Once tool calls appear, we're past initialization."""
        text = (
            "Claude Code v2.1.84\n"
            "╭─ Bash ─────────────────────────╮\n"
            "│ ls                             │\n"
            "╰────────────────────────────────╯\n"
        )
        status = classify(_snap(text))
        assert status.state != AgentState.INITIALIZING


# ---------------------------------------------------------------------------
# State classification — WAITING_APPROVAL
# ---------------------------------------------------------------------------

class TestWaitingApprovalState:
    def test_yes_no_selector(self) -> None:
        text = (
            "Claude wants to run: rm -rf /tmp/test\n"
            "\n"
            "Do you want to proceed?\n"
            "❯ Yes\n"
            "  No\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.WAITING_APPROVAL
        assert status.confidence >= 0.9

    def test_allow_once_prompt(self) -> None:
        text = (
            "Bash wants to execute: curl https://example.com\n"
            "\n"
            "Allow once\n"
            "Allow always\n"
            "Deny\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.WAITING_APPROVAL

    def test_allow_tool_prompt(self) -> None:
        text = (
            "Claude wants to run Bash\n"
            "> Allow\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.WAITING_APPROVAL

    def test_approval_overrides_working(self) -> None:
        """Permission prompt should take priority over tool call patterns."""
        text = (
            "╭─ Bash ─────────────────────────╮\n"
            "│ dangerous-command               │\n"
            "╰────────────────────────────────╯\n"
            "\n"
            "Do you want to proceed?\n"
            "❯ Yes\n"
            "  No\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.WAITING_APPROVAL


# ---------------------------------------------------------------------------
# State classification — ERRORED
# ---------------------------------------------------------------------------

class TestErroredState:
    def test_api_error(self) -> None:
        text = (
            "Thinking...\n"
            "API error: rate limit exceeded\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.ERRORED
        assert "rate limit" in status.summary.lower()

    def test_auth_error(self) -> None:
        text = "Authentication failed. Please check your API key.\n"
        status = classify(_snap(text))
        assert status.state == AgentState.ERRORED

    def test_error_inside_tool_result_is_not_errored(self) -> None:
        """An error message inside a tool result box is the tool's output, not Claude crashing."""
        text = (
            "╭─ Bash Result ──────────────────╮\n"
            "│ Error: file not found          │\n"
            "╰────────────────────────────────╯\n"
            "\n"
            "The file doesn't exist. Let me try another approach.\n"
            "\n"
            "╭─ Bash ─────────────────────────╮\n"
            "│ find . -name 'config*'         │\n"
            "╰────────────────────────────────╯\n"
        )
        status = classify(_snap(text))
        # Should be WORKING, not ERRORED
        assert status.state != AgentState.ERRORED

    def test_error_with_prompt_below_is_recovered(self) -> None:
        """If there's an input prompt below the error, Claude recovered."""
        text = (
            "API error: rate limit exceeded\n"
            "Retrying...\n"
            "I've fixed the issue.\n"
            "\n"
            ">\n"
        )
        status = classify(_snap(text))
        # The prompt below means Claude recovered; not ERRORED
        assert status.state != AgentState.ERRORED

    def test_connection_error(self) -> None:
        text = "connection timed out\n"
        status = classify(_snap(text))
        assert status.state == AgentState.ERRORED

    def test_budget_exceeded(self) -> None:
        text = "budget exceeded for this session\n"
        status = classify(_snap(text))
        assert status.state == AgentState.ERRORED


# ---------------------------------------------------------------------------
# State classification — WORKING
# ---------------------------------------------------------------------------

class TestWorkingState:
    def test_tool_call_visible(self) -> None:
        text = (
            "I'll check the file structure.\n"
            "\n"
            "╭─ Bash ─────────────────────────╮\n"
            "│ ls -la src/                    │\n"
            "╰────────────────────────────────╯\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.WORKING
        assert "Bash" in status.summary

    def test_edit_tool(self) -> None:
        text = (
            "╭─ Edit ──────────────────────────╮\n"
            "│ src/main.py                     │\n"
            "╰─────────────────────────────────╯\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.WORKING
        assert "Edit" in status.summary

    def test_spinner_characters(self) -> None:
        text = "⠋ Processing request..."
        status = classify(_snap(text))
        assert status.state == AgentState.WORKING

    def test_thinking_indicator(self) -> None:
        text = "Thinking..."
        status = classify(_snap(text))
        assert status.state == AgentState.WORKING

    def test_tool_call_with_prompt_means_not_working(self) -> None:
        """If tool calls are visible but input prompt is at bottom, we're done working."""
        text = (
            "╭─ Bash ─────────────────────────╮\n"
            "│ git status                     │\n"
            "╰────────────────────────────────╯\n"
            "╭─ Bash Result ──────────────────╮\n"
            "│ On branch main                 │\n"
            "╰────────────────────────────────╯\n"
            "\n"
            "Everything looks good!\n"
            "\n"
            ">\n"
        )
        status = classify(_snap(text))
        # Tool calls visible but prompt at bottom -> not WORKING
        assert status.state != AgentState.WORKING

    def test_mcp_tool_call(self) -> None:
        text = (
            "╭─ mcp_github_create_issue ──────╮\n"
            "│ title: Fix bug                 │\n"
            "╰────────────────────────────────╯\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.WORKING

    def test_summary_includes_tool_content(self) -> None:
        text = (
            "╭─ Bash ─────────────────────────╮\n"
            "│ pytest tests/ -v               │\n"
            "╰────────────────────────────────╯\n"
        )
        status = classify(_snap(text))
        assert "Bash" in status.summary
        assert "pytest" in status.summary


# ---------------------------------------------------------------------------
# State classification — DONE
# ---------------------------------------------------------------------------

class TestDoneState:
    def test_completed_with_prompt(self) -> None:
        text = (
            "I've completed all the changes. The tests pass and the code is clean.\n"
            "\n"
            ">\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.DONE
        assert "completed" in status.summary.lower()

    def test_let_me_know_with_prompt(self) -> None:
        text = (
            "All changes have been committed. Let me know if you'd like any adjustments.\n"
            "\n"
            ">\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.DONE

    def test_completion_without_prompt_is_working(self) -> None:
        """Completion phrases without input prompt means Claude is still outputting."""
        text = (
            "I've completed the first part. Now let me work on the tests.\n"
            "\n"
            "╭─ Edit ──────────────────────────╮\n"
            "│ tests/test_foo.py               │\n"
            "╰─────────────────────────────────╯\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.WORKING

    def test_successfully_committed(self) -> None:
        text = (
            "I've successfully committed all changes.\n"
            "\n"
            ">\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.DONE

    def test_is_there_anything_else(self) -> None:
        text = (
            "The implementation is ready. Is there anything else you'd like me to do?\n"
            "\n"
            ">\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.DONE


# ---------------------------------------------------------------------------
# State classification — WAITING_INPUT
# ---------------------------------------------------------------------------

class TestWaitingInputState:
    def test_bare_prompt(self) -> None:
        text = (
            "Some previous conversation...\n"
            "\n"
            ">\n"
        )
        status = classify(_snap(text))
        assert status.state in (AgentState.WAITING_INPUT, AgentState.DONE)

    def test_prompt_after_tool_use_no_completion(self) -> None:
        """Prompt visible after tools but no completion phrase = waiting for input."""
        text = (
            "╭─ Bash ─────────────────────────╮\n"
            "│ ls                             │\n"
            "╰────────────────────────────────╯\n"
            "╭─ Bash Result ──────────────────╮\n"
            "│ file1.py  file2.py             │\n"
            "╰────────────────────────────────╯\n"
            "\n"
            "Here are the files in the directory.\n"
            "\n"
            ">\n"
        )
        status = classify(_snap(text))
        assert status.state == AgentState.WAITING_INPUT


# ---------------------------------------------------------------------------
# Confidence values
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_shell_high_confidence(self) -> None:
        text = "Claude exited. Shell kept open.\n$\n"
        status = classify(_snap(text))
        assert status.confidence >= 0.9

    def test_unknown_zero_confidence(self) -> None:
        text = "random gibberish that matches nothing"
        status = classify(_snap(text))
        assert status.state == AgentState.UNKNOWN
        assert status.confidence == 0.0


# ---------------------------------------------------------------------------
# Surface ID propagation
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_surface_id_preserved(self) -> None:
        snap = _snap("Thinking...", surface_id="surface-42")
        status = classify(snap)
        assert status.surface_id == "surface-42"

    def test_captured_at_preserved(self) -> None:
        snap = _snap("Thinking...")
        status = classify(snap)
        assert status.captured_at == snap.captured_at


# ---------------------------------------------------------------------------
# Poll timing
# ---------------------------------------------------------------------------

class TestPollTiming:
    def test_working_has_short_interval(self) -> None:
        pt = PollTiming(surface_id="s1", last_state=AgentState.WORKING)
        assert pt.interval() <= 2.0

    def test_done_has_long_interval(self) -> None:
        pt = PollTiming(surface_id="s1", last_state=AgentState.DONE)
        assert pt.interval() >= 5.0

    def test_slowdown_after_repeated_same_state(self) -> None:
        pt = PollTiming(surface_id="s1", last_state=AgentState.WORKING)
        base = pt.interval()
        # Simulate many same-state polls
        pt.consecutive_same = 10
        assert pt.interval() > base

    def test_state_change_resets_slowdown(self) -> None:
        pt = PollTiming(surface_id="s1", last_state=AgentState.WORKING)
        pt.consecutive_same = 10
        pt.interval()
        pt.record(AgentState.DONE)
        assert pt.consecutive_same == 0

    def test_should_poll_initially_true(self) -> None:
        pt = PollTiming(surface_id="s1")
        assert pt.should_poll()

    def test_should_poll_false_immediately_after(self) -> None:
        pt = PollTiming(surface_id="s1")
        pt.record(AgentState.WORKING)
        assert not pt.should_poll()

    def test_interval_never_exceeds_max(self) -> None:
        pt = PollTiming(surface_id="s1", last_state=AgentState.DONE)
        pt.consecutive_same = 1000
        assert pt.interval() <= pt.MAX_INTERVAL


class TestPollScheduler:
    def test_surfaces_due_initially(self) -> None:
        sched = PollScheduler()
        due = sched.surfaces_due(["s1", "s2", "s3"])
        assert due == ["s1", "s2", "s3"]

    def test_surfaces_not_due_after_record(self) -> None:
        sched = PollScheduler()
        sched.record("s1", AgentState.WORKING)
        due = sched.surfaces_due(["s1", "s2"])
        assert "s1" not in due
        assert "s2" in due

    def test_remove_surface(self) -> None:
        sched = PollScheduler()
        sched.record("s1", AgentState.WORKING)
        sched.remove("s1")
        # After removal, surface gets fresh timing
        due = sched.surfaces_due(["s1"])
        assert "s1" in due

    def test_override_interval_passed_to_timing(self) -> None:
        sched = PollScheduler(override_interval=3.0)
        timing = sched.get_timing("s1")
        assert timing.override_interval == 3.0
        assert timing.interval() == 3.0


class TestPollTimingOverride:
    def test_override_used(self) -> None:
        t = PollTiming(surface_id="s1", override_interval=5.0)
        assert t.interval() == 5.0

    def test_override_ignores_state(self) -> None:
        t = PollTiming(surface_id="s1", override_interval=2.0)
        t.record(AgentState.WORKING)
        assert t.interval() == 2.0
        t.record(AgentState.DONE)
        assert t.interval() == 2.0

    def test_zero_override_uses_adaptive(self) -> None:
        t = PollTiming(surface_id="s1", override_interval=0.0, last_state=AgentState.WORKING)
        assert t.interval() == 1.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_screen(self) -> None:
        status = classify(_snap(""))
        assert status.state == AgentState.UNKNOWN

    def test_whitespace_only(self) -> None:
        status = classify(_snap("   \n\n  \n"))
        assert status.state == AgentState.UNKNOWN

    def test_ansi_codes_stripped_before_matching(self) -> None:
        """ANSI codes should not interfere with pattern matching."""
        text = "\x1b[31mAPI error: rate limit exceeded\x1b[0m\n"
        status = classify(_snap(text))
        assert status.state == AgentState.ERRORED

    def test_error_in_code_comment_inside_tool_result(self) -> None:
        """Error: in a code comment inside a tool result box is not a real error."""
        text = (
            "╭─ Read Result ──────────────────╮\n"
            "│ # Error: this is expected      │\n"
            "│ def handle_error():            │\n"
            "╰────────────────────────────────╯\n"
            "\n"
            "╭─ Edit ──────────────────────────╮\n"
            "│ src/handler.py                  │\n"
            "╰─────────────────────────────────╯\n"
        )
        status = classify(_snap(text))
        assert status.state != AgentState.ERRORED

    def test_long_screen_performance(self) -> None:
        """Classify should handle large screen dumps without issue."""
        # 500 lines of tool output
        lines = []
        for i in range(500):
            lines.append(f"│ line {i} of output               │")
        text = "\n".join(lines) + "\n\n>\n"
        status = classify(_snap(text))
        # Should still be parseable
        assert status.state in (AgentState.WAITING_INPUT, AgentState.DONE, AgentState.UNKNOWN)
