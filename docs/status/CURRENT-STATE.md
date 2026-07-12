# Current State

## Project Snapshot

- Project: DCI-Agent-Lite — evolving from a Pi-based DCI benchmark harness into an agent-application framework.
- Current branch: `main`
- Theme-level focus: Agent Runtime Protocol foundation and governed multi-runtime framework delivery.
- Framework north star: `docs/architecture/agent-framework.md`
- Active work package: `AF-050` — Rust controlled executor boundary.

## Current Architecture

- Product contract: a versioned Agent Runtime Protocol will normalize lifecycle, capabilities, events, artifacts, cancellation, and deadlines across adapters.
- Reference runtime: the existing Python controller drives external Pi through a hardened JSONL RPC boundary; it is the first reference adapter, not the framework boundary.
- Capability direction: DCI direct local-corpus research becomes the first reusable capability package; no embedding index is required by that capability.
- Language roles: Python owns research/evaluation/orchestration, TypeScript owns Node/service integration, and Rust is reserved for controlled execution infrastructure.
- Governance: `docs/status/WORKLIST.md` is the sole active package ledger. A scope audit must pass before manager dispatch or climb execution.
- Maintenance history: Pi/Judge reliability H-001 through H-019 is completed and remains available as reference-maintenance evidence; it is not an active roadmap stream.
- Claude Code provider access: the adapter supports stored login and inherited environment-configured backends; provider-backed UAT is deferred while the local account is unavailable and does not block host-language work.
- Host contracts: Python and TypeScript expose the same schema-backed runtime manifest, request, event, and asynchronous client boundary without adapter-private types.
- Controlled execution: `dci.executor/v1` defines execute/cancel/result envelopes; the Rust sidecar has a canonicalized trusted workspace/program policy and explicit protocol resource ceilings, but process execution is not implemented yet.

## Open Problems (theme-level)

- Agent Runtime Protocol contract, capability manifest, and conformance semantics.
- Provider-backed acceptance of the first non-Pi runtime when credentials or a compatible gateway become available.
- Controlled Rust execution/isolation boundary without duplicating orchestration or runtime-adapter responsibilities.
- Enterprise policy, artifact, observability, and isolation boundaries after the reference vertical slice.

## Key Files

### Loaded every session

- `AGENTS.md` — shared repository operating rules and framework scope control.
- `docs/architecture/agent-framework.md` — framework north star.
- `docs/status/WORKLIST.md` — active package ledger.
- `~/.claude/projects/-Users-sujiangwen-sandbox-agentic-2026-DCI-Agent-Lite/memory/MEMORY.md` — concise collaboration-memory index.

### State / handoff

- `docs/status/INDEX.md` — status-file discovery hub.
- `docs/status/JOURNAL.md` — append-only event log.
- `docs/status/RESUME-NEXT-SESSION.md` — current session handoff baton.
- `docs/status/DECISIONS.md` — architecture decisions and revalidation triggers.
- `docs/status/climb/research-tree.md` — generated summary of legacy or parented autonomous research state.

### Implementation entry points

- `src/dci/benchmark/pi_rpc_runner.py` — existing Pi RPC reference runtime.
- `src/dci/benchmark/pi_system_prompt.py` — Pi-owned system-prompt bridge.
- `src/dci/framework/host.py` — public Python Agent Runtime Protocol host contract.
- `packages/typescript/agent-runtime/` — public TypeScript host package and shared-fixture validator.
- `src/dci/framework/executor_protocol.py` — Python reference validator for `dci.executor/v1`.
- `packages/rust/executor/` — active Rust controlled-executor package; trusted policy exists, process service is pending.
- `scripts/bcplus_eval/run_bcplus_eval.py` — DCI reference benchmark harness.
- `tools/climb/` — autonomous-work adapter; future cycles require a work-package parent.

## Resume Instructions

1. Read this file, then `docs/architecture/agent-framework.md` and `docs/status/WORKLIST.md`.
2. Read `RESUME-NEXT-SESSION.md`, recent JOURNAL entries, and the relevant collaboration-memory entry.
3. Run `git status --short`, `git log --oneline -5`, and `python3 tools/project_scope_check.py`.
4. Work only on the named active package; repair state before dispatch when the scope audit fails.
