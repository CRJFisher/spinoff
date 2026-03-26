---
name: approve
description: Approve a pending permission prompt for a spinoff agent.
argument-hint: "<name>"
allowed-tools: Bash(python *), Bash(PYTHONPATH=*)
---

# Spinoff Approve

Send approval to a specific agent waiting for a permission prompt.

## Usage

```
/spinoff:approve <name>
```

## Your Task

### 1. Parse arguments

Extract the agent name from `$ARGUMENTS`. If no name is provided, ask the user which agent to approve.

### 2. Run the approve command

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.overview approve $ARGUMENTS
```

### 3. Report the result to the user.

$ARGUMENTS
