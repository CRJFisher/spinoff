# Tech Stack Detection

## Stack Detection Table

| File                                  | Stack   |
| ------------------------------------- | ------- |
| `package.json`                        | Node.js |
| `pyproject.toml` / `requirements.txt` | Python  |
| `Cargo.toml`                          | Rust    |
| `go.mod`                              | Go      |
| `pom.xml` / `build.gradle`            | Java    |
| `Gemfile`                             | Ruby    |

## Build Commands

| Stack          | Build Command                    |
| -------------- | -------------------------------- |
| Node.js (npm)  | `npm install && npm run build`   |
| Node.js (pnpm) | `pnpm install && pnpm run build` |
| Node.js (yarn) | `yarn install && yarn build`     |
| Python         | `pip install -e .`               |
| Rust           | `cargo build`                    |
| Go             | `go build ./...`                 |

## State Files to Copy

Find state files that should be copied to each worktree: `.env`, `.env.local`, `.env.development`, local config files.
