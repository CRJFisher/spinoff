# Mode Selection Heuristics

Decide the agent mode (`plan` or `implement`) using these rules in order:

## 1. Explicit `--mode` flag

If provided, use it directly. Done.

## 2. Task description keyword signals

If `--task` was provided, scan for keyword signals:

**Plan signals**: plan, design, explore, investigate, analyze, compare, evaluate, research, review, assess, propose, understand, audit

**Implement signals**: implement, fix, build, create, add, update, refactor, migrate, remove, delete, replace, write, change, move, rename, upgrade, convert, integrate

If a strong signal is found, suggest that mode and confirm with the user.

## 3. Project default

Read `default_mode` from `.claude/spinoff.json` and confirm with user.

## Mode descriptions

- **plan**: Read-only exploration. Agent uses `--permission-mode plan` (no sandbox). Good for investigation, design, and code review.
- **implement**: Sandboxed execution. Agent can write files and run commands. Auto-commits work before finishing. Good for bug fixes, features, and refactoring.
