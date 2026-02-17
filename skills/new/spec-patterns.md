# Spec and Task File Discovery

## Search Patterns

Search for existing task or spec files that match the task name:

### Spec-Kit files (check `specs/` directory)

Use the Glob tool to find specs matching the task name:
- `specs/**/*<task-name>*` — directories/files matching the task name
- `specs/*/spec.md`, `specs/*/plan.md`, `specs/*/tasks.md` — standard spec files

### Backlog tasks (check `backlog/tasks/` directory)

Use the Glob tool:
- `backlog/tasks/*<task-name>*.md` — task files matching the name

### General task/spec patterns

Use the Glob tool with broader patterns:
- `**/specs/*<task-name>*.md`
- `**/tasks/*<task-name>*.md`
- `**/backlog/*<task-name>*.md`

## Appending to task description

If matching files are found:
- List them to the user for confirmation
- Append the file paths to the `--task` description

Example: If user runs `/spinoff:new feat-auth` and `specs/auth/spec.md` exists, the task becomes:
```
--task "Implement feature. Relevant files: specs/auth/spec.md, specs/auth/plan.md, specs/auth/tasks.md"
```

## Verify Referenced Files Are Committed

Before creating the worktree, verify that all referenced files exist and are committed to the base branch. Files that aren't committed to the base won't be available in the new worktree.

### 1. Collect all referenced file paths

- Files discovered by Glob (spec files, task files)
- Files the user explicitly mentioned in their request or `--task` description
- Any other files discussed in the conversation that the task depends on

### 2. Determine the base branch

Use `--base` arg if provided, otherwise the current branch:
```bash
git rev-parse --abbrev-ref HEAD
```

### 3. Check each file exists and is committed

```bash
git cat-file -e <base>:<relative-path> 2>/dev/null
```
Non-zero exit means the file doesn't exist on the base branch.

### 4. Handle missing files

- **If all files exist on the base branch:** Proceed.
- **If any files are missing:**
  - List the problematic files to the user.
  - Explain: "These files don't exist or aren't committed to `<base>`. They won't be available in the new worktree."
  - **If base is the current branch**: Offer to commit them.
  - **If base is a different branch**: Warn the user. Suggest they commit the files to the base branch first.
  - **Do NOT proceed silently** — always surface the issue.
