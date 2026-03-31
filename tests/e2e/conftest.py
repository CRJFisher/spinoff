"""E2E test fixtures and configuration."""

import json
import subprocess
import uuid
from pathlib import Path

import pytest

import spinoff.cmux as cmux


def pytest_collection_modifyitems(config, items):
    """Auto-skip e2e tests if cmux is not available."""
    if not cmux.available():
        skip = pytest.mark.skip(reason="cmux not available")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip)


@pytest.fixture
def plugin_root():
    """Path to the plugin root (repo root)."""
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def test_project(tmp_path):
    """Create a single git repo with spinoff config and initial commit on main."""
    project = tmp_path / "project"
    project.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True,
                    capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project,
                    capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project,
                    capture_output=True)

    # Create spinoff config
    config_dir = project / ".claude"
    config_dir.mkdir()
    config = {
        "project_name": f"e2e-{uuid.uuid4().hex[:8]}",
        "state_files": [],
        "build_command": "",
        "worktree_dir": ".claude/worktrees",
        "default_mode": "implement",
    }
    (config_dir / "spinoff.json").write_text(json.dumps(config, indent=2) + "\n")

    # Initial commit
    (project / "README.md").write_text("# Test Project\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project, check=True,
                    capture_output=True)

    return project


@pytest.fixture
def test_project_pair(tmp_path):
    """Create TWO git repos with unique project_name values."""
    projects = []
    for label in ("alpha", "beta"):
        project = tmp_path / label
        project.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True,
                        capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project,
                        capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=project,
                        capture_output=True)

        config_dir = project / ".claude"
        config_dir.mkdir()
        config = {
            "project_name": f"e2e-{label}-{uuid.uuid4().hex[:8]}",
            "state_files": [],
            "build_command": "",
            "worktree_dir": ".claude/worktrees",
            "default_mode": "implement",
        }
        (config_dir / "spinoff.json").write_text(json.dumps(config, indent=2) + "\n")

        (project / "README.md").write_text(f"# {label}\n")
        subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project, check=True,
                        capture_output=True)
        projects.append(project)

    return projects[0], projects[1]


@pytest.fixture(autouse=True)
def cleanup_terminals():
    """Track terminal workspaces before/after test, close new ones on teardown."""
    if not cmux.available():
        yield
        return

    before = {w.get("terminal_id", "") for w in cmux.list_workspaces()}
    yield
    after = {w.get("terminal_id", "") for w in cmux.list_workspaces()}
    new_workspaces = after - before
    for terminal_id in new_workspaces:
        cmux.close_workspace(terminal_id)


def run_create_worktree(project, task_name, plugin_root, **kwargs):
    """Helper to run spinoff.create for e2e tests."""
    cmd = [
        "python", "-m", "spinoff.create", task_name,
    ]

    for key, val in kwargs.items():
        if val is not None:
            cmd.extend([f"--{key}", str(val)])

    env_extra = {"PYTHONPATH": str(plugin_root)}
    import os
    env = {**os.environ, **env_extra}

    result = subprocess.run(
        cmd, cwd=project, capture_output=True, text=True, env=env,
    )
    return result
