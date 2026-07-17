# Asterion DCI Full Functional Verification Guide

If you want to configure and run Asterion DCI without reading the audit
details below, start with the
[command-first Asterion capability usage guide](../guides/asterion-capability-usage.md).
For the function-by-function product boundary and evidence labels, use the
[complete Asterion DCI product reference](../guides/asterion-dci-complete-reference.md).

This is the authoritative operator guide for verifying that the independent
Asterion DCI capability and its runnable `asterion-dci` application preserve
the original Pi-based DCI behavior. In the current combined checkout, run mixed-repository verification commands from the parent mixed-repository root.
Use `uv run --project asterion` to select the Asterion Python project without
changing the invocation CWD: both products then load the shared root `.env`, and
relative values such as `DCI_PI_DIR=./pi` resolve against that same root. A
section explicitly labeled standalone may instead run from a promoted
standalone Asterion repository root.

## 1. Scope and definition of “complete”

“Complete” means the source-only original DCI baseline, the Asterion-owned DCI
wheel, the Pi-default application, durable run/resume/evaluation behavior,
batch/export/profile behavior, all launcher mappings, bounded real acceptance,
and repository gates are independently verifiable. Full datasets are operator
workloads, not a prerequisite for migration closure.

## 2. Safety and prerequisites

Both products load the repository-root `.env`. It must define `DCI_PROVIDER`,
`DCI_MODEL`, the selected provider credential, and Judge settings when used.
`DCI_PI_DIR` selects the external Pi checkout; `./pi` is preferred. Never print
`.env`, credentials, provider bodies, or private evidence paths.

Set `$ASTERION_DCI_CORPUS_ROOT` to an absolute corpus root before any real
Asterion command; this is required even in the main checkout so a missing
worktree corpus cannot silently select the wrong path. Use
`$ASTERION_DCI_OUTPUT_ROOT` for Asterion artifacts. Supply retained private
evidence only through `$AF250_ACCEPTANCE_ROOT`.

### Paper context-profile evidence

The Asterion-owned Pi extension implements the exact closed
`dci.context-profile/v1` set: `level0` has no transformation; `level1` caps tool
results at 50,000 characters; `level2` caps them at 20,000; `level3` also
compacts after more than 240,000 original tool characters and retains the latest
12 complete turns; `level4` targets 20,000 recent tokens and suppresses summaries
after 3 consecutive summary failures while retaining level3 compaction. This is
live model context behavior, not post-run conversation processing.

Run the model-free contract first:

```bash
uv run --project asterion python tools/verify_dci_context_acceptance.py
```

Expected safe output includes `Provider operations: 0` and
`Full dataset ran: no`. Tests and private artifacts prove the **Implemented** and
**Model-free verified** layers. The command validates extension identity,
profile thresholds, public surfaces, artifact schemas, and original Pi session
resume without making a provider request.

The following command is explicitly cost-bearing. It performs exactly one L3
compaction case and one L4 successful-summary case and retains body-free public
evidence under the caller-owned output root:

```bash
uv run --project asterion python tools/verify_dci_context_acceptance.py \
  --provider-backed \
  --env-file .env \
  --output-root outputs/asterion-dci-context-acceptance
```

Only a successful retained run earns **Bounded provider verified**. It does not
earn **Experiment reproduced**: complete paper datasets, score tables, and
ablations remain AF-340 work and require separate time/cost authorization. Never
commit the output root, credentials, prompts, answers, or tool bodies. Profile
runs intended for resume must preserve the original Pi session with
`--keep-session`.

### Paper and bounded ablation matrix

Run the paper-product verifier model-free first:

```bash
uv run --project asterion asterion-dci paper verify
```

It must report zero agent and Judge operations, a planned bound of three, and
`Full dataset ran: no`. The cost-bearing terminal command is deliberately
separate:

```bash
uv run --project asterion asterion-dci paper verify \
  --provider-backed \
  --env-file .env \
  --output-root outputs/asterion-dci-paper-acceptance
```

Before starting Pi it requires an empty private output root, a clean checkout at
the locked Pi revision, hash-valid installed QA/IR/corpus resources, provider
credentials, and the exact `gpt-4.1` Responses Judge. It then runs only
`qa-agent`, `qa-judge`, and `ir-agent`, in that order. The 0600 report contains
identities and digests but no prompt, answer, tool body, credential, or private
path. Agent API request multiplicity remains externally ambiguous. Bind a
successful report only after the verifier exits successfully:

