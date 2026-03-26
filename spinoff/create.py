#!/usr/bin/env python3
"""
Spinoff Worktree Creator

Creates isolated worktrees with a terminal backend (cmux or WezTerm) +
Claude Code's built-in sandbox. Each worktree gets a sandboxed Claude
session in its own terminal workspace.

Flow:
1. Create git worktree
2. Copy state files (.env, etc.)
3. Open terminal workspace that chains build command + Claude (sandbox enabled via --settings flag)
"""
# /// script
# requires-python = ">=3.11"
# ///

import argparse
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from spinoff.backends import get_backend
from spinoff.config import load_config
from spinoff.sandbox import claude_available, get_claude_command
from spinoff.state import DependencyError, add_worktree


def sanitize_task_name(raw: str) -> str:
    """Sanitize and validate a task name. Raises ValueError if invalid."""
    safe = raw.replace("/", "-").replace(" ", "-").lower().strip("-")
    if not safe or safe in (".", ".."):
        raise ValueError(f"Invalid task name: '{raw}'")
    if safe.startswith("-") or safe.startswith("."):
        raise ValueError(f"Task name cannot start with '-' or '.': '{safe}'")
    if ".." in safe:
        raise ValueError(f"Task name cannot contain '..': '{safe}'")
    if not all(c.isalnum() or c in "-_" for c in safe):
        raise ValueError(f"Task name contains invalid characters: '{safe}'")
    return safe


def write_startup_script(
    script_path: Path,
    worktree_path: Path,
    build_command: str,
    claude_cmd: list[str],
) -> Path:
    """
    Write a startup script that runs the build and then Claude.

    The script is placed as a sibling to the worktree directory inside
    the worktree_dir (e.g. .claude/worktrees/), which is gitignored. Each command is on its own
    line — no nested quoting needed.

    On any failure (build or Claude exit), `exec bash` keeps the tab alive
    so the user can inspect errors or interact.

    Args:
        script_path: Where to write the script
        worktree_path: Absolute path to the worktree directory
        build_command: Shell command to run before Claude (may be empty)
        claude_cmd: Claude command as list of arguments

    Returns:
        Path to the written script
    """
    lines = ["#!/bin/bash"]
    lines.append(f"cd {shlex.quote(str(worktree_path))}")
    lines.append("")

    # Clear parent Claude Code session markers so the child doesn't
    # refuse to start ("cannot be launched inside another session")
    lines.append("unset CLAUDECODE")
    lines.append("unset CLAUDE_CODE_ENTRYPOINT")
    lines.append("")

    if build_command:
        lines.append("# Run build")
        lines.append(build_command)
        lines.append('if [ $? -ne 0 ]; then')
        lines.append('    echo "Build failed. Shell kept open for debugging."')
        lines.append('    exec bash')
        lines.append("fi")
        lines.append("")

    lines.append("# Run Claude")
    claude_cmd_str = " ".join(shlex.quote(c) for c in claude_cmd)
    lines.append(claude_cmd_str)
    lines.append("")

    lines.append("# Keep shell alive after Claude exits")
    lines.append('echo "Claude exited. Shell kept open."')
    lines.append("exec bash")

    script_path.write_text("\n".join(lines) + "\n")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return script_path


