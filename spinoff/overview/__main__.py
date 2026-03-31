"""CLI entry point for spinoff.overview."""

import argparse
import sys
from pathlib import Path

import spinoff.cmux as cmux
from spinoff._util import git_project_root
from spinoff.overview import close_overview, open_overview
from spinoff.overview.poller import watch
from spinoff.state import load_state


def main() -> None:
    default_project = git_project_root()

    parser = argparse.ArgumentParser(
        description="Spinoff overview panel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m spinoff.overview                    Open or focus the overview panel
  python -m spinoff.overview --close            Close the overview panel
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
    subparsers.add_parser("watch", help="Start the overview poller (internal)")

    args = parser.parse_args()

    if args.command == "watch":
        watch(args.project)
    elif args.close:
        ok, msg = close_overview(args.project)
        print(msg)
        if not ok:
            sys.exit(1)
    else:
        window_id = cmux.get_window_id()
        if window_id is None:
            window_id = load_state(args.project).window_id
        ok, msg = open_overview(args.project, window_id=window_id)
        print(msg)
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
