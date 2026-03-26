#!/usr/bin/env python3
"""
Claude Code Screen Parser

Parses terminal output from Claude Code sessions (captured via cmux read-screen)
to determine agent state and extract activity summaries.

Claude Code renders a TUI (Ink/React) with ANSI escape codes. The cmux read-screen
command returns the visible text content with ANSI stripped. This module matches
against the plain-text patterns Claude Code produces.

## Claude Code TUI layout

The terminal contains, from top to bottom:
- A session header line (e.g. "Claude Code v2.1.84")
- Message blocks: user messages, assistant messages, tool calls, tool results
- A status/input area at the bottom

## Key visual patterns

Tool calls appear as boxed regions:
    ╭─ Bash ─────────────────────────────╮
    │ git status                         │
    ╰────────────────────────────────────╯

Tool results appear similarly:
    ╭─ Bash Result ──────────────────────╮
    │ On branch main                     │
    ╰────────────────────────────────────╯

Permission prompts show a question with Yes/No options:
    Do you want to proceed?
    ❯ Yes
      No

The input prompt at the bottom looks like:
    >

When Claude is thinking/working, a spinner or activity indicator appears.
When Claude finishes a task and returns to the prompt, the bottom shows the
input cursor.

Completion messages typically contain phrases like:
    "I've completed", "I have completed", "Let me know if",
    "Is there anything else", "I'm done", "Task complete"
"""
# /// script
# requires-python = ">=3.11"
# ///

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AgentState(Enum):
    """Observable state of a Claude Code agent."""
    INITIALIZING = "initializing"      # Claude Code is booting up
    WORKING = "working"                # Actively producing output (tool calls, thinking)
    WAITING_INPUT = "waiting_input"    # At the input prompt, waiting for user
    WAITING_APPROVAL = "waiting_approval"  # Permission prompt visible
    ERRORED = "errored"               # An error occurred
    DONE = "done"                     # Task completed, back at prompt
    SHELL = "shell"                   # Claude exited, bare shell visible
    UNKNOWN = "unknown"               # Cannot determine state


@dataclass
class ScreenSnapshot:
    """A captured terminal screen with metadata."""
    surface_id: str
    text: str
    captured_at: float  # time.monotonic()


@dataclass
class AgentStatus:
    """Parsed agent state from a screen snapshot."""
    state: AgentState
    summary: str          # 1-2 line human-readable summary of last activity
    confidence: float     # 0.0-1.0 confidence in the state classification
    surface_id: str
    captured_at: float


