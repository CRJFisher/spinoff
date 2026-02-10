---
name: list
description: List all active spinoff worktrees with their status, branch, and WezTerm pane liveness.
allowed-tools: Bash(python *)
---

# List Spinoffs

Show all tracked spinoff worktrees for the current project.

---

## Usage

```
/spinoff:list
```

---

## Your Task

### 1. List worktree state

Run the worktree state script to get all tracked spinoffs:

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/worktree_state.py" list
```

### 2. Check WezTerm pane liveness

If there are active worktrees, check which WezTerm panes are still alive:

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/worktree_wezterm.py" list
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
