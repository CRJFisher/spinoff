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

```shell
/plugin marketplace add CRJFisher/spinoff
/plugin install spinoff@CRJFisher-spinoff
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
/spinoff:new explore-auth --task "analyze the auth architecture" --mode plan
```

**Modes:**

| Mode | Description |
| ---- | ----------- |
| `implement` | Sandboxed execution — agent can write files, run commands, and auto-commits before finishing |
| `plan` | Read-only exploration — agent uses `--permission-mode plan`, no sandbox |

**Options:**

| Option                 | Default              | Description                                   |
| ---------------------- | -------------------- | --------------------------------------------- |
| `--base <branch>`      | current branch       | Base branch for the worktree                  |
| `--task <description>` | none                 | Task description for the Claude agent         |
| `--mode <mode>`        | project default_mode | `plan` (read-only) or `implement` (sandbox)   |

### `/spinoff:list`

List all active spinoffs with their status, branch, and WezTerm pane liveness.

```
/spinoff:list
```

### `/spinoff:merge <name>`

Merge a spinoff back to the target branch with full cleanup.

```
/spinoff:merge fix-auth-bug
/spinoff:merge fix-auth-bug --target develop
/spinoff:merge fix-auth-bug --strategy squash
/spinoff:merge fix-auth-bug --keep-branch
```

**Options:**

| Option              | Default | Description                    |
| ------------------- | ------- | ------------------------------ |
| `--target <branch>` | `main`  | Branch to merge into           |
| `--strategy <mode>` | `merge` | `merge`, `squash`, or `rebase` |
| `--keep-branch`     | false   | Keep the branch after merge    |

## How It Works

```
Your repo/
├── .claude/
│   └── spinoff.json          # Project config (created by /spinoff:init)
├── .worktrees/               # Ignored by git
│   ├── .state.json           # Worktree state tracking
│   ├── fix-auth/             # Worktree 1 (branch: worktree/fix-auth)
│   └── feat-dark-mode/       # Worktree 2 (branch: worktree/feat-dark-mode)
└── src/
    └── ...
```

1. **`/spinoff:init`** detects your stack and writes `.claude/spinoff.json`
2. **`/spinoff:new`** creates a git worktree, copies state files, tracks state in `.worktrees/.state.json`, runs the build, and opens a WezTerm tab with a sandboxed Claude agent
3. **`/spinoff:list`** shows all tracked spinoffs and their WezTerm pane status
4. **`/spinoff:merge`** validates preconditions, merges changes back, closes the tab, removes the worktree, and deletes the branch

Each spinoff runs in Claude Code's native sandbox — near-zero overhead, instant startup, no Docker required.

## Configuration

The `.claude/spinoff.json` file stores per-project settings:

```json
{
  "project_name": "my-app",
  "state_files": [".env", ".env.local"],
  "build_command": "pnpm install",
  "worktree_dir": ".worktrees",
  "default_mode": "implement"
}
```

## Usage Patterns

### Plan Competition (N-Plan)

A workflow where the parent agent spawns N Plan sub-agents in parallel to explore different approaches, compares their plans, then uses `/spinoff:new` for sandboxed implementation.

**1. Spawn N Plan agents in parallel**

The parent agent launches multiple Plan agents using the `Task` tool, each independently exploring the codebase and proposing an approach:

```
Use the Task tool to spawn 3 Plan agents in parallel (all in one message):

- Task 1: subagent_type=Plan, prompt="Plan approach A for <task description>"
- Task 2: subagent_type=Plan, prompt="Plan approach B for <task description>"
- Task 3: subagent_type=Plan, prompt="Plan approach C for <task description>"
```

Each Plan agent has access to Glob, Grep, and Read — they explore the codebase and return a proposed implementation plan.

**2. Compare and synthesize**

All N results return into the parent's context. The parent agent:

- Identifies common ground and divergences across plans
- Evaluates unique strengths of each approach
- Synthesizes the best elements into a single recommended plan

**3. Spinoff for implementation**

```
/spinoff:new <task-name> --task "<synthesized plan>"
```

The synthesized plan gets implemented in a sandboxed worktree while the parent continues other work.

## License

MIT
