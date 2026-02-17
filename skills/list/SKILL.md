---
name: list
description: List all active spinoff worktrees with their status, branch, and WezTerm pane liveness.
context: fork
disable-model-invocation: true
allowed-tools: Bash(python *), Bash(PYTHONPATH=*)
---

# List Spinoffs

Show all tracked spinoff worktrees for the current project.

---

## Usage

```
/spinoff:list
```

---

## Current State

!PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.state list

---

## Your Task

### 1. List worktree state

The current state is pre-loaded above. If you need to refresh:

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.state list
```

### 2. Check WezTerm pane liveness

If there are active worktrees, check which WezTerm panes are still alive:

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.wezterm list
```

### 3. Present results

Show a table with columns:
- **Name** — spinoff name
- **Branch** — git branch
- **Path** — worktree path
- **Pane** — alive/dead (cross-reference pane IDs from state with live WezTerm panes)

If no spinoffs are tracked, tell the user and suggest `/spinoff:new <task-name>` to create one.

---

## Related Commands

- **`/spinoff:new`** — Create a new spinoff
- **`/spinoff:merge`** — Merge and clean up a spinoff
- **`/spinoff:init`** — Initialize spinoff support

$ARGUMENTS
