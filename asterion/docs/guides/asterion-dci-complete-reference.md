# Asterion DCI 完整产品参考

本文描述 Asterion 自己实现并随 `asterion` wheel 发布的 DCI 产品。它面向两类读者：需要运行研究和 benchmark 的使用者，以及需要判断迁移完整性的维护者。入门只需阅读[能力包使用指南](asterion-capability-usage.md)；逐项验收见[完整功能验证指南](../verification/asterion-dci-validation-guide.md)。

Asterion DCI 与 mixed-repository dependency [`src/dci`](../../../src/dci/) 共用混合仓库根目录 `.env` 和外部 Pi，但生产代码不导入、启动或打包该原始 DCI 基线。权威领域实现位于 [`asterion/dci`](../../src/asterion/dci/)。

## 证据状态说明

本文统一使用四种状态，避免把“有代码”“通过测试”和“跑过昂贵实验”混为一谈：

| 状态 | 含义 |
|---|---|
| **Implemented** | 权威 Asterion 模块中存在生产实现。 |
| **Verified** | 测试、模型外验收或有界真实运行直接证明了该行为。 |
| **External-limited** | Asterion 保留了配置、状态或扩展边界，但当前外部依赖没有暴露所需能力。 |
| **Not rerun** | 功能实现和模型外等价性存在，但迁移收尾没有重跑完整昂贵实验或复现历史数值。 |

`provider-backed operations` 表示 Asterion 调度的 Pi 运行或 Judge 评测操作数，不等于底层模型 API 请求数；一次多轮 Pi 运行可以产生多个模型请求。

## 配置与依赖

### 必需组件

- Python 3.10 或更高版本以及 `uv`；
- Node.js 20 或更高版本；
- 外部 Pi checkout，缺省为 `./pi`，可通过 `DCI_PI_DIR` 指定；
- Pi provider、model 及认证；
- 运行所需的本地 corpus；
- 使用 Judge 时的 Judge endpoint、model 和密钥变量。

正常配置面是仓库根目录 `.env`。源码 DCI 与 Asterion DCI 共用 `DCI_*` 设置，显式 CLI 参数优先于环境变量。Asterion 特有的输出位置使用 `ASTERION_DCI_OUTPUT_ROOT`，缺省为 `outputs/asterion-dci-runs`。

常用变量：

```dotenv
DCI_PROVIDER=openai
DCI_MODEL=<MODEL>
DCI_PI_DIR=./pi
DCI_TOOLS=read,bash
DCI_PI_THINKING_LEVEL=high
DCI_EVAL_JUDGE_MODEL=<JUDGE_MODEL>
DCI_EVAL_JUDGE_API_KEY_ENV=OPENAI_API_KEY
OPENAI_API_KEY=<SECRET>
```

认证值不会进入产品描述、公开错误或 body-free 应用结果。通过 Pi 保存到 `.pi/agent/auth.json` 的受管认证也可被 preflight 识别。

配置解析见 [`config.py`](../../src/asterion/dci/config.py)，Pi 进程/RPC 边界见 [`pi_rpc.py`](../../src/asterion/dci/pi_rpc.py)。

## 单次研究、终端与系统提示词

### `run`：有产物的研究运行

```bash
asterion-dci run \
  --cwd "$PWD/corpus/wiki_corpus" \
  --provider openai \
  --model gpt-5.4-nano \
  --tools read,bash \
  --thinking-level high \
  --max-turns 20 \
  "Answer using only the local corpus."
```

问题也可以来自 `--question-file`。`--system-prompt-file` 替换系统提示词，`--append-system-prompt-file` 追加内容；`--show-tools` 输出安全工具进度；`--keep-session` 保留 Pi session；`--node-max-old-space-size-mb` 控制 Node heap；重复的 `--extra-arg` 原样作为 argv 交给 Pi，不经过 shell 解释。

运行请求校验、Pi 调用和恢复逻辑见 [`run.py`](../../src/asterion/dci/run.py)。

### `terminal`：直接 TTY

```bash
asterion-dci terminal \
  --cwd "$PWD/corpus/wiki_corpus" \
  --provider openai \
  --model gpt-5.4-nano \
  "Research the question interactively."
```

