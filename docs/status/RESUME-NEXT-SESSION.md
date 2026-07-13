# Live Session Checkpoint

> Updated: 2026-07-13 23:03. **AF-210 is merged into main; this is a live post-merge checkpoint, not a final handoff.**

Active work package: none

## TL;DR

- AF-210 Climb H-001 through H-004 are confirmed 4/4 with deterministic local evidence.
- `EnvironmentDciRunExecutor` now maps `ASTERION_RUNTIME_CWD` and `ASTERION_DCI_*` paths into one native DCI invocation, verified with a fake runner and no provider request.
- The first-party DCI provider now binds that executor only for `pi.reference`; the installed application CLI test confirms native dispatch and body-free references, while the Claude fixture path remains unchanged.
- A clean-worktree baseline repair makes `scripts/check_pi_rpc.py --help` source-runnable and removes a test dependency on an untracked empty directory.

## Where things stand

- Branch: `main`; merge commit `dcd4bf3` integrates AF-210 and its closure evidence.
- The working tree contains this merge-journal/checkpoint update only; carry it into the next approved successor-work commit.
- H-001 through H-004 are all confirmed 4/4; no provider request occurred.
- User approved the complete-product migration direction and bounded real Pi/Judge acceptance. AF-220 is proposed pending written-spec review; do not implement or launch Climb until its plan activates the package.

## Next action

1. Select a new governed work package before starting any successor implementation.
2. Obtain written-spec review for `docs/superpowers/specs/2026-07-13-asterion-dci-complete-product-parity-design.md`, then write AF-220's plan and activate exactly one package before implementation.

## Guardrails

- Do not modify/import `src/dci` or add DCI parsing to generic CLI/runner modules.
- Do not send Pi, judge, or Claude provider requests; Claude remains fixture-only.

## Ready-to-paste commands

```bash
uv run python -m unittest discover -v
npm --prefix packages/typescript/asterion-runtime test
make test-rust-executor
git status --short
```
