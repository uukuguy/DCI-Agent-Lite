# Live Session Checkpoint

> Updated: 2026-07-23 09:05 +0800. **Session remains active — not a final handoff.**

Active work package: AF-350

Package: AF-350 — Asterion standalone promotion readiness

Currently running: no process.

## TL;DR

- Tasks 1–4 are complete: `asterion/` owns its repository skeleton, package-owned provider-free acceptance, and all 14 standalone-root launchers.
- Standalone tests pass 153/153; mixed integration remains 8/8 product rows, 538/538 selectors, 12/12 launcher pairs, and zero provider operations.
- Continue inline with Task 5: complete standalone documentation and its local link/command checker.

## Where things stand

- Local `main` remains unpushed and ahead of `origin/main`; the prior AF-340 lifecycle is complete.
- `09b47e8` adds standalone root assets, complete Make targets, package metadata, and reproducible locks.
- `945261b` makes installed acceptance package-owned and source/wheel equivalent while preserving the mixed-root parity gate.
- `ef03e3c` makes all 14 launchers resolve the copied project root and an explicit external resource root without parent traversal.
- The only active package is AF-350. It does not authorize provider requests, full datasets, paper reproduction, publication, remote push, release, or external `pi/` mutation.
- No evaluator, verifier, test, Rust, Node, or promotion process is running.

## Next steps

1. Execute Task 5 RED/GREEN for standalone documentation and link/command verification.
2. Make the framework overview and functional validation guide complete from the promoted root perspective.
3. Preserve evidence labels and keep mixed-root-only procedures explicitly separate.

## Open questions

- No design question remains. Execution mode is inline; standalone docs are the next implementation boundary.
- Creating a separate Git repository, remote, release, or package publication remains outside AF-350.

## Ruled-out paths

- Do not copy original `src/dci`, mixed-root governance, retained private evidence, corpora, datasets, credentials, or external Pi into `asterion/`.
- Do not reintroduce a dynamic mixed-root verifier as installed acceptance.
- Do not treat mixed 538-selector integration evidence as standalone installed verification.
- Do not run providers, a Judge, or a full dataset during AF-350 promotion readiness.

## Ready commands

```bash
python3 tools/project_scope_check.py
git status --short --branch
sed -n '625,730p' docs/superpowers/plans/2026-07-23-af-350-asterion-standalone-promotion-readiness.md
(cd asterion && uv run python -m unittest -v tests.test_standalone_docs)
git diff --check
```
