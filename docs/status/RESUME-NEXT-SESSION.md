# Live Session Checkpoint

> Updated: 2026-07-14. AF-220 remains active in the isolated `af-220-shared-dci-config` worktree; this is not a final handoff.

Active work package: AF-220

## TL;DR

- AF-220-H-001 through H-004 remain confirmed 4/4 with tracked local records (cycles 67–70); the full provider-independent closure passed.
- With process-local main `.env`, main Pi checkout, worktree source path, and approved absolute corpus root, both model-free prerequisites and both real examples pass. The runtime-context output includes a completed native state, recorded unsupported current-Pi context control, and `eval_result.json.is_correct` as a boolean.
- The installed application ran a bounded real Pi request to a completed native state and persisted nonempty shared provider/model/tools fields. Its generic CLI acceptance fails because `PiRpcClient.prompt_and_wait` writes text deltas directly to stdout before `asterion.cli` writes the body-free JSON projection.
- The one-row Pi-plus-Judge benchmark remains intentionally unrun. AF-220 is correctly still `in_progress`.

## Next action

Make the Asterion native Pi client support an explicit non-streaming mode for the generic installed-application boundary, preserving product-CLI operator output where applicable. Add focused regression coverage proving the generic `asterion run` stdout is one body-free JSON object, rerun local closure, then restart Task 7 at installed application acceptance.

After the application passes, run the one-row benchmark exactly as prescribed. Stop at the first nonzero result and journal safe status only. Do not mark AF-220 complete until all four authorized checks succeed.

## Guardrails

- Do not modify or import `src/dci`; Asterion retains independent runtime ownership.
- Do not add DCI option parsing to generic CLI/runner modules.
- `DCI_*` is the shared normal `.env` surface; `ASTERION_DCI_OUTPUT_ROOT` remains product-local.
- Use the process-local main `.env`, main `DCI_PI_DIR`, and approved absolute `ASTERION_DCI_CORPUS_ROOT`; do not copy/symlink configuration, Pi, or corpus data into the worktree.
- Do not print/store credentials or provider bodies, and do not run full external datasets.
