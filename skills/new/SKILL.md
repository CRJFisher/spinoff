---
name: new
description: Spin off a new autonomous Claude agent in an isolated git worktree with cmux workspace and sandbox.
argument-hint: <task-name> [--base <branch>] [--task <description>] [--mode <plan|implement>] [--model <model>]
allowed-tools: Bash(git *), Bash(python *), Bash(PYTHONPATH=*), Read, Glob, Grep
---

# Create Spinoff

Create an isolated git worktree for parallel development on a specific task.

Each spinoff runs in Claude Code's native sandbox with a dedicated cmux workspace. This enables running multiple Claude agents in parallel on different tasks.

---

## Usage

```
/spinoff:new <task-name> [options]
```

**Examples:**

- `/spinoff:new fix-auth-bug` - Create spinoff from current branch
- `/spinoff:new feat-dark-mode --base develop` - Create from develop branch
- `/spinoff:new JIRA-1234 --task "Implement user profile page"` - With task for agent
- `/spinoff:new explore-auth --task "analyze the auth architecture" --mode plan` - Read-only exploration

**Options:**

- `--base <branch>` - Base branch to create worktree from (default: current branch)
- `--task <description>` - Task description passed to Claude agent
- `--mode <plan|implement>` - Agent mode: `plan` (read-only) or `implement` (sandbox + auto-commit). Falls back to project `default_mode`.
- `--model <model>` - Claude model to use (e.g. `haiku`, `sonnet`, `opus`). If omitted, uses user's default.

---

## Your Task

### 1. Check Prerequisites

Verify you're in a git repository:

```bash
git rev-parse --show-toplevel
```

If this fails, inform the user they need to be in a git repository.

### 2. Check for Spinoff Config

Look for the project's spinoff configuration:

```bash
ls -la .claude/spinoff.json
```

**If the config exists**: Proceed to step 3.

**If the config does NOT exist**:

- Inform the user: "This project doesn't have spinoff configured yet."
- Ask if they want to set it up now.
- If yes, ask the user to run `/spinoff:init` to create it.
- After setup completes, proceed to step 3.

### 3. Parse Arguments

Parse `$ARGUMENTS` for:

- **Task name** (required, first positional argument)
- **--base <branch>** (optional)
- **--task <description>** (optional)
- **--mode <plan|implement>** (optional)
- **--model <model>** (optional)

If no task name provided, ask the user for a descriptive task name. Good examples:

- `fix-auth-timeout`
- `feat-dark-mode`
- `JIRA-1234-user-profile`
- `refactor-api-client`

### 3a. Determine Agent Mode

For mode selection heuristics (keyword scanning, fallback rules), see [mode-heuristics.md](mode-heuristics.md).

### 4. Find Related Task/Spec Files

Search for existing task or spec files that match the task name. For search patterns and verification workflow, see [spec-patterns.md](spec-patterns.md).

### 5. Execute the Script

Run the spinoff creation script with parsed arguments:

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.create "<task-name>" [--base <branch>] [--task "<description with spec file paths>"] [--mode <plan|implement>] [--model <model>]
```

### 6. Report Result

Provide the user with:

- Worktree location path
- Branch name created
- Mode (`plan` or `implement`)
- cmux workspace info
- For implement mode: mention that the agent will auto-commit its work before finishing

---

## Handling Errors

### Worktree Already Exists

If the script reports the worktree already exists:

- List existing worktrees: `git worktree list`
- Suggest alternative names (append `-v2`, date, etc.)
- Offer to navigate to the existing worktree instead

### cmux Not Available

If cmux is not installed or not running:

- Inform the user to install cmux and start it first
- The spinoff infrastructure requires cmux for workspace management

### Git Errors

If git commands fail:

- Check if there are uncommitted changes: `git status`
- Ensure the base branch exists: `git branch -a | grep <base-branch>`

---

## Output

Provide a clear summary:

```
Spinoff Created
  Location: /path/to/repo/.claude/worktrees/<task-name>
  Branch: worktree/<task-name>
  Mode: implement (sandbox + auto-commit)
  cmux workspace: {project_name}: <task-name>
```

---

## Related Commands

- **`/spinoff:init`** - Set up spinoff support for a project

$ARGUMENTS
