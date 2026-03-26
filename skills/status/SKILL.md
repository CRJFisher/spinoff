---
name: status
description: Show a text-based status table of all spinoff agents.
disable-model-invocation: true
allowed-tools: Bash(python *), Bash(PYTHONPATH=*)
---

# Spinoff Status

Print a table showing all agents, their state, and last activity.

## Current State

!PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.overview status

## Your Task

The status table is pre-loaded above. Present it to the user.

If no agents are tracked, suggest `/spinoff:new <task-name>` to create one.

$ARGUMENTS