```bash
uv run --project asterion python tools/climb/bind-paper-benchmark-evidence.py \
  --report outputs/asterion-dci-paper-acceptance/paper-benchmark-acceptance.json \
  --pi-dir /path/to/clean/locked/pi
```

The binder rehashes every referenced private artifact and rechecks the clean Pi
identity before atomically creating the terminal H004 result. Failed attempts
remain diagnostic and must not be bound.

The packaged matrix keeps ten paper-declared rows separate from ten tiny
bounded analogues; it never generates a Cartesian product at execution time.
Validate and inspect it without loading `.env`, Pi, a provider, a Judge, or a
dataset:

```bash
uv run --project asterion asterion-dci ablation validate
uv run --project asterion asterion-dci ablation list
uv run --project asterion asterion-dci ablation list \
  --execution-class bounded-fixture
uv run --project asterion asterion-dci ablation render \
  paper.corpus.100000
uv run --project asterion asterion-dci ablation render \
  bounded.tools.read-grep
```

The paper render is deliberately a `NON-EXECUTABLE` comment. Every
`paper-full` row remains blocked until separately reviewed AF-340 authority.
FineWeb corpus rows preserve the paper's unreported revision, seed, selection
algorithm, IDs, and manifest digest as null; they do not invent reproduction
identity. The restricted tool row is the literal Pi `read,grep` set and never
smuggles command filtering through `bash`. A bounded render names exactly one
row and still requires the ordinary benchmark/provider authorization when Task
execution still resolves normal provider/model authorization from explicit CLI
options or `.env`; it never inherits a provider default from the matrix.

Command class: **provider-free**

```bash
uv sync --project asterion
node --version
test -d "${DCI_PI_DIR:-./pi}"
uv run --project asterion asterion-dci --help
uv run --project asterion asterion list --provider dci-agent-lite
```

Pass: Node is at least 20, Pi exists, both CLIs exit zero, and the DCI
application is listed. These commands send no provider request.

## 3. Tier 1 — provider-free smoke verification

Command class: **provider-free**

```bash
PYTHONPATH="src" uv run --project asterion python -m dci.benchmark.pi_rpc_runner --help
uv run --project asterion asterion-dci run --help
uv run --project asterion asterion-dci terminal --help
uv run --project asterion asterion-dci resume --help
uv run --project asterion asterion-dci system-prompt --help
uv run --project asterion asterion-dci evaluate --help
uv run --project asterion asterion-dci benchmark --help
uv run --project asterion asterion-dci export --help
uv run --project asterion asterion-dci ablation --help
bash -n scripts/examples/dci_basic_example.sh \
  scripts/examples/dci_runtime_context_example.sh \
  scripts/examples/asterion_dci_basic_example.sh \
  scripts/examples/asterion_dci_runtime_context_example.sh
uv run --project asterion python tools/verify_asterion_dci_product.py
```

Pass: every command exits zero. The verifier reports 8/8 checked-in product
rows, 533/533 delegated selectors, 12/12 launcher pairs, 6/6 batch extras, and
bounded acceptance 7/7 while executing zero Pi or Judge requests.

## 4. Tier 2 — original DCI examples

These canonical source-baseline checks load the shared `.env`. The second also
uses the configured Judge.

Command class: **bounded provider-backed**

```bash
bash scripts/examples/dci_basic_example.sh
bash scripts/examples/dci_runtime_context_example.sh high
```

Pass: both exit zero, have completed state and a nonempty `final.txt`, and the
second has a true `eval_result.json`. Expected answers are Pudding Lane and
Adaku. Provider/Judge requests are expected.

## 5. Tier 2 — Asterion DCI examples

These call `asterion-dci`, never `src/dci`.

Command class: **bounded provider-backed**

```bash
: "${ASTERION_DCI_CORPUS_ROOT:?Set an absolute corpus root}"
test "${ASTERION_DCI_CORPUS_ROOT#/}" != "$ASTERION_DCI_CORPUS_ROOT"
test -d "$ASTERION_DCI_CORPUS_ROOT"
export ASTERION_DCI_OUTPUT_ROOT="${ASTERION_DCI_OUTPUT_ROOT:-$PWD/outputs/asterion-dci-runs}"
bash scripts/examples/asterion_dci_basic_example.sh
bash scripts/examples/asterion_dci_runtime_context_example.sh high
```

Pass: both exit zero; private run directories contain completed `state.json`,
settled `events.jsonl`, `conversation_full.json`, `conversation.json`,
`latest_model_context.json`, `final.txt`, `stderr.txt`, `tool_results/`, and a
`protocol/` attempt. The runtime-context verdict is true.

