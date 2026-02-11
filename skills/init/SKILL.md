---
name: init
description: Initialize a project for spinoff support. Analyzes tech stack and creates spinoff config.
allowed-tools: Bash(git *), Bash(python *), Read, Glob, Grep, Write, Edit
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

Identify the technology stack by checking for:

| File | Stack |
|------|-------|
| `package.json` | Node.js |
| `pyproject.toml` / `requirements.txt` | Python |
| `Cargo.toml` | Rust |
| `go.mod` | Go |
| `pom.xml` / `build.gradle` | Java |
| `Gemfile` | Ruby |

Find state files that should be copied: `.env`, `.env.local`, `.env.development`, local config files.

Determine the build command:

| Stack | Build Command |
|-------|---------------|
| Node.js (npm) | `npm install && npm run build` |
| Node.js (pnpm) | `pnpm install && pnpm run build` |
| Node.js (yarn) | `yarn install && yarn build` |
| Python | `pip install -e .` |
| Rust | `cargo build` |
| Go | `go build ./...` |

### 3. Present findings and request confirmation

Show the user:
- Detected stack
- State files to copy
- Build command

Wait for user confirmation before proceeding.

### 4. Update .gitignore

Add `.worktrees/` to `.gitignore` if not already present. Commit with message: `chore: configure gitignore for worktree support`

### 5. Write spinoff configuration

Write the detected configuration to `.claude/spinoff.json`:

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/spinoff_config.py"
```

Or write the file directly. The format is:

```json
{
  "project_name": "<detected-project-name>",
  "state_files": [".env", ".env.local"],
  "build_command": "pnpm install",
  "worktree_dir": ".worktrees"
}
```

Where:
- `project_name` — Name of the project (typically the repo directory name)
- `state_files` — List of files to copy into each worktree (e.g., `.env`)
- `build_command` — Command to run after creating a worktree (e.g., `pnpm install`)
- `worktree_dir` — Directory for worktrees (default: `.worktrees`)

### 6. Report the result

Provide:

1. **Config location**: `.claude/spinoff.json`
2. **Configuration**: What state files and build command were configured
3. **Usage examples**:
   - Create spinoff: `/spinoff:new my-feature`
   - With base branch: `/spinoff:new my-feature --base develop`
   - With task description: `/spinoff:new my-feature --task "Implement feature X"`
   - With permission mode: `/spinoff:new my-feature --permission-mode bypassPermissions`
4. **Slash commands**: Explain the available slash commands (see below)

---

## Slash Commands

After setup, the user can use these slash commands in Claude Code:

### `/spinoff:new <task-name>`

Creates a new spinoff with sandbox isolation and WezTerm tab.

```
/spinoff:new fix-auth-bug
/spinoff:new feat-dark-mode --base develop
/spinoff:new JIRA-1234 --task "Implement user profile page"
/spinoff:new fix-bug --permission-mode bypassPermissions
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--base` | current branch | Base branch for the worktree |
| `--task` | none | Task description to pass to Claude |
| `--permission-mode` | `plan` | Permission mode: `acceptEdits`, `bypassPermissions`, `default`, `dontAsk`, `plan` |

**What it does:**
1. Creates git worktree at `.worktrees/<task-name>`
2. Creates branch `worktree/<task-name>`
3. Copies state files and runs build command
4. Opens WezTerm tab with Claude agent in plan mode (requires approval before making changes)

### `/spinoff:merge <spinoff-name>`

Merges spinoff back to target branch and cleans up.

```
/spinoff:merge fix-auth-bug
/spinoff:merge fix-auth-bug --target develop
/spinoff:merge fix-auth-bug --strategy squash
```

**What it does:**
1. Closes WezTerm tab if one exists
2. Merges changes (merge/squash/rebase)
3. Removes worktree directory
4. Deletes branch
5. Updates state file

**IMPORTANT**: Tell the user about these commands! They provide a convenient way to manage spinoffs without remembering script paths.

---

## State File Location

Worktree state is tracked in `.worktrees/.state.json`.

You can inspect state with:

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/worktree_state.py" list
python "$CLAUDE_PLUGIN_ROOT/scripts/worktree_state.py" show <name>
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
