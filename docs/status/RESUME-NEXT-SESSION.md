# Live Session Checkpoint

> Updated: 2026-07-15 03:47 +0800. **Session remains active — not a final handoff.** AF-240 is closed and AF-250 is active in the isolated `af-220-shared-dci-config` worktree.

Active work package: AF-250

## TL;DR

- AF-220 through AF-240 are completed. AF-240 confirms all four Climb hypotheses 4/4 and maps all 533 batch/evaluation/export inventory rows to executable Asterion evidence.
- AF-240 final gates passed 1204 Python, 11 TypeScript, and 19 Rust tests; compile, Ruff, 12 launcher shell checks, scope/diff, model-free launcher preflights, and isolated-wheel/resource/help/import checks also passed.
- One bounded one-row Pi-plus-Judge recovery batch completed with one correct verdict and 28 credential-clean private artifacts. Exact reuse kept native/Judge hashes and mtimes unchanged, retained one protocol attempt, and created no second generation.
- Full migration is not yet claimed. AF-250 must execute the final cross-product acceptance matrix, including both original example scripts and the installed Pi-default Asterion application.
- AF-250 Task 1 now has a strict eight-row product matrix, real model-free behavior selectors, exact owners, seven body-free provider case IDs, and four pending package-owned Climb hypotheses.

## Committed / unpushed state

- Branch: `af-220-shared-dci-config`.
- AF-240 Climb confirmation: `6e651b3`; lifecycle contract correction: `16ceec5`.
- AF-240 closure/state changes are committed at `3e28d5c` and the independent-review repair at `b15d5f1`; only the latest post-commit journal entry remains uncommitted.
- AF-250 Task 1 initially landed at `447395b`; its single review-repair commit is the commit immediately after `447395b` and is recorded by exact SHA in the recent Journal/git log after landing.
- Commits are local/unpushed unless Git reports otherwise.

## Next action

Execute Task 2 of `docs/superpowers/plans/2026-07-15-af-250-product-acceptance-matrix.md`: restore independently executable source DCI Judge verification targets and add model-free execution evidence for both source and Asterion example pairs.

## Open questions / defects to verify

- `make check-judge-config` currently invokes the source script without `PYTHONPATH=src`; in this workspace it fails with `ModuleNotFoundError: dci`. AF-250 must test and repair the source runnable surface rather than treating a worklist label as evidence.
- The root-configured default Provider rejected the AF-240 acceptance at zero usage. The authorized recovery used the existing OpenRouter credential with Pi and completed; do not interpret the default account quota as an Asterion defect.
- No user decision is currently required. Do not download or start full corpora.

## Ruled-out paths

- Do not claim full parity from AF-240 closure or inventory counts alone; AF-250 executable evidence is mandatory.
- Do not import, launch, or modify `src/dci` from Asterion production code. The original DCI stays independently runnable and may receive only bounded compatibility repairs under AF-250.
- Do not redirect the Pi-default migration to another agent runtime.
- Do not run full BCPlus/QA/BRIGHT datasets automatically or persist credentials/provider bodies.

## Ready commands

```bash
python3 tools/project_scope_check.py
git status --short
git log --oneline -12
uv run python -m unittest discover -v
PYTHONPATH=src uv run python scripts/check_judge.py --config-only
bash scripts/examples/dci_basic_example.sh
bash scripts/examples/asterion_dci_basic_example.sh
```

## Guardrails

- Active package is AF-250; register any Climb hypotheses under AF-250 before running them.
- Root `.env` is the shared configuration surface; never print or persist its credentials.
- Treat `pi/` as an external checkout and do not edit it.
- Keep AF-250 fixtures tiny and reproducible; separate local, Pi-only, and Pi-plus-Judge evidence.