`terminal` 要求 stdin/stdout 都是 TTY，直接启动 Pi，返回子进程退出码，保留 Pi 自己的 session，但不创建 Asterion RPC 运行目录。它没有 resume、Judge、输出目录或 conversation artifact 处理选项。

### `system-prompt`：检查最终提示词

```bash
asterion-dci system-prompt \
  --system-prompt-file prompts/system_prompt.txt \
  --append-system-prompt-file prompts/local-rules.txt
```

这个入口用于生成或检查 Asterion 将交给 Pi 的提示词，不发送模型请求。

## 原生产物、隐私与恢复

一次 `run` 的私有目录包含：

```text
run-directory/
├── question.txt
├── events.jsonl
├── state.json
├── conversation_full.json
├── conversation.json
├── latest_model_context.json
├── tool_results/
├── final.txt
├── stderr.txt
├── provenance.json
└── protocol/
    └── attempt-*/
```

- `conversation_full.json` 保存完整证据；`conversation.json` 是按选择的保存策略处理后的视图。
- `latest_model_context.json` 记录最近一次 Pi 报告的模型上下文元数据，不伪造外部运行时未提供的字段。
- `protocol/attempt-*` 隔离初次运行与恢复尝试。
- 运行目录使用 descriptor-relative 原子写入、私有权限和单写者锁；路径重绑定、symlink 和并发 writer 会失败关闭。
- provenance 只保存安全的 Pi revision/origin 事实，不保存 URL credential、Git diff、环境值或任意额外参数内容。

产物实现和验证位于 [`artifacts.py`](../../src/asterion/dci/artifacts.py) 与 `provenance.py`。

恢复失败或未完成运行：

```bash
asterion-dci resume --output-dir path/to/run-directory
```

恢复从 `state.json` 重建不可变请求，拒绝已完成、损坏或不兼容的运行，并创建新的 protocol attempt。启用 profile 的首次运行若使用 `--keep-session`，恢复会校验并复用 original Pi session 的 file、ID 和 entry cursor；任一不匹配都会在 provider 请求前失败。

## Context Management：两个不同层次

“Context Management”在本项目中有两个不同含义，必须分开理解。

### 1. Pi 模型输入前的运行时策略

Asterion 通过 Asterion-owned Pi extension 实现闭合的 `dci.context-profile/v1`，它在 provider 请求前改变 live model context：

| Profile | 精确行为 |
|---|---|
| `level0` | 不转换上下文。 |
| `level1` | 每个 tool result 上限 50,000 字符。 |
| `level2` | 每个 tool result 上限 20,000 字符。 |
| `level3` | 使用 20,000 字符上限；累计 original tool characters 超过 240,000 后 compact，并保留最新 12 complete turns。 |
| `level4` | 继承 level3，以 20,000 recent tokens 为 summarization 目标；3 consecutive summary failures 后停止继续 summary，但保留 level3 compaction。 |

`asterion-dci run`、benchmark、resume、安装应用和 wheel 都解析同一个 profile identity 与 extension digest。未知值、保留 transport flag、损坏 extension、profile/阈值/digest/session 不匹配都会在 provider 请求前失败。

私有 `state.json` 的 `runtime_context_control` 保存这份不可变策略 identity；公开应用结果只投影 body-free 版本、计数器、extension digest 和 opaque artifact reference。

证据层严格分为 **Implemented**、**Model-free verified**、**Bounded provider verified** 和 **Experiment reproduced**。当前实现与模型外测试属于前两层；有界 L3/L4 证据由 `tools/verify_dci_context_acceptance.py --provider-backed` 单独生成；完整论文复现仍属于 AF-340，Full dataset ran: no。

### 2. 已保存 conversation artifact 的处理

这一层是 post-run conversation processing，不改变模型已经看到的历史，只控制 `conversation.json` 的保存视图；`conversation_full.json` 始终保留完整证据：

| 参数 | 行为 |
|---|---|
| `--conversation-clear-tool-results` | 将较旧 tool result body 替换为统计和占位信息。 |
| `--conversation-clear-tool-results-keep-last N` | 保留最后 N 个 tool result body，缺省为 3。 |
| `--conversation-externalize-tool-results` | 把完整 tool result 写入私有 `tool_results/`，conversation 保存相对引用和统计。 |
| `--conversation-strip-thinking` | 从处理后的保存视图移除 thinking。 |
| `--conversation-strip-usage` | 从处理后的保存视图移除 usage。 |

