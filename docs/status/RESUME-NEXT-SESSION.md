# Terminal Migration Checkpoint

> Updated: 2026-07-15 07:42 +0800. Asterion DCI migration and product acceptance are complete.

Active work package: none

## TL;DR

- AF-250 and every worklist package are completed; repository lifecycle is `complete`.
- Asterion DCI independently implements the original Pi-based DCI product surface without importing or launching `src/dci`.
- Acceptance covers eight model-free rows, 533 delegated selectors, twelve launcher pairs, six batch extras, an isolated installed wheel/application, and seven bounded real source/Asterion/application/Pi-plus-Judge/reuse cases.
- The authoritative runnable procedure is `docs/verification/asterion-dci-validation-guide.md`.
- No full dataset ran; full-dataset performance is separate operator-authorized work, not a migration gap.

## Committed state

- Product implementation and acceptance: `327a070`.
- Accepted recovery checkpoint: `41de2db`.
- Terminal lifecycle design and plan: `6d42ebf`, `3345aa2`.
- Explicit lifecycle governance: `3717c63`.
- Full functional verification guide: `673ac03`.

The final terminal-state commit is the newest commit after these entries. The
branch is `af-220-shared-dci-config`; inspect `git log --oneline -8` rather than
relying on chat history.

## Verified evidence

- Public product verifier: 8/8 rows, 533/533 delegated selectors, 12/12 launcher pairs, 6/6 batch extras, bounded acceptance 7/7, zero provider execution during verification.
- Retained native evidence: private acceptance 7/7 after digest, mode, lifecycle, Judge, exact-reuse, mtime, and credential-value checks.
- Final terminal closure: 1275 Python, 11 TypeScript, and 19 Rust tests plus compile, Ruff, shell, scope, explicit terminal-dispatch rejection, diff, wheel/application, and both verifier modes.
- Independent closeout review is approved with no Critical or Important findings.

## Reopening rule

There is no implementation next action. Before any new autonomous work, add an
approved work package to `docs/status/WORKLIST.md`, change its status to
`in_progress`, change lifecycle to `active`, update this marker and CURRENT,
and run `python3 tools/project_scope_check.py`. Do not reuse AF-250 as a generic
maintenance anchor.

## Ruled-out paths

- Do not infer completion from worklist status alone; use the verification guide and executable evidence.
- Do not rerun a full dataset merely to reconfirm bounded migration acceptance.
- Do not modify the external `pi/` checkout or persist credentials, provider bodies, corpora, or private evidence paths.
- Do not make `src/dci` and Asterion import or launch one another.

## Ready commands

```bash
python3 tools/project_scope_check.py
uv run python tools/verify_asterion_dci_product.py
uv run python tools/verify_asterion_dci_product.py \
  --acceptance-root "$AF250_ACCEPTANCE_ROOT" \
  --validate-only
uv run python -m unittest discover -v
git status --short
```
