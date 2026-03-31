"""Tests for spinoff.create."""

import os
import stat
from pathlib import Path

import pytest

from spinoff.create import sanitize_task_name, write_startup_script


class TestSanitizeTaskName:
    def test_slashes_to_hyphens(self) -> None:
        assert sanitize_task_name("feat/auth") == "feat-auth"

    def test_spaces_to_hyphens(self) -> None:
        assert sanitize_task_name("fix bug") == "fix-bug"

    def test_lowercasing(self) -> None:
        assert sanitize_task_name("Fix-Auth") == "fix-auth"

    def test_strip_leading_hyphens(self) -> None:
        assert sanitize_task_name("-fix") == "fix"

    def test_strip_trailing_hyphens(self) -> None:
        assert sanitize_task_name("fix-") == "fix"

    def test_accepts_hyphens(self) -> None:
        assert sanitize_task_name("fix-auth-bug") == "fix-auth-bug"

    def test_accepts_underscores(self) -> None:
        assert sanitize_task_name("fix_auth") == "fix_auth"

    def test_accepts_alphanumeric(self) -> None:
        assert sanitize_task_name("fix123") == "fix123"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="Invalid task name"):
            sanitize_task_name("")

    def test_rejects_dot(self) -> None:
        with pytest.raises(ValueError, match="Invalid task name"):
            sanitize_task_name(".")

    def test_rejects_dotdot(self) -> None:
        with pytest.raises(ValueError, match="Invalid task name"):
            sanitize_task_name("..")

    def test_rejects_leading_dot(self) -> None:
        with pytest.raises(ValueError, match="cannot start with"):
            sanitize_task_name(".hidden")

    def test_rejects_embedded_dotdot(self) -> None:
        with pytest.raises(ValueError, match="cannot contain"):
            sanitize_task_name("a..b")

    def test_rejects_at_sign(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            sanitize_task_name("fix@auth")

    def test_rejects_exclamation(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            sanitize_task_name("fix!now")

    def test_rejects_hash(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            sanitize_task_name("fix#123")

    def test_complex_sanitization(self) -> None:
        assert sanitize_task_name("Feature/Add Login") == "feature-add-login"

    def test_only_hyphens_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid task name"):
            sanitize_task_name("---")


class TestWriteStartupScript:
    def test_has_shebang(self, tmp_path: Path) -> None:
        script = tmp_path / "start.sh"
        write_startup_script(script, tmp_path / "wt", "", ["claude"])
        content = script.read_text()
        assert content.startswith("#!/bin/bash\n")

    def test_has_cd(self, tmp_path: Path) -> None:
        wt = tmp_path / "wt"
        script = tmp_path / "start.sh"
        write_startup_script(script, wt, "", ["claude"])
        content = script.read_text()
        assert f"cd '{wt}'" in content or f'cd "{wt}"' in content or f"cd {wt}" in content

    def test_has_claude_command(self, tmp_path: Path) -> None:
        script = tmp_path / "start.sh"
        write_startup_script(script, tmp_path / "wt", "", ["claude", "--flag"])
        content = script.read_text()
        assert "claude" in content
        assert "--flag" in content

    def test_has_exec_bash(self, tmp_path: Path) -> None:
        script = tmp_path / "start.sh"
        write_startup_script(script, tmp_path / "wt", "", ["claude"])
        content = script.read_text()
        assert "exec bash" in content

    def test_with_build_includes_build_command(self, tmp_path: Path) -> None:
        script = tmp_path / "start.sh"
        write_startup_script(script, tmp_path / "wt", "npm install", ["claude"])
        content = script.read_text()
        assert "npm install" in content
        assert "Build failed" in content

    def test_without_build_omits_build(self, tmp_path: Path) -> None:
        script = tmp_path / "start.sh"
        write_startup_script(script, tmp_path / "wt", "", ["claude"])
        content = script.read_text()
        assert "Run build" not in content
        assert "Build failed" not in content

    def test_executable_permission(self, tmp_path: Path) -> None:
        script = tmp_path / "start.sh"
        write_startup_script(script, tmp_path / "wt", "", ["claude"])
        mode = script.stat().st_mode
        assert mode & stat.S_IXUSR

    def test_paths_with_spaces_quoted(self, tmp_path: Path) -> None:
        wt = tmp_path / "my worktree"
        script = tmp_path / "start.sh"
        write_startup_script(script, wt, "", ["claude"])
        content = script.read_text()
        # shlex.quote wraps paths with spaces in single quotes
        assert f"'{wt}'" in content