这些保存策略是 **Implemented** 且经过 artifact、resume、evaluation 和 batch mutation tests **Verified**。

## Judge、评测与精确缓存

运行时直接评测：

```bash
asterion-dci run \
  --cwd "$PWD/corpus/bc_plus_docs" \
  --eval-answer "Adaku" \
  "Answer the local-corpus question."
```

评测已有运行：

```bash
asterion-dci evaluate \
  --output-dir path/to/run-directory \
  --gold-answer "Adaku"
```

Judge transport支持 Responses 或 Chat Completions、超时、JSON mode、strict schema、thinking 控制、`store` 控制和成本字段。公开异常不回显 endpoint response body、密钥或答案正文。

精确缓存 identity 绑定最终回答证据与所有影响请求的 Judge 配置；model、API 类型、schema/store/thinking、token limit 或其他 request-shaping 字段变化都会失效缓存。实现见 [`evaluation.py`](../../src/asterion/dci/evaluation.py) 和 `judge.py`。

状态：Judge shaping、boolean verdict、安全 transport 和精确缓存为 **Implemented**；模型外 mutation tests 与有界 Judge 运行均为 **Verified**。

## Benchmark DCI-Agent-Lite

统一入口：

```bash
asterion-dci benchmark \
  --profile qa.hotpotqa \
  --limit 1
```

[`benchmark.py`](../../src/asterion/dci/benchmark.py) 提供：

- QA 与 IR 两种模式；
- JSONL dataset 加载和确定性选择；
- 并发 worker、max turns、timeout 和 cancellation；
- `compatible`、`fresh`、`reuse` 恢复/复用策略；
- 每题独立原生运行目录；
- QA Judge 与 IR ranking metric；
- 已完成运行和 Judge 结果的精确复用；
- batch state、results、summary、analysis 和 figures 的原子发布；
- 可选的论文口径 trajectory resolution：每题 coverage（any/mean/all）、
  surfaced-gold localization、最终模型上下文 retained coverage；
- 失败、取消和部分结果的真实状态，不把不可用值伪造成 0。

要启用 resolution 分析，benchmark 必须同时提供语料根、完整 registry 和正整数
segment 宽度，并保持 tool-result externalization 开启：

```bash
asterion-dci benchmark \
  --dataset dataset.jsonl \
  --corpus corpus \
  --output-root outputs/eval \
  --resolution-registry gold/registry.json \
  --resolution-segment-characters 20000 \
  --conversation-externalize-tool-results
```

registry 使用闭合的 `dci.gold-document-registry/v1` schema，声明唯一
`dataset_id`，并为本次选中的每个 `query_id` 精确列出 manifest 相对路径和
SHA-256。所有 manifest 的 dataset identity 必须与 registry 相同。manifest 使用
`dci.gold-document-manifest/v1`，记录 dataset/query identity，以及相对语料根的
gold document 路径、SHA-256 和半开区间 evidence spans。缺项、额外字段、符号链接、
digest/identity 不匹配或 IR gold IDs 不一致都会在 provider 启动前失败。

每个完成题目的完整对齐证据保存在该题原生运行目录的私有
`trajectory-resolution.json`；`summary.json`、`analysis.json[l]`、Markdown 和
`analysis_figures/resolution_metrics.png` 仅接收经过严格校验的 body-free 汇总。
segment、registry/manifest、语料、原生轨迹、最终上下文或对齐策略变化都会改变
identity 或使旧证据失效。这里的“论文口径”指指标定义和可执行证据链已经实现，
不代表完整数据集或论文历史分数已经重跑。

安装包内的完整 paper identity 可直接检查，不读取当前目录中的同名文件：

```bash
asterion-dci paper describe
asterion-dci paper verify
asterion-dci ablation validate
asterion-dci ablation list --execution-class paper-full
asterion-dci ablation list --execution-class bounded-fixture
```

`paper describe` 用 body-free JSON 同时绑定 13 个 dataset、16 个实验 scope、
20 个 ablation row、L0–L4、BEIR profiles、resolution 配置/指标和三份 canonical
resource digest。十个 `paper-full` row 只能 list/validate/render；AF-320 不存在
执行它们的 override。论文没有公开 FineWeb revision、seed、selection algorithm、
selected IDs 或 manifest digest，因此这些字段保持 `paper-unreported`/null。

