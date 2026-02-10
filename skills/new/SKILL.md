---
name: new
description: Spin off a new autonomous Claude agent in an isolated git worktree with WezTerm tab and sandbox.
argument-hint: <task-name> [--base <branch>] [--task <description>] [--permission-mode <mode>]
allowed-tools: Bash(git *), Bash(python *), Read, Glob, Grep
---

# Create Spinoff

Create an isolated git worktree for parallel development on a specific task.

Each spinoff runs in Claude Code's native sandbox with a dedicated WezTerm tab. This enables running multiple Claude agents in parallel on different tasks.

---

## Usage

```
/spinoff:new <task-name> [options]
```

**Examples:**
- `/spinoff:new fix-auth-bug` - Create spinoff from current branch
- `/spinoff:new feat-dark-mode --base develop` - Create from develop branch
- `/spinoff:new JIRA-1234 --task "Implement user profile page"` - With task for agent

**Options:**
- `--base <branch>` - Base branch to create worktree from (default: current branch)
- `--task <description>` - Task description passed to Claude agent
- `--permission-mode <mode>` - Permission mode for Claude session (default: plan)

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
- **--permission-mode <mode>** (optional, default: plan)

If no task name provided, ask the user for a descriptive task name. Good examples:
- `fix-auth-timeout`
- `feat-dark-mode`
- `JIRA-1234-user-profile`
- `refactor-api-client`

### 4. Find Related Task/Spec Files

Search for existing task or spec files that match the task name:

**Spec-Kit files** (check `specs/` directory):
Use the Glob tool to find specs matching the task name:
- `specs/**/*<task-name>*` — directories/files matching the task name
- `specs/*/spec.md`, `specs/*/plan.md`, `specs/*/tasks.md` — standard spec files

**Backlog tasks** (check `backlog/tasks/` directory):
Use the Glob tool:
- `backlog/tasks/*<task-name>*.md` — task files matching the name

**General task/spec patterns**:
Use the Glob tool with broader patterns:
- `**/specs/*<task-name>*.md`
- `**/tasks/*<task-name>*.md`
- `**/backlog/*<task-name>*.md`

If matching files are found:
- List them to the user for confirmation
- Append the file paths to the `--task` description

Example: If user runs `/spinoff:new feat-auth` and `specs/auth/spec.md` exists, the task becomes:
```
--task "Implement feature. Relevant files: specs/auth/spec.md, specs/auth/plan.md, specs/auth/tasks.md"
```

### 5. Execute the Script

Run the spinoff creation script with parsed arguments:

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/create_worktree.py" "<task-name>" [--base <branch>] [--task "<description with spec file paths>"] [--permission-mode <mode>]
```

### 6. Report Result

Provide the user with:
- Worktree location path
- Branch name created
- WezTerm tab info
- Reminder about `/spinoff:merge` when done

---

## Handling Errors

### Worktree Already Exists

If the script reports the worktree already exists:
- List existing worktrees: `git worktree list`
- Suggest alternative names (append `-v2`, date, etc.)
- Offer to navigate to the existing worktree instead

### WezTerm Not Available

If WezTerm is not installed:
- Inform the user to install WezTerm first
- The spinoff infrastructure requires WezTerm for tab management

Note: If WezTerm is installed but not running, the script will start it automatically.

### Git Errors

If git commands fail:
- Check if there are uncommitted changes: `git status`
- Ensure the base branch exists: `git branch -a | grep <base-branch>`

---

## Output

Provide a clear summary:

```
Spinoff Created
  Location: /path/to/repo/.worktrees/<task-name>
  Branch: worktree/<task-name>
  WezTerm tab: wt: <task-name>

To start working:
  cd /path/to/repo/.worktrees/<task-name>

When done, merge with:
  /spinoff:merge <task-name>
```

---

## Related Commands

- **`/spinoff:merge`** - Merge spinoff back to target branch and clean up
- **`/spinoff:init`** - Set up spinoff support for a project

$ARGUMENTS
