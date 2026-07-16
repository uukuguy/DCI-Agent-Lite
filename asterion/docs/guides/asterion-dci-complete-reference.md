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
- 失败、取消和部分结果的真实状态，不把不可用值伪造成 0。

完整实现的模型外验收包括 533/533 个细粒度 selector、6/6 个额外 batch 语义和 12/12 个原始/Asterion launcher 对。迁移期间还运行过一条有界 Pi+Judge batch 及精确 reuse 证明。

但 AF-290 没有重新运行完整 benchmark 数据集，也没有重新复现 62.9% 或 README 中其他历史分数。这些分数属于原始 DCI 的历史实验结果，当前状态为 **Not rerun**，不能由 533 个模型外 selector 推导出来。

## 数据集、Profile 与 Launcher

Bundled profile 定义在 `asterion/dci/resources/batch-profiles.json`：

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

12 个 Asterion launcher：

```text
scripts/bcplus_eval/run_L3.sh
scripts/bcplus_eval/run_bcplus_eval_openai.sh
scripts/bright/run_bio.sh
scripts/bright/run_earth_science.sh
scripts/bright/run_economics.sh
scripts/bright/run_robotics.sh
scripts/qa/run_2wikimultihopqa_dev_sample50.sh
scripts/qa/run_bamboogle_test_sample50.sh
scripts/qa/run_hotpotqa_dev_sample50.sh
scripts/qa/run_musique_dev_sample50.sh
scripts/qa/run_nq_test_sample50.sh
scripts/qa/run_triviaqa_test_sample50.sh
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
asterion-dci export bright --dataset DATASET --output-dir OUTPUT
asterion-dci export bcplus-qa --source-file SOURCE --output-file OUTPUT
```

[`export.py`](../../src/asterion/dci/export.py) 实现 BC+ 文档导出、BRIGHT corpus subset 导出和 BC+ QA 提取/解密；临时文件不会被当成成功输出，失败保持原目标不变。

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
| 完整模型外产品面 | `make asterion-verify-acceptance` | 0 | 8/8、533/533、12/12、6/6、7/7、wheel/application | **Verified** |
| 综合有界验证 | `make asterion-verify-complete` | 3 个调度操作 | preflight → basic → acceptance；不跑完整数据集 | **Verified** |
| Pi runtime `level0`–`level4` | `--runtime-context-level` | 模型外或有界 | 同一 extension/profile identity 与 body-free counters | **Implemented / Model-free verified** |
| 全量 benchmark 与历史分数 | 操作者显式 launcher | 很高 | 没有在迁移关闭或 AF-290 中重跑 | **Not rerun** |

最重要的边界是：Asterion DCI 的产品功能实现和模型外完整性已经验收，但外部 Pi 未公开的 runtime context profile 不能由 Asterion伪造；昂贵的全量 benchmark 结果也不能由本地测试替代。
