# Live Session Checkpoint

> Updated: 2026-07-20 12:58 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

## TL;DR

- The quota-interrupted Task 6 work was recovered, completed, verified, and committed as `ec4d1e9`.
- Five immutable profiles now bind runtime/Judge plus AF-320 inventory, scope, selection, corpus, metric, and context identities; `current-default/claude-minimax` is locked to the verified `MiniMax-M3` configuration and paper variants use `level3`.
- Full execution remains fail-closed behind an invocation-only authorization, finite budget, fresh 0700 root, 0600 record, and matching profile/scope/batch identity. No provider operation or full dataset ran.

## Where things stand

- Project route: managed; lifecycle: active; package: AF-340.
- Task 6 verification: 130 focused tests and 10 public product tests pass; final source CLI and isolated wheel both resolve all five profiles and report zero dry-run operations.
- Static/governance gates: Python compile, Ruff, final wheel build/import, `project_scope_check.py`, and `git diff --check` pass.
- Profile digests:
  - `current-default/pi`: `25e1f8e50a742fedf9c9027806680db1f8be87be69a9d717325d2d8b95d3df20`
  - `current-default/claude-subscription`: `458175537ec60de825a2f8deac0638267a15293440f5ad6a4d6876d45e417ede`
  - `current-default/claude-minimax`: `ab22c083bedc6ccb003cb7f72a1454faeb783fb4e06fb50c72bbc8141c25c64d`
  - `paper-reference/pi`: `4d1bdde65381c6cfd93aab672e96246fd3438cdaa9a980e22ff157d2405f096e`
  - `paper-reference/claude-code`: `fa3b0ec9b7225ca6c058000088e0b28f171f871427e64fa548888f783ffaa934`
- External `pi/` was not edited; no evaluator, Climb cycle, provider verifier, or full execution is running.

## Next action

1. Begin AF-340 Task 7 with RED manifest-validation and statistical-comparison tests.
2. Bind normalized per-query evidence to the Task 6 profile/effective-config identities and preserve failed/cancelled/timed-out/missing rows.
3. Do not begin Task 8 full coordination or request full-cost authority until Task 7 is committed and provider-free verification passes.

## Ready command

```bash
uv run python -m unittest -v tests.test_asterion_dci_reproduction tests.test_asterion_dci_paper_resolution_analysis tests.test_asterion_dci_paper_product
```
