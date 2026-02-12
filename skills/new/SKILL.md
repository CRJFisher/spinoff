---
name: new
description: Spin off a new autonomous Claude agent in an isolated git worktree with WezTerm tab and sandbox.
argument-hint: <task-name> [--base <branch>] [--task <description>] [--mode <plan|implement>]
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
- `/spinoff:new explore-auth --task "analyze the auth architecture" --mode plan` - Read-only exploration

**Options:**
- `--base <branch>` - Base branch to create worktree from (default: current branch)
- `--task <description>` - Task description passed to Claude agent
- `--mode <plan|implement>` - Agent mode: `plan` (read-only) or `implement` (sandbox + auto-commit). Falls back to project `default_mode`.

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

If no task name provided, ask the user for a descriptive task name. Good examples:
- `fix-auth-timeout`
- `feat-dark-mode`
- `JIRA-1234-user-profile`
- `refactor-api-client`

### 3a. Determine Agent Mode

Decide the agent mode (`plan` or `implement`) using these rules in order:

1. **Explicit `--mode` flag** → use it, done.
2. **Task description heuristics** — if `--task` was provided, scan for keyword signals:
   - **Plan signals**: plan, design, explore, investigate, analyze, compare, evaluate, research, review, assess, propose, understand, audit
   - **Implement signals**: implement, fix, build, create, add, update, refactor, migrate, remove, delete, replace, write, change, move, rename, upgrade, convert, integrate
   - If a strong signal is found → suggest that mode, confirm with user.
3. **Project default** — read `default_mode` from `.claude/spinoff.json` and confirm with user.

Tell the user the chosen mode and what it means:
- **plan**: Read-only exploration. Agent uses `--permission-mode plan` (no sandbox). Good for investigation, design, and code review.
- **implement**: Sandboxed execution. Agent can write files and run commands. Auto-commits work before finishing. Good for bug fixes, features, and refactoring.

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

### 4a. Verify Referenced Files Exist and Are Committed

Before creating the worktree, verify that all referenced files exist and are committed to the base branch. Files that aren't committed to the base won't be available in the new worktree.

**1. Collect all referenced file paths:**
- Files discovered by Glob in step 4 (spec files, task files)
- Files the user explicitly mentioned in their request or `--task` description
- Any other files discussed in the conversation that the task depends on

**2. Determine the base branch:**
Use `--base` arg if provided, otherwise the current branch:
```bash
git rev-parse --abbrev-ref HEAD
```

**3. Check each file exists and is committed** to the base branch:
```bash
git cat-file -e <base>:<relative-path> 2>/dev/null
```
Non-zero exit means the file doesn't exist on the base branch (untracked, uncommitted, or only on a different branch).

**4. If all files exist on the base branch:** Proceed to step 5.

**5. If any files are missing:**
- List the problematic files to the user.
- Explain: "These files don't exist or aren't committed to `<base>`. They won't be available in the new worktree."
- **If base is the current branch** (common case): Offer to commit them:
  ```bash
  git add <file1> <file2> ...
  git commit -m "Add task files for <task-name>"
  ```
- **If base is a different branch** (`--base` specified): Warn the user. Suggest they commit the files to the base branch first, or proceed without them.
- **If user declines to commit**: Ask if they want to proceed anyway (the task description will still reference the paths, but the agent won't be able to read them).
- **Do NOT proceed silently** — always surface the issue.

### 5. Execute the Script

Run the spinoff creation script with parsed arguments:

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/create_worktree.py" "<task-name>" [--base <branch>] [--task "<description with spec file paths>"] [--mode <plan|implement>]
```

### 6. Report Result

Provide the user with:
- Worktree location path
- Branch name created
- Mode (`plan` or `implement`)
- WezTerm tab info
- For implement mode: mention that the agent will auto-commit its work before finishing
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
  Mode: implement (sandbox + auto-commit)
  WezTerm tab: wt: <task-name>

When done, merge with:
  /spinoff:merge <task-name>
```

---

## Related Commands

- **`/spinoff:merge`** - Merge spinoff back to target branch and clean up
- **`/spinoff:init`** - Set up spinoff support for a project

$ARGUMENTS
