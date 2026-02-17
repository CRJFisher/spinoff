# Manual Merge Fallback

Use these steps when the merge script is unavailable or the spinoff config doesn't exist.

## 1. Check Worktree State

```bash
# Check for uncommitted changes
git status --porcelain

# Show commits to be merged
git log --oneline origin/main..HEAD
```

**If uncommitted changes exist**: Ask the user to commit or stash them first.

## 2. Identify Target Branch

Determine the target branch to merge into:
- Check `$ARGUMENTS` for explicit target
- Default to `main` or `master` (whichever exists)
- Or ask the user if unclear

## 3. Choose Merge Strategy

Present options to the user (default: merge commit):

1. **Merge commit** (recommended) - Creates explicit merge commit preserving full history
2. **Squash merge** - Combines all commits into one clean commit
3. **Rebase** - Replays commits on top of target for linear history

## 4. Execute Merge

See [strategies.md](strategies.md) for the git commands for each strategy.

## 5. Clean Up

```bash
# Remove the worktree
git worktree remove <worktree-path>

# Delete the branch
git branch -d <worktree-branch>
```