def main():
    parser = argparse.ArgumentParser(
        description="Create a worktree for parallel development (terminal + Claude sandbox)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m spinoff.create fix-auth-bug
  python -m spinoff.create feat-dark-mode --base develop
  python -m spinoff.create JIRA-1234 --task "Implement user profile page"
""",
    )
    parser.add_argument("task_name", help="Name for the task/branch")
    parser.add_argument("-b", "--base", help="Base branch (default: current)")
    parser.add_argument(
        "-t", "--task",
        help="Task description to pass to Claude agent",
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=["plan", "implement"],
        help="Agent mode: plan (read-only) or implement (sandbox + auto-commit). Falls back to config default_mode.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Claude model (e.g. haiku, sonnet, opus)",
    )
    parser.add_argument(
        "--depends-on",
        default=None,
        help="Comma-separated list of worktree names this task depends on",
    )
    args = parser.parse_args()

    # Validate Claude prerequisite
    if not claude_available():
        print("Error: Claude CLI is not available", file=sys.stderr)
        print("  Install Claude Code and try again.", file=sys.stderr)
        sys.exit(1)

    # Get repo root
    repo_root = Path(subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True
    ).stdout.strip())

    # Load project config
    config = load_config(repo_root)

    # Get terminal backend
    try:
        backend = get_backend(config)
    except (RuntimeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    if not backend.available():
        print("Error: No terminal backend available", file=sys.stderr)
        sys.exit(1)

    # Sanitize and validate task name
    try:
        safe_name = sanitize_task_name(args.task_name)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    worktree_path = repo_root / config.worktree_dir / safe_name
    branch_name = f"worktree/{safe_name}"

    if worktree_path.exists():
        print(f"Error: {worktree_path} already exists", file=sys.stderr)
        sys.exit(1)

    # Parse and validate dependencies early (before creating resources)
    depends_on: list[str] | None = None
    if args.depends_on:
        depends_on = [d.strip() for d in args.depends_on.split(",") if d.strip()] or None
    if depends_on:
        from spinoff.state import load_state, validate_dependencies
        try:
            state = load_state(repo_root)
            validate_dependencies(state, safe_name, depends_on)
        except DependencyError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Get base branch
    base = args.base or subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True
    ).stdout.strip()

    # Create worktree
    print(f"Creating worktree: {safe_name} (from {base})")
    (repo_root / config.worktree_dir).mkdir(exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", branch_name, str(worktree_path), base],
        check=True, cwd=repo_root
    )

    # Copy state files
    for f in config.state_files:
        src = repo_root / f
        if src.exists():
            dest = worktree_path / f
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"  Copied: {f}")

    # Resolve mode: explicit flag > config default
    mode = args.mode or config.default_mode

    # Build claude command (pass task as positional arg if provided)
    claude_cmd = get_claude_command(task=args.task, mode=mode, model=args.model)
    tab_title = f"wt: {safe_name}"

    # Generate startup script as sibling to the worktree directory
    script_path = repo_root / config.worktree_dir / f"{safe_name}.start.sh"
    write_startup_script(
        script_path=script_path,
        worktree_path=worktree_path,
        build_command=config.build_command,
        claude_cmd=claude_cmd,
    )
    if config.build_command:
        print(f"  Build will run in terminal workspace: {config.build_command}")
    tab_cmd = [str(script_path)]

    # Create terminal workspace for this worktree
    print("  Opening terminal workspace...")
    success, terminal_id, msg = backend.create_workspace(
        title=tab_title,
        cwd=worktree_path,
        command=tab_cmd,
        project_name=config.project_name,
    )
    if not success:
        print(f"  Warning: {msg}", file=sys.stderr)
        terminal_id = None

    # Update state file
    add_worktree(
        repo_root,
        name=safe_name,
        worktree_path=str(worktree_path.relative_to(repo_root)),
        branch=branch_name,
        base_branch=base,
        terminal_id=terminal_id,
        depends_on=depends_on,
    )

    # Print summary
    print(f"\nWorktree ready at: {worktree_path}")
    print(f"Branch: {branch_name}")
    print(f"Mode: {mode}")
    if mode == "implement":
        print(f"Sandbox: enabled (Claude Code built-in)")
        print(f"Auto-commit: agent will commit before finishing")
    else:
        print(f"Plan mode: read-only exploration (no sandbox)")
    if terminal_id:
        print(f"Terminal: {tab_title} (id {terminal_id})")
    if args.task:
        print(f"Task: {args.task}")


if __name__ == "__main__":
    main()
