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
class SpinoffConfig:
    """Per-project spinoff configuration."""
    project_name: str
    state_files: list[str] = field(default_factory=list)
    build_command: str = ""
    worktree_dir: str = ".worktrees"


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

    return SpinoffConfig(
        project_name=data["project_name"],
        state_files=data.get("state_files", []),
        build_command=data.get("build_command", ""),
        worktree_dir=data.get("worktree_dir", ".worktrees"),
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

    data = {
        "project_name": config.project_name,
        "state_files": config.state_files,
        "build_command": config.build_command,
        "worktree_dir": config.worktree_dir,
    }

    config_file.write_text(json.dumps(data, indent=2) + "\n")
