# Asterion Agent Application Framework

## Product objective

Build Asterion as a multi-runtime, multi-language agent-application framework. DCI is its first complete capability-package reference product: an independently owned DCI implementation composes through Asterion contracts into an AI application, while the existing source-only DCI product remains a separate comparison baseline.

## Layers

1. **Versioned Agent Runtime Protocol** — run/session lifecycle, capability manifests, normalized events, artifacts, cancellation, deadlines, and conformance fixtures.
2. **Runtime adapters** — Pi first; then one independent runtime; Pydantic AI, LangGraph, Claude Code, and Hermes-agent as their supported integration contracts permit.
3. **Capability packages** — complete domain implementations (first DCI research), tool and policy, workflow, memory and observability, and evaluation. A package owns its domain workflow internally and exposes portable contracts to the framework.
4. **Language hosts** — Python for research, evaluation, and orchestration; TypeScript for Node and service integration; Rust for controlled execution infrastructure.
5. **Application execution** — exact package implementations execute through explicit application-provider bindings in the single Asterion product distribution; future external providers use the same selected-only contract.

## Delivery strategy

- Define and test the runtime protocol before building additional adapters.
- Keep the existing Pi JSONL RPC boundary as the first reference adapter.
- Use the full Asterion DCI package as the first proof that a complete domain implementation can compose through capability contracts into an AI application, while retaining a separate legacy DCI baseline for parity checks.
- Expose installed runtime factories by exact identity; constructing a factory is not provider authorization or a provider invocation.
- Add enterprise policy, audit, artifact, and observability boundaries through the shared protocol rather than adapter-private behavior.
- Keep Asterion's generic core domain-neutral; package-local CLIs and implementation details must not enter generic framework selection or execution paths.

## Layered runtime configuration

- `.env`, exported environment, CLI fields, and application request fields are layers of one public configuration contract. Explicit invocation values override exported process values; exported values override repository `.env`; both override defaults owned by the selected runtime or Judge role.
- Runtime selection resolves before `DCI_PROVIDER` and `DCI_MODEL`. Those shared field names are interpreted and validated by the selected adapter; they do not imply that every provider is portable across runtimes.
- Pi owns the broader provider surface and defaults to `openai-codex` with `gpt-5.6-luna`. Claude Code owns its subscription-login default plus explicit compatible provider translations such as MiniMax Coding Plan. Unsupported runtime/provider pairs fail before provider construction.
- `DCI_EVAL_JUDGE_*` is an independent evaluation role whose default is the DeepSeek V4 Flash OpenAI-compatible Chat Completions contract. Agent and Judge credentials, requests, evidence, and cache identities remain separate.
- Original DCI and Asterion implement the contract independently and emit the same body-free effective-configuration schema for parity. Full-dataset execution requires explicit invocation-level authorization; normal `.env` values never authorize cost by themselves.

## Non-goals

- Do not claim identical native semantics or reasoning traces across runtimes.
- Do not rewrite the Pi integration before protocol conformance requires it.
- Do not make Pi/Judge maintenance the roadmap without a parent work package.
- Do not build every listed adapter or a production multi-tenant control plane in the first framework release.
- Do not make the mixed-repository original DCI baseline [`src/dci`](../../../src/dci/) an Asterion runtime dependency or compatibility layer.

## Governance

The mixed-repository dependency [`docs/status/WORKLIST.md`](../../../docs/status/WORKLIST.md) is the sole active work-package ledger. Work may begin only under its active package; the mixed-root `tools/project_scope_check.py` enforces the repository markers before manager or climb dispatch.

## Design baseline

- Mixed-repository dependency: [framework governance design](../../../docs/superpowers/specs/2026-07-12-agent-framework-governance-design.md).
