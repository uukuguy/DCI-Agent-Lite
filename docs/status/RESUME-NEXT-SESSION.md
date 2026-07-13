# Live Session Checkpoint

> Updated: 2026-07-14. AF-220 remains active in the isolated `af-220-shared-dci-config` worktree; this is not a final handoff.

Active work package: AF-220

## TL;DR

- AF-220-H-001 through H-004 remain confirmed 4/4 with tracked local records (cycles 67–70); the full provider-independent closure passed.
- The worktree can use the approved shared configuration process-locally: source the main-repository `.env`, set `DCI_PI_DIR` to the main external Pi checkout, and add the worktree `src` to `PYTHONPATH`. Under that setup `make check-pi-rpc && make check-judge-config` passes without a model or HTTP request.
- The first real acceptance, `make asterion-example`, stopped before Pi startup because the example hard-codes this worktree's missing `corpus/wiki_corpus` directory. It created one native run directory whose state is `failed`, with no events or stderr; provider/model/tools were resolved. No Pi model or Judge HTTP request occurred.
- The runtime-context example, installed application, and one-row benchmark were not run after this failure. AF-220 is correctly still `in_progress`.

## Next action

Add an AF-220-scoped safe corpus-location boundary for Asterion examples and acceptance commands that lets the isolated worktree read the existing main-repository corpus without copying data, changing the external Pi checkout, or exposing configuration values. Re-run the bounded sequence from Step 2 only after the prerequisite remains green:

1. `make asterion-example && make asterion-runtime-example`
2. the installed `asterion run` Pi application command from the AF-220 plan
3. the one-row `asterion-dci benchmark` command from the AF-220 plan

Stop at the first nonzero result and journal safe status only. Do not mark AF-220 complete until all four authorized checks succeed.

## Guardrails

- Do not modify or import `src/dci`; Asterion retains independent runtime ownership.
- Do not add DCI option parsing to generic CLI/runner modules.
- `DCI_*` is the shared normal `.env` surface; `ASTERION_DCI_OUTPUT_ROOT` remains product-local.
- Do not copy/symlink `.env`, Pi, or corpus data into the worktree, and do not print/store credentials or provider bodies.
- Do not run full external datasets.
