# Journal — append-only event log

> One line per commit / verified result / dropped path. Never edit past lines.
> Format: `## YYYY-MM-DD` date headers, then `- HH:MM <fact> [commit hash if any]`

## 2026-07-12
- 05:23 建立本地 `AGENTS.md`，`CLAUDE.md` 软链接共享项目指令。
- 05:30 `.env` 驱动示例与 Make targets 已整理提交 [2f9f271]
- 05:30 初始化 repo-native project-state 三文件体系。
- 05:30 project-state 核心文件已纳入版本管理。
- 05:57 RPC 加固通过 20 项单测及 runtime-example，DeepSeek judge 判定正确。
- 06:02 固化快速 handoff 协议与分级 MEMORY 索引；resume 可按统一入口恢复。
- 06:05 judge 环境配置与 DeepSeek 兼容修复已提交。[ac78808, 9844dc8]
- 06:05 RPC 生命周期加固及 20 项回归测试已提交。[cd33679]
- 06:05 快速 handoff 协议与分级 MEMORY 已提交。[829787e]
- 06:05 当前判断：保留 Python+RPC；TS sidecar 仅在触发条件出现时复议。
- 06:05 handoff 边界完成；无残留进程，临时计划清理，恢复入口同步。
- 07:29 已安装跨 Codex/Claude checkpoint 策略；canonical skill 与事件提醒验证通过。
- 07:34 漏交接恢复改为 recovery checkpoint；非 GSD 仓库跳过 GSD 启动 hook。
- 07:54 自动 checkpoint 工作流完成；正式 handoff 开始同步 Git、状态与协作记忆。
- 08:19 Pi 精确 revision lock 设计完成，避免 moving-main 漂移。[db62f20]
- 08:23 测试优先实施计划完成，覆盖安全 checkout 与 climb 验证。[d6ae990]
- 08:27 DCI climb adapter 已建立；research-tree 生成回归通过。[63531e4]
- 08:29 active climb 恢复边界已 checkpoint，H-001 测试优先继续。[e65da92]
- 08:31 Pi lock checkout state machine 六项集成回归通过。[27a68a6]
- 08:32 Pi lock 配置、升级文档与 D-003 决策同步完成。[2049c3b]
- 08:40 H-001 climb train/eval/record/sync adapter 回归完成。[79e91cb]
- 08:40 H-001 confirmed 4/4; setup-policy acceptance recorded.
- 08:44 H-001 全量 31 tests + runtime-example 正确；外部 Pi 状态未变。
- 08:45 H-001 4/4 evidence 与可移植 climb state 已提交。[c9f60c7]
- 08:53 H-002 read-only gate 4/4；35 tests 通过，真实 Pi 状态未变。
- 08:54 H-002 read-only pin verification 已提交并推进 H-003。[862a51e]
- 09:28 H-003 model-free RPC probe 4/4；40 tests 与真实 handshake 通过。
- 09:29 H-003 RPC compatibility preflight 已提交；pool 进入 Knowledge Layer。[e53822f]
- 09:31 Knowledge Layer 生成 H-004/005/006；优先补齐 run-level Pi provenance。
- 08:51 H-002 confirmed 4/4; setup-policy acceptance recorded.
- 09:28 H-003 confirmed 4/4; setup-policy acceptance recorded.
- 16:04 H-004 confirmed 4/4; setup-policy acceptance recorded.
- 16:04 H-004 confirmed 4/4; setup-policy acceptance recorded.
- 16:06 correction: H-004 第二条为同 run replay；未提交结构化重复已归一化，recorder 现幂等。
- 16:08 H-004 provenance 4/4；45 tests 与真实 runtime artifact 断言通过。
- 16:09 H-004 run provenance 与幂等 climb recorder 已提交。[09d677d]
- 16:12 H-005 pre-run mismatch warning 4/4；48 tests 全通过。
- 16:13 H-005 non-blocking revision warning 已提交并推进 H-006。[b5b29b8]
- 16:11 H-005 confirmed 4/4; setup-policy acceptance recorded.
- 16:15 context hard pause：H-001..H-005 均 4/4；H-006 judge preflight 为唯一续点。
- 16:16 live checkpoint 已提交；fresh session 直接从 H-006 RED 继续。[ed600cd]
- 16:18 handoff 边界已核验：无残留进程，H-006 明确为 pending；临时计划已清理，外部 dirty `pi/` 保持排除，状态与协作记忆可从 `project-state resume` 恢复。
- 16:18 final handoff baton 已提交，固化 H-006 续点与恢复边界。[9f335ec]
- 16:29 resume detected final Journal boundary after baton; recovery checkpoint restored H-006 as the active continuation.
- 16:35 H-006 design accepted: one explicit judge preflight reusing the existing transport; no automatic batch gate.
- 16:40 H-006 implementation plan locks test-first CLI, explicit Make target, documentation, and deterministic climb acceptance.
- 17:07 H-006 local contract 4/4; 56 tests, Ruff, compile, Bash syntax, and Pi RPC probe passed before live preflight.
- 17:09 H-006 live request reached DeepSeek but 401 rejected configured key; provider bodies are now redacted. Await credential rotation.
- 17:10 repeated live preflight confirms the 401 is safely redacted; H-006 remains pending on credential rotation.
- 17:16 user-requested retry again reached DeepSeek and returned redacted HTTP 401; credential remains invalid.
