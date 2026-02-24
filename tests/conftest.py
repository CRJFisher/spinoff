"""Shared test fixtures for spinoff tests."""

import json
from pathlib import Path

import pytest

from spinoff.config import SpinoffConfig, CONFIG_FILENAME


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project directory with spinoff config."""
    config = SpinoffConfig(
        project_name="test-project",
        state_files=[],
        build_command="",
        worktree_dir=".claude/worktrees",
        default_mode="implement",
    )
    config_file = tmp_path / CONFIG_FILENAME
    config_file.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "project_name": config.project_name,
        "state_files": config.state_files,
        "build_command": config.build_command,
        "worktree_dir": config.worktree_dir,
        "default_mode": config.default_mode,
    }
    config_file.write_text(json.dumps(data, indent=2) + "\n")
    return tmp_path
