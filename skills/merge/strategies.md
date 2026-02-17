# Merge Strategies

## Merge commit (default)

Creates an explicit merge commit preserving full history.

```bash
cd <main-repo-path>
git checkout <target-branch>
git merge <worktree-branch> --no-ff -m "Merge worktree: <task-name>"
```

## Squash merge

Combines all commits into one clean commit.

```bash
cd <main-repo-path>
git checkout <target-branch>
git merge --squash <worktree-branch>
git commit -m "Complete: <task-name>"
```

## Rebase

Replays commits on top of target for linear history.

```bash
# First rebase worktree onto target
cd <worktree-path>
git rebase <target-branch>

# Then fast-forward merge
cd <main-repo-path>
git checkout <target-branch>
git merge <worktree-branch> --ff-only
```
