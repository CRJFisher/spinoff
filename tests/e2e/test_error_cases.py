"""E2E tests for error handling."""

import pytest

from .conftest import run_create_worktree


pytestmark = pytest.mark.e2e


class TestErrorCases:
    def test_create_duplicate_name(self, test_project, plugin_root):
        """Creating a worktree with an existing name fails."""
        r1 = run_create_worktree(test_project, "dup-test", plugin_root)
        assert r1.returncode == 0, r1.stderr

        r2 = run_create_worktree(test_project, "dup-test", plugin_root)
        assert r2.returncode != 0
