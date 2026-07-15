# AF-270 Design Checkpoint

> Updated: 2026-07-15 08:42 +0800. The completed DCI migration remains accepted; AF-270 is a product-usability successor.

Active work package: AF-270

## TL;DR

- AF-250 migration remains completed and verified; repository lifecycle is reopened only for AF-270.
- Asterion DCI independently implements the original Pi-based DCI product surface without importing or launching `src/dci`.
- Acceptance covers eight model-free rows, 533 delegated selectors, twelve launcher pairs, six batch extras, an isolated installed wheel/application, and seven bounded real source/Asterion/application/Pi-plus-Judge/reuse cases.
- The approved AF-270 design adds generic `asterion describe/verify` discovery and four DCI verification levels.
- No full dataset ran; full-dataset performance is separate operator-authorized work, not a migration gap.

## Committed state

- Product implementation and acceptance: `327a070`.
- Accepted recovery checkpoint: `41de2db`.
- Terminal lifecycle design and plan: `6d42ebf`, `3345aa2`.
- Explicit lifecycle governance: `3717c63`.
- Full functional verification guide: `673ac03`.
- Terminal hardening and main integration: `2994db0`.

The current branch is `main`. The newest commit after these entries is the
AF-270 design/governance checkpoint; inspect `git log --oneline -8` rather than
relying on chat history.

## Verified evidence

- Public product verifier: 8/8 rows, 533/533 delegated selectors, 12/12 launcher pairs, 6/6 batch extras, bounded acceptance 7/7, zero provider execution during verification.
- Retained native evidence: private acceptance 7/7 after digest, mode, lifecycle, Judge, exact-reuse, mtime, and credential-value checks.
- Final terminal closure: 1275 Python, 11 TypeScript, and 19 Rust tests plus compile, Ruff, shell, scope, explicit terminal-dispatch rejection, diff, wheel/application, and both verifier modes.
- Independent closeout review is approved with no Critical or Important findings.

## Next action

After written-spec approval, create the AF-270 implementation plan and execute
it with TDD. Do not change accepted AF-250 evidence or run a full dataset.

## Ruled-out paths

- Do not infer completion from worklist status alone; use the verification guide and executable evidence.
- Do not rerun a full dataset merely to reconfirm bounded migration acceptance.
- Do not modify the external `pi/` checkout or persist credentials, provider bodies, corpora, or private evidence paths.
- Do not make `src/dci` and Asterion import or launch one another.

## Ready commands

```bash
python3 tools/project_scope_check.py
sed -n '1,260p' docs/superpowers/specs/2026-07-15-asterion-capability-discovery-verification-design.md
uv run python tools/verify_asterion_dci_product.py
uv run python tools/verify_asterion_dci_product.py \
  --acceptance-root "$AF250_ACCEPTANCE_ROOT" \
  --validate-only
uv run python -m unittest discover -v
git status --short
```
