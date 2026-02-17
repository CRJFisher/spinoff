---
name: merge
description: Merge a spinoff's changes back to target branch with cleanup of WezTerm tabs and git branches.
argument-hint: [spinoff-name] [--target <branch>] [--strategy <merge|squash|rebase>] [--keep-branch]
allowed-tools: Bash(git *), Bash(python *), Bash(PYTHONPATH=*), Read, Glob, Grep
---

# Merge Spinoff

Merge spinoff changes back to the target branch and clean up the worktree.

This command handles WezTerm tab cleanup automatically. Sandbox processes exit when the tab closes.

---

## Usage

```
/spinoff:merge [spinoff-name] [options]
```

**Examples:**
- `/spinoff:merge fix-auth-bug` - Merge into main with merge commit
- `/spinoff:merge fix-auth-bug --target develop` - Merge into develop
- `/spinoff:merge fix-auth-bug --strategy squash` - Squash all commits
- `/spinoff:merge fix-auth-bug --strategy rebase` - Rebase for linear history
- `/spinoff:merge fix-auth-bug --keep-branch` - Don't delete branch after merge

**Options:**
- `--target <branch>` - Target branch to merge into (default: branch the spinoff was created from, or main)
- `--strategy <merge|squash|rebase>` - Merge strategy (default: merge)
- `--keep-branch` - Keep the worktree branch after merge

**Note:** If run from within a worktree, the worktree name is auto-detected.

---

## Active Worktrees

!PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.state list

---

## Your Task

### 1. Identify Worktree Context

Determine if you're currently in a worktree:

```bash
git rev-parse --git-dir
```

If the output contains `/.worktrees/`, you're in a worktree. Extract:
- **Worktree path**: Current directory
- **Worktree branch**: `git branch --show-current`
- **Main repo path**: Parent of `.worktrees` directory

If NOT in a worktree, list available worktrees and ask which one to merge:

```bash
git worktree list
```

### 2. Check for Spinoff Config

Look for the project's spinoff configuration:

```bash
ls -la .claude/spinoff.json
```

**If the config exists**: Use the merge script (handles WezTerm cleanup automatically).

**If the config does NOT exist**: Fall back to manual merge steps. See [manual-merge.md](manual-merge.md).

### 3. Execute Merge with Script (Preferred)

If `.claude/spinoff.json` exists, use the merge script:

```bash
# Default merge (into main)
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.merge "<spinoff-name>"

# Specify target branch
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.merge "<spinoff-name>" --target develop

# Choose merge strategy
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.merge "<spinoff-name>" --strategy squash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.merge "<spinoff-name>" --strategy rebase

# Keep the branch after merge
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python -m spinoff.merge "<spinoff-name>" --keep-branch
```

The script will:
1. Close the WezTerm tab if one exists
2. Check for uncommitted changes (error if dirty)
3. Perform the merge
4. Remove the worktree directory
5. Delete the branch
6. Update the state file

### 4. Handle Conflicts

If conflicts occur during merge:

1. List conflicting files: `git diff --name-only --diff-filter=U`
2. For each conflicting file:
   - Show the conflict markers
   - Help the user understand both versions
   - Apply the resolution
   - Stage the resolved file: `git add <file>`
3. Complete the merge: `git commit`

### 5. Report Result

Provide a summary:

```
Merge Complete
  Source: worktree/<task-name>
  Target: main
  Strategy: merge commit
  Commits merged: <count>

Cleanup:
  Worktree removed: /path/to/.worktrees/<task-name>
  Branch deleted: worktree/<task-name>
  WezTerm tab closed (if applicable)
```

---

## Error Handling

The merge script provides descriptive error messages:

| Error | Message |
|-------|---------|
| Worktree not found | `Error: Worktree 'name' not found at .worktrees/name` |
| Uncommitted changes | `Error: Worktree has uncommitted changes. Commit or stash first:` followed by git status output |
| Merge conflict | `Error: Merge conflict. Resolve manually:` followed by conflicting files and instructions |
| Branch in use | `Error: Cannot delete branch - it's checked out elsewhere` |

For merge strategy details, see [strategies.md](strategies.md).

---

## Output

Provide clear status updates throughout the process:

1. "Closing WezTerm tab..." (if applicable)
2. "Checking worktree state..."
3. "Switching to target branch..."
4. "Merging changes..." (or "Resolving conflicts...")
5. "Cleaning up worktree..."
6. Final summary with any warnings

---

## Related Commands

- **`/spinoff:new`** - Create a new spinoff for parallel development
- **`/spinoff:init`** - Set up spinoff support for a project

$ARGUMENTS
