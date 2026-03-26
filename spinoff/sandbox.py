#!/usr/bin/env python3
"""
Sandbox Configuration for Worktrees

Configures Claude Code's built-in sandbox via --settings CLI flag.
This replaces the previous Docker/sandbox-exec approach with near-zero overhead.

Key advantages:
- ~0 RAM overhead (vs ~6GB for Docker)
- Instant startup (vs seconds for Docker)
- Native Keychain access for OAuth tokens
- No external dependencies (built into Claude Code)
- No settings.json files to accidentally commit (sandbox via CLI flag)
"""
# /// script
# requires-python = ">=3.11"
# ///

import json
import shutil
from typing import Optional


def claude_available() -> bool:
    """Check if claude CLI is available."""
    return shutil.which("claude") is not None


COMMIT_INSTRUCTIONS = (
    "\n\n---\n"
    "When you have completed all work, commit your changes before finishing:\n"
    "1. Stage all modified and new files with `git add` (use specific file paths, not `git add .`)\n"
    "2. Create a commit with a descriptive message summarizing what was done\n"
    "3. Verify with `git status` that the working tree is clean\n"
    "Do NOT push to a remote."
)


def get_claude_command(task: Optional[str] = None, mode: str = "implement", model: Optional[str] = None) -> list[str]:
    """
    Get claude command for interactive session.

    If a task is provided, it's passed as a positional argument to Claude,
    which will execute it automatically while remaining interactive.

    Args:
        task: Optional task description to pass to Claude
        mode: Agent mode - "plan" (read-only) or "implement" (sandbox, can write)
        model: Optional Claude model (e.g. "haiku", "sonnet", "opus")

    Returns:
        Claude command as list of arguments
    """
    cmd = ["claude"]

    if mode == "plan":
        cmd.extend(["--permission-mode", "plan"])
        if model:
            cmd.extend(["--settings", json.dumps({"model": model})])
    else:  # implement
        settings: dict[str, object] = {
            "sandbox": {
                "enabled": True,
                "autoAllowBashIfSandboxed": True
            }
        }
        if model:
            settings["model"] = model
        cmd.extend(["--settings", json.dumps(settings)])
        cmd.append("--dangerously-skip-permissions")

    if task:
        if mode == "implement":
            task = task + COMMIT_INSTRUCTIONS
        cmd.append(task)

    return cmd


if __name__ == "__main__":
    print("Claude Code Sandbox Configuration for Worktrees")
    print("=" * 50)
    print(f"Claude CLI available: {claude_available()}")
    print(f"\nImplement mode: {' '.join(get_claude_command(mode='implement'))}")
    print(f"Plan mode:      {' '.join(get_claude_command(mode='plan'))}")
