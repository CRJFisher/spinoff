"""Tests for spinoff.config."""

import json
from pathlib import Path

import pytest

from spinoff.config import ConfigError, NotificationConfig, SpinoffConfig, load_config, save_config, CONFIG_FILENAME


class TestDefaults:
    def test_defaults(self) -> None:
        config = SpinoffConfig(project_name="my-app")
        assert config.default_mode == "implement"
        assert config.worktree_dir == ".claude/worktrees"
        assert config.build_command == ""
        assert config.state_files == []

    def test_custom_values(self) -> None:
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
    def test_save_creates_directory(self, tmp_path: Path) -> None:
        config = SpinoffConfig(project_name="test")
        save_config(tmp_path, config)
        assert (tmp_path / CONFIG_FILENAME).exists()
        assert (tmp_path / ".claude").is_dir()

    def test_save_json_format(self, tmp_path: Path) -> None:
        config = SpinoffConfig(project_name="test")
        save_config(tmp_path, config)
        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert content.endswith("\n")
        data = json.loads(content)
        assert data["project_name"] == "test"

    def test_overwrite(self, tmp_path: Path) -> None:
        save_config(tmp_path, SpinoffConfig(project_name="first"))
        save_config(tmp_path, SpinoffConfig(project_name="second"))
        data = json.loads((tmp_path / CONFIG_FILENAME).read_text())
        assert data["project_name"] == "second"


class TestLoadConfig:
    def test_roundtrip(self, tmp_path: Path) -> None:
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

    def test_load_missing_optional_fields(self, tmp_path: Path) -> None:
        config_file = tmp_path / CONFIG_FILENAME
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"project_name": "minimal"}))
        loaded = load_config(tmp_path)
        assert loaded.project_name == "minimal"
        assert loaded.state_files == []
        assert loaded.build_command == ""
        assert loaded.worktree_dir == ".claude/worktrees"
        assert loaded.default_mode == "implement"

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="No spinoff config found"):
            load_config(tmp_path)

    def test_load_malformed_json_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / CONFIG_FILENAME
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("{bad json")
        with pytest.raises(ConfigError, match="Malformed JSON"):
            load_config(tmp_path)


class TestNotificationConfig:
    def test_defaults(self) -> None:
        nc = NotificationConfig()
        assert nc.desktop is True
        assert nc.flash is True
        assert nc.on_done is True
        assert nc.cooldown_urgent_secs == 30
        assert nc.cooldown_info_secs == 60

    def test_spinoff_config_default_notifications(self) -> None:
        config = SpinoffConfig(project_name="test")
        assert config.notifications.desktop is True
        assert config.overview_poll_interval == 0.0

    def test_load_missing_notifications(self, tmp_path: Path) -> None:
        config_file = tmp_path / CONFIG_FILENAME
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({"project_name": "old"}))
        loaded = load_config(tmp_path)
        assert loaded.notifications.desktop is True
        assert loaded.overview_poll_interval == 0.0

    def test_load_partial_notifications(self, tmp_path: Path) -> None:
        config_file = tmp_path / CONFIG_FILENAME
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(json.dumps({
            "project_name": "p",
            "notifications": {"desktop": False, "cooldown_urgent_secs": 10},
        }))
        loaded = load_config(tmp_path)
        assert loaded.notifications.desktop is False
        assert loaded.notifications.cooldown_urgent_secs == 10
        assert loaded.notifications.flash is True  # default

    def test_roundtrip_with_notifications(self, tmp_path: Path) -> None:
        nc = NotificationConfig(desktop=False, cooldown_urgent_secs=15)
        original = SpinoffConfig(project_name="app", notifications=nc, overview_poll_interval=3.0)
        save_config(tmp_path, original)
        loaded = load_config(tmp_path)
        assert loaded.notifications.desktop is False
        assert loaded.notifications.cooldown_urgent_secs == 15
        assert loaded.notifications.flash is True
        assert loaded.overview_poll_interval == 3.0

    def test_save_omits_default_notifications(self, tmp_path: Path) -> None:
        config = SpinoffConfig(project_name="clean")
        save_config(tmp_path, config)
        data = json.loads((tmp_path / CONFIG_FILENAME).read_text())
        assert "notifications" not in data
        assert "overview_poll_interval" not in data

    def test_save_includes_non_default(self, tmp_path: Path) -> None:
        nc = NotificationConfig(desktop=False)
        config = SpinoffConfig(project_name="x", notifications=nc)
        save_config(tmp_path, config)
        data = json.loads((tmp_path / CONFIG_FILENAME).read_text())
        assert data["notifications"] == {"desktop": False}
