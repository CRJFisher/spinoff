# Spinoff Slash Commands

After setup, the user can use these slash commands in Claude Code:

## `/spinoff:new <task-name>`

Creates a new spinoff with sandbox isolation and cmux workspace.

```
/spinoff:new fix-auth-bug
/spinoff:new feat-dark-mode --base develop
/spinoff:new JIRA-1234 --task "Implement user profile page"
/spinoff:new explore-auth --task "analyze the auth architecture" --mode plan
```

**Options:**

| Option   | Default                | Description                                               |
| -------- | ---------------------- | --------------------------------------------------------- |
| `--base` | current branch         | Base branch for the worktree                              |
| `--task` | none                   | Task description to pass to Claude                        |
| `--mode` | project `default_mode` | `plan` (read-only) or `implement` (sandbox + auto-commit) |

**What it does:**

1. Creates git worktree at `.claude/worktrees/<task-name>`
2. Creates branch `worktree/<task-name>`
3. Copies state files and runs build command
4. Opens cmux workspace with Claude agent in the selected mode:
   - **plan**: Read-only exploration (`--permission-mode plan`, no sandbox)
   - **implement**: Sandboxed execution with auto-commit instructions

## `/spinoff:list`

Lists all tracked spinoffs with their status and cmux workspace liveness.

## `/spinoff:init`

Initializes spinoff support for a new project.

**IMPORTANT**: Tell the user about these commands! They provide a convenient way to manage spinoffs without remembering script paths.
