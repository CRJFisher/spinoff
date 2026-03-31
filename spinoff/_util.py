"""Shared internal utilities."""

import subprocess
from pathlib import Path


def git_project_root() -> Path:
    """Detect the git repository root, falling back to cwd."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()
