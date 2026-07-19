# Live Session Checkpoint

> Updated: 2026-07-19 20:20 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

Package: README reproduction and runtime-result parity

Currently running: no repository-owned process.

## TL;DR

- AF-340 当前收口到 judge/运行时层级收敛点：保持 `CLI > .env/process > runtime defaults`，并明确 `--runtime` 可选；`DCI_RUNTIME` 与 `DCI_PROVIDER`/`DCI_MODEL` 通过统一解析链进入 `resolve_original_runtime` / `resolve_dci_runtime_options`。
- Judge 统一契约稳定为 DeepSeek V4 Flash（`DEEPSEEK_API_KEY`，`deepseek-v4-flash`，`chat-completions`，定价字段默认 0），源端与 Asterion judge 指纹都已剔除密钥名字段影响。
- 本轮已修复 `test_parse_args_preserves_runtime_defaults_for_layered_resolution` 的层次边界问题，并把 Asterion/源 product parity 中 judge 请求 token 字段断言按 API 形状（responses/chat）自适应。
- 已跑通过关键回归：`tests.test_judge`、`tests.test_asterion_dci_judge`、`tests.test_check_judge`、`tests.test_asterion_dci_product_parity`（109 tests），以及 `py_compile`、`ruff`、`project_scope_check.py`。

## Where things stand

- Project route: managed.
- Lifecycle: active.
- Active package: AF-340.
- Dependencies: AF-330 completed.
- Bounded AF-340 provider-backed 复现实验已通过（未 full dataset），流程中的 `.env` 及进程环境优先级已显式对齐。
- 外部 `pi/` 保持外部仓库不变；`.env` 凭据未读取或打印。
- 工作包当前聚焦：AF-340 的剩余是补齐 README/bench 场景的授权式执行边界证据，当前 judge 与层级解析契约已收口完备。

## Next action

1. 继续补齐 AF-340 剩余 README-labeled 路径的运行时分支验证（以 `--runtime=pi` 与 `--runtime=claude-code` 为主），仍限制不做 full dataset，除非用户显式授权。
2. 将每一段验证边界与哈希补充到 `docs/status/JOURNAL.md`，并保持工作树只含 AF-340 计划内改动。
3. 继续维持 `project_scope_check.py` + `py_compile` + `ruff` + 关键回归测试的每轮闭环。
4. 若用户再次授权 full 执行，则保留当前签名和证据不变，单独进行成本核算后的全量验证与复核。

## Accepted boundaries

- `.env` and CLI are complementary layers, not alternate modes.
- `DCI_PROVIDER`/`DCI_MODEL` are common public fields interpreted by the selected runtime.
- Original DCI supports Pi only; Asterion supports Pi and Claude Code.
- Agent and Judge roles remain independently configured and credentialed.
- Local, bounded, and full verification are distinct evidence classes.
- Full comparison retains per-query evidence and versioned non-inferiority/confidence criteria.

## Ruled-out paths

- Do not create runtime-specific public provider variable families.
- Do not apply Pi provider compatibility or defaults to Claude Code.
- Do not substitute internal fixtures for the literal README user paths.
- Do not claim full or comparable results from bounded `--limit 1` evidence.
- Do not make Asterion import or launch original DCI to manufacture parity.
- Do not let `.env`, generic verification, or cache presence authorize full-dataset cost.
- Keep `AF-340 Task` evidence aligned to scoped runtime-contract assertions before any full comparison.

- 最新验证边界文件：
  - `/Users/sujiangwen/sandbox/agentic-2026/DCI-Agent-Lite/.worktrees/af-340-implementation/outputs/verification/af340-bounded-claude-minimax-r6/af340-bounded-report.json`（pass，agent 2，judge 2，no full）
  - 本次回合：`tests.test_judge`、`tests.test_asterion_dci_judge`、`tests.test_check_judge`、`tests.test_asterion_dci_product_parity`（109 tests，全部通过）

## Ready command

```bash
python3 tools/project_scope_check.py
```
