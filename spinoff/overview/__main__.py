"""CLI entry point for spinoff.overview."""

import argparse
import subprocess
import sys
from pathlib import Path

from spinoff.overview import close_overview, cmd_approve, cmd_status, open_overview
from spinoff.overview.poller import watch


def main() -> None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        default_project = Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        default_project = Path.cwd()

    parser = argparse.ArgumentParser(
        description="Spinoff overview panel and agent management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m spinoff.overview                    Open or focus the overview panel
  python -m spinoff.overview --close            Close the overview panel
  python -m spinoff.overview status             Text-based agent status table
  python -m spinoff.overview approve fix-auth   Approve an agent's pending prompt
  python -m spinoff.overview watch              Start the overview poller (internal)
""",
    )
    parser.add_argument(
        "-p", "--project", type=Path, default=default_project,
        help=f"Project path (default: {default_project})",
    )
    parser.add_argument(
        "--close", action="store_true",
        help="Close the overview panel",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.add_parser("status", help="Print agent status table")

    approve_parser = subparsers.add_parser("approve", help="Approve agent permission prompt")
    approve_parser.add_argument("name", help="Agent/worktree name")

    subparsers.add_parser("watch", help="Start the overview poller (internal)")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args.project)
    elif args.command == "approve":
        cmd_approve(args.project, args.name)
    elif args.command == "watch":
        watch(args.project)
    elif args.close:
        ok, msg = close_overview(args.project)
        print(msg)
        if not ok:
            sys.exit(1)
    else:
        ok, msg = open_overview(args.project)
        print(msg)
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
