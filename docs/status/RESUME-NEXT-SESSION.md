# Live Session Checkpoint

> Updated: 2026-07-14. AF-220 is closed; AF-230 is the active successor in the isolated `af-220-shared-dci-config` worktree.

Active work package: AF-230

## TL;DR

- AF-220 is complete: all four local hypotheses remain confirmed 4/4, and all authorized bounded real checks passed using process-local shared configuration only.
- Safe real evidence: model-free Pi RPC/Judge-config prerequisites exited zero; basic Pi example completed native `question.txt`/`events.jsonl`/`final.txt`/`state.json`; runtime-context Pi-plus-Judge example completed with boolean `eval_result.json.is_correct`; the application completed through `uv run --project packages/python/asterion-core asterion` because the direct binary is not on the worktree PATH, producing exactly one body-free JSON object and native shared provider/model/tools fields; one-row benchmark produced one native query directory, `result.json`, `summary.json` total 1, and boolean verdict.
- Temporary acceptance roots are under the system temporary directory with prefixes `af220-basic-output.`, `af220-context-retry-output.`, `af220-application-final-output.`, and `af220-benchmark.`. Status documents contain no credentials or provider bodies.
- AF-230 is now active. It has no implementation plan or Climb hypotheses yet; do not begin code changes before creating its detailed plan and registering its parented hypotheses.

## Next action

Derive and review the AF-230 implementation plan from the approved complete-product-parity design, covering native operator controls, artifact/provenance semantics, and resume behavior against source DCI. Then register AF-230 Climb state, rerun scope preflight, and begin implementation only through the approved plan.

## Guardrails

- Do not modify or import `src/dci`; Asterion retains independent runtime ownership.
- Do not edit the external Pi checkout or copy/symlink configuration, Pi, or corpus data into the worktree.
- `DCI_*` remains the shared normal `.env` surface; `ASTERION_DCI_OUTPUT_ROOT` remains product-local.
- Do not print/store credentials or provider bodies, and do not run full external datasets without new authorization.