十个 bounded analogue 每次只能显式选择一行，例如：

```bash
asterion-dci ablation render bounded.tools.read-grep
asterion-dci benchmark \
  --ablation-row bounded.tools.read-grep \
  --output-root outputs/asterion-dci-ablation/bounded.tools.read-grep
```

该行从安装包解析哈希校验过的 tiny dataset/corpus，固定 `level4`、8 turns 和
literal `read,grep`，并强制 externalized tool results；provider/model 仍必须由
正常 CLI 或 `.env` 授权，矩阵不携带隐藏默认值。任何同时给出的 dataset、corpus、
profile、mode、limit、tools、context 或 resolution override 都会在读取 provider
配置前失败。三个 corpus analogue 分别位于独立的 base、base+1、base+2 安装资源
目录，不会把未选 distractor 暴露给 agent。

`paper verify` 缺省只验证安装资源、identity、矩阵与三操作 cost contract，输出
`Agent operations: 0`、`Judge operations: 0` 和 `Full dataset ran: no`。只有显式
传入 `--provider-backed --env-file PRIVATE_ENV --output-root PRIVATE_DIR` 才会执行
固定的 `QA agent → configured Judge → IR agent`；preflight 要求私有配置、空的
0700 output root、与 `pi-revision.txt` 一致且 clean 的外部 Pi checkout。成功报告
为 0600、body-free，并绑定实际 Judge 的 endpoint、API、model、安全 request-shaping
字段和 prompt-contract digest，以及两个 agent operation、一个 Judge operation、安装资源和
私有 artifact digests。agent 多轮内部 API request 数仍标为 externally ambiguous，
不会伪称三个 operation 等于三个底层 HTTP request。binder 会重新哈希全部引用产物
并再次检查 clean runtime；任何 symlink、权限、digest、runtime 或既有 binding 冲突
都在不修改 Climb 状态的情况下失败。GPT-4.1 是论文实验 provenance；只有 AF-340
声称论文分数可比时才要求该实验配置。完整数据集和论文分数复现仍属于 AF-340。

完整实现的模型外验收包括 537/537 个细粒度 selector、6/6 个额外 batch 语义和 12/12 个原始/Asterion launcher 对。迁移期间还运行过一条有界 Pi+Judge batch 及精确 reuse 证明；AF-320 的三操作 terminal evidence 只有在上述 verifier 成功且 binder 重哈希后才可标记为 bounded provider verified。

但 AF-290 没有重新运行完整 benchmark 数据集，也没有重新复现 62.9% 或 README 中其他历史分数。这些分数属于原始 DCI 的历史实验结果，当前状态为 **Not rerun**，不能由 537 个模型外 selector 推导出来。

## 数据集、Profile 与 Launcher

Bundled profile 定义在 `asterion/dci/resources/batch-profiles.json`：

绑定 AF-320 `paper-full` inventory 的 profile，其未修改命令仍会在读取数据或
启动 provider 前失败关闭，并且只能由 AF-340 的显式 full authorization 执行。
AF-340 另行开放精确整数 `--limit 1` 的有界 successor gate：系统先验证未截断
数据与 profile 绑定的完整 paper scope 完全一致，再只执行一行；配置证据固定记录
versioned `paper-bounded` execution class、`limit-1`、`full_dataset: false` 和
`comparable: false`。授权完整运行记录独立的 `paper-full-authorized` class；其他
运行显式记录 `non-paper`，因此删除或跨 class 改写 selection 不能形成有效证据。
省略 limit、使用布尔值或使用大于 1 的 limit 都不能进入该 gate。
`qa.bamboogle` 仍是未绑定的 sample-50 迁移 profile，不能代表论文的 Bamboogle
full-125 scope。