## 6. Tier 3 — project-entrypoint Pi-default application

This checks the repository project entrypoint against the same native Asterion
DCI workflow, explicitly selecting Pi. It is not an isolated installation; the
isolated-wheel proof is performed by `verify_asterion_dci_product.py`, which
builds a wheel, creates a separate environment outside the repository, verifies
that `dci` is absent, and runs the installed application model-free.

Command class: **bounded provider-backed**

```bash
: "${ASTERION_DCI_CORPUS_ROOT:?Set an absolute corpus root}"
export ASTERION_RUNTIME_CWD="$ASTERION_DCI_CORPUS_ROOT/wiki_corpus"
uv run --project asterion asterion run \
  --provider dci-agent-lite \
  --application dci.research-capability@1.0.0 \
  --runtime pi.reference \
  --input "Using only wiki_dump.jsonl, where did the Great Fire of London originate?"
```

Pass: the command exits zero, returns a body-free result, and references a
completed native Asterion run. The separate public product verifier proves the
installed wheel contains no `dci` package.

## 7. Tier 3 — complete operator command surface

Command class: **provider-free**

```bash
: "${ASTERION_DCI_CORPUS_ROOT:?Set an absolute corpus root}"
uv run --project asterion asterion-dci system-prompt \
  --cwd "$ASTERION_DCI_CORPUS_ROOT/wiki_corpus" \
  --tools read,bash
```

Command class: **bounded provider-backed**

```bash
RUN_DIR="${ASTERION_DCI_OUTPUT_ROOT:-$PWD/outputs/asterion-dci-runs}/guide-run"
uv run --project asterion asterion-dci run \
  --cwd "$ASTERION_DCI_CORPUS_ROOT/wiki_corpus" \
  --tools read,bash --max-turns 6 \
  --conversation-externalize-tool-results \
  --conversation-strip-thinking \
  --output-dir "$RUN_DIR" \
  "Using only wiki_dump.jsonl, where did the Great Fire of London originate?"
uv run --project asterion asterion-dci evaluate \
  --output-dir "$RUN_DIR" \
  --gold-answer "Pudding Lane"
```

Pass: the run completes; `conversation_full.json` retains protected evidence,
the projection reflects requested controls, and evaluation writes a
fingerprinted true verdict.

`asterion-dci resume --output-dir "$RUN_DIR"` is valid only for a failed or
incomplete run. Interrupt a disposable bounded run after state exists, then
resume it. Pass means a new protocol attempt is appended without changing
immutable inputs or prior evidence. A completed run must be rejected before Pi
starts.

`asterion-dci terminal` requires a TTY and creates no Asterion run directory.

Command class: **bounded provider-backed**

```bash
uv run --project asterion asterion-dci terminal \
  --cwd "$ASTERION_DCI_CORPUS_ROOT/wiki_corpus" \
  --provider "$DCI_PROVIDER" --model "$DCI_MODEL" \
  --tools read,bash "Use only the local corpus."
```

Pass: Pi opens interactively and the command returns its exit status. Non-TTY
use fails before Pi starts.

## 8. Tier 3 — batch profiles, exports, and twelve launchers

Command class: **provider-free**

```bash
uv run --project asterion asterion-dci export bcplus --help
uv run --project asterion asterion-dci export bright --help
uv run --project asterion asterion-dci export bcplus-qa --help
```

The twelve Pi-default Asterion launchers, paired one-to-one with the original
launchers, are:

- `asterion/scripts/bcplus_eval/run_L3.sh`
- `asterion/scripts/bcplus_eval/run_bcplus_eval_openai.sh`
- `asterion/scripts/bright/run_bio.sh`
- `asterion/scripts/bright/run_earth_science.sh`
- `asterion/scripts/bright/run_economics.sh`
- `asterion/scripts/bright/run_robotics.sh`
- `asterion/scripts/qa/run_2wikimultihopqa_dev_sample50.sh`
- `asterion/scripts/qa/run_bamboogle_test_sample50.sh`
- `asterion/scripts/qa/run_hotpotqa_dev_sample50.sh`
- `asterion/scripts/qa/run_musique_dev_sample50.sh`
- `asterion/scripts/qa/run_nq_test_sample50.sh`
- `asterion/scripts/qa/run_triviaqa_test_sample50.sh`

These launchers resolve the mixed-repository root from their own file location,
so their internal root/config setup does not depend on the operator's CWD.

Use `--limit 1` or `ASTERION_DCI_BATCH_LIMIT=1` for bounded verification.

Command class: **bounded provider-backed**

