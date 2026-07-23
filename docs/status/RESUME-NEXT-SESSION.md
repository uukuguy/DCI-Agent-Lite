# Live Session Checkpoint

> Updated: 2026-07-23 09:02 +0800. **Session remains active — not a final handoff.**

Active work package: AF-350

Package: AF-350 — Asterion standalone promotion readiness

Currently running: no process.

## TL;DR

- The user approved the complete AF-350 design for making `asterion/` promotion-ready as a GitHub repository root without creating or publishing a separate repository.
- D-056 separates package-owned, provider-free standalone acceptance from the mixed-repository 538-selector original DCI/Asterion integration gate.
- Tasks 1–3 are complete: the standalone skeleton and package-owned installed acceptance are GREEN from source and wheel.

## Where things stand

- Local `main` remains unpushed and ahead of `origin/main`; the prior AF-340 lifecycle is complete.
- Governance commit `3e8be41` records AF-350, D-056, the approved written design, and the active recovery boundary.
- Planning commit `df0b901` records the eight-task RED/GREEN implementation and closure sequence.
- Implementation commit `09b47e8` adds standalone root assets, both required uv locks, 143-test GREEN evidence, and build/lint entry points.
- Acceptance commit `945261b` removes the dynamic mixed-root loader, adds seven exact installed checks, restores ignored package resources, and preserves mixed 8/8 plus 538/538 parity.
- The only new package is AF-350. It does not authorize a provider request, full dataset, paper reproduction, publication, remote push, or external `pi/` mutation.
- The approved design target is `docs/superpowers/specs/2026-07-23-af-350-asterion-standalone-promotion-readiness-design.md`.
- No evaluator, verifier, test, Rust, Node, or promotion process is running.

## Next steps

1. Execute Task 4 RED/GREEN for standalone-root launchers.
2. Replace mixed-root `REPO_ROOT/asterion` resolution with project-root and explicit external-resource resolution.
3. Keep benchmark identities and execution semantics unchanged.

## Open questions

- No design question remains. Execution mode is inline; package-owned acceptance is the next implementation boundary.
- Creating a separate Git repository, remote, release, or package publication remains outside AF-350.

## Ruled-out paths

- Do not copy the original `src/dci`, mixed-root governance, retained private evidence, corpora, datasets, credentials, or external Pi into `asterion/`.
- Do not preserve the current dynamic mixed-root verifier as standalone installed acceptance.
- Do not ship only a repository skeleton while leaving standalone acceptance or launchers dependent on the parent tree.
- Do not relabel the 538-selector integration matrix as current standalone product verification.
- Do not run providers, a Judge, or a full dataset during AF-350 promotion readiness.

## Ready commands

```bash
python3 tools/project_scope_check.py
git status --short --branch
git diff --check
sed -n '1,280p' docs/superpowers/specs/2026-07-23-af-350-asterion-standalone-promotion-readiness-design.md
```
