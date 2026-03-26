"""Shared test fixtures for spinoff tests."""

from pathlib import Path

import pytest

from spinoff.config import SpinoffConfig, save_config


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with spinoff config."""
    config = SpinoffConfig(
        project_name="test-project",
        state_files=[],
        build_command="",
        worktree_dir=".claude/worktrees",
        default_mode="implement",
    )
    save_config(tmp_path, config)
    return tmp_path
