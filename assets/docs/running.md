# Running Pi

## Python RPC Wrapper

Run `make check-pi-rpc` for a fast model-free compatibility check before a benchmark. It validates JSONL framing plus the `get_state` response contract without sending a prompt or consuming model tokens.

Main entry point:

```bash
PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner
```

The runner reads `DCI_PI_DIR` from the repository-root `.env`. Without an explicit value it prefers an existing `./pi` checkout and falls back to the legacy `./pi-mono` path. `--package-dir` and `--agent-dir` remain available as one-off overrides. `setup.sh` pins new and clean existing checkouts to the full commit in `pi-revision.txt`; `DCI_PI_REVISION` is an explicit override for deliberate revision tests.

Before sending a prompt, the RPC runner compares the actual Pi commit with the expected revision (`DCI_PI_REVISION` when set, otherwise `pi-revision.txt`). A mismatch emits a non-blocking warning and is preserved in `pi_source`; custom experiments may continue intentionally.

`dci-run-pi-rpc` remains available as a legacy alias.

By default:

- Pi uses its own dynamically generated system prompt
- Run artifacts go under `outputs/runs/<timestamp>/`
- Non-empty `--output-dir` values are rejected unless you pass `--resume`
- Each RPC prompt has a 3600-second wall-clock deadline, configurable through `DCI_RPC_TIMEOUT_SECONDS` in `.env` or `--rpc-timeout-seconds`; `0` disables it

### Basic example

```bash
PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner \
  --provider openai \
  --model gpt-5.4-nano \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6 \
  --extra-arg="--thinking low" \
  "your question here"
```

Provider-specific runnable examples live under `scripts/examples/`:

- Anthropic: `dci_basic_anthropic_example.sh`
- OpenAI: `dci_basic_openai_example.sh`
- vLLM: `dci_basic_vllm_example.sh`

### Interactive terminal

Use `--terminal` to launch Pi's interactive terminal UI through the same wrapper:

```bash
PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner --terminal \
  --provider openai \
  --model gpt-5.4-nano \
  --cwd "$PWD/corpus/wiki_corpus" \
  --tools read,bash \
  --extra-arg="--thinking high"
```

Optional positional text or `--question-file` is forwarded as the initial message. Terminal mode does not write RPC runner artifacts, so it cannot be combined with runner-only flags such as `--output-dir`, `--resume`, `--max-turns`, `--show-tools`, or `--eval-answer`.

### Resume a run

Resume by pointing directly at a run directory:

```bash
PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner \
  --resume "$PWD/outputs/runs/bonang-test" \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6
```

Or resume the same directory named in `--output-dir`:

```bash
PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner \
  --output-dir "$PWD/outputs/runs/bonang-test" \
  --resume \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --cwd "$PWD/corpus/bc_plus_docs/thefourwallmag.wordpress.com" \
  --tools read,bash \
  --max-turns 6
```

`--resume` reuses the artifact directory and validates that run settings match. True agent continuity also requires `--keep-session`.

### Override system prompt

```bash
PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner \
  --system-prompt-file "$(git rev-parse --show-toplevel)/prompts/system_prompt.txt" \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your system prompt"
```

## Runtime Context-Management Levels

The currently configured external Pi CLI does not expose a typed `--context-management-level` option. Runtime profiles such as `level0` through `level5` therefore cannot be presented as executable Pi behavior or used as valid ablation commands in this checkout. This boundary is **External-limited**.

Asterion accepts `--runtime-context-level` only as a requested diagnostic. It persists the requested value together with `runtime_context_control=unsupported` and deliberately does not invent or forward an unsupported Pi argument. Re-check Pi's own CLI help before changing that status.

This is different from saved conversation artifact compaction. Asterion can deterministically produce a smaller `conversation.json` while retaining complete native evidence in `conversation_full.json`:

```bash
asterion-dci run \
  --conversation-clear-tool-results \
  --conversation-clear-tool-results-keep-last 3 \
  --conversation-externalize-tool-results \
  --conversation-strip-thinking \
  --conversation-strip-usage \
  "your question here"
```

These controls change saved artifacts, not the context Pi sends to the model. See [artifacts.md](artifacts.md#artifact-only-transcript-compaction) and the [complete Asterion DCI reference](../../asterion/docs/guides/asterion-dci-complete-reference.md#context-management两个不同层次) for the two-layer distinction.

## Running Pi Directly From Node

If you want the raw CLI instead of the Python RPC wrapper:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT/corpus/bc_plus_docs/thefourwallmag.wordpress.com"

PI_CODING_AGENT_DIR="$REPO_ROOT/pi/.pi/agent" \
node "$REPO_ROOT/pi/packages/coding-agent/dist/cli.js" \
  --model claude-sonnet-4-20250514 \
  --thinking off \
  --tools read,bash \
  --max-turns 6 \
  --no-session \
  -p "your question here"
```

Direct examples in `scripts/examples/`:

- Anthropic: `pi_direct_anthropic_example.sh`
- OpenAI: `pi_direct_openai_example.sh`
- vLLM: `pi_direct_vllm_example.sh`
