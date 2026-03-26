# Migrate from WezTerm to cmux

## Context

cmux (manaflow-ai/cmux) is a native macOS terminal app built on Ghostty's rendering engine, purpose-built for AI coding agent workflows. It provides a superset of WezTerm's programmatic control capabilities, plus agent-specific features (notification rings, `read-screen`, sidebar metadata, embedded browser).

## 002.1 — Findings: cmux as WezTerm Replacement

### What cmux is

- Native macOS app (Swift/AppKit), not Electron, not a terminal multiplexer
- Built on Ghostty's rendering engine (libghostty), GPU-accelerated
- ~10.5k GitHub stars, created 2026-01-28, v0.62.2 as of 2026-03-14
- Install: `brew tap manaflow-ai/cmux && brew install --cask cmux`
- License: AGPL-3.0 (dual-licensed commercial)

### CLI and socket API

cmux provides ~40+ CLI commands and a Unix socket API (JSON-RPC v2 over `~/Library/Application Support/cmux/cmux.sock`). Every WezTerm CLI operation spinoff uses has a direct equivalent:

| Spinoff operation       | `wezterm cli`                       | `cmux` equivalent                                 |
| ----------------------- | ----------------------------------- | ------------------------------------------------- |
| Check if running        | `list-clients`                      | `ping`                                            |
| Create tab in workspace | `spawn --workspace X --window-id Y` | `new-workspace [--cwd <path>] [--command <text>]` |
| List panes (JSON)       | `list --format json`                | `--json list-workspaces`, `--json tree`           |
| Send text to pane       | `send-text --pane-id X`             | `send --surface <id> <text>`                      |
| Kill pane               | `kill-pane --pane-id X`             | `close-surface --surface <id>`                    |
| Set tab title           | `set-tab-title --pane-id X`         | `rename-workspace --workspace <id> <title>`       |
| Focus pane              | `activate-pane --pane-id X`         | `select-workspace --workspace <id>`               |

### Capabilities beyond WezTerm

| Feature               | Command                                     | Use for spinoff                        |
| --------------------- | ------------------------------------------- | -------------------------------------- |
| Read terminal content | `read-screen --surface <id> [--scrollback]` | Monitor agent output, detect state     |
| Notifications         | `notify --title "..." --body "..."`         | Alert user when agent needs attention  |
| Sidebar metadata      | `set-status`, `set-progress`, `log`         | Show agent progress per workspace      |
| Send keystrokes       | `send-key --surface <id> enter`             | Approve agent prompts programmatically |
| Embedded browser      | `browser open`, `browser navigate`, etc.    | Show PR diffs, test results            |
| Environment vars      | `CMUX_WORKSPACE_ID`, `CMUX_SURFACE_ID`      | Agent self-identification              |

### Terminology mapping

| WezTerm   | cmux                   | Notes                                     |
| --------- | ---------------------- | ----------------------------------------- |
| Window    | Window                 | Top-level OS window                       |
| Workspace | (no direct equivalent) | cmux groups by window, not workspace name |
| Tab       | Workspace              | Vertical sidebar entry                    |
| Pane      | Surface                | Individual terminal session               |
| —         | Pane                   | Split container holding surfaces          |

### Socket access modes

The socket defaults to `cmuxOnly` (only processes spawned inside cmux can connect). For external orchestration scripts, set to `automation` mode in cmux Settings. If spinoff scripts always run inside cmux terminals, the default works.

### Risks

| Risk                             | Severity | Mitigation                                                           |
| -------------------------------- | -------- | -------------------------------------------------------------------- |
| macOS only                       | Medium   | All current spinoff users are on macOS; document platform constraint |
| Young project (2 months)         | High     | Implement behind a backend abstraction; pin to specific version      |
| API instability (V1->V2 already) | High     | Use CLI not raw socket; pin version; test on upgrade                 |
| AGPL license                     | Low      | Spinoff uses cmux as a tool, doesn't modify or distribute it         |
| Ghostty fork dependency          | Medium   | Not our problem unless cmux dies; monitor project health             |

## 002.1 — Migration Plan

See [002.1-cmux-migration-plan.md](002.1-cmux-migration-plan.md).

## 002.2 — cmux Overview Panel

See [002.2-cmux-overview-panel.md](002.2-cmux-overview-panel.md).

## 002.3 — Window Targeting & Overview Auto-Switch

See [002.3-cmux-window-targeting.md](002.3-cmux-window-targeting.md).
