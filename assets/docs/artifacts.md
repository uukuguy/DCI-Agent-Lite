# Run Artifacts

Each run produces the following under `outputs/runs/<timestamp>/`:

```text
outputs/runs/<timestamp>/
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

`state.json`, `conversation_full.json`, and `latest_model_context.json` include a `pi_source` object so a result can identify its actual external runtime source:

- `repo_dir` and `origin_url` — detected Git checkout and remote
- `commit` and `dirty` — exact `HEAD` plus whether tracked/untracked local changes were present
- `lock_file` and `lock_revision` — the DCI default pin used for comparison
- `lock_match` — whether the run used that default commit (`null` for a non-Git/custom package directory)
- `expected_revision`, `expected_revision_source`, and `expected_match` — compare against an explicit `DCI_PI_REVISION` when set, otherwise the tracked lock

Local modifications are reported as a boolean; their contents are never copied into artifacts.

If you pass `--system-prompt-file`, both `conversation_full.json` and `conversation.json` include a single `system` message built from that file and any appended system prompt file.

## Artifact-Only Transcript Compaction

The runner supports Claude Code-inspired transcript compaction for `conversation.json`. These are **independent and all off by default**.

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
uv run dci-agent-lite \
  --conversation-clear-tool-results \
  --conversation-externalize-tool-results \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your question here"

# level5
uv run dci-agent-lite \
  --conversation-clear-tool-results \
  --conversation-clear-tool-results-keep-last 0 \
  --conversation-externalize-tool-results \
  --conversation-strip-thinking \
  --conversation-strip-usage \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  "your question here"
```

If tool outputs are bloating `conversation.json`, start with `level1`. If the transcript is still too large, move to `level3`. For the leanest artifact, use `level5`.

Runnable examples in `scripts/examples/`:

- `dci_conversation_level1.sh` through `dci_conversation_level5.sh`
