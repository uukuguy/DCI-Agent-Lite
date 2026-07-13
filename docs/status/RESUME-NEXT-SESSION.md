# Live Session Checkpoint

> Updated: 2026-07-13 23:00. **AF-210 is complete; this is a live post-closure checkpoint, not a final handoff.**

Active work package: none

## TL;DR

- AF-210 Climb H-001 through H-004 are confirmed 4/4 with deterministic local evidence.
- `EnvironmentDciRunExecutor` now maps `ASTERION_RUNTIME_CWD` and `ASTERION_DCI_*` paths into one native DCI invocation, verified with a fake runner and no provider request.
- The first-party DCI provider now binds that executor only for `pi.reference`; the installed application CLI test confirms native dispatch and body-free references, while the Claude fixture path remains unchanged.
- A clean-worktree baseline repair makes `scripts/check_pi_rpc.py --help` source-runnable and removes a test dependency on an untracked empty directory.

## Where things stand

- Branch: `codex/af-210-application-parity`; commits through `6412d17` are ahead of main, with AF-210 closure changes pending commit.
- The working tree contains closure documentation, deterministic Climb records, adapter mappings, the current JOURNAL lines, and this live checkpoint.
- H-001 through H-004 are all confirmed 4/4; no provider request occurred.

## Next action

1. Run the final repository verification matrix, then commit the AF-210 closure evidence.
2. Select a new governed work package before starting any successor implementation; Claude provider-backed parity remains outside the closed AF-210 local scope.

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