# ---------------------------------------------------------------------------
# ANSI stripping
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[.*?[@-~]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from terminal output."""
    return _ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Pattern definitions
#
# Each pattern group targets a specific Claude Code TUI element.
# Patterns match against plain text (ANSI already stripped).
# ---------------------------------------------------------------------------

# --- Permission / approval prompts ---
# Claude Code shows a permission prompt when it wants to run a tool
# that requires user approval. The prompt contains option indicators.
PERMISSION_PATTERNS: list[re.Pattern[str]] = [
    # The yes/no selector with arrow indicator
    re.compile(r"[❯>]\s*(Yes|Allow|Approve)", re.IGNORECASE),
    # Permission question phrasing
    re.compile(r"Do you want to (proceed|allow|run|execute|approve)", re.IGNORECASE),
    # "Allow once" / "Allow always" style prompts
    re.compile(r"(Allow once|Allow always|Deny)", re.IGNORECASE),
    # Tool permission request
    re.compile(r"wants to (run|execute|use|call)\b", re.IGNORECASE),
    # "Allow .* to" pattern
    re.compile(r"Allow .+ to (read|write|execute|run|access)", re.IGNORECASE),
]

# --- Error patterns ---
# Actual errors from Claude Code (not just the word "error" in code output).
# These appear outside of tool-result boxes.
ERROR_PATTERNS: list[re.Pattern[str]] = [
    # Claude Code's own error messages
    re.compile(r"^Error:", re.MULTILINE),
    re.compile(r"^ERROR:", re.MULTILINE),
    # API errors
    re.compile(r"API error|rate limit|overloaded|503|529", re.IGNORECASE),
    # Authentication errors
    re.compile(r"authentication failed|invalid api key|unauthorized", re.IGNORECASE),
    # Connection errors
    re.compile(r"connection (refused|reset|timed out|error)", re.IGNORECASE),
    # Claude Code specific crash/abort
    re.compile(r"(unexpected error|fatal error|panic|unhandled)", re.IGNORECASE),
    # Budget exhausted
    re.compile(r"budget (exceeded|exhausted|limit)", re.IGNORECASE),
]

# --- Tool call patterns ---
# These indicate Claude is actively working (invoking tools).
TOOL_CALL_PATTERNS: list[re.Pattern[str]] = [
    # Box-drawing tool headers: ╭─ ToolName ─╮  or  ╭─ ToolName(args) ─╮
    re.compile(r"[╭┌]─\s*(Bash|Read|Edit|Write|Grep|Glob|Skill|WebFetch|WebSearch|NotebookEdit|TodoWrite|Agent|mcp_)"),
    # Tool result headers
    re.compile(r"[╭┌]─\s*(Bash|Read|Edit|Write|Grep|Glob|Skill|WebFetch|WebSearch|NotebookEdit|TodoWrite|Agent|mcp_)\s*(Result|Output)"),
]

# --- Thinking / working indicators ---
THINKING_PATTERNS: list[re.Pattern[str]] = [
    # Spinner characters that Claude Code renders
    re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]"),
    # "Thinking" or "Working" text
    re.compile(r"(Thinking|Working|Processing)\.\.\.", re.IGNORECASE),
]

# --- Completion indicators ---
# Phrases Claude uses when it considers a task done.
COMPLETION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"I'?ve completed", re.IGNORECASE),
    re.compile(r"I have completed", re.IGNORECASE),
    re.compile(r"task (is )?complete", re.IGNORECASE),
    re.compile(r"(all |the )?changes have been (made|applied|committed)", re.IGNORECASE),
    re.compile(r"everything (is|has been) (done|committed|updated)", re.IGNORECASE),
    re.compile(r"let me know if (you('d| would) like|there'?s anything)", re.IGNORECASE),
    re.compile(r"is there anything else", re.IGNORECASE),
    re.compile(r"I'?m done", re.IGNORECASE),
    re.compile(r"successfully (completed|merged|committed|implemented)", re.IGNORECASE),
]

# --- Shell prompt (Claude exited) ---
# After Claude exits, the startup script prints a message and drops to bash.
SHELL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Claude exited\. Shell kept open"),
    re.compile(r"Build failed\. Shell kept open"),
    # Generic shell prompt at the very end of screen
    re.compile(r"^\$\s*$", re.MULTILINE),
]

# --- Input prompt ---
# Claude Code's input prompt is a ">" character at the bottom of the screen,
# sometimes with a preceding blank line.
INPUT_PROMPT_RE = re.compile(r"^>\s*$", re.MULTILINE)

# --- Initializing ---
# Claude Code startup shows version info and loading indicators.
INIT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Claude Code v\d+\.\d+"),
    re.compile(r"(Loading|Starting|Initializing)\s*(session|project|workspace)?", re.IGNORECASE),
    re.compile(r"Discovering MCP servers", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Tool result box detection
#
# Content inside tool-result boxes (between ╭ and ╯ lines where the header
# contains "Result") should NOT be treated as agent output for error/completion
# detection. An "Error:" inside a tool result is the tool's output, not
# Claude Code crashing.
# ---------------------------------------------------------------------------

_BOX_TOP_RE = re.compile(r"^.*[╭┌]─.*─[╮┐]\s*$", re.MULTILINE)
_BOX_BOTTOM_RE = re.compile(r"^.*[╰└]─.*─*[╯┘]\s*$", re.MULTILINE)
_RESULT_HEADER_RE = re.compile(r"[╭┌]─\s*\S+\s*(Result|Output)\s*─", re.MULTILINE)


def _extract_outside_tool_results(text: str) -> str:
    """
    Return text with tool-result box contents removed.

    Tool result boxes look like:
        ╭─ Bash Result ──────╮
        │ ... content ...    │
        ╰────────────────────╯

    We remove everything between a result-header box-top and the next box-bottom.
    This prevents false-positive error detection from tool output.
    """
    lines = text.split("\n")
    filtered: list[str] = []
    inside_result_box = False

    for line in lines:
        if inside_result_box:
            if _BOX_BOTTOM_RE.match(line):
                inside_result_box = False
            # Skip lines inside result boxes
            continue

        if _RESULT_HEADER_RE.search(line):
            inside_result_box = True
            continue

        filtered.append(line)

    return "\n".join(filtered)


# ---------------------------------------------------------------------------
# Bottom-of-screen extraction
#
# The most recent state is at the bottom of the terminal. We focus on the
# last N lines for prompt/approval detection, and scan more broadly for
# error/completion patterns in the assistant's most recent message.
# ---------------------------------------------------------------------------

_BOTTOM_LINES = 15  # Lines from bottom to check for prompts
_SCAN_LINES = 60    # Lines from bottom to scan for errors/completion


def _bottom(text: str, n: int) -> str:
    """Get the last n non-empty lines of text."""
    lines = [line for line in text.split("\n") if line.strip()]
    return "\n".join(lines[-n:])


def _any_match(patterns: list[re.Pattern[str]], text: str) -> Optional[re.Match[str]]:
    """Return the first match from a list of patterns, or None."""
    for p in patterns:
        m = p.search(text)
        if m:
            return m
    return None


# ---------------------------------------------------------------------------
# Summary extraction
#
# Extract a short description of what the agent is doing / last did.
# ---------------------------------------------------------------------------

_TOOL_HEADER_RE = re.compile(
    r"[╭┌]─\s*(Bash|Read|Edit|Write|Grep|Glob|Skill|WebFetch|WebSearch|NotebookEdit|TodoWrite|Agent|mcp_\S+)"
    r"(?:\s*\(([^)]*)\))?"  # optional args in parens
    r"\s*─"
)


def _extract_summary(text: str, state: AgentState) -> str:
    """
    Build a 1-2 line summary of the agent's last activity.

    Strategy:
    - For WORKING: show the most recent tool call name + first arg line
    - For WAITING_APPROVAL: show what permission is being requested
    - For ERRORED: show the error message
    - For DONE: show the completion phrase
    - For SHELL: "Claude exited"
    - For WAITING_INPUT: "Waiting for input"
    - For INITIALIZING: "Starting up"
    """
    bottom = _bottom(text, _SCAN_LINES)

    if state == AgentState.INITIALIZING:
        return "Starting up"

    if state == AgentState.SHELL:
        return "Claude exited, shell open"

    if state == AgentState.WAITING_INPUT:
        # Look for the last tool call or assistant text before the prompt
        tool_matches = list(_TOOL_HEADER_RE.finditer(bottom))
        if tool_matches:
            last = tool_matches[-1]
            tool_name = last.group(1)
            tool_args = last.group(2) or ""
            if tool_args:
                return f"Idle after {tool_name}({tool_args})"
            return f"Idle after {tool_name}"
        return "Waiting for input"

    if state == AgentState.WAITING_APPROVAL:
        for p in PERMISSION_PATTERNS:
            m = p.search(bottom)
            if m:
                # Get the line containing the match for context
                for line in bottom.split("\n"):
                    if m.group() in line:
                        return f"Approval needed: {line.strip()[:80]}"
        return "Waiting for approval"

    if state == AgentState.ERRORED:
        outside = _extract_outside_tool_results(bottom)
        for p in ERROR_PATTERNS:
            m = p.search(outside)
            if m:
                for line in outside.split("\n"):
                    if m.group() in line:
                        return f"Error: {line.strip()[:80]}"
        return "Error detected"

    if state == AgentState.DONE:
        for p in COMPLETION_PATTERNS:
            m = p.search(bottom)
            if m:
                for line in bottom.split("\n"):
                    if m.group() in line:
                        return line.strip()[:100]
        return "Task completed"

    if state == AgentState.WORKING:
        # Find the most recent tool call
        tool_matches = list(_TOOL_HEADER_RE.finditer(bottom))
        if tool_matches:
            last = tool_matches[-1]
            tool_name = last.group(1)
            tool_args = last.group(2) or ""
            # Try to get the first content line after the tool header.
            # Skip to the next full line (the header match is mid-line).
            match_end = last.end()
            remaining = bottom[match_end:]
            lines_after = remaining.split("\n")
            # Skip the remainder of the header line (contains ─╮)
            if lines_after:
                lines_after = lines_after[1:]
            # Extract content lines: strip box chrome (│ prefix), skip box borders
            content_lines: list[str] = []
            for line in lines_after:
                stripped = line.strip()
                if not stripped:
                    continue
                # Skip box top/bottom borders
                if stripped.startswith(("╭", "┌", "╰", "└")) and "─" in stripped:
                    continue
                # Strip box-drawing left border
                cleaned = stripped.lstrip("│").strip()
                if cleaned:
                    content_lines.append(cleaned)
            first_content = content_lines[0][:60] if content_lines else ""
            if first_content:
                return f"{tool_name}: {first_content}"
            if tool_args:
                return f"{tool_name}({tool_args})"
            return f"Running {tool_name}"
        # Spinner/thinking with no tool call visible
        return "Thinking..."

    return "Unknown state"


# ---------------------------------------------------------------------------
# Main classification
# ---------------------------------------------------------------------------

def classify(snapshot: ScreenSnapshot) -> AgentStatus:
    """
    Classify the agent state from a terminal screen snapshot.

    Classification priority (highest to lowest):
    1. Shell (Claude exited) -- terminal-level, not Claude TUI
    2. Initializing -- Claude is still booting
    3. Waiting for approval -- permission prompt visible
    4. Errored -- error outside tool results
    5. Working -- tool calls or thinking indicators visible recently
    6. Done -- completion phrases + input prompt
    7. Waiting for input -- input prompt visible, no completion phrases
    8. Unknown

    The priority order matters: a permission prompt during a tool call means
    "waiting_approval", not "working". An error during initialization means
    "errored", not "initializing".
    """
    raw = snapshot.text
    text = strip_ansi(raw)

    bottom = _bottom(text, _BOTTOM_LINES)
    scan_area = _bottom(text, _SCAN_LINES)

    # 1. Shell -- Claude has exited entirely
    if _any_match(SHELL_PATTERNS, bottom):
        return AgentStatus(
            state=AgentState.SHELL,
            summary=_extract_summary(text, AgentState.SHELL),
            confidence=0.95,
            surface_id=snapshot.surface_id,
            captured_at=snapshot.captured_at,
        )

    # 2. Initializing -- very early in the session
    # Only if we see init patterns AND no tool calls yet
    if _any_match(INIT_PATTERNS, text) and not _any_match(TOOL_CALL_PATTERNS, text):
        return AgentStatus(
            state=AgentState.INITIALIZING,
            summary=_extract_summary(text, AgentState.INITIALIZING),
            confidence=0.8,
            surface_id=snapshot.surface_id,
            captured_at=snapshot.captured_at,
        )

    # 3. Waiting for approval -- permission prompt in bottom of screen
    if _any_match(PERMISSION_PATTERNS, bottom):
        return AgentStatus(
            state=AgentState.WAITING_APPROVAL,
            summary=_extract_summary(text, AgentState.WAITING_APPROVAL),
            confidence=0.9,
            surface_id=snapshot.surface_id,
            captured_at=snapshot.captured_at,
        )

    # 4. Errored -- error patterns OUTSIDE tool result boxes
    outside_results = _extract_outside_tool_results(scan_area)
    error_match = _any_match(ERROR_PATTERNS, outside_results)
    if error_match:
        # Check it's not just an old error scrolled up -- it should be in the
        # bottom portion. Also check there's no input prompt below it (which
        # would mean Claude recovered and is waiting for input).
        error_in_bottom = _any_match(ERROR_PATTERNS, _extract_outside_tool_results(bottom))
        has_prompt = bool(INPUT_PROMPT_RE.search(bottom))
        if error_in_bottom and not has_prompt:
            return AgentStatus(
                state=AgentState.ERRORED,
                summary=_extract_summary(text, AgentState.ERRORED),
                confidence=0.85,
                surface_id=snapshot.surface_id,
                captured_at=snapshot.captured_at,
            )

    # 5. Working -- tool calls or thinking indicators in bottom area
    tool_match = _any_match(TOOL_CALL_PATTERNS, scan_area)
    thinking_match = _any_match(THINKING_PATTERNS, bottom)

    # Tool call visible and no input prompt at bottom = still working
    if tool_match and not INPUT_PROMPT_RE.search(bottom):
        return AgentStatus(
            state=AgentState.WORKING,
            summary=_extract_summary(text, AgentState.WORKING),
            confidence=0.85,
            surface_id=snapshot.surface_id,
            captured_at=snapshot.captured_at,
        )

    if thinking_match:
        return AgentStatus(
            state=AgentState.WORKING,
            summary=_extract_summary(text, AgentState.WORKING),
            confidence=0.8,
            surface_id=snapshot.surface_id,
            captured_at=snapshot.captured_at,
        )

    # 6 & 7. Input prompt visible -- either done or waiting
    has_prompt = bool(INPUT_PROMPT_RE.search(bottom))
    if has_prompt:
        completion_match = _any_match(COMPLETION_PATTERNS, scan_area)
        if completion_match:
            return AgentStatus(
                state=AgentState.DONE,
                summary=_extract_summary(text, AgentState.DONE),
                confidence=0.85,
                surface_id=snapshot.surface_id,
                captured_at=snapshot.captured_at,
            )
        return AgentStatus(
            state=AgentState.WAITING_INPUT,
            summary=_extract_summary(text, AgentState.WAITING_INPUT),
            confidence=0.7,
            surface_id=snapshot.surface_id,
            captured_at=snapshot.captured_at,
        )

    # 8. Unknown
    return AgentStatus(
        state=AgentState.UNKNOWN,
        summary="Cannot determine agent state",
        confidence=0.0,
        surface_id=snapshot.surface_id,
        captured_at=snapshot.captured_at,
    )


# ---------------------------------------------------------------------------
# Polling controller
#
# Manages read frequency per surface to avoid hammering cmux.
# ---------------------------------------------------------------------------

@dataclass
class PollTiming:
    """Adaptive poll timing for a single surface."""
    surface_id: str
    last_poll: float = 0.0
    last_state: AgentState = AgentState.UNKNOWN
    consecutive_same: int = 0
    override_interval: float = 0.0  # If non-zero, use this instead of adaptive

    # Interval bounds in seconds
    MIN_INTERVAL: float = 1.0
    MAX_INTERVAL: float = 10.0
    # How many consecutive same-state readings before we slow down
    SLOWDOWN_THRESHOLD: int = 3

    def interval(self) -> float:
        """
        Compute the next poll interval based on current state.

        Fast polling (1-2s) for:
        - WORKING (output changing rapidly)
        - INITIALIZING (want to catch transition quickly)
        - UNKNOWN (need to establish state)

        Medium polling (3-5s) for:
        - WAITING_APPROVAL (user needs to see this, but it's stable)
        - ERRORED (stable, but user needs to know)

        Slow polling (5-10s) for:
        - DONE (nothing changing)
        - WAITING_INPUT (idle, nothing happening)
        - SHELL (terminal, nothing happening)

        Adaptive: if the state hasn't changed for SLOWDOWN_THRESHOLD polls,
        increase interval toward MAX_INTERVAL.
        """
        if self.override_interval > 0.0:
            return self.override_interval

        base: float
        match self.last_state:
            case AgentState.WORKING | AgentState.INITIALIZING | AgentState.UNKNOWN:
                base = 1.0
            case AgentState.WAITING_APPROVAL | AgentState.ERRORED:
                base = 3.0
            case AgentState.DONE | AgentState.WAITING_INPUT | AgentState.SHELL:
                base = 5.0

        # Slow down if state is stable
        if self.consecutive_same >= self.SLOWDOWN_THRESHOLD:
            extra = min(
                (self.consecutive_same - self.SLOWDOWN_THRESHOLD) * 1.0,
                self.MAX_INTERVAL - base,
            )
            base += max(0.0, extra)

        return min(base, self.MAX_INTERVAL)

    def should_poll(self) -> bool:
        """Return True if enough time has elapsed since the last poll."""
        return (time.monotonic() - self.last_poll) >= self.interval()

    def record(self, state: AgentState) -> None:
        """Record a poll result, updating adaptive timing."""
        self.last_poll = time.monotonic()
        if state == self.last_state:
            self.consecutive_same += 1
        else:
            self.consecutive_same = 0
            self.last_state = state


class PollScheduler:
    """Manages poll timing across multiple surfaces."""

    def __init__(self, override_interval: float = 0.0) -> None:
        self._timings: dict[str, PollTiming] = {}
        self._override_interval = override_interval

    def get_timing(self, surface_id: str) -> PollTiming:
        """Get or create timing state for a surface."""
        if surface_id not in self._timings:
            self._timings[surface_id] = PollTiming(
                surface_id=surface_id,
                override_interval=self._override_interval,
            )
        return self._timings[surface_id]

    def surfaces_due(self, surface_ids: list[str]) -> list[str]:
        """Return the subset of surface_ids that are due for polling."""
        return [
            sid for sid in surface_ids
            if self.get_timing(sid).should_poll()
        ]

    def record(self, surface_id: str, state: AgentState) -> None:
        """Record a poll result for a surface."""
        self.get_timing(surface_id).record(state)

    def remove(self, surface_id: str) -> None:
        """Stop tracking a surface."""
        self._timings.pop(surface_id, None)
