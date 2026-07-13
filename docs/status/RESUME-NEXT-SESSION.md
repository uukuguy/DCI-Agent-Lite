# Live Session Checkpoint

> Updated: 2026-07-13 22:50. **Session remains active — not a final handoff.**

Active work package: AF-210

## TL;DR

- AF-210 Climb is registered with H-001 through H-004; its new session targets provider-bound Pi application parity only.
- `EnvironmentDciRunExecutor` now maps `ASTERION_RUNTIME_CWD` and `ASTERION_DCI_*` paths into one native DCI invocation, verified with a fake runner and no provider request.
- The first-party DCI provider now binds that executor only for `pi.reference`; the installed application CLI test confirms native dispatch and body-free references, while the Claude fixture path remains unchanged.
- A clean-worktree baseline repair makes `scripts/check_pi_rpc.py --help` source-runnable and removes a test dependency on an untracked empty directory.

## Where things stand

- Branch: `codex/af-210-application-parity`; commits `b1ee100`, `4f85e15`, and `dfe3e43` are ahead of main.
- The working tree contains H-002 implementation, its tests, the current JOURNAL line, and this live checkpoint.
- H-001 and H-002 are implemented but not yet recorded through `cycle.sh`; AF-210 adapters still need their deterministic test mappings before cycles can run.

## Next action

1. Add the H-003 installed-projection/redaction integration test, then implement only any missing wiring.
2. Extend the AF-210 Climb adapter and record H-001/H-002 cycles after deterministic mappings are available.

## Guardrails

- Do not modify/import `src/dci` or add DCI parsing to generic CLI/runner modules.
- Do not send Pi, judge, or Claude provider requests; Claude remains fixture-only.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py --climb-hypothesis AF-210-H-002
uv run python -m unittest tests.test_dci_research_capability -v
git status --short
```
