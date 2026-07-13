<a name="readme-top"></a>

<p align="center">
  <img src="assets/imgs/banner.svg" alt="DCI-Agent-Lite" height="120">
</p>

<h2 align="center">
  Deep Research on Your Personal Knowledge Base
</h2>

<div align="center">
  <a href="https://huggingface.co/papers/2605.05242"><img src="https://img.shields.io/badge/arXiv-B31B1B?style=for-the-badge&logo=arXiv&logoColor=white" alt="arXiv"></a>
  <a href="https://x.com/zhuofengli96475/status/2052784645398303198"><img src="https://img.shields.io/badge/Twitter-000000?style=for-the-badge&logo=X&logoColor=white" alt="Twitter"></a>
  <a href="https://huggingface.co/DCI-Agent"><img src="https://img.shields.io/badge/Hugging%20Face-FFD21E?style=for-the-badge&logo=huggingface&logoColor=white" alt="Hugging Face"></a>
  <a href="https://huggingface.co/spaces/DCI-Agent/demo"><img src="https://img.shields.io/badge/Demo-F97316.svg?style=for-the-badge&logo=gradio&logoColor=white" alt="Demo"></a>
  <a href="https://huggingface.co/datasets/DCI-Agent/eval-logs"><img src="https://img.shields.io/badge/Eval%20Logs-755BB4?style=for-the-badge&logo=google-sheets&logoColor=white" alt="Eval Logs"></a>
</div>

---

## 💥 Introduction

**DCI** is a **direct corpus interaction paradigm** for agentic search. Instead of querying a fixed semantic retriever or retrieval API, the agent **searches the raw corpus directly with terminal tools**. This lets the agent freely compose search primitives and interact with the corpus as an open research environment. It also substantially simplifies the overall retrieval system. 

**DCI-Agent-Lite** is the **minimal open implementation** of this paradigm, built on [Pi](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent) with **bash tools** and **lightweight context management** for **long-horizon deep research**. With `GPT-5.4-nano`, it achieves an impressive **62.9%** accuracy on BrowseComp-Plus, **surpassing** agentic search agents powered by `GPT-5.2`, `Claude-Sonnet-4.6`, `Qwen3.5-122B`, and `GLM-4.7`.

The repository also develops **Asterion**, the independent agent-application framework beneath DCI. Its minimal application runner consumes a resolved plan and an explicit runtime client without adding a scheduler, registry, or automatic service startup; see [`docs/architecture/application-runner.md`](docs/architecture/application-runner.md).

Asterion is the repository's only buildable Python distribution. After
installation, discover its providers and applications without locating internal
resource files:

```bash
asterion list
asterion list --provider dci-agent-lite
asterion run \
  --provider dci-agent-lite \
  --application dci.research-capability@1.0.0 \
  --runtime pi.reference \
  --input "Research this corpus"
```

The installed Pi runtime reads `DCI_PI_DIR`, `DCI_PI_PACKAGE_DIR`,
`DCI_PI_AGENT_DIR`, `ASTERION_RUNTIME_CWD`, `DCI_PROVIDER`, `DCI_MODEL`, and
`DCI_TOOLS` from the caller environment or current-directory `.env`.

### Independent Asterion DCI execution

`asterion-dci` is the Asterion-owned DCI product command. It uses only
`ASTERION_DCI_PI_DIR`, `ASTERION_DCI_PI_PACKAGE_DIR`,
`ASTERION_DCI_PI_AGENT_DIR`, and `ASTERION_DCI_OUTPUT_ROOT`; it does not use
the legacy DCI configuration namespace or run `src/dci`.

```bash
asterion-dci run \
  --cwd "$PWD/corpus/wiki_corpus" \
  --tools read,bash \
  --extra-arg="--thinking high" \
  "Answer using only the local corpus."
```

An AF-190 run writes `question.txt`, `events.jsonl`, `state.json`,
`conversation_full.json`, `conversation.json`, `latest_model_context.json`,
`tool_results/`, `final.txt`, `stderr.txt`, and a separate `protocol/` attempt
directory beneath the independent output root. `conversation_full.json` and
raw tool-result bodies remain protected native evidence; package results expose
only body-free artifact references.

Resume a failed or incomplete run without re-entering its immutable inputs:

```bash
asterion-dci resume --output-dir path/to/asterion-dci-run
```

