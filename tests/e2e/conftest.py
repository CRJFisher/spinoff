"""E2E test fixtures and configuration."""

import json
import os
import subprocess
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

import spinoff.cmux as cmux


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip e2e tests if cmux is not available."""
    if not cmux.available():
        skip = pytest.mark.skip(reason="cmux not available")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip)


def _make_test_project(base_dir: Path, label: str) -> Path:
    """Create a git repo with spinoff config and initial commit."""
    project = base_dir / label
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

    return project


@pytest.fixture
def plugin_root() -> Path:
    """Path to the plugin root (repo root)."""
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def test_project(tmp_path: Path) -> Path:
    """Create a single git repo with spinoff config and initial commit on main."""
    return _make_test_project(tmp_path, "project")


@pytest.fixture
def test_project_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Create TWO git repos with unique project_name values."""
    return _make_test_project(tmp_path, "alpha"), _make_test_project(tmp_path, "beta")


@pytest.fixture(autouse=True)
def cleanup_workspaces() -> Generator[None, None, None]:
    """Track terminal workspaces before/after test, close new ones on teardown."""
    if not cmux.available():
        yield
        return

    before = {str(w.get("terminal_id", "")) for w in cmux.list_workspaces()}
    yield
    after = {str(w.get("terminal_id", "")) for w in cmux.list_workspaces()}
    new_workspaces = after - before
    for terminal_id in new_workspaces:
        cmux.close_workspace(terminal_id)


def run_create_worktree(
    project: Path,
    task_name: str,
    plugin_root: Path,
    **kwargs: str | None,
) -> subprocess.CompletedProcess[str]:
    """Helper to run spinoff.create for e2e tests."""
    cmd = [
        "python", "-m", "spinoff.create", task_name,
    ]

    for key, val in kwargs.items():
        if val is not None:
            cmd.extend([f"--{key}", str(val)])

    env_extra = {"PYTHONPATH": str(plugin_root)}
    env = {**os.environ, **env_extra}

    return subprocess.run(
        cmd, cwd=project, capture_output=True, text=True, env=env,
    )
