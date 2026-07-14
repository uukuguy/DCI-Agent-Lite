# Live Session Checkpoint

> Updated: 2026-07-15 06:38 +0800. **Session remains active — not a final handoff.** AF-250 migration implementation and acceptance are complete in the isolated `af-220-shared-dci-config` worktree.

Active work package: AF-250

## TL;DR

- AF-250 accepted implementation is committed at `327a070` on `af-220-shared-dci-config`.
- AF-250 implementation and bounded product acceptance are complete: eight product rows, 533 delegated selectors, twelve launcher pairs, six batch extras, isolated installed-wheel/application proof, and seven real source/Asterion/application/Pi-plus-Judge/reuse cases pass.
- The earlier real-run failures were caused by the isolated worktree lacking the external main-repository `corpus/`, not by a missing Asterion DCI behavior. Explicit shared Pi/corpus paths plus the repository-root `.env` produced successful bounded runs.
- `assets/dci/product-acceptance.json` contains only commands, inherited variable names, exit codes, modes, hashes, counts, verdict booleans, and timestamps. Credential values matched zero; provider bodies and private paths are excluded. A caller-owned private acceptance root retains all seven native cases for digest/mode/semantic revalidation.
- The product matrix digest-binds that seven-case manifest. AF-250-H-005 was reconfirmed 4/4 with private-native mutation coverage in cycle 85 after its initial cycle 84, following H-001 through H-004 in cycles 80–83.

## Verification

- `uv run python tools/verify_asterion_dci_product.py`: 8/8 rows, 533/533 delegated, 12/12 launchers, 6/6 batch extras, 7/7 bounded acceptance, zero provider execution during verification.
- With the shared `.env` exported, `--acceptance-root "$AF250_ACCEPTANCE_ROOT" --validate-only` reports private acceptance 7/7 after rehashing artifacts, parsing lifecycle/Judge evidence, comparing reuse mtimes, and scanning actual credential values without printing them.
- Full discovery passes 1266/1266 Python tests; TypeScript passes 11/11 and Rust passes 19/19.
- Compile, Ruff, shell syntax, scope, Rust fmt/Clippy, installed wheel/application proof, and diff checks pass.

## Next action

Commit the cohesive AF-250 recovery/acceptance changes after independent review. Keep AF-250 as the terminal active governance anchor until branch integration or a successor package is explicitly selected.

## Ruled-out paths

- Do not treat the former worktree-local missing `corpus/` condition as a product failure.
- Do not rerun full datasets to reconfirm bounded acceptance.
- Do not modify `pi/`, persist credentials, or copy provider bodies/private paths into public evidence.

## Ready commands

```bash
python3 tools/project_scope_check.py
uv run python tools/verify_asterion_dci_product.py
uv run python tools/verify_asterion_dci_product.py --acceptance-root "$AF250_ACCEPTANCE_ROOT" --validate-only
uv run python -m unittest tests.test_asterion_dci_product_acceptance -v
git status --short
```
