# Live Session Checkpoint

> Updated: 2026-07-13 22:50. **Session remains active — not a final handoff.**

Active work package: AF-210

## TL;DR

- AF-210 Climb is registered with H-001 through H-004; its new session targets provider-bound Pi application parity only.
- `EnvironmentDciRunExecutor` now maps `ASTERION_RUNTIME_CWD` and `ASTERION_DCI_*` paths into one native DCI invocation, verified with a fake runner and no provider request.
- The first-party DCI provider now binds that executor only for `pi.reference`; the installed application CLI test confirms native dispatch and body-free references, while the Claude fixture path remains unchanged.
- A clean-worktree baseline repair makes `scripts/check_pi_rpc.py --help` source-runnable and removes a test dependency on an untracked empty directory.

## Where things stand

- Branch: `codex/af-210-application-parity`; commits through `c7c96cc` are ahead of main.
- The working tree contains the post-commit JOURNAL line and this live checkpoint only.
- H-001 through H-003 are implemented and locally verified but not yet recorded through `cycle.sh`; AF-210 adapters still need their deterministic test mappings before cycles can run.

## Next action

1. Extend the AF-210 Climb adapter with deterministic H-001 through H-004 test mappings.
2. Record the H-001 through H-004 cycles, then run the final closure matrix and update AF-210 documentation/worklist status.

## Guardrails

- Do not modify/import `src/dci` or add DCI parsing to generic CLI/runner modules.
- Do not send Pi, judge, or Claude provider requests; Claude remains fixture-only.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py --climb-hypothesis AF-210-H-002
uv run python -m unittest tests.test_dci_research_capability -v
git status --short
```