| Profile | 模式 | 数据/语料 |
|---|---|---|
| `bcplus.level3` | QA | BrowseComp-Plus / `corpus/bc_plus_docs` |
| `bcplus.openai` | QA | BrowseComp-Plus / `corpus/bc_plus_docs` |
| `qa.2wikimultihopqa` | QA | 2WikiMultiHopQA / Wikipedia-18 |
| `qa.bamboogle` | QA | Bamboogle / Wikipedia-18 |
| `qa.hotpotqa` | QA | HotpotQA / Wikipedia-18 |
| `qa.musique` | QA | MuSiQue / Wikipedia-18 |
| `qa.nq` | QA | Natural Questions / Wikipedia-18 |
| `qa.triviaqa` | QA | TriviaQA / Wikipedia-18 |
| `bright.biology` | IR | BRIGHT Biology |
| `bright.earth-science` | IR | BRIGHT Earth Science |
| `bright.economics` | IR | BRIGHT Economics |
| `bright.robotics` | IR | BRIGHT Robotics |
| `beir.arguana` | IR | BEIR ArguAna |
| `beir.scifact` | IR | BEIR SciFact |

11 个主要 launcher 是一一对应的独立产品入口；`run_L3.sh` 保留为兼容 helper，
不计入这 11 对：

| 实验 | 原始 DCI | Asterion DCI |
|---|---|---|
| BrowseComp-Plus | `scripts/bcplus_eval/run_bcplus_eval_openai.sh` | `asterion/scripts/bcplus_eval/run_bcplus_eval_openai.sh` |
| 2WikiMultiHopQA | `scripts/qa/run_2wikimultihopqa_dev_sample50.sh` | `asterion/scripts/qa/run_2wikimultihopqa_dev_sample50.sh` |
| Bamboogle | `scripts/qa/run_bamboogle_test_sample50.sh` | `asterion/scripts/qa/run_bamboogle_test_sample50.sh` |
| HotpotQA | `scripts/qa/run_hotpotqa_dev_sample50.sh` | `asterion/scripts/qa/run_hotpotqa_dev_sample50.sh` |
| MuSiQue | `scripts/qa/run_musique_dev_sample50.sh` | `asterion/scripts/qa/run_musique_dev_sample50.sh` |
| Natural Questions | `scripts/qa/run_nq_test_sample50.sh` | `asterion/scripts/qa/run_nq_test_sample50.sh` |
| TriviaQA | `scripts/qa/run_triviaqa_test_sample50.sh` | `asterion/scripts/qa/run_triviaqa_test_sample50.sh` |
| BRIGHT Biology | `scripts/bright/run_bio.sh` | `asterion/scripts/bright/run_bio.sh` |
| BRIGHT Earth Science | `scripts/bright/run_earth_science.sh` | `asterion/scripts/bright/run_earth_science.sh` |
| BRIGHT Economics | `scripts/bright/run_economics.sh` | `asterion/scripts/bright/run_economics.sh` |
| BRIGHT Robotics | `scripts/bright/run_robotics.sh` | `asterion/scripts/bright/run_robotics.sh` |

所有 22 个主要 wrapper 都把参数原样透传一次，由 Python 配置层非覆盖地读取
仓库 `.env`；wrapper 不 `source` `.env`，也不写死 provider/model。对应的 11 个
主要 Asterion batch profile 同样不携带 provider/model，因此不会把 profile 值提升为
invocation override；显式 CLI、已导出环境、`.env` 和 runtime default 的层次保持不变。
代表性有界命令：

```bash
bash scripts/bcplus_eval/run_bcplus_eval_openai.sh level3 high --limit 1
bash scripts/qa/run_hotpotqa_dev_sample50.sh --limit 1
bash scripts/bright/run_bio.sh --limit 1
bash asterion/scripts/bcplus_eval/run_bcplus_eval_openai.sh level3 high --limit 1
bash asterion/scripts/qa/run_hotpotqa_dev_sample50.sh --limit 1
bash asterion/scripts/bright/run_bio.sh --limit 1
```

不带 `--limit` 的命令是 full-dataset surface，不等于 full execution
authorization；`--limit 1` 也不能被称为完整结果。完整执行只能由 Task 8 的显式
verifier 授权：`uv run python tools/verify_af340_reproduction.py full ...
--authorize-full`。

### AF-340 reproduction coordinator

Run the complete provider-free matrix first:

```bash
uv run python tools/verify_af340_reproduction.py local
```

