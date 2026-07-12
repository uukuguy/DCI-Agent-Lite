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

- Status: completed
- Parent objective: Agent Application Framework
- Scope: migrate the existing Pi JSONL RPC path behind the Agent Runtime Protocol.
- Dependencies: AF-010
- Acceptance: a DCI run yields protocol-conformant normalized events and artifacts.
- Design: `docs/superpowers/specs/2026-07-12-pi-protocol-adapter-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-pi-protocol-adapter.md`

## AF-030 — Independent runtime vertical slice

- Status: completed
- Parent objective: Agent Application Framework
- Scope: add one non-Pi adapter and run the same DCI research capability across both adapters.
- Dependencies: AF-010
- Acceptance: Pi provider-backed evidence plus Claude Code fixture, safe-failure, restricted-command, and environment-boundary tests prove the shared protocol surface without requiring a currently unavailable account.
- Design: `docs/superpowers/specs/2026-07-12-claude-code-protocol-adapter-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-claude-code-protocol-adapter.md`
- Deferred acceptance: run the tiny local-corpus provider-backed Claude slice when a Claude login or compatible `ANTHROPIC_*` gateway is available; this does not block AF-040.

## AF-040 — Python and TypeScript host boundaries

- Status: completed
- Parent objective: Agent Application Framework
- Scope: expose protocol clients without adapter-private types in the Python and TypeScript hosts.
- Dependencies: AF-020, AF-030
- Acceptance: both hosts consume the same contract and capability manifests.
- Design: `docs/superpowers/specs/2026-07-12-python-typescript-host-boundaries-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-python-typescript-host-boundaries.md`

## AF-050 — Rust executor boundary

- Status: completed
- Parent objective: Agent Application Framework
- Scope: define a controlled Rust tool-execution or isolation-sidecar boundary without duplicating orchestration.
- Dependencies: AF-010
- Acceptance: the executor contract conforms to policy, artifact, and cancellation semantics.
- Design: `docs/superpowers/specs/2026-07-12-rust-executor-boundary-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-rust-executor-boundary.md`

## AF-060 — Composable workflow and enterprise packages

- Status: completed
- Parent objective: Agent Application Framework
- Scope: workflow, memory, governance, observability, evaluation, and enterprise application packages.
- Dependencies: AF-020, AF-030
- Acceptance: packages compose through declared capabilities and policy boundaries.
- Design: `docs/superpowers/specs/2026-07-12-composable-framework-packages-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-composable-framework-packages.md`

## AF-070 — Controlled code validation packages

- Status: completed
- Parent objective: Agent Application Framework
- Scope: prove a second portable policy/workflow/observability/evaluation graph against normalized runtimes plus the shared controlled-executor host service.
- Dependencies: AF-050, AF-060
- Acceptance: the controlled-code graph composes deterministically across Pi and Claude Code normalized edges, rejects every missing boundary, and remains static composition rather than execution.
- Design: `docs/superpowers/specs/2026-07-12-controlled-code-validation-packages-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-controlled-code-validation-packages.md`

## AF-080 — Local package catalog

- Status: completed
- Parent objective: Agent Application Framework
- Scope: deterministically discover, validate, and exact-select portable manifests from explicit local directories without loading or executing packages.
- Dependencies: AF-060, AF-070
- Acceptance: explicit roots produce a deterministic fail-closed catalog whose exact selections compose both reference graphs without network, installation, or implicit version policy.
- Design: `docs/superpowers/specs/2026-07-13-local-package-catalog-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-local-package-catalog.md`

## AF-090 — Static application assembly

- Status: completed
- Parent objective: Agent Application Framework
- Scope: bind one runtime identity, exact catalog package refs, and explicit host-service edges into a deterministic auditable composition plan without execution.
- Dependencies: AF-040, AF-080
- Acceptance: both reference applications resolve through the shared runtime/catalog/composer contracts with cross-language validation and no execution side effects.
- Design: `docs/superpowers/specs/2026-07-13-static-application-assembly-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-static-application-assembly.md`

## AF-100 — Application runner vertical slice

- Status: in_progress
- Parent objective: Agent Application Framework
- Scope: execute one resolved DCI application plan through an explicitly supplied runtime client and host services, returning normalized immutable events/artifacts without a general workflow engine.
- Dependencies: AF-020, AF-030, AF-090
- Acceptance: Pi and Claude fixture runtimes satisfy the same plan-driven runner contract; runtime/service mismatch, cancellation, malformed streams, and unsafe errors fail closed before accidental execution.
- Design: `docs/superpowers/specs/2026-07-13-application-runner-vertical-slice-design.md`
- Plan: pending written-spec approval
