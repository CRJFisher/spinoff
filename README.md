# spinoff

A Claude Code plugin that spins off autonomous Claude agents into isolated git worktrees with WezTerm tabs and sandbox isolation.

Each spinoff gets:
- An isolated git worktree with its own branch
- A dedicated WezTerm tab
- Claude Code running in sandbox mode
- Automatic state file copying and build setup

## Prerequisites

- [WezTerm](https://wezfurlong.org/wezterm/) terminal emulator
- Python 3.11+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI

## Installation

### From GitHub

```bash
claude plugin add crjfisher/spinoff
```

### Local development

```bash
claude --plugin-dir /path/to/spinoff
```

## Commands

### `/spinoff:init`

Initialize a project for spinoff support. Analyzes your tech stack and creates `.claude/spinoff.json` with:

- Project name
- State files to copy (`.env`, etc.)
- Build command (`pnpm install`, `cargo build`, etc.)

```
/spinoff:init
```

### `/spinoff:new <task-name>`

Spin off a new autonomous Claude agent in an isolated worktree.

```
/spinoff:new fix-auth-bug
/spinoff:new feat-dark-mode --base develop
/spinoff:new JIRA-1234 --task "Implement user profile page"
/spinoff:new fix-bug --permission-mode bypassPermissions
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--base <branch>` | current branch | Base branch for the worktree |
| `--task <description>` | none | Task description for the Claude agent |
| `--permission-mode <mode>` | `plan` | Claude permission mode |

### `/spinoff:merge <name>`

Merge a spinoff back to the target branch with full cleanup.

```
/spinoff:merge fix-auth-bug
/spinoff:merge fix-auth-bug --target develop
/spinoff:merge fix-auth-bug --strategy squash
/spinoff:merge fix-auth-bug --keep-branch
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--target <branch>` | `main` | Branch to merge into |
| `--strategy <mode>` | `merge` | `merge`, `squash`, or `rebase` |
| `--keep-branch` | false | Keep the branch after merge |

## How It Works

```
Your repo/
├── .claude/
│   └── spinoff.json          # Project config (created by /spinoff:init)
├── .worktrees/                # Ignored by git
│   ├── fix-auth/              # Worktree 1 (branch: worktree/fix-auth)
│   └── feat-dark-mode/        # Worktree 2 (branch: worktree/feat-dark-mode)
└── src/
    └── ...
```

1. **`/spinoff:init`** detects your stack and writes `.claude/spinoff.json`
2. **`/spinoff:new`** creates a git worktree, copies state files, runs the build, and opens a WezTerm tab with a sandboxed Claude agent
3. **`/spinoff:merge`** merges changes back, closes the tab, removes the worktree, and deletes the branch

Each spinoff runs in Claude Code's native sandbox — near-zero overhead, instant startup, no Docker required.

## Configuration

The `.claude/spinoff.json` file stores per-project settings:

```json
{
  "project_name": "my-app",
  "state_files": [".env", ".env.local"],
  "build_command": "pnpm install",
  "worktree_dir": ".worktrees"
}
```

## License

MIT