Each bounded command requires the repository environment file, a fresh output
root, and the resource tree used by the README examples. `--resource-root`
defaults to the code checkout, but worktree runs should set it explicitly to the
main/shared checkout; the environment-file parent is not guessed. Code executes
from the current checkout, while Quick Start and launcher sample inputs come
from the resource root. Pi checks the exact 11 launcher dataset/corpus pairs;
the Claude variants require only the wiki corpus. The retained plan and report
bind the exact selected-resource content manifest. Run the variants separately:

```bash
DCI_RESOURCE_ROOT=/absolute/path/to/main/DCI-Agent-Lite
uv run python tools/verify_af340_reproduction.py bounded --variant pi \
  --env-file .env --resource-root "$DCI_RESOURCE_ROOT" \
  --output-root outputs/verification/af340-bounded-pi
uv run python tools/verify_af340_reproduction.py bounded --variant claude-subscription \
  --env-file .env --resource-root "$DCI_RESOURCE_ROOT" \
  --output-root outputs/verification/af340-bounded-claude-subscription
uv run python tools/verify_af340_reproduction.py bounded --variant claude-minimax \
  --provider minimax --model MiniMax-M3 --env-file .env \
  --resource-root "$DCI_RESOURCE_ROOT" \
  --output-root outputs/verification/af340-bounded-claude-minimax
```

Inspect the three retained 0600 reports without contacting a provider; the
inspection passes only when original Pi, Asterion Pi, Claude subscription, and
Claude MiniMax form the exact four-dimensional evidence set. Inspection
rebuilds the exact selected dataset/corpus content manifest from the external
resource root, so coordinated report-hash rewrites and same-path input mutation
cannot satisfy the gate:

```bash
uv run python tools/verify_af340_reproduction.py inspect \
  --resource-root "$DCI_RESOURCE_ROOT" \
  --report outputs/verification/af340-bounded-pi/af340-bounded-report.json \
  --report outputs/verification/af340-bounded-claude-subscription/af340-bounded-report.json \
  --report outputs/verification/af340-bounded-claude-minimax/af340-bounded-report.json
```

The AF-340 H004 train/evaluation hooks require
`AF340_RESOURCE_ROOT="$DCI_RESOURCE_ROOT"` alongside the three retained-report
variables and forward that external anchor to `inspect`.

Print the immutable profile digest, selected-query counts, operation maxima, and
budget before requesting authority:

```bash
uv run python tools/verify_af340_reproduction.py full --profile current-default/pi \
  --output-root outputs/verification/af340-full-pi \
  --estimated-budget-usd 0 --dry-run
```

Actual full execution is a separate cost boundary and is never inferred from
`.env`, cache state, local checks, or bounded evidence. After reviewing the dry
plan and explicitly authorizing its named profile and budget, use:

```bash
uv run python tools/verify_af340_reproduction.py full --profile current-default/pi \
  --output-root outputs/verification/af340-full-pi \
  --estimated-budget-usd 0 --authorize-full
```

The coordinator writes one strict Task 7 manifest in each product/scope private
root and immediately performs the matched Pi or target-only Claude comparison.
Body-free comparison reports are retained under the full root's `comparisons/`
directory; no separate manual comparison command is required. Inspection
rehashes native bounded evidence and requires consumed Task 6 receipts plus
exact product/scope Task 7 manifest identities; report JSON alone cannot close
the gate.

Validate that the retained full report was explicitly authorized, covered every
profile scope, matched the exact operation maxima, and contains no rejected
comparison:

```bash
uv run python tools/verify_af340_reproduction.py inspect-full \
  --report outputs/verification/af340-full-pi/af340-full-report.json
```

To re-run one retained comparison explicitly, use the Task 7 ready command:

```bash
uv run --project asterion asterion-dci paper compare \
  --baseline path/to/original/af340-run-manifest.json \
  --candidate path/to/asterion/af340-run-manifest.json \
  --profile current-default/pi \
  --output path/to/private-comparison.json
```

Operator credentials live only in `.env` or exported environment variables;
full authorization is always an explicit CLI action. Reports contain hashes,
counts, safe identities, and status classes—not credentials, prompts, answers,
private paths, or child process bodies.


兼容 helper 是 `scripts/bcplus_eval/run_L3.sh` 与
`asterion/scripts/bcplus_eval/run_L3.sh`。

