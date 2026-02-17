# Set up GitHub repo governance, versioning, and CI

## Goals

1. **Branch protection** — protect `main`: require PRs, no direct pushes, require status checks to pass
2. **Merge policy** — squash merges via PR only, delete branch on merge
3. **Versioning** — adopt semver (e.g. `v1.0.0`), tag releases, maintain a CHANGELOG
4. **CI: unit tests** — GitHub Actions workflow runs `pytest tests/unit/` on every PR
5. **CI: e2e tests** — run `pytest -m e2e` on minor/major version bumps only (not patches), since e2e requires WezTerm and is expensive. This could be a manually-triggered workflow or triggered by tag pattern (`v*.*.0` for minor, `v*.0.0` for major)
6. **Release workflow** — version bump script or GitHub release that creates a tag and triggers e2e
7. **Research: Claude Code plugin deployment/ops** — investigate the standard practices for publishing and maintaining a Claude Code plugin:
   - How does the marketplace/registry work? Versioning conventions?
   - Is there a review/approval process for plugin updates?
   - How do users get updates (auto-update, manual reinstall, version pinning)?
   - Are there official guidelines for plugin CI/CD, testing, or release workflows?
   - What do other published plugins do for their release process?
   - Document findings and incorporate into the CI/release workflow design

## Notes

- E2E CI requires a macOS runner with WezTerm installed (self-hosted or pre-configured)
- Unit tests can run on any runner (ubuntu, macos)
- Consider a `Makefile` or `just` target for `test-unit`, `test-e2e`, `test-all`
- The research subtask should be done first — its findings may influence the CI/versioning decisions
