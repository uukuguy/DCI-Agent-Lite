# Live Session Checkpoint

> Updated: 2026-07-15 03:06. **Session remains active — not a final handoff.** AF-240 Task 6 is in progress in the isolated `af-220-shared-dci-config` worktree.

Active work package: AF-240

## TL;DR

- AF-240 Tasks 0–5 are complete. Task 5 passed independent R4 review after immutable source snapshots, descriptor-relative publication, bounded streaming, namespace collision controls, and crash-safe export recovery were approved.
- Task 5 verification passed 100 focused tests and a single full run of 1133 Python tests; the complete log ended in `OK`. Ruff, compile, scope, and diff gates also passed.
- Task 6 RED contracts landed at `fa2000a`; installed package-local profiles, 12 one-to-one Pi-default launchers, full Judge overrides, and repository-independent wheel behavior are under implementation.
- A root inventory audit found 26 stale Task 3 rows. RED evidence landed at `179cb5d`; `724dedc` bound all 26 to executable Asterion replacements and 89 batch tests pass. Exactly 40 missing rows remain, all owned by Task 6.
- No complete source-product parity claim is valid yet. AF-240 Tasks 6–7 and AF-250 remain.

## Committed / unpushed state

- Branch: `af-220-shared-dci-config`.
- Task 5 approval evidence: `c228d6b`; Task 3 inventory repair: `724dedc`; Task 6 RED boundary: `fa2000a`.
- Commits are local/unpushed unless Git reports otherwise. The Task 6 implementer may have uncommitted RED tests; inspect before editing.

## Next action

Continue AF-240 Task 6 from `docs/superpowers/plans/2026-07-14-af-240-batch-evaluation-export-parity.md`: finish the in-flight CLI/profile/launcher implementation, verify exact dynamic launcher argv and explicit-path semantics, update the remaining 40 inventory rows, run isolated-wheel checks, then obtain an independent review before Task 7.

## Open questions

- None requiring user input. Launcher/profile fixtures must remain tiny/local; do not download or run full corpora.
- Only AF-240 Task 7 may consume the authorized bounded one-row real Pi-plus-Judge request.

## Ruled-out paths

- Do not claim completion from WORKLIST labels alone; executable inventory, fixtures, installed-boundary checks, bounded provider evidence, and AF-250 must agree.
- Do not import, launch, or modify `src/dci`; it is the independent comparison baseline.
- Do not redirect this Pi-default migration toward Claude provider work.
- Do not publish aggregates through untrusted path rebinding or accept self-authored cache/result evidence without exact validation.

## Ready commands

```bash
python3 tools/project_scope_check.py
git status --short
git log --oneline -12
uv run python -m unittest -q tests.test_asterion_dci_batch_launchers tests.test_asterion_dci_cli
uv run python -m unittest -q tests.test_asterion_dci_batch
uv run python -m unittest -q tests.test_climb_tools.Af240InventoryTests
```

## Guardrails

- Do not edit the external `pi/` checkout or persist credentials/provider bodies.
- Keep shared normal configuration in root `.env`; keep Asterion output ownership independent.
- Do not run full external datasets automatically.
- AF-250 owns the final no-unsupported-row product acceptance matrix and full-parity conclusion.