AF-320 另提供两个 paper-inventory launcher；它们没有原始/Asterion
一对一迁移计数声明。它们对应 `paper-full` scope，在 AF-320 会于 provider
启动前失败关闭；只有 AF-340 的独立授权才能执行：

```text
scripts/beir/benchmark_arguana.sh
scripts/beir/benchmark_scifact.sh
```

Profile 中的 `runtime_context_level=level3` 解析为完整 threshold identity，并与已安装 extension digest 一同进入 batch/run/row fingerprint；profile 或扩展变化会阻止跨策略复用。thinking、max turns、concurrency、dataset/corpus、mode 和 heap 等其余配置正常映射。

## 指标、分析、图表与导出

[`analysis.py`](../../src/asterion/dci/analysis.py) 与 `metrics.py` 生成：

- QA accuracy、correct/incorrect/failed counts；
- IR NDCG 与 ranking 统计；
- end-to-end、agent、tool、Judge 和批次时间；
- token、cache、工具类型及调用分布；
- percentile、slice、dataset/model/provider 分组；
- `summary.json`、`analysis.json`、`analysis.md`、JSONL 明细；
- runtime breakdown、metric distribution、scatter 和 tool summary 图表。

导出入口：

```bash
asterion-dci export bcplus --source-dir SOURCE --output-dir OUTPUT
asterion-dci export bright --source-root SOURCE --output-root OUTPUT
asterion-dci export bcplus-qa --parquet-dir SOURCE --output OUTPUT
asterion-dci export resolution \
  --run-dir RUN --attempt 1 --corpus-dir CORPUS \
  --gold-manifest GOLD.json --segment-characters 20000
```

[`export.py`](../../src/asterion/dci/export.py) 实现 BC+ 文档导出、BRIGHT corpus subset 导出、BC+ QA 提取/解密和 authoritative resolution reanalysis；最后一种只输出严格 body-free projection，不信任已保存的公共 summary。临时文件不会被当成成功输出，失败保持原目标不变。

状态：指标、分析、图表和三类导出为 **Implemented**，golden/mutation/integration tests 为 **Verified**；完整数据集最终图表和历史论文数值为 **Not rerun**。

## 安装应用与能力包入口

产品 CLI 适合直接使用 DCI 全功能：

```bash
asterion-dci run --help
asterion-dci benchmark --help
```

框架应用入口把研究能力装配进通用 Asterion application runner：

```bash
asterion run \
  --provider dci-agent-lite \
  --application dci.research-capability@1.0.0 \
  --runtime pi.reference \
  --run-id example-run \
  --input "Research the local corpus."
```

能力 manifests 位于 `asterion/capabilities/dci_research/manifests/`，应用 assemblies 和 provider 位于 `asterion/applications/dci_agent_lite/`。安装应用使用同一个 Asterion DCI native executor，并只向通用框架投影 body-free artifact references，不返回 provider answer body。

查看产品能力和配置：

```bash
make asterion-describe
# 安装环境中使用：asterion describe --provider dci-agent-lite
```

## 完整验证矩阵

| 验证层 | 命令 | Provider 操作 | 证明内容 | 状态 |
|---|---|---:|---|---|
| 环境准备 | `make asterion-verify-preflight` | 0 | `.env`、Pi、Node、corpus、Judge | **Verified** |
| 两个基础案例 | `make asterion-verify-basic` | 3 个调度操作 | 两个各 6 轮的 Pi 案例和一个 Judge | **Verified** |
| 完整模型外产品面 | `make asterion-verify-acceptance` | 0 | 8/8、537/537、12/12、6/6、7/7、wheel/application | **Verified** |
| 综合有界验证 | `make asterion-verify-complete` | 3 个调度操作 | preflight → basic → acceptance；不跑完整数据集 | **Verified** |
| Pi runtime `level0`–`level4` | `--runtime-context-level` | 模型外或有界 | 同一 extension/profile identity 与 body-free counters | **Implemented / Model-free verified** |
| 全量 benchmark 与历史分数 | 操作者显式 launcher | 很高 | 没有在迁移关闭或 AF-290 中重跑 | **Not rerun** |

最重要的边界是：Asterion DCI 的产品功能实现和模型外完整性已经验收，但外部 Pi 未公开的 runtime context profile 不能由 Asterion伪造；昂贵的全量 benchmark 结果也不能由本地测试替代。
