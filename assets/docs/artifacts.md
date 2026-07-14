# Run Artifacts

Each Asterion DCI run produces the following under its private generated or
explicit run directory (normally
`outputs/asterion-dci-runs/asterion-dci-<UTC>-<random>/`):

```text
outputs/asterion-dci-runs/<run-id>/
  events.jsonl              # raw RPC event stream, appended in real time
  state.json                # low-level debug snapshot, rewritten after each event
  conversation_full.json    # full normalized transcript without DCI-side compaction
  conversation.json         # cleaner transcript view, optionally compacted
  latest_model_context.json # most recent context snapshot prepared for the next model call
  final.txt                 # final assistant answer
  stderr.txt                # Pi stderr capture
  question.txt              # question text used for the run
  protocol/
    attempt-0001.request.json # Agent Runtime Protocol v1 request for this attempt
    attempt-0001.events.jsonl # normalized, conformant event stream for this attempt
```

Each resume creates the next isolated protocol attempt (`attempt-0002`, and so on). Raw Pi events continue to append to `events.jsonl`; protocol events contain normalized text, tool, usage, artifact, and terminal events, but exclude hidden thinking and provider request payloads. `state.json.protocol` points to the current attempt and its protocol run ID.

`state.json`, `conversation_full.json`, and `latest_model_context.json` include
a credential-safe `pi_source` object so a result can identify its actual
external runtime source. It contains revision/match/dirty facts and, only when
safe, a sanitized remote identity; it does not persist local checkout paths,
URL credentials, query strings, fragments, environment values, or arbitrary
extra-argument bodies.

- `commit` and `dirty` — exact `HEAD` plus whether tracked/untracked local changes were present
- `lock_revision` — the DCI default pin used for comparison
- `lock_match` — whether the run used that default commit (`null` for a non-Git/custom package directory)
- `expected_revision`, `expected_revision_source`, and `expected_match` — compare against an explicit `DCI_PI_REVISION` when set, otherwise the tracked lock

Local modifications are reported as a boolean; their contents are never copied into artifacts.

If you pass `--system-prompt-file`, both `conversation_full.json` and
`conversation.json` include a single `system` message built from that file and
any appended system prompt file. Relative question, prompt, and
evaluation-answer resources resolve from the invocation directory first and
repository root second, never from the Pi child `--cwd`; missing, unreadable,
or symlinked resources fail before Pi. The standalone `system-prompt` command
applies the same boundary to its appended prompt before rendering.

## Artifact-Only Transcript Compaction

`asterion-dci run` supports independent transcript-processing controls for
`conversation.json`. They are all off by default except the inert keep-last
value of `3`.

**Important:** this does **not** change Pi's runtime behavior. It only changes how DCI stores the processed transcript view on disk. If your question is "does context management affect performance or behavior?", this layer is usually not the one you want.

Use it only when you want:

- smaller artifacts
- easier-to-read saved transcripts
- separate archival/debug views where full tool output lives outside `conversation.json`

### Available flags

- `--conversation-clear-tool-results` — Replaces older `toolResult` payloads with short placeholders.
- `--conversation-clear-tool-results-keep-last N` — Keep the most recent `N` tool results inline. Default: `3`.
- `--conversation-externalize-tool-results` — Saves each full `toolResult` to `tool_results/*.json` and keeps a pointer in `conversation.json`.
- `--conversation-strip-thinking` — Removes assistant `thinking` blocks.
- `--conversation-strip-usage` — Removes assistant token and cost metadata.

### Optimize levels

| Level | Goal | Flags |
|-------|------|-------|
| `level1` | Minimal compaction, safest for debugging | `--conversation-clear-tool-results --conversation-externalize-tool-results` |
| `level2` | Keep only the most recent tool result inline | `--conversation-clear-tool-results --conversation-clear-tool-results-keep-last 1 --conversation-externalize-tool-results` |
| `level3` | Aggressive tool-output compaction | `--conversation-clear-tool-results --conversation-clear-tool-results-keep-last 0 --conversation-externalize-tool-results` |
| `level4` | Aggressive + remove hidden reasoning | + `--conversation-strip-thinking` |
| `level5` | Maximum compression | + `--conversation-strip-usage` |

### Example commands

```bash
# level1
uv run asterion-dci run \
  --conversation-clear-tool-results \
  --conversation-externalize-tool-results \
  --provider "$DCI_PROVIDER" \
  --model "$DCI_MODEL" \
  "your question here"

# level5
uv run asterion-dci run \
  --conversation-clear-tool-results \
  --conversation-clear-tool-results-keep-last 0 \
  --conversation-externalize-tool-results \
  --conversation-strip-thinking \
  --conversation-strip-usage \
  --provider "$DCI_PROVIDER" \
  --model "$DCI_MODEL" \
  "your question here"
```

If tool outputs are bloating `conversation.json`, start with `level1`. If the transcript is still too large, move to `level3`. For the leanest artifact, use `level5`.

`conversation_full.json`, raw events, stderr, and externalized tool-result
bodies are protected native evidence. Framework/application projections expose
only body-free artifact URIs. `conversation.json` is the processed view and may
omit or replace bodies only according to the five explicit controls above.

Resume appends a new isolated protocol attempt and preserves prior evidence. It
is artifact continuation, not Pi session continuity when the original request
did not enable `--keep-session`. `runtime_context_level` is recorded only as an
unsupported diagnostic until Pi exposes a typed control. Run-directory files
are private and atomically maintained, but the directory is not a read-only
sandbox when bash is available.

## Batch artifacts

`asterion-dci benchmark` creates one Asterion-owned batch root. Inputs and
configuration are fingerprinted before workers start; per-query native evidence
is committed before incremental and final aggregates:

```text
outputs/asterion/<family>/<profile>/
  config.json
  batch-state.json
  results.jsonl
  summary.json
  analysis.json
  analysis.jsonl
  analysis_figures/
    scatter_overview.png
    runtime_breakdown.png
    metric_distributions.png
    tool_summary.png
  <query-id>/
    item.json
    input_question.txt
    result.json
    timing.json
    native-generation-0001/ # private single-run evidence described above
```

QA rows bind their exact Judge request fingerprint and cached verdict. BRIGHT
IR rows bind ranked-document evidence and NDCG. Batch and analysis files are
private native artifacts: they include benchmark questions, gold answers, final
answers, and Judge reasons. They exclude credentials and provider error bodies;
framework projections remain body-free references. `--resume-policy compatible`
continues only matching incomplete rows and reuses matching complete rows;
`reuse` refuses to run a new Pi or Judge request. Figures require analysis, so
use `--no-analysis --no-figures` together when disabling both.

## Product-acceptance evidence

AF-250 keeps public acceptance evidence separate from private native artifacts.
The local verifier records only executable local/model-free matrix results; it
does not create a provider-backed acceptance record. A
`product-acceptance.json` manifest is valid only when all seven bounded real
cases completed successfully with body-free structural checks. It must not
contain credentials, provider bodies, or private paths.

No manifest is present when any required real case failed. That absence is a
truthful blocked-acceptance signal, not a missing artifact to reconstruct from
private native evidence. Retained one-row Pi-plus-Judge/reuse evidence may
support only its corresponding two case IDs and cannot establish other failed
example or application cases.
