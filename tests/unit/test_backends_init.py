"""Tests for spinoff.backends — auto-detection logic."""

from unittest.mock import MagicMock, patch

import pytest

from spinoff.backends import get_backend
from spinoff.backends.cmux import CmuxBackend
from spinoff.backends.wezterm import WezTermBackend
from spinoff.config import SpinoffConfig


class TestExplicitConfig:
    def test_config_cmux(self) -> None:
        config = SpinoffConfig(project_name="test", terminal_backend="cmux")
        backend = get_backend(config)
        assert isinstance(backend, CmuxBackend)

    def test_config_wezterm(self) -> None:
        config = SpinoffConfig(project_name="test", terminal_backend="wezterm")
        backend = get_backend(config)
        assert isinstance(backend, WezTermBackend)

    def test_config_invalid_backend_raises(self) -> None:
        config = SpinoffConfig(project_name="test", terminal_backend="tmux")
        with pytest.raises(ValueError, match="tmux"):
            get_backend(config)


class TestAutoDetection:
    @patch.object(WezTermBackend, "available", return_value=False)
    @patch.object(CmuxBackend, "available", return_value=True)
    def test_cmux_preferred(
        self, mock_cmux: MagicMock, mock_wez: MagicMock,
    ) -> None:
        backend = get_backend()
        assert isinstance(backend, CmuxBackend)

    @patch.object(WezTermBackend, "available", return_value=True)
    @patch.object(CmuxBackend, "available", return_value=False)
    def test_wezterm_fallback_when_cmux_unavailable(
        self, mock_cmux: MagicMock, mock_wez: MagicMock,
    ) -> None:
        backend = get_backend()
        assert isinstance(backend, WezTermBackend)

    @patch.object(WezTermBackend, "available", return_value=False)
    @patch.object(CmuxBackend, "available", return_value=False)
    def test_raises_when_nothing_available(
        self, mock_cmux: MagicMock, mock_wez: MagicMock,
    ) -> None:
        with pytest.raises(RuntimeError, match="[Nn]o terminal backend"):
            get_backend()


class TestAutoDetectWithConfig:
    @patch("spinoff.backends.cmux.subprocess.run")
    @patch("spinoff.backends.cmux.shutil.which", return_value="/usr/local/bin/cmux")
    def test_empty_string_triggers_auto_detect(
        self, mock_which: MagicMock, mock_run: MagicMock,
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        config = SpinoffConfig(project_name="test", terminal_backend="")
        backend = get_backend(config)
        assert isinstance(backend, CmuxBackend)

    @patch("spinoff.backends.cmux.subprocess.run")
    @patch("spinoff.backends.cmux.shutil.which", return_value="/usr/local/bin/cmux")
    def test_none_config_triggers_auto_detect(
        self, mock_which: MagicMock, mock_run: MagicMock,
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        backend = get_backend(None)
        assert isinstance(backend, CmuxBackend)
