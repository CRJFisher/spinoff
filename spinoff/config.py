#!/usr/bin/env python3
"""
Spinoff Configuration

Loads per-project configuration from .claude/spinoff.json.
This replaces the old placeholder-replacement pattern where values
were baked into scripts at setup time.
"""
# /// script
# requires-python = ">=3.11"
# ///

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NotificationConfig:
    """Notification preferences for the overview panel."""
    desktop: bool = True
    flash: bool = True
    on_done: bool = True
    on_error: bool = True
    on_waiting: bool = True
    cooldown_urgent_secs: int = 30
    cooldown_info_secs: int = 60


@dataclass
class SpinoffConfig:
    """Per-project spinoff configuration."""
    project_name: str
    state_files: list[str] = field(default_factory=list)
    build_command: str = ""
    worktree_dir: str = ".claude/worktrees"
    default_mode: str = "implement"
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    overview_poll_interval: float = 0.0  # 0.0 = use adaptive


CONFIG_FILENAME = ".claude/spinoff.json"


def load_config(project_path: Path) -> SpinoffConfig:
    """
    Load spinoff configuration from .claude/spinoff.json.

    Args:
        project_path: Root of the git repository

    Returns:
        SpinoffConfig with project settings

    Raises:
        SystemExit: If config file is missing
    """
    config_file = project_path / CONFIG_FILENAME

    if not config_file.exists():
        import sys
        print(
            f"Error: No spinoff config found at {config_file}\n"
            f"Run /spinoff:init first to configure this project.",
            file=sys.stderr,
        )
        sys.exit(1)

    data = json.loads(config_file.read_text())

    notif_data = data.get("notifications", {})
    notifications = NotificationConfig(
        desktop=notif_data.get("desktop", True),
        flash=notif_data.get("flash", True),
        on_done=notif_data.get("on_done", True),
        on_error=notif_data.get("on_error", True),
        on_waiting=notif_data.get("on_waiting", True),
        cooldown_urgent_secs=notif_data.get("cooldown_urgent_secs", 30),
        cooldown_info_secs=notif_data.get("cooldown_info_secs", 60),
    )

    return SpinoffConfig(
        project_name=data["project_name"],
        state_files=data.get("state_files", []),
        build_command=data.get("build_command", ""),
        worktree_dir=data.get("worktree_dir", ".claude/worktrees"),
        default_mode=data.get("default_mode", "implement"),
        notifications=notifications,
        overview_poll_interval=data.get("overview_poll_interval", 0.0),
    )


def save_config(project_path: Path, config: SpinoffConfig) -> None:
    """
    Save spinoff configuration to .claude/spinoff.json.

    Args:
        project_path: Root of the git repository
        config: Configuration to save
    """
    config_file = project_path / CONFIG_FILENAME
    config_file.parent.mkdir(parents=True, exist_ok=True)

    notif = config.notifications
    notif_defaults = NotificationConfig()
    notif_data: dict[str, bool | int] = {}
    if notif.desktop != notif_defaults.desktop:
        notif_data["desktop"] = notif.desktop
    if notif.flash != notif_defaults.flash:
        notif_data["flash"] = notif.flash
    if notif.on_done != notif_defaults.on_done:
        notif_data["on_done"] = notif.on_done
    if notif.on_error != notif_defaults.on_error:
        notif_data["on_error"] = notif.on_error
    if notif.on_waiting != notif_defaults.on_waiting:
        notif_data["on_waiting"] = notif.on_waiting
    if notif.cooldown_urgent_secs != notif_defaults.cooldown_urgent_secs:
        notif_data["cooldown_urgent_secs"] = notif.cooldown_urgent_secs
    if notif.cooldown_info_secs != notif_defaults.cooldown_info_secs:
        notif_data["cooldown_info_secs"] = notif.cooldown_info_secs

    data: dict[str, object] = {
        "project_name": config.project_name,
        "state_files": config.state_files,
        "build_command": config.build_command,
        "worktree_dir": config.worktree_dir,
        "default_mode": config.default_mode,
    }
    if notif_data:
        data["notifications"] = notif_data
    if config.overview_poll_interval != 0.0:
        data["overview_poll_interval"] = config.overview_poll_interval

    config_file.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    import argparse
    import subprocess
    import sys

    # Try to detect project root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        default_project = Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        default_project = Path.cwd()

    parser = argparse.ArgumentParser(
        description="Manage spinoff configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m spinoff.config show
  python -m spinoff.config save --project-name my-app --build-command "pnpm install"
  python -m spinoff.config save --project-name my-app --state-files .env .env.local
""",
    )
    parser.add_argument(
        "-p", "--project",
        type=Path,
        default=default_project,
        help=f"Project path (default: {default_project})",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # show command
    subparsers.add_parser("show", help="Show current configuration")

    # save command
    save_parser = subparsers.add_parser("save", help="Save configuration")
    save_parser.add_argument("--project-name", required=True, help="Project name")
    save_parser.add_argument("--state-files", nargs="*", default=[], help="State files to copy")
    save_parser.add_argument("--build-command", default="", help="Build command")
    save_parser.add_argument("--worktree-dir", default=".claude/worktrees", help="Worktree directory")
    save_parser.add_argument("--default-mode", default="implement", choices=["plan", "implement"], help="Default agent mode (default: implement)")
    args = parser.parse_args()

    if args.command == "show":
        config = load_config(args.project)
        print(f"Project:       {config.project_name}")
        print(f"State files:   {config.state_files}")
        print(f"Build command: {config.build_command}")
        print(f"Worktree dir:  {config.worktree_dir}")
        print(f"Default mode:  {config.default_mode}")
        print(f"Config file:   {args.project / CONFIG_FILENAME}")
    elif args.command == "save":
        config = SpinoffConfig(
            project_name=args.project_name,
            state_files=args.state_files,
            build_command=args.build_command,
            worktree_dir=args.worktree_dir,
            default_mode=args.default_mode,
        )
        save_config(args.project, config)
        print(f"Saved config to {args.project / CONFIG_FILENAME}")
    else:
        parser.print_help()
        sys.exit(1)
