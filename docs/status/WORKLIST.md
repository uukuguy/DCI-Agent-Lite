# Framework Worklist

> Canonical active work-package ledger. No action may begin without exactly one `in_progress` package or explicit user authorization recorded in its package.

## AF-000 — Framework control plane

- Status: completed
- Parent objective: Agent Application Framework
- Scope: north star, worklist, scope audit, manager repair, climb parent enforcement, and state migration only.
- Dependencies: none
- Acceptance: resume recovers AF-000; audit passes valid state and rejects invalid package, resume, and climb relationships; manager and climb dispatch invoke it.
- Design: `docs/superpowers/specs/2026-07-12-agent-framework-governance-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-agent-framework-governance.md`

## AF-010 — Agent Runtime Protocol

- Status: completed
- Parent objective: Agent Application Framework
- Scope: versioned run, session, capability, event, artifact, cancellation, and deadline contracts with conformance fixtures.
- Dependencies: AF-000
- Acceptance: fixtures define portable lifecycle and event semantics for every adapter.
- Design: `docs/superpowers/specs/2026-07-12-agent-runtime-protocol-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-agent-runtime-protocol.md`

## AF-020 — Pi reference adapter

- Status: in_progress
- Parent objective: Agent Application Framework
- Scope: migrate the existing Pi JSONL RPC path behind the Agent Runtime Protocol.
- Dependencies: AF-010
- Acceptance: a DCI run yields protocol-conformant normalized events and artifacts.
- Design: `docs/superpowers/specs/2026-07-12-pi-protocol-adapter-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-pi-protocol-adapter.md`

## AF-030 — Independent runtime vertical slice

- Status: pending
- Parent objective: Agent Application Framework
- Scope: add one non-Pi adapter and run the same DCI research capability across both adapters.
- Dependencies: AF-010
- Acceptance: cross-runtime DCI acceptance proves shared events and artifacts.
- Design: `docs/architecture/agent-framework.md`
- Plan: not yet planned

## AF-040 — Python and TypeScript host boundaries

- Status: pending
- Parent objective: Agent Application Framework
- Scope: expose protocol clients without adapter-private types in the Python and TypeScript hosts.
- Dependencies: AF-020, AF-030
- Acceptance: both hosts consume the same contract and capability manifests.
- Design: `docs/architecture/agent-framework.md`
- Plan: not yet planned

## AF-050 — Rust executor boundary

- Status: pending
- Parent objective: Agent Application Framework
- Scope: define a controlled Rust tool-execution or isolation-sidecar boundary without duplicating orchestration.
- Dependencies: AF-010
- Acceptance: the executor contract conforms to policy, artifact, and cancellation semantics.
- Design: `docs/architecture/agent-framework.md`
- Plan: not yet planned

## AF-060 — Composable workflow and enterprise packages

- Status: pending
- Parent objective: Agent Application Framework
- Scope: workflow, memory, governance, observability, evaluation, and enterprise application packages.
- Dependencies: AF-020, AF-030
- Acceptance: packages compose through declared capabilities and policy boundaries.
- Design: `docs/architecture/agent-framework.md`
- Plan: not yet planned
