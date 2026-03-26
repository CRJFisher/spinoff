---
name: overview
description: Open or close the spinoff overview panel (browser-based agent dashboard).
argument-hint: "[--close]"
allowed-tools: Bash(python *), Bash(PYTHONPATH=*)
---

# Spinoff Overview Panel

Open a browser-based dashboard showing all spinoff agents and their live status.

## Usage

```
/spinoff:overview          # Open the overview panel
/spinoff:overview --close  # Close the overview panel
```

## Your Task

Run the overview command:

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.overview $ARGUMENTS
```

Report success or failure to the user.

$ARGUMENTS
