---
name: list
description: List all active spinoff worktrees with their status, branch, and cmux workspace liveness.
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

### 2. Check cmux workspace liveness

If there are active worktrees, check which cmux workspaces are still alive:

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -c "import spinoff.cmux as cmux; import json; print(json.dumps(cmux.list_workspaces(), indent=2))"
```

### 3. Present results

Show a table with columns:

- **Name** — spinoff name
- **Branch** — git branch
- **Path** — worktree path
- **Workspace** — alive/dead (cross-reference terminal IDs from state with live cmux workspaces)

If no spinoffs are tracked, tell the user and suggest `/spinoff:new <task-name>` to create one.

---

## Related Commands

- **`/spinoff:new`** — Create a new spinoff
- **`/spinoff:init`** — Initialize spinoff support

$ARGUMENTS
