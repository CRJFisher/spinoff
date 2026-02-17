---
name: init
description: Initialize a project for spinoff support. Analyzes tech stack and creates spinoff config.
disable-model-invocation: true
allowed-tools: Bash(git *), Bash(python *), Bash(PYTHONPATH=*), Read, Glob, Grep, Write, Edit
---

# Spinoff Init

Set up spinoff support for a project. This enables isolated parallel development environments where each spinoff gets its own branch and runs in Claude Code's native sandbox with a WezTerm tab.

---

## Usage

```
/spinoff:init
```

Run this command in a git repository to configure spinoff support.

---

## Prerequisites

- **WezTerm** must be installed (the script starts it automatically if not running)

---

## Your Task

Follow these steps:

### 1. Verify git repository

```bash
git rev-parse --show-toplevel
```

If this fails, inform the user and exit.

### 2. Analyze project structure

Identify the technology stack and determine the build command. For detection tables and build commands, see [tech-stacks.md](tech-stacks.md).

Find state files that should be copied: `.env`, `.env.local`, `.env.development`, local config files.

### 3. Present findings and request confirmation

Show the user:

- Detected stack
- State files to copy
- Build command

Ask the user their preferred default mode for spinoff agents:

> "When spinning off tasks, should the default be **plan** mode (read-only exploration) or **implement** mode (sandbox, can write files and auto-commits)?"

Default to `implement` if the user has no preference.

Wait for user confirmation before proceeding.

### 4. Update .gitignore

Add `.worktrees/` to `.gitignore` if not already present. Commit with message: `chore: configure gitignore for worktree support`. No need to mention spinoff in the `.gitignore` or commit message.

### 5. Write spinoff configuration

Write the detected configuration to `.claude/spinoff.json`:

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.config save --project-name "<name>" --state-files .env --build-command "pnpm install"
```

Or write the file directly. The format is:

```json
{
  "project_name": "<detected-project-name>",
  "state_files": [".env", ".env.local"],
  "build_command": "pnpm install",
  "worktree_dir": ".worktrees",
  "default_mode": "implement"
}
```

Where:

- `project_name` — Name of the project (typically the repo directory name)
- `state_files` — List of files to copy into each worktree (e.g., `.env`)
- `build_command` — Command to run after creating a worktree (e.g., `pnpm install`)
- `worktree_dir` — Directory for worktrees (default: `.worktrees`)
- `default_mode` — Default agent mode: `plan` (read-only) or `implement` (sandbox + auto-commit)

### 6. Report the result

Provide:

1. **Config location**: `.claude/spinoff.json`
2. **Configuration**: What state files and build command were configured
3. **Usage examples** and **Slash commands**: See [commands-reference.md](commands-reference.md) for the full list to show the user.

---

## State File Location

Worktree state is tracked in `.worktrees/.state.json`.

You can inspect state with:

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.state list
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.state show <name>
```

---

## Best Practices

- Prefer build commands over symlinking
- Copy state files, don't share them
- Verify git status before proceeding

---

## Related Commands

- **`/spinoff:new`** - Create a new spinoff for parallel development
- **`/spinoff:merge`** - Merge spinoff back to target branch and clean up

$ARGUMENTS
