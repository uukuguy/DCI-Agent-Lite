# Asterion 能力包使用指南（以 DCI 为例）

这份指南只回答三个实际问题：Asterion 的 DCI 能做什么、需要配置什么、怎样用一条统一命令验证它。无需阅读 Python 源码，也无需手动寻找能力包里的脚本。

## 五分钟开始

以下命令都在仓库根目录执行。Asterion 与原始 DCI 共用根目录的 `.env`；如果现有 `.env` 已经能运行原始 DCI 两个示例，通常无需另建配置。

```bash
uv sync

# 先看 DCI 能做什么；不调用模型
uv run asterion describe --provider dci-agent-lite

# 检查 .env、Pi、Node 和两个示例语料；不调用模型
uv run asterion verify \
  --provider dci-agent-lite \
  --level preflight \
  --env-file .env \
  --corpus-root "$PWD/corpus"

# 完整验证；会进行两次有界 Pi 运行和一次 Judge 评测操作
uv run asterion verify \
  --provider dci-agent-lite \
  --level complete \
  --env-file .env \
  --corpus-root "$PWD/corpus" \
  --output-root "$PWD/outputs/asterion-verification"
```

若只想确认迁移代码和安装边界完整、不想调用模型，将最后一条命令的 `complete` 改为 `acceptance`，并可省略 `.env`、语料和输出目录参数。

## 最少需要哪些环境变量

如果还没有 `.env`，先执行：

```bash
cp .env.template .env
```

然后在 `.env` 中确认下面几类值。以下只是一个“Anthropic 负责 Pi、OpenAI 负责 Judge”的示例；尖括号内容必须替换，不能原样使用。

```dotenv
# Pi 研究模型
DCI_PROVIDER=anthropic
DCI_MODEL=<YOUR_PI_MODEL>
ANTHROPIC_API_KEY=<YOUR_PROVIDER_API_KEY>

# 外部 Pi checkout；缺省也是 ./pi
DCI_PI_DIR=./pi

# Judge：basic 和 complete 的第二个案例会使用它
DCI_EVAL_JUDGE_BASE_URL=https://api.openai.com/v1
DCI_EVAL_JUDGE_API=responses
DCI_EVAL_JUDGE_MODEL=<YOUR_JUDGE_MODEL>
DCI_EVAL_JUDGE_API_KEY_ENV=OPENAI_API_KEY
OPENAI_API_KEY=<YOUR_JUDGE_API_KEY>
```

如果 `DCI_PROVIDER=openai`，Pi 使用 `OPENAI_API_KEY`；如果是 `anthropic`，使用 `ANTHROPIC_API_KEY`。通过 Pi 登录保存到 `.pi/agent/auth.json` 的认证也可直接共用，例如 `openai-codex`，无需另造 `OPENAI_CODEX_API_KEY`。Judge 的密钥变量由 `DCI_EVAL_JUDGE_API_KEY_ENV` 指定。Asterion 只检查认证是否存在，不会在输出中显示密钥值。

还需要：

- Node.js 20 或更高版本；
- `DCI_PI_DIR/packages/coding-agent` 和 `DCI_PI_DIR/.pi/agent` 存在；
- 语料根目录下存在 `wiki_corpus/` 和 `bc_plus_docs/`。

不必设置一长串 `ASTERION_DCI_*` 变量。统一验证命令优先使用 `--corpus-root` 和 `--output-root`；普通 `asterion-dci` 运行仍可使用根目录 `.env` 中的共享 `DCI_*` 设置。

## 查看能力：describe

```bash
uv run asterion describe --provider dci-agent-lite
```

该命令列出能力名称、用途、可运行命令、所需配置和四种验证级别。它不会读取密钥值，也不会发出模型请求。机器或脚本需要结构化结果时加 `--json`：

```bash
uv run asterion describe --provider dci-agent-lite --json
```

## 只检查准备情况：--level preflight

```bash
uv run asterion verify \
  --provider dci-agent-lite \
  --level preflight \
  --env-file .env \
  --corpus-root "$PWD/corpus"
```

它检查 `.env`、provider/model、provider 密钥是否存在、Judge 配置、Pi 目录、Node 版本和两个示例语料。它不会运行 Pi 或 Judge，失败时只报告缺少哪一类条件。

## 验证两个基础示例：--level basic

```bash
uv run asterion verify \
  --provider dci-agent-lite \
  --level basic \
  --env-file .env \
  --corpus-root "$PWD/corpus" \
  --output-root "$PWD/outputs/asterion-verification"
```

这条命令替代手动执行两个 Asterion 示例脚本，固定运行：

1. `wiki_corpus`：回答伦敦大火起源街道的问题，`max_turns=6`、`thinking=high`；一次 Pi 运行。
2. `bc_plus_docs`：回答 Bonang Matheba 访谈问题，`max_turns=6`、`thinking=high`；一次 Pi 生成，再由 Judge 对照 `Adaku` 评测。

命令固定调度两次 Pi 运行操作和一次 Judge 评测操作，每个 Pi 案例都有六轮限制。Pi 在一轮中可能搜索、读取文件并继续下一轮，所以终端显示的 `3` 是“provider-backed operations”，不是底层 provider API 请求数。它不运行批量数据集，任何一步失败都会停止后续操作。

## 不调用模型验证完整迁移：--level acceptance

```bash
uv run asterion verify \
  --provider dci-agent-lite \
  --level acceptance
```

