# Live Session Checkpoint

> Updated: 2026-07-14. AF-220 local closure is complete in the isolated `af-220-shared-dci-config` worktree; this is not a final handoff.

Active work package: AF-220

## TL;DR

- AF-220-H-001 through H-004 are each confirmed 4/4 with tracked local records (cycles 67–70).
- The local Climb adapter now maps the four AF-220 hypotheses to the current focused configuration/Judge, Pi-control, CLI/benchmark, and installed-application/example suites.
- The adapter no longer requires a closed AF-210 work-package scope to evaluate current work. Historical AF-210 local contracts remain executable with current active-package preflight.
- Full local Python, compile/Ruff, TypeScript, Rust, shell, scope, and diff closure passed; no Pi, Judge, or other provider request was sent.

## Next action

Run AF-220 Task 7’s already-authorized bounded external acceptance from this worktree. Do not mark AF-220 complete unless all of these succeed:

1. `make check-pi-rpc && make check-judge-config`
2. `make asterion-example && make asterion-runtime-example`
3. the installed `asterion run` Pi application command in the AF-220 plan
4. the one-row `asterion-dci benchmark` Pi-plus-Judge command in the plan

Journal only safe output locations, exit status, configuration names, and verdicts—never credentials or provider bodies. On any failure, retain AF-220 as `in_progress` and record the exact safe failure.

## Guardrails

- Do not modify or import `src/dci`; Asterion retains independent runtime ownership.
- Do not add DCI option parsing to generic CLI/runner modules.
- `DCI_*` is the shared normal `.env` surface; `ASTERION_DCI_OUTPUT_ROOT` remains product-local.
- Do not run full external datasets.

## Ready-to-paste local checks

```bash
python3 tools/project_scope_check.py --climb-hypothesis AF-220-H-004
uv run python -m unittest discover -v
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
git diff --check
```
