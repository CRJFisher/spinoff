#!/usr/bin/env python3
"""
Spinoff Worktree Creator

Creates isolated worktrees with WezTerm + Claude Code's built-in sandbox.
Each worktree gets a sandboxed Claude session in a WezTerm tab.

Flow:
1. Create git worktree
2. Copy state files (.env, etc.)
3. Open WezTerm tab that chains build command + Claude (sandbox enabled via --settings flag)
"""
# /// script
# requires-python = ">=3.11"
# ///

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# Ensure sibling modules are importable (plugin directory)
sys.path.insert(0, str(Path(__file__).parent))

from spinoff_config import load_config
from worktree_state import add_worktree
from worktree_sandbox import claude_available, get_claude_command
from worktree_wezterm import ensure_wezterm_running, create_tab


def main():
    parser = argparse.ArgumentParser(
        description="Create a worktree for parallel development (WezTerm + Claude sandbox)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_worktree.py fix-auth-bug
  python create_worktree.py feat-dark-mode --base develop
  python create_worktree.py JIRA-1234 --task "Implement user profile page"
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
    args = parser.parse_args()

    # Validate prerequisites
    if not ensure_wezterm_running():
        print("Error: WezTerm CLI not available or failed to start", file=sys.stderr)
        sys.exit(1)

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

    # Sanitize and validate task name
    safe_name = args.task_name.replace("/", "-").replace(" ", "-").lower()
    safe_name = safe_name.strip("-")

    if not safe_name or safe_name in (".", ".."):
        print(f"Error: Invalid task name: '{args.task_name}'", file=sys.stderr)
        sys.exit(1)
    if safe_name.startswith("-") or safe_name.startswith("."):
        print(f"Error: Task name cannot start with '-' or '.': '{safe_name}'", file=sys.stderr)
        sys.exit(1)
    if ".." in safe_name:
        print(f"Error: Task name cannot contain '..': '{safe_name}'", file=sys.stderr)
        sys.exit(1)
    if not all(c.isalnum() or c in "-_" for c in safe_name):
        print(f"Error: Task name contains invalid characters: '{safe_name}'", file=sys.stderr)
        print("  Use only letters, numbers, hyphens, and underscores.", file=sys.stderr)
        sys.exit(1)

    worktree_path = repo_root / config.worktree_dir / safe_name
    branch_name = f"worktree/{safe_name}"

    if worktree_path.exists():
        print(f"Error: {worktree_path} already exists", file=sys.stderr)
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
    claude_cmd = get_claude_command(task=args.task, mode=mode)
    tab_title = f"wt: {safe_name}"

    # Chain build command and claude command in the WezTerm tab
    # Build runs in the tab so the user isn't blocked, and errors are visible there
    if config.build_command:
        print(f"  Build will run in WezTerm tab: {config.build_command}")
        claude_cmd_str = " ".join(shlex.quote(c) for c in claude_cmd)
        tab_cmd = ["bash", "-c", f"{config.build_command} && {claude_cmd_str}"]
    else:
        tab_cmd = claude_cmd

    # Create WezTerm tab in project-specific workspace
    print("  Opening WezTerm tab...")
    success, pane_id, msg = create_tab(
        title=tab_title,
        cwd=worktree_path,
        command=tab_cmd,
        workspace=config.project_name,
    )
    if not success:
        print(f"  Warning: {msg}", file=sys.stderr)
        pane_id = None

    # Update state file
    add_worktree(
        repo_root,
        name=safe_name,
        worktree_path=str(worktree_path.relative_to(repo_root)),
        branch=branch_name,
        base_branch=base,
        pane_id=pane_id,
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
    if pane_id:
        print(f"WezTerm tab: {tab_title} (pane {pane_id})")
    if args.task:
        print(f"Task: {args.task}")


if __name__ == "__main__":
    main()
