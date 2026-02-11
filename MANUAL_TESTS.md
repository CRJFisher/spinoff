# Spinoff Plugin — Manual Test Plan

Run these after installing the plugin. Each test verifies a specific change from the friction-reduction work.

## Setup

### Install the plugin

**Option A — Local dev (picks up changes on restart):**

```bash
claude --plugin-dir /Users/chuck/workspace/spinoff
```

**Option B — From GitHub:**

```bash
# Inside Claude Code, run:
/plugin marketplace add CRJFisher/spinoff
/plugin install spinoff@CRJFisher-spinoff
```

Skills will be namespaced as `/spinoff:init`, `/spinoff:new`, `/spinoff:merge`, `/spinoff:list`.

### Verify skills are loaded

```
/spinoff:list
```

If this shows "No worktrees tracked" or lists spinoffs, the plugin is working. If the command is not recognized, the plugin isn't loaded.

### Prepare a test project

Use a Node.js repo with `pnpm` (or any repo). Make sure WezTerm is running.

```bash
# In the test project, ensure .claude/spinoff.json does NOT exist yet
rm -f .claude/spinoff.json
```

---

## Test 1: `/spinoff:init` (model invocation + config CLI)

**What changed:** Model invocation enabled, save_config has CLI entry point.

```
/spinoff:init
```

**Verify:**

- [ ] Claude analyzes the tech stack (not just rigid template execution)
- [ ] Claude presents findings and waits for confirmation
- [ ] `.claude/spinoff.json` is created with correct project_name, state_files, build_command
- [ ] Claude mentions `/spinoff:new`, `/spinoff:merge`, and `/spinoff:list` in the summary

---

## Test 2: `/spinoff:new` — happy path (build-in-tab, base_branch, name validation)

**What changed:** Build runs in WezTerm tab (non-blocking), base_branch recorded, Glob used for spec discovery.

```
/spinoff:new test-task --base main --task "Say hello and exit"
```

**Verify:**

- [ ] Worktree created at `.worktrees/test-task`
- [ ] Branch `worktree/test-task` created
- [ ] WezTerm tab opens immediately (parent process NOT blocked by build)
- [ ] Inside the WezTerm tab: build command runs first, then Claude starts
- [ ] If build fails, error is visible in the tab (Claude does not start)
- [ ] State file `.worktrees/.state.json` exists (NOT `.worktrees.local.md`)
- [ ] State file contains `"base_branch": "main"`

```bash
# Quick check:
cat .worktrees/.state.json
```

---

## Test 3: `/spinoff:list`

**What changed:** New skill.

```
/spinoff:list
```

**Verify:**

- [ ] Shows `test-task` with branch, path, and pane status
- [ ] Cross-references live WezTerm panes (shows alive/dead)
- [ ] If no spinoffs exist, suggests `/spinoff:new`

---

## Test 4: `/spinoff:merge` — happy path (base_branch default, validate-before-close)

**What changed:** Default target = stored base_branch, validation before tab close.

First, make sure the spinoff has at least one commit (so there's something to merge):

```
# In the WezTerm tab for test-task, or manually:
cd .worktrees/test-task
echo "test" > test-file.txt
git add test-file.txt
git commit -m "test commit"
cd ../..
```

Then merge (no `--target` flag — should default to `main` from stored base_branch):

```
/spinoff:merge test-task
```

**Verify:**

- [ ] Merges into `main` without needing `--target main` (uses stored base_branch)
- [ ] WezTerm tab closes
- [ ] Worktree directory removed
- [ ] Branch deleted
- [ ] State file updated (test-task removed)

---

## Test 5: Name validation — bad names rejected

```
/spinoff:new ..
/spinoff:new .hidden-task
/spinoff:new bad@name
```

**Verify:**

- [ ] `..` — rejected with clear error
- [ ] `.hidden-task` — rejected (starts with `.`)
- [ ] `bad@name` — rejected (invalid character `@`)
- [ ] `--flag` — sanitized to `flag` (stripped leading hyphens), proceeds normally
  - Clean up after: `/spinoff:merge flag` or `git worktree remove .worktrees/flag`

---

## Test 6: Merge with nonexistent target — error before tab close

Create a spinoff first:

```
/spinoff:new merge-fail-test --task "test merge failure"
```

Then try to merge into a branch that doesn't exist:

```
/spinoff:merge merge-fail-test --target nonexistent-branch
```

**Verify:**

- [ ] Error message: "Target branch 'nonexistent-branch' does not exist"
- [ ] WezTerm tab is still alive (not closed)
- [ ] Can still work in the WezTerm tab after the failed merge

Clean up:

```
# Close the tab manually or:
/spinoff:merge merge-fail-test
```

---

## Test 7: Merge with uncommitted changes — error before tab close

Create a spinoff:

```
/spinoff:new dirty-test --task "test dirty merge"
```

Make the worktree dirty (don't commit):

```bash
echo "dirty" > .worktrees/dirty-test/uncommitted.txt
```

Try to merge:

```
/spinoff:merge dirty-test
```

**Verify:**

- [ ] Error message mentions uncommitted changes
- [ ] WezTerm tab is still alive (not closed)

Clean up:

```bash
rm .worktrees/dirty-test/uncommitted.txt
/spinoff:merge dirty-test
```

---

## Test 8: `/spinoff:new` with `--base develop` (merge target tracking)

```
git checkout -b develop
git checkout main
/spinoff:new develop-test --base develop --task "test base branch tracking"
```

**Verify:**

- [ ] State file shows `"base_branch": "develop"`

```bash
cat .worktrees/.state.json | python3 -m json.tool
```

Now merge without specifying target:

```
/spinoff:merge develop-test
```

- [ ] Merges into `develop` (not `main`) automatically

---

## Cleanup

After all tests, verify no leftover worktrees:

```bash
git worktree list
ls .worktrees/
cat .worktrees/.state.json
```