The command reconstructs the request from `state.json`, rejects completed or
invalid runs before starting Pi, and retains previous evidence while creating a
new protocol attempt. The generic `asterion` CLI remains domain-neutral. Judge,
evaluation, and benchmark functions remain deferred to AF-200. Use
`asterion-dci system-prompt` to print Pi's generated prompt.

Evaluate a completed native run with an explicitly configured Asterion judge:

```bash
asterion-dci evaluate --output-dir path/to/run --gold-answer "Expected answer"
asterion-dci benchmark --dataset dataset.jsonl --output-root outputs/eval --cwd corpus
```

Evaluation reuses only an exact fingerprint of the public judge configuration and
fully shaped request. Batch rows must contain unique `query_id`, `query`, and
`answer` fields. Both commands are product-local and require operator
authorization before a real judge or Pi request; AF-210 retains application and
authorized runtime-semantic parity.

The installed registry also exposes `claude-code.reference`. Its factory uses
`ASTERION_CLAUDE_EXECUTABLE` (default `claude`) and `ASTERION_RUNTIME_CWD`, but
constructing it neither authenticates nor sends a provider request. The bundled
DCI application explicitly supports `pi.reference` and
`claude-code.reference`; the latter is fixture-verified only until an operator
supplies authorization for a real provider-backed run. For either runtime, the
generic CLI selects the application's unique matching canonical assembly.

The bundled controlled-code application requires an explicit executor binary,
Rust policy, and validation configuration. Supply all three through flags or
the matching `ASTERION_EXECUTOR_*` environment variables; no service is
automatically discovered or reused.

<div align="center">
  <img src="assets/imgs/teaser.png" alt="OpenResearcher Teaser" width="100%" style="max-width: 850px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
</div>

<br>

## 🏆 Main Results

DCI-Agent-Lite outperforms top-performing baselines across 13 benchmarks spanning agentic search, knowledge-intensive QA, and IR-ranking tasks.

- **Table 1 -** Agentic Search results.

<div align="center">
  <img src="assets/imgs/bcp.png" alt="Knowledge-intensive QA results" width="65%" style="max-width: 850px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
</div>


- **Table 2 -** Knowledge-intensive QA results.

<div align="center">
  <img src="assets/imgs/table_qa.png" alt="Knowledge-intensive QA results" width="85%" style="max-width: 850px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
</div>

- **Table 3 -** IR ranking results.

<div align="center">
  <img src="assets/imgs/table_ir.png" alt="IR ranking results" width="85%" style="max-width: 850px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
</div>


## 🌟 Key Features
- 🔒 **Your private deep-research assistant**: Point DCI-Agent-Lite at a local corpus and start immediately. It searches, inspects, cross-checks, and answers from your own knowledge base without sending documents to a hosted retrieval service.
- ⚡ **High-resolution, zero-index retrieval**: No embeddings, vector databases, or offline index builds. The agent searches raw files directly with terminal commands like `rg`, `find`, and `sed`, so it can start immediately and maintain fine-grained control over the knowledge base.
- 🛠️ **Minimal harness, long-horizon power**: Built on [Pi](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent) with only bash tools and lightweight context management, DCI-Agent-Lite is small enough to hack and strong enough for serious deep research runs.
- 🚀 **Remarkable agentic-search performance**: DCI-Agent-Lite with GPT-5.4-nano beats top baselines across 13 benchmarks, spanning BrowseComp-Plus, knowledge-intensive QA, and IR ranking.

---

## 📑 Table of Contents

