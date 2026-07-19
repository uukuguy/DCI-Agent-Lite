# Live Session Checkpoint

> Updated: 2026-07-19 11:22 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

## TL;DR

- AF-340 已完成一轮交付：`verify_original_readme.py` 与 `tests/test_original_readme_acceptance.py` 已提交，完成
  README 契约与 launcher 合约的可验证钩子。
- Added `tests/test_original_readme_acceptance.py` to enforce literal README commands and bounded entry-point command shape.
- Updated launcher tests to match current contract (`source "$REPO_ROOT/.env"` is no longer expected in generated launcher scripts).

## Where things stand

- Project route: managed.
- Lifecycle: active.
- Active package: AF-340.
- Work in-flight: README reproduction path hardening and one-cycle bounded verification wiring.
- Confirmed:
  - `python3 tools/project_scope_check.py` (AF-340 active, scope clean).
  - `uv run python -m unittest -v tests.test_original_readme_acceptance tests.test_asterion_dci_batch_launchers tests.test_asterion_documentation tests.test_asterion_dci_product_parity` (121 tests, all pass).
  - `ruff check` on touched files and `python3 -m py_compile` for touched files pass.
  - `git diff --check` clean.
- Bounded execution in this environment is currently blocked by provider quota from `tools/verify_original_readme.py --level bounded` (`Codex error: The usage limit has been reached`), so no new bounded report was produced in this session.
- External `pi/` remains untouched; credentials were not printed.

## Next action

1. Confirm commit `d2a873c` has been pushed/checked in and continue `AF-340` proofing on quota-valid run tokens.
2. If user authorizes a quota-valid bounded run, execute:
   `python3 tools/verify_original_readme.py --level bounded --env-file .env --output-root /tmp/verify-readme-run`.
3. Keep all future evidence updates in `JOURNAL` and keep unrelated working tree files untouched.

## Ready command

```bash
git diff --cached -- tools/verify_original_readme.py tests/test_original_readme_acceptance.py tests/test_asterion_dci_batch_launchers.py
```