```bash
bash asterion/scripts/qa/run_hotpotqa_dev_sample50.sh --limit 1
bash asterion/scripts/bcplus_eval/run_bcplus_eval_openai.sh level3 high --limit 1
```

Pass: each row has completed native and Judge artifacts, one settled protocol
attempt, summaries, analysis, and figures. A repeat with
`--resume-policy reuse` preserves hashes and mtimes and sends no new request.

This next command is deliberately excluded from routine verification.

Command class: **full-dataset**

```bash
bash asterion/scripts/bright/run_bio.sh
```

Omitting `--limit` can issue many Pi/Judge requests and requires explicit
operator authorization, full data, time, and budget.

## 9. Tier 4 — public and private product acceptance

Command class: **provider-free**

```bash
uv run --project asterion python tools/verify_asterion_dci_product.py
```

Pass: 8/8 rows, 533/533 selectors, 12/12 launcher pairs, 6/6 extras, bounded
acceptance 7/7, and zero provider-backed execution.

Validate retained native evidence without another provider request. Never put
the concrete private path in a committed file. The verifier deliberately fails
when none of the credentials referenced by the acceptance manifest is exported;
an unrelated environment password does not count. Select the repository-root
`.env`, or explicitly point `DCI_ENV_FILE` at the shared main-checkout file from
another worktree, and source it without printing values.

Command class: **provider-free**

```bash
DCI_ENV_FILE="${DCI_ENV_FILE:-.env}"
test -f "$DCI_ENV_FILE"
set -a
source "$DCI_ENV_FILE"
set +a
: "${AF250_ACCEPTANCE_ROOT:?Set the caller-owned retained evidence root}"
uv run --project asterion python tools/verify_asterion_dci_product.py \
  --acceptance-root "$AF250_ACCEPTANCE_ROOT" \
  --validate-only
```

`--validate-only` 与 `--acceptance-root` 同时使用时只复核私有证据，不运行八组本地产品测试；目录不存在、证据不匹配或凭据扫描条件不满足都会以非零状态退出。

Pass: output is `private-acceptance 7/7`. Digests, modes, completed state, settled
events, finals, Judge fingerprints/verdicts/counts, reuse hashes and nanosecond
mtimes validate, and credential matches remain zero.

## 10. Tier 5 — full repository closure gates

Command class: **provider-free**

```bash
(cd asterion && uv run python -m unittest discover -s tests -v)
uv run --project asterion python -m unittest discover -s tests -v
uv run --project asterion python -m compileall -q asterion/src/asterion asterion/tests tests tools
uv run --project asterion ruff check asterion/src/asterion asterion/tests tests tools
npm --prefix asterion/packages/typescript/asterion-runtime test
cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml
cargo fmt --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --check
cargo clippy --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --all-targets -- -D warnings
bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
python3 tools/project_scope_check.py
git diff --check
```

Pass: every process exits zero. The first discovery reproduces the 90 project-local
tests from the Asterion project root; the second reproduces the 1230 root tests
from the mixed-repository root without resolving the wrong
`tests` package. A closed roadmap reports lifecycle `complete`, `active_package`
null, and no scope errors.

## 11. Expected artifacts and pass criteria

A native run is valid only when state is completed, events contain one terminal
result with nothing after it, `final.txt` is nonempty and matches that result,
and the protected protocol attempt is complete. Evaluation adds a Judge result
whose cache identity covers the public request shape. Batch verification also
requires per-query results, summaries/metrics, analysis, and figures unless
explicitly disabled.

Body-free public evidence may contain artifact roles, hashes, counts, modes,
verdicts, and timestamps. It must not contain credentials, private paths,
questions, answers, conversations, or provider bodies.

## 12. Troubleshooting without weakening evidence

- Set `DCI_PI_DIR` if Pi is missing; do not edit or vendor the external checkout.
- Set absolute `ASTERION_DCI_CORPUS_ROOT` if a worktree lacks corpora; never
  copy private corpora into Git.
- Install Node 20 or newer when Node preflight fails.
- Check that the variable named by `DCI_EVAL_JUDGE_API_KEY_ENV` exists without
  printing its value. Do not replace required real evidence with a fixture.
- Completed runs are correctly rejected by resume; use exact benchmark reuse
  for completed rows.
- Choose a fresh output directory rather than mutating retained evidence.
- Add `--limit 1` when a full launcher is too expensive, and never call that a
  full-dataset result.

Completion comes from provider-free product/gate evidence plus the retained
bounded provider-backed 7/7 record—not from worklist status alone.
