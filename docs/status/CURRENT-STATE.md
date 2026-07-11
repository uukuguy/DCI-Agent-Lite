# Current State

## Project Snapshot

- Project: DCI-Agent-Lite — minimal Pi-based implementation of direct raw-corpus interaction for agentic search.
- Current branch: `main`
- Theme-level focus: Configuration-driven, failure-bounded Pi runtime and OpenAI-compatible benchmark evaluation.

## Current Architecture

- Python CLI/orchestration: `dci-agent-lite` launches the external Pi coding agent in RPC or terminal mode, waits for session-level `agent_settled`, applies a configurable wall-clock deadline, and records run artifacts.
- External runtime: Pi is resolved through `DCI_PI_DIR`, preferring `./pi` with a legacy `./pi-mono` fallback.
- Corpus interaction: the agent searches local raw corpora directly with terminal tools; there is no required embedding index or retrieval service.
- Evaluation: a shared judge transport supports OpenAI Responses and compatible Chat Completions backends; batch evaluators reuse the same `.env` configuration.
- Configuration/artifacts: repository-root `.env` controls agent, Pi, and judge settings; run outputs live under `outputs/`.

## Open Problems (theme-level)

- Reproducible version pinning and distribution of the external Pi checkout.
- Protocol compatibility as the external Pi checkout evolves independently.
- Structured-output variability across nominally OpenAI-compatible judge backends.

## Key Files

### Loaded every Claude session

- `CLAUDE.md` — symlink to the canonical local `AGENTS.md` project instructions.
- `AGENTS.md` — shared Codex/Claude repository working instructions.
- `~/.claude/projects/-Users-sujiangwen-sandbox-agentic-2026-DCI-Agent-Lite/memory/MEMORY.md` — concise collaboration-memory index with confidence labels and Cold/Audit pointers.

### State / handoff

- `docs/status/INDEX.md` — status-file discovery hub.
- `docs/status/JOURNAL.md` — append-only event log.
- `docs/status/RESUME-NEXT-SESSION.md` — current session handoff; created by `project-state handoff` and not present yet.
- `docs/status/CURRENT-STATE.md` — this structural snapshot.

### Implementation entry points

- `pyproject.toml` — Python package metadata and CLI entry points.
- `src/dci/config.py` — `.env` loading and Pi path resolution.
- `src/dci/benchmark/pi_rpc_runner.py` — main CLI, Pi RPC orchestration, artifacts, and single-run evaluation.
- `src/dci/benchmark/judge.py` — OpenAI-compatible judge configuration, request shaping, parsing, and cost metadata.
- `scripts/bcplus_eval/run_bcplus_eval.py` — concurrent BrowseComp-Plus execution and aggregation.
- `scripts/examples/dci_runtime_context_example.sh` — representative agent-plus-judge end-to-end example.
- `tests/` — first-party configuration, judge transport, and Pi RPC lifecycle regressions.
- `.env.template` — primary runtime, Pi, and judge configuration examples.
- `setup.sh` — dependency, external Pi, corpus, and benchmark setup.

## Resume Instructions

1. Read this file for structure, theme, and open problems.
2. Read `RESUME-NEXT-SESSION.md` for in-flight intent and the next concrete action, if it exists.
3. Run `git status --short` and `git log --oneline -5`.
4. Load `CLAUDE.md`/`AGENTS.md`, then the project MEMORY index and only directly relevant linked memory entries.
