#!/usr/bin/env python3
"""
Agent Discovery

Discovers and parses Claude Code agent .md files from project-level
(.claude/agents/) and global (~/.claude/agents/) directories.
"""
# /// script
# requires-python = ">=3.11"
# ///

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AgentInfo:
    """Represents a discovered agent."""
    name: str
    description: str
    source: str  # "project" or "global"
    file_path: str


def _parse_frontmatter(file_path: Path) -> Optional[AgentInfo]:
    """
    Parse YAML frontmatter from an agent .md file.

    Extracts flat key: value pairs between --- delimiters.
    Returns None if no frontmatter or no name field found.
    """
    try:
        text = file_path.read_text()
    except (OSError, UnicodeDecodeError):
        return None

    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None

    frontmatter = match.group(1)
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        kv = re.match(r"^(\w[\w-]*)\s*:\s*(.+)$", line)
        if kv:
            fields[kv.group(1).strip()] = kv.group(2).strip()

    name = fields.get("name")
    if not name:
        return None

    return AgentInfo(
        name=name,
        description=fields.get("description", ""),
        source="",  # filled by caller
        file_path=str(file_path),
    )


def discover_agents(project_path: Path) -> list[AgentInfo]:
    """
    Scan project-level and global agent directories.

    Project agents (.claude/agents/) override global agents (~/.claude/agents/)
    when names collide.
    """
    agents_by_name: dict[str, AgentInfo] = {}

    # Global agents first (lower priority)
    global_dir = Path.home() / ".claude" / "agents"
    if global_dir.is_dir():
        for md_file in sorted(global_dir.glob("*.md")):
            info = _parse_frontmatter(md_file)
            if info:
                info.source = "global"
                agents_by_name[info.name] = info

    # Project agents override global
    project_dir = project_path / ".claude" / "agents"
    if project_dir.is_dir():
        for md_file in sorted(project_dir.glob("*.md")):
            info = _parse_frontmatter(md_file)
            if info:
                info.source = "project"
                agents_by_name[info.name] = info

    return sorted(agents_by_name.values(), key=lambda a: a.name)


def check_configured_agents(
    configured_names: list[str],
    project_path: Path,
) -> tuple[list[AgentInfo], list[str]]:
    """
    Validate that configured agent names exist.

    Returns:
        (found, missing) — found AgentInfo list and missing name list
    """
    available = {a.name: a for a in discover_agents(project_path)}
    found = []
    missing = []
    for name in configured_names:
        if name in available:
            found.append(available[name])
        else:
            missing.append(name)
    return found, missing


def cmd_discover(project_path: Path) -> None:
    """List all available agents."""
    agents = discover_agents(project_path)
    if not agents:
        print("No agents found.")
        print(f"  Project dir: {project_path / '.claude' / 'agents'}")
        print(f"  Global dir:  {Path.home() / '.claude' / 'agents'}")
        return

    print(f"Available agents ({len(agents)}):")
    for agent in agents:
        print(f"  {agent.name} ({agent.source}): {agent.description}")


def cmd_check(project_path: Path, names: list[str]) -> None:
    """Check which configured agents exist."""
    found, missing = check_configured_agents(names, project_path)
    if found:
        print(f"Found ({len(found)}):")
        for a in found:
            print(f"  {a.name} ({a.source}): {a.description}")
    if missing:
        print(f"Missing ({len(missing)}):")
        for name in missing:
            print(f"  {name}")


if __name__ == "__main__":
    import argparse
    import sys

    from spinoff._util import git_project_root

    default_project = git_project_root()

    parser = argparse.ArgumentParser(
        description="Discover and manage Claude Code agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m spinoff.agents discover
  python -m spinoff.agents check refactor-reviewer code-reviewer
""",
    )
    parser.add_argument(
        "-p", "--project",
        type=Path,
        default=default_project,
        help=f"Project path (default: {default_project})",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # discover command
    subparsers.add_parser("discover", help="List all available agents")

    # check command
    check_parser = subparsers.add_parser("check", help="Check if agents exist")
    check_parser.add_argument("names", nargs="+", help="Agent names to check")

    args = parser.parse_args()

    if args.command == "discover":
        cmd_discover(args.project)
    elif args.command == "check":
        cmd_check(args.project, args.names)
    else:
        parser.print_help()
        sys.exit(1)
