"""Tests for spinoff.agents."""

from pathlib import Path

import pytest

from spinoff.agents import AgentInfo, parse_frontmatter, discover_agents, check_configured_agents


class TestParseFrontmatter:
    def test_valid_frontmatter(self, tmp_path):
        md = tmp_path / "reviewer.md"
        md.write_text(
            "---\n"
            "name: refactor-reviewer\n"
            "description: Reviews refactors through architecture lens\n"
            "---\n\n"
            "# Refactor Reviewer\n"
        )
        info = parse_frontmatter(md)
        assert info is not None
        assert info.name == "refactor-reviewer"
        assert info.description == "Reviews refactors through architecture lens"

    def test_missing_name_returns_none(self, tmp_path):
        md = tmp_path / "no-name.md"
        md.write_text(
            "---\n"
            "description: No name field\n"
            "---\n\n"
            "# No Name\n"
        )
        assert parse_frontmatter(md) is None

    def test_no_frontmatter_returns_none(self, tmp_path):
        md = tmp_path / "plain.md"
        md.write_text("# Just a heading\n\nSome content.\n")
        assert parse_frontmatter(md) is None

    def test_file_not_found_returns_none(self, tmp_path):
        assert parse_frontmatter(tmp_path / "nonexistent.md") is None

    def test_extra_fields_ignored(self, tmp_path):
        md = tmp_path / "extra.md"
        md.write_text(
            "---\n"
            "name: test-agent\n"
            "description: A test agent\n"
            "custom-field: some value\n"
            "---\n"
        )
        info = parse_frontmatter(md)
        assert info is not None
        assert info.name == "test-agent"


class TestDiscoverAgents:
    def _make_agent(self, directory: Path, name: str, description: str = "") -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        md = directory / f"{name}.md"
        md.write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n"
        )
        return md

    def test_global_agents(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "home" / ".claude" / "agents"
        self._make_agent(global_dir, "global-agent", "A global agent")
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        project = tmp_path / "project"
        project.mkdir()
        agents = discover_agents(project)
        assert len(agents) == 1
        assert agents[0].name == "global-agent"
        assert agents[0].source == "global"

    def test_project_agents(self, tmp_path, monkeypatch):
        # Empty global dir
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        project = tmp_path / "project"
        project_dir = project / ".claude" / "agents"
        self._make_agent(project_dir, "project-agent", "A project agent")

        agents = discover_agents(project)
        assert len(agents) == 1
        assert agents[0].name == "project-agent"
        assert agents[0].source == "project"

    def test_project_overrides_global(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "home" / ".claude" / "agents"
        self._make_agent(global_dir, "shared-agent", "Global version")
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        project = tmp_path / "project"
        project_dir = project / ".claude" / "agents"
        self._make_agent(project_dir, "shared-agent", "Project version")

        agents = discover_agents(project)
        assert len(agents) == 1
        assert agents[0].name == "shared-agent"
        assert agents[0].source == "project"
        assert agents[0].description == "Project version"

    def test_empty_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        project = tmp_path / "project"
        project.mkdir()
        agents = discover_agents(project)
        assert agents == []

    def test_mixed_agents_sorted(self, tmp_path, monkeypatch):
        global_dir = tmp_path / "home" / ".claude" / "agents"
        self._make_agent(global_dir, "zebra-agent", "Z agent")
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        project = tmp_path / "project"
        project_dir = project / ".claude" / "agents"
        self._make_agent(project_dir, "alpha-agent", "A agent")

        agents = discover_agents(project)
        assert len(agents) == 2
        assert agents[0].name == "alpha-agent"
        assert agents[1].name == "zebra-agent"


class TestCheckConfiguredAgents:
    def _setup_agents(self, tmp_path, monkeypatch, names):
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        project = tmp_path / "project"
        project_dir = project / ".claude" / "agents"
        project_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            md = project_dir / f"{name}.md"
            md.write_text(f"---\nname: {name}\ndescription: Agent {name}\n---\n")
        return project

    def test_all_found(self, tmp_path, monkeypatch):
        project = self._setup_agents(tmp_path, monkeypatch, ["agent-a", "agent-b"])
        found, missing = check_configured_agents(["agent-a", "agent-b"], project)
        assert len(found) == 2
        assert missing == []

    def test_missing_agent(self, tmp_path, monkeypatch):
        project = self._setup_agents(tmp_path, monkeypatch, ["agent-a"])
        found, missing = check_configured_agents(["agent-a", "ghost"], project)
        assert len(found) == 1
        assert found[0].name == "agent-a"
        assert missing == ["ghost"]

    def test_empty_config(self, tmp_path, monkeypatch):
        project = self._setup_agents(tmp_path, monkeypatch, ["agent-a"])
        found, missing = check_configured_agents([], project)
        assert found == []
        assert missing == []
