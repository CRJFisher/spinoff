"""Tests for spinoff_config.py."""

import json

import pytest

from spinoff_config import SpinoffConfig, load_config, save_config, CONFIG_FILENAME


class TestDefaults:
    def test_defaults(self):
        config = SpinoffConfig(project_name="my-app")
        assert config.default_mode == "implement"
        assert config.worktree_dir == ".worktrees"
        assert config.build_command == ""
        assert config.state_files == []

    def test_custom_values(self):
        config = SpinoffConfig(
            project_name="app",
            state_files=[".env"],
            build_command="npm install",
            worktree_dir="wt",
            default_mode="plan",
        )
        assert config.project_name == "app"
        assert config.state_files == [".env"]
        assert config.build_command == "npm install"
        assert config.worktree_dir == "wt"
        assert config.default_mode == "plan"


class TestSaveConfig:
    def test_save_creates_directory(self, tmp_path):
        config = SpinoffConfig(project_name="test")
        save_config(tmp_path, config)
        assert (tmp_path / CONFIG_FILENAME).exists()
        assert (tmp_path / ".claude").is_dir()

    def test_save_json_format(self, tmp_path):
        config = SpinoffConfig(project_name="test")
        save_config(tmp_path, config)
        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert content.endswith("\n")
        data = json.loads(content)
        assert data["project_name"] == "test"

    def test_overwrite(self, tmp_path):
        save_config(tmp_path, SpinoffConfig(project_name="first"))
        save_config(tmp_path, SpinoffConfig(project_name="second"))
        data = json.loads((tmp_path / CONFIG_FILENAME).read_text())
        assert data["project_name"] == "second"


class TestLoadConfig:
    def test_roundtrip(self, tmp_path):
        original = SpinoffConfig(
            project_name="app",
            state_files=[".env", ".env.local"],
            build_command="pnpm install",
            worktree_dir=".wt",
            default_mode="plan",
        )
        save_config(tmp_path, original)
        loaded = load_config(tmp_path)
        assert loaded.project_name == original.project_name
        assert loaded.state_files == original.state_files
        assert loaded.build_command == original.build_command
        assert loaded.worktree_dir == original.worktree_dir
        assert loaded.default_mode == original.default_mode

    def test_load_missing_optional_fields(self, tmp_path):
        config_file = tmp_path / CONFIG_FILENAME
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"project_name": "minimal"}))
        loaded = load_config(tmp_path)
        assert loaded.project_name == "minimal"
        assert loaded.state_files == []
        assert loaded.build_command == ""
        assert loaded.worktree_dir == ".worktrees"
        assert loaded.default_mode == "implement"

    def test_load_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            load_config(tmp_path)
        assert exc_info.value.code == 1
