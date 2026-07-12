# Current State

## Project Snapshot

- Project: DCI-Agent-Lite — evolving from a Pi-based DCI benchmark harness into an agent-application framework.
- Current branch: `main`
- Theme-level focus: Deterministic fail-closed discovery and exact selection of local framework packages.
- Framework north star: `docs/architecture/agent-framework.md`
- Active work package: `AF-080` — local package catalog.

## Current Architecture

- Product contract: a versioned Agent Runtime Protocol will normalize lifecycle, capabilities, events, artifacts, cancellation, and deadlines across adapters.
- Reference runtime: the existing Python controller drives external Pi through a hardened JSONL RPC boundary; it is the first reference adapter, not the framework boundary.
- Capability direction: DCI direct local-corpus research becomes the first reusable capability package; no embedding index is required by that capability.
- Language roles: Python owns research/evaluation/orchestration, TypeScript owns Node/service integration, and Rust is reserved for controlled execution infrastructure.
- Governance: `docs/status/WORKLIST.md` is the sole active package ledger. A scope audit must pass before manager dispatch or climb execution.
- Maintenance history: Pi/Judge reliability H-001 through H-019 is completed and remains available as reference-maintenance evidence; it is not an active roadmap stream.
- Claude Code provider access: the adapter supports stored login and inherited environment-configured backends; provider-backed UAT is deferred while the local account is unavailable and does not block host-language work.
- Host contracts: Python and TypeScript expose the same schema-backed runtime manifest, request, event, and asynchronous client boundary without adapter-private types.
- Controlled execution: `dci.executor/v1` has a runnable concurrent Rust JSONL sidecar with trusted startup policy, direct execution, bounded dual-stream draining, deadline/cancel kill-and-reap, duplicate-ID denial, out-of-order correlation, safe parse errors, EOF draining, operator documentation, and root verification targets.
- Package composition: `dci.package/v1` and the deterministic Python composer resolve a portable policy → DCI research → evaluation → observability graph identically for Pi and Claude Code capability mappings. The TypeScript host exports the same manifest types and validates the canonical schema/fixtures without implementing a second composer.
- Controlled-code packages: portable policy → workflow → evaluation/observability manifests form the second static graph identically for Pi and Claude Code normalized read capabilities plus the shared `executor.controlled` host service. Capability, policy, event, artifact, and permutation boundaries are verified without changing the composer.
- TypeScript package parity: the public host validates all eight checked-in manifests through the canonical schema, and a source-boundary test prevents a second TypeScript composer.
- AF-070 acceptance: the controlled-code graph, host-service boundary, failure matrix, cross-language validation, and non-execution documentation pass full framework closure; the static contract did not require an execution engine change.
- Local catalog: the Python reference surface deterministically discovers and validates direct JSON children across explicit root/file permutations without recursion; fail-closed filesystem and identity hardening is next.

## Open Problems (theme-level)

- Provider-backed acceptance of the first non-Pi runtime when credentials or a compatible gateway become available.
- Discover checked-in and operator-supplied manifests without hidden global state, recursion, symlink ambiguity, or executable loading.
- Select exact package identities and feed both verified graphs to the existing composer without adding version solving or execution.

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
- `src/dci/framework/package_catalog.py` — explicit-root deterministic local package discovery and catalog types.
- `packages/typescript/agent-runtime/` — public TypeScript host package and shared-fixture validator.
- `src/dci/framework/executor_protocol.py` — Python reference validator for `dci.executor/v1`.
- `packages/rust/executor/` — runnable Rust controlled-executor sidecar and library with complete AF-050 policy/process/resource/service acceptance.
- `docs/superpowers/specs/2026-07-12-composable-framework-packages-design.md` — active AF-060 package contract and non-goals.
- `docs/superpowers/specs/2026-07-12-controlled-code-validation-packages-design.md` — active AF-070 second-graph contract and non-goals.
- `docs/superpowers/specs/2026-07-13-local-package-catalog-design.md` — active AF-080 discovery, exact-selection, and trust-boundary contract.
- `docs/architecture/composable-packages.md` — package authoring, static composition, extension, and security boundary guide.
- `docs/architecture/controlled-code-validation-packages.md` — second-graph, shared host-service, non-execution, and non-sandbox guide.
- `scripts/bcplus_eval/run_bcplus_eval.py` — DCI reference benchmark harness.
- `tools/climb/` — autonomous-work adapter; future cycles require a work-package parent.

## Resume Instructions

1. Read this file, then `docs/architecture/agent-framework.md` and `docs/status/WORKLIST.md`.
2. Read `RESUME-NEXT-SESSION.md`, recent JOURNAL entries, and the relevant collaboration-memory entry.
3. Run `git status --short`, `git log --oneline -5`, and `python3 tools/project_scope_check.py`.
4. Work only on the named active package; repair state before dispatch when the scope audit fails.