- [⚙️ Setup](#setup)
- [⚡ Quick Start](#quick-start)
- [🚀 Running Experiments](#running-experiments)
- [🎯 Benchmark Evaluation](#benchmark-evaluation)
- [🏗️ Repository Layout](#repository-layout)
- [🙏 Acknowledgements](#acknowledgements)
- [📚 Citation](#citation)

---

<a name="setup"></a>
## ⚙️ Setup

### One-Click Install

**Unix / macOS**

```bash
bash setup.sh
```

<details>
<summary>Manual Steps</summary>

See [`assets/docs/setup.md`](assets/docs/setup.md) for detailed prerequisites, repo build instructions, API-key configuration, and vLLM provider setup.

Quick manual path:

```bash
# 1. Install uv + ripgrep, then sync Python deps
uv sync

# 2. Clone the verified Pi revision, then build it
git clone --no-checkout https://github.com/earendil-works/pi.git pi
git -C pi checkout --detach "$(cat pi-revision.txt)"
cd pi && npm install && npm run build && cd ..

# 3. Configure API keys (copy template, edit .env, auto-loaded by setup.sh)
cp .env.template .env
# edit .env, then re-run setup.sh or source it manually

# 4. Download datasets (auto-downloaded by setup.sh, or run manually)
#    Corpus: https://huggingface.co/datasets/DCI-Agent/corpus
uv run python scripts/download_corpus.py

#    Benchmark datasets: https://huggingface.co/datasets/DCI-Agent/dci-bench
uv run python scripts/download_dci_bench.py
```

</details>

### Configuration

Copy the template to `.env`, then fill in the variables you need. `dci-agent-lite` automatically loads this file from the repository root:

```bash
cp .env.template .env
```

Common variables:

- `ANTHROPIC_API_KEY` for Anthropic model runs.
- `OPENAI_API_KEY` for OpenAI model runs or the optional official OpenAI judge configuration.
- `DEEPSEEK_API_KEY` for the primary DeepSeek judge example.
- `DCI_PROVIDER` and `DCI_MODEL` select the agent used by environment-driven example scripts.
- `DCI_EVAL_JUDGE_BASE_URL`, `DCI_EVAL_JUDGE_API`, `DCI_EVAL_JUDGE_MODEL`, and
  `DCI_EVAL_JUDGE_API_KEY_ENV` select the eval judge backend. See `.env.template` for DeepSeek,
  OpenAI, and local-compatible examples. The base URL must be an absolute HTTP(S) origin without
  credentials, query data, or a fragment; judge redirects are rejected rather than followed.

Before a costly batch evaluation, run `make check-judge` to make one small request through the
configured judge transport and verify that it returns the required structured verdict. The command
uses the configured credential indirectly and prints only safe configuration, verdict, usage, and
cost metadata.

An exported **process environment** key intentionally takes precedence over a value in `.env`.
`make check-judge` reports `judge_api_key_source` and
`judge_api_key_shadowed_by_environment` without exposing key material; after rotating only `.env`,
unset any stale exported key or start a fresh shell before running the preflight.
Run `make check-judge-config` to inspect those same safe fields without making an HTTP request.
For an official Responses judge, `DCI_EVAL_JUDGE_STRICT_JSON_SCHEMA=true` opts into a fixed
strict verdict schema; leave it false for compatible Chat Completions backends.
Official Responses requests also set `store=false` by default to avoid retaining the evaluation
response. Set `DCI_EVAL_JUDGE_RESPONSES_STORE=true` only when that retention is intentional;
compatible Responses endpoints do not receive the field.

<a name="quick-start"></a>
## ⚡ Quick Start

**Prerequisites**: Install dependencies and configure the agent and judge credentials you plan to use (see [Setup](#setup)).

The example below illustrates DCI-Agent-Lite in action: the deep research agent searches the corpus, inspects relevant documents, and produces evidence-grounded answers entirely within the given wikipedia corpus.

1. **Open the DCI-Agent-Lite TUI**:

```bash
# load keys from .env if not already in environment
set -a; source .env 2>/dev/null; set +a

PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner --terminal \
  --provider openai \
  --model gpt-5.4-nano \
  --cwd "corpus/wiki_corpus" \
  --extra-arg="--thinking high"
```

2. **Run your first task**. In the TUI, type:

```text
Answer the following question using only wiki_dump.jsonl in the current directory. Do not use web search. Use rg instead of grep for fast searching. Question: In which street did the Great Fire of London originate?
```

3. (Optional) **Run Programmatically from the CLI**. Remove the `--terminal` flag and pass your task as the final argument:

```bash
set -a; source .env 2>/dev/null; set +a

PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner \
  --provider openai \
  --model gpt-5.4-nano \
  --cwd "corpus/wiki_corpus" \
  --extra-arg="--thinking high" \
  "Answer the following question using only wiki_dump.jsonl in the current directory. Do not use web search. Use rg instead of grep for fast searching. Question: In which street did the Great Fire of London originate?"
```

Programmatic runs save artifacts under `outputs/runs/<timestamp>/`. The final answer is in `final.txt`, the original question is in `question.txt`, and the full trajectory is in `conversation_full.json`. To choose a specific location, pass `--output-dir path/to/run`. 

More runnable examples for OpenAI, Anthropic and vLLM are available in [`scripts/examples/`](scripts/examples/) as `dci_basic_*.sh`. See the [setup guide](assets/docs/setup.md#5-optional-configure-a-local-vllm-provider) for vLLM configuration.


## 🚀 Context Management Strategies

DCI-Agent-Lite includes a lightweight runtime context-management layer for long-horizon deep research runs.

It uses three simple strategies:

- **Truncation** shortens large tool results in each turn.
- **Compaction** keeps recent turns and replaces older tool results with placeholders.
- **Summarization** summarizes older history when the context gets crowded.

<details>
<summary><strong>Context management illustration</strong></summary>

<div align="center">
  <img src="assets/imgs/context_management.png" alt="Context management strategies: truncation, compaction, and summarization" width="100%" style="max-width: 900px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
</div>

</details>

The runtime levels move from no context management to more aggressive compression:

| Level | Behavior |
|-------|----------|
| `level0` | No context management. |
| `level1` | Light truncation. |
| `level2` | Stronger truncation. |
| `level3` | Truncation and compaction. |
| `level4` | Truncation, compaction, and summarization. |

Pass a level through Pi with `--extra-arg`:

```bash
set -a; source .env 2>/dev/null; set +a

PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner \
  --provider openai \
  --model gpt-5.4-nano \
  --cwd "corpus/wiki_corpus" \
  --extra-arg="--thinking high" \
  --extra-arg="--context-management-level level4" \
  "Answer the following question using only wiki_dump.jsonl in the current directory. Do not use web search. Use rg instead of grep for fast searching. Question: In which street did the Great Fire of London originate?"
```


<a name="running-experiments"></a>
## 🎯 Benchmark DCI-Agent-Lite 

We benchmark DCI-Agent-Lite on the following benchmark suites using OpenAI `gpt-5.4-nano` with `--thinking high`, context management set to `level3`, and a maximum turn budget of 300.

| Data | Data Size | Retrieval Corpus | Corpus Size | Avg. Corpus Len. (words) | Corpus Path |
|------|-----------|------------------|-------------|--------------------------|-------------|
| BrowseComp-Plus | 830 | BrowseComp-Plus | 100,195 docs | 5,179 | `corpus/bc_plus_docs/` |
| BRIGHT-Biology | 103 | BRIGHT-Biology | 57,359 docs | 48 | `corpus/bright_corpus/biology/` |
| BRIGHT-Earth Science | 116 | BRIGHT-Earth Science | 121,249 docs | 28 | `corpus/bright_corpus/earth_science/` |
| BRIGHT-Economics | 103 | BRIGHT-Economics | 50,220 docs | 52 | `corpus/bright_corpus/economics/` |
| BRIGHT-Robotics | 101 | BRIGHT-Robotics | 61,961 docs | 25 | `corpus/bright_corpus/robotics/` |
| NQ, TriviaQA, Bamboogle, HotpotQA, 2WikiMultiHopQA, MuSiQue | 50 each / 300 total | Wikipedia-18 | 21,015,324 docs | 100 | `corpus/wiki_corpus/` |


### Agentic Search (BrowseComp-Plus)

```bash
bash scripts/bcplus_eval/run_bcplus_eval_openai.sh
```

### Knowledge-Intensive QA

```bash
bash scripts/qa/run_hotpotqa_dev_sample50.sh
bash scripts/qa/run_musique_dev_sample50.sh
bash scripts/qa/run_nq_test_sample50.sh
bash scripts/qa/run_triviaqa_test_sample50.sh
bash scripts/qa/run_2wikimultihopqa_dev_sample50.sh
bash scripts/qa/run_bamboogle_test_sample50.sh
```

### IR Ranking

```bash
# BRIGHT
bash scripts/bright/run_bio.sh
bash scripts/bright/run_earth_science.sh
bash scripts/bright/run_economics.sh
bash scripts/bright/run_robotics.sh
```

## 🤝 Core Contributors

<table>
<tr>
    <td align="center">
        <a href="https://zhuofeng-li.github.io/">
            <img src="https://github.com/Zhuofeng-Li.png" width="75px;" alt="Zhuofeng Li"/>
            <br />
            <sub><b>Zhuofeng Li</b></sub>
        </a>
    </td>
        <td align="center">
        <a href="https://github.com/jdf-prog">
            <img src="https://github.com/jdf-prog.png" width="75px;" alt="Dongfu Jiang"/>
            <br />
            <sub><b>Dongfu Jiang</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://isaacghx.github.io/about/">
            <img src="https://github.com/IsaacGHX.png" width="75px;" alt="Haoxiang Zhang"/>
            <br />
            <sub><b>Haoxiang Zhang</b></sub>
        </a>
    </td>
    </td>
        <td align="center">
        <a href="https://congwei1230.github.io/">
            <img src="https://congwei1230.github.io/images/profile.png" width="75px;" alt="Cong Wei"/>
            <br />
            <sub><b>Cong Wei</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://lupantech.github.io/">
            <img src="https://github.com/lupantech.png" width="75px;" alt="Pan Lu"/>
            <br />
            <sub><b>Pan Lu</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/erenup">
            <img src="https://github.com/erenup.png" width="75px;" alt="Ping Nie"/>
            <br />
            <sub><b>Ping Nie</b></sub>
        </a>
    </td>
</tr>
</table>

## 🎓 Advisors

<table>
<tr>
        <td align="center">
        <a href="https://yejinc.github.io/">
            <img src="https://yejinc.github.io/profile-uw-2022.jpeg" width="70px;" alt="Yejin Choi"/>
            <br />
            <sub><b>Yejin Choi</b></sub>
        </a>
    </td>
        <td align="center">
        <a href="https://www.james-zou.com/">
            <img src="https://static.wixstatic.com/media/0f3e8f_cfa7e327b97745ddb8c4a66454b5eb3e~mv2.jpg/v1/fill/w_199,h_279,al_c,q_80,usm_0.66_1.00_0.01,enc_avif,quality_auto/46824428A5822_ForWeb.jpg" width="60px;" alt="James Zou"/>
            <br />
            <sub><b>James Zou</b></sub>
        </a>
    </td>
     <td align="center">
        <a href="https://hanj.cs.illinois.edu/">
            <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTYsR82-ravgyteSRLka-SC5A9EwwlJ0opdlVb_4PHVAFHzHu_dmYjegv43Z7gF2MC2k2euJEAA3y4GXrZ-m-h_7F9QWtwd8ITdgD6WMsdMEsmuzb_K&s=10&ec=121643094" width="80px;" alt="Jiawei Han"/>
            <br />
            <sub><b>Jiawei Han</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://github.com/wenhuchen">
            <img src="https://github.com/wenhuchen.png" width="75px;" alt="Wenhu Chen"/>
            <br />
            <sub><b>Wenhu Chen</b></sub>
        </a>
    </td>
    <td align="center">
        <a href="https://cs.uwaterloo.ca/~jimmylin/">
            <img src="https://github.com/lintool.png" width="75px;" alt="Jimmy Lin"/>
            <br />
            <sub><b>Jimmy Lin</b></sub>
        </a>
    </td>
        <td align="center">
        <a href="https://yuzhimanhua.github.io/">
            <img src="https://yuzhimanhua.github.io/profile_pic.jpg" width="75px;" alt="Yu Zhang"/>
            <br />
            <sub><b>Yu Zhang</b></sub>
        </a>
    </td>
</tr>
</table>

<a name="acknowledgements"></a>

## 🙏  Awesome work powered or inspired by DCI-Agent
- [GrepSeek](https://github.com/alirezasalemi7/grepseek): Scaling Deep Research via Reinforcement Learning in Real-world Environments. [![[code]](https://img.shields.io/github/stars/alirezasalemi7/grepseek)](https://github.com/alirezasalemi7/grepseek)
  
<!-- TODO: fill in acknowledgements -->

---

<a name="citation"></a>
## 📚 Citation

```bibtex
@article{li2026beyond,
  title={Beyond Semantic Similarity: Rethinking Retrieval for Agentic Search via Direct Corpus Interaction},
  author={Li, Zhuofeng and Zhang, Haoxiang and Wei, Cong and Lu, Pan and Nie, Ping and Lu, Yi and Bai, Yuyang and Feng, Shangbin and Zhu, Hangxiao and Zhong, Ming and Zhang, Yuyu and Xie, Jianwen and Choi, Yejin and Zou, James and Han, Jiawei and Chen, Wenhu and Lin, Jimmy and Jiang, Dongfu and Zhang, Yu},
  journal={arXiv preprint arXiv:2605.05242},
  year={2026}
}
```

<p align="right"><a href="#readme-top">↑ Back to Top ↑</a></p>

## Star History

<a href="https://www.star-history.com/?repos=DCI-Agent%2FDCI-Agent-Lite&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=DCI-Agent/DCI-Agent-Lite&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=DCI-Agent/DCI-Agent-Lite&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=DCI-Agent/DCI-Agent-Lite&type=date&legend=top-left" />
 </picture>
</a>