它验证已经迁移的完整产品面：8 个产品功能组、533 项批处理/指标/导出检查、12 对原始与 Asterion 启动脚本、6 项额外语义检查、7 项有界验收记录，以及安装 wheel 后的应用边界。它会运行本地测试和构建隔离 wheel，因此可能需要几十秒，但模型请求数始终为 0，也不会运行完整数据集。

## 一条命令全部验证：--level complete

```bash
uv run asterion verify \
  --provider dci-agent-lite \
  --level complete \
  --env-file .env \
  --corpus-root "$PWD/corpus" \
  --output-root "$PWD/outputs/asterion-verification"
```

执行顺序固定为 `preflight → basic → acceptance`。前一步失败就停止。全部通过时，provider-backed operations 固定为 3 次（两次有界 Pi 运行、一次 Judge 评测），不会启动完整数据集。

## 原始 DCI 功能与 Asterion 命令

| 原始 DCI 功能 | Asterion 中怎样使用 | 怎样验证 |
|---|---|---|
| 本地语料研究 | `asterion-dci run --cwd ...` | `verify --level basic` 的第一个案例 |
| 运行上下文与 Judge | `asterion-dci run --max-turns ... --thinking-level ... --eval-answer ...` | `verify --level basic` 的第二个案例 |
| 交互终端 | `asterion-dci terminal --cwd ...` | `asterion describe` 查看入口；TTY 中直接运行 |
| 中断后继续 | `asterion-dci resume --output-dir ...` | `verify --level acceptance` 覆盖恢复语义 |
| 对已保存结果评测 | `asterion-dci evaluate --output-dir ... --gold-answer ...` | `basic` 的 Judge 案例和 `acceptance` 的缓存检查 |
| QA、IR、BC+、BRIGHT 批处理 | `asterion-dci benchmark --profile ... --limit 1` | `acceptance` 验证 533 项完整清单；不会启动全量数据集 |
| 结果导出 | `asterion-dci export bcplus|bright|bcplus-qa ...` | `acceptance` 验证导出语义 |
| 安装后的 Pi 应用 | `asterion run --provider dci-agent-lite --application dci.research-capability@1.0.0 --runtime pi.reference ...` | `acceptance` 在仓库外构建并验证 wheel |
| 整体迁移完整性 | 无需拼接内部测试命令 | `asterion verify --provider dci-agent-lite --level complete` |

日常研究、终端、恢复、评测、批处理和导出使用 `asterion-dci`；“能力包有什么”和“迁移是否完整”统一使用通用的 `asterion describe/verify`。

## 预期输出

`preflight` 成功时末尾类似：

```text
Overall: PASS
Provider-backed operations: 0
Full dataset ran: no
```

`complete` 成功时末尾必须是：

```text
Overall: PASS
Provider-backed operations: 3
Full dataset ran: no
```

需要 JSON 时在任意 `verify` 命令末尾加 `--json`。命令退出码：`0` 表示整体通过，`1` 表示验证执行后未全部通过，`2` 表示命令、provider 或输入本身无效。

## 费用和请求次数

| 级别 | Pi 运行操作 | 每个 Pi 案例轮数上限 | Judge 操作 | 完整数据集 |
|---|---:|---:|---:|---|
| `preflight` | 0 | 0 | 0 | 否 |
| `basic` | 2 | 6 | 1 | 否 |
| `acceptance` | 0 | 0 | 0 | 否 |
| `complete` | 2 | 6 | 1 | 否 |

实际 provider API 请求数取决于 Pi 在六轮限制内的工具调用和推理过程，不能把一次 Pi 运行误算成一次 API 请求。若只接受零费用验证，使用 `preflight` 或 `acceptance`。

真正的 benchmark 全量运行必须由用户单独执行；这四个验证级别都不会偷偷启动它。

## 产物在哪里

`basic` 和 `complete` 在 `--output-root` 下创建一个随机命名的 `verify-*` 私有目录，每个案例各有独立子目录。里面是正常的 Asterion DCI 原生运行产物，例如 `state.json`、`events.jsonl`、`conversation_full.json`、`final.txt` 和 `protocol/`。

终端显示或 JSON 返回的 `artifact_refs` 只是相对角色引用，不包含回答正文、对话、provider 响应、密钥或本机绝对路径。

## 常见问题

`environment` 失败：确认 `.env` 存在，或用 `--env-file` 指向正确文件。

`configuration` 失败：确认 `DCI_PROVIDER`、`DCI_MODEL` 以及对应 provider 密钥已设置。密钥名由 provider 决定。

`judge` 失败：确认 `DCI_EVAL_JUDGE_MODEL`、`DCI_EVAL_JUDGE_API_KEY_ENV`，以及后者指向的密钥变量都存在。

Judge 配置存在但请求仍失败：运行 `make check-judge-config`。如果显示 `judge_api_key_shadowed_by_environment: true`，说明当前 shell 中的密钥覆盖了 `.env`；确认该值正确，或用 `env -u 密钥变量名` 运行验证，让 `.env` 中的值生效。

`pi` 失败：确认 `DCI_PI_DIR` 是 Pi checkout，且其中存在 `packages/coding-agent/package.json` 和 `.pi/agent/`。

`corpora` 失败：`--corpus-root` 指向的是两个语料目录的父目录，不是 `wiki_corpus` 本身。

`acceptance` 显示 `NOT RUN`：该级别需要 DCI-Agent-Lite 源码仓库中的验收清单和工具；安装 wheel 后仍可使用 `describe` 与 `preflight`，但完整源码迁移验收应在仓库根目录执行。

需要复核每个测试选择器、产物结构、原始 DCI 对照和私有验收证据时，再阅读[完整功能验证指南](../verification/asterion-dci-validation-guide.md)。
