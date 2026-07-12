# Agent Application Framework

## Product objective

Build a multi-runtime, multi-language agent-application framework. DCI is a reference capability and benchmark, not the product boundary.

## Layers

1. **Versioned Agent Runtime Protocol** — run/session lifecycle, capability manifests, normalized events, artifacts, cancellation, deadlines, and conformance fixtures.
2. **Runtime adapters** — Pi first; then one independent runtime; Pydantic AI, LangGraph, Claude Code, and Hermes-agent as their supported integration contracts permit.
3. **Capability packages** — DCI research, tool and policy, workflow, memory and observability, and evaluation.
4. **Language hosts** — Python for research, evaluation, and orchestration; TypeScript for Node and service integration; Rust for controlled execution infrastructure.

## Delivery strategy

- Define and test the runtime protocol before building additional adapters.
- Keep the existing Pi JSONL RPC boundary as the first reference adapter.
- Prove the protocol with a DCI research vertical slice across Pi and one independent runtime before expanding packages or language hosts.
- Add enterprise policy, audit, artifact, and observability boundaries through the shared protocol rather than adapter-private behavior.

## Non-goals

- Do not claim identical native semantics or reasoning traces across runtimes.
- Do not rewrite the Pi integration before protocol conformance requires it.
- Do not make Pi/Judge maintenance the roadmap without a parent work package.
- Do not build every listed adapter or a production multi-tenant control plane in the first framework release.

## Governance

`docs/status/WORKLIST.md` is the sole active work-package ledger. Work may begin only under its active package; `tools/project_scope_check.py` will enforce the repository markers before manager or climb dispatch.

## Design baseline

- `docs/superpowers/specs/2026-07-12-agent-framework-governance-design.md`
