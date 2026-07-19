# Live Session Checkpoint

> Updated: 2026-07-19 12:24 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

## TL;DR

- AF-340 已完成一轮交付：`verify_original_readme.py` 与 `tests/test_original_readme_acceptance.py` 已提交，完成
  README 契约与 launcher 合约的可验证钩子。
- Added `tests/test_original_readme_acceptance.py` to enforce literal README commands and bounded entry-point command shape.
- Updated launcher tests to match current contract (`source "$REPO_ROOT/.env"` is no longer expected in generated launcher scripts).
- AF-340 Task5 已落地：统一 source 与 Asterion 的 11 套 benchmark launcher 为薄封装，去除硬编码 provider/model 与脚本内 `.env` 注入，同时同步 `README` 与 Asterion 指南示例。
- Local 复现与 launcher/文档契约回归全部通过：`tools/verify_original_readme.py --level local` 与 `test_asterion_dci_*` 套件。

## Where things stand

- Project route: managed.
- Lifecycle: active.
- Active package: AF-340.
- Work in-flight: continue AF-340 Task6（immutable experiment profile 与显式 `--authorize-full` 门控）的实现与 Task8 协调器准备。
- Confirmed:
  - `python3 tools/project_scope_check.py` (AF-340 active, scope clean).
  - `uv run python -m unittest -v tests.test_original_readme_acceptance tests.test_asterion_dci_batch_launchers tests.test_asterion_dci_product_parity tests.test_asterion_documentation` (121 tests, all pass).
  - `python3 tools/verify_original_readme.py --level local` passes (`Agent operations: 0`, `Judge operations: 0`, `Full dataset ran: no`).
  - `ruff check` on touched files and `python3 -m py_compile` for touched files pass.
  - `git diff --check` clean.
- Bounded execution in this environment is currently blocked by provider quota from `tools/verify_original_readme.py --level bounded` (`Codex error: The usage limit has been reached`), so no new bounded report was produced in this session.
- External `pi/` remains untouched; credentials were not printed.

## Next action

1. Continue `AF-340` Task6（immutable profile/授权）与 Task8（统一协调器）实现，并保持 bounded/full 与授权解耦。
2. 确认并推动 commit `6385d58` 已纳入流水线后，继续 `AF-340` 的有界验证与全量授权门前置准备。
3. 若后续配额可用，执行有界复现：
   `python3 tools/verify_original_readme.py --level bounded --env-file .env --output-root /tmp/verify-readme-run`。
3. Keep all future evidence updates in `JOURNAL` and keep unrelated working tree files untouched.

## Ready command

```bash
git diff --cached -- tools/verify_original_readme.py tests/test_original_readme_acceptance.py tests/test_asterion_dci_batch_launchers.py tests/test_asterion_dci_product_parity.py tests/test_asterion_documentation.py
```
