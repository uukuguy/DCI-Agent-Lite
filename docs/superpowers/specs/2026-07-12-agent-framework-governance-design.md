# Agent Application Framework and Scope Governance Design

> Status: approved direction reconstructed from the user's original requirement on 2026-07-12. This document is the design baseline; implementation is tracked through `docs/status/WORKLIST.md` once that control plane exists.

## Problem

DCI-Agent-Lite began as a Pi-based DCI benchmark harness. A later product direction expanded the goal to a reusable agent-application framework spanning multiple agent runtimes, capability packages, and Python/TypeScript/Rust products. That decision remained only in conversation. The durable state consequently presented Pi/Judge maintenance as the project theme, and autonomous `climb` work advanced unrelated reliability hypotheses.

The correction must both establish the framework architecture and prevent unparented maintenance work from replacing the approved product objective.

## Product Direction

Build an agent-application framework that:

- normalizes execution across Pi, Claude Code, Hermes-agent, Pydantic AI, LangGraph, and later compatible runtimes;
- exposes composable capability packages that can implement DCI-style direct-corpus research and other agentic workflows;
- provides coherent Python, TypeScript, and Rust surfaces for their respective enterprise roles; and
- carries policy, artifacts, observability, evaluation, and lifecycle semantics across all runtimes.

The existing DCI benchmark remains a reference workload and an initial capability package. It is not the product boundary.

## Chosen Architecture

### 1. Language-neutral runtime contract

Define a versioned Agent Runtime Protocol before adding adapters. Its canonical contract includes:

- task/run/session start, input, cancel, and completion;
- capability manifests and negotiated degraded behavior;
- normalized streaming events for text, reasoning visibility where supported, tool calls/results, usage, artifacts, warnings, and failures;
- artifact references, provenance, cancellation, deadlines, and terminal status; and
- a portable wire representation suitable for JSON Schema plus JSONL local-process transport first.

The contract is the only common dependency shared by adapters and language hosts. It prevents an N-by-M integration matrix.

### 2. Runtime adapters

Adapters translate native runtime behavior into the contract without claiming unavailable features. The staged order is:

1. Pi reference adapter, preserving the existing hardened JSONL RPC boundary.
2. One independent second runtime, selected during the first vertical-slice plan.
3. Native Python adapters for Pydantic AI and LangGraph.
4. CLI/service adapters for Claude Code and Hermes-agent when their supported integration contracts are confirmed.

An adapter advertises its capabilities; orchestration and applications must not infer parity from its name.

### 3. Composable functional packages

Functional packages depend on the contract, never directly on a particular runtime:

- `research.dci`: direct local-corpus investigation, constrained tool policy, evidence/artifact capture, and evaluation hooks;
- tool and policy packages: filesystem, shell, corpus/search, permissions, deadlines, and sandbox boundaries;
- workflow packages: task decomposition, handoff, and supervisor patterns after the single-run contract is proven;
- platform packages: artifacts, telemetry, memory interfaces, auditability, and evaluation; and
- enterprise application templates, added only after the underlying packages have stable conformance coverage.

### 4. Language responsibilities

| Surface | Primary role | Initial boundary |
|---|---|---|
| Python | evaluation, research/data workflows, orchestration, Pydantic AI/LangGraph integration | continue to host existing benchmark logic while it is moved behind the contract |
| TypeScript | Node-native runtime adapters, services, web/realtime integrations | host Pi and later compatible Node/CLI integrations |
| Rust | controlled tool executor, isolation sidecar, high-throughput infrastructure | do not duplicate the orchestration layer in the first release |

### 5. Enterprise cross-cutting boundaries

The protocol and packages must preserve policy enforcement, secret boundaries, provenance, event observability, artifact retention, evaluation, and cancellation. Authentication, tenancy, remote service transport, and a full sandbox product are explicitly later work unless a package acceptance criterion adds them.

## Scope Governance

### Canonical files and roles

- `docs/architecture/agent-framework.md`: durable north-star architecture, supported runtime strategy, language roles, and non-goals.
- `docs/status/WORKLIST.md`: the only active multi-package worklist. Each item has an ID, parent objective, scope, dependencies, acceptance criteria, status, owner, and design/plan links.
- `docs/status/CURRENT-STATE.md`: structural snapshot that points to the north star and identifies the active work-package theme.
- `docs/status/RESUME-NEXT-SESSION.md`: names the exact active work-package ID and its next action.
- `docs/status/DECISIONS.md`: durable architectural decisions and their revalidation triggers.
- `docs/status/JOURNAL.md`: immutable chronology of package transitions, commits, verification, and ruled-out paths.

### Mandatory scope gate

Before design, dispatch, implementation, autonomous experimentation, or a maintenance change:

1. Read the north-star architecture, worklist, current state, resume baton, and recent journal.
2. Identify exactly one `WORKLIST` package ID and verify that its status permits the action.
3. Verify that the action's scope and acceptance criteria are stated by that package.
4. If no package matches, create or amend a worklist item through `ai-project-manager`; do not begin implementation.
5. Treat reliability, security, and `climb` work as child work only. It requires an explicit parent work package or direct user authorization.
6. Stop and escalate when the requested work changes the north-star architecture, external contract, security boundary, or package scope.

### Mechanical audit

Add a repository check that reports failure when any of these conditions holds:

- the active worklist has no architecture link;
- an `in_progress` item lacks scope, acceptance criteria, dependencies, or a design/plan link;
- more than one package is `in_progress` without an explicit concurrency justification;
- the resume baton omits its active package ID or names a non-active package;
- current state omits the north-star architecture or contradicts it; or
- a `climb` session targets an unparented work package.

The check is a guardrail, not a substitute for architectural review. It must run before a manager dispatches work and before a work-package closeout.

### `ai-project-manager` repair

The skill must be amended to require this preflight and to make the coordinator reject unscoped work. It must also require:

- dependency-aware package selection and explicit scope/acceptance review before parallel dispatch;
- a package transition update only after verification evidence is available;
- a recovery rule that halts autonomous work whenever state files disagree; and
- a repair loop: a detected process failure becomes a tracked governance improvement, with its own verification before future dispatch.

## Alternatives Considered

1. **Continue with Pi/Judge reliability as the main roadmap.** Rejected: it improves a reference runtime but does not build the requested multi-runtime product.
2. **Build one framework implementation per language before defining a contract.** Rejected: this produces incompatible abstractions and expensive cross-language reconciliation.
3. **Protocol-first vertical slices.** Chosen: establish one contract, prove it with Pi plus an independent adapter, then expand functionality and language surfaces behind conformance tests.

## Work Package Sequence

| ID | Outcome | Dependencies | Initial acceptance |
|---|---|---|---|
| AF-000 | North star, worklist, scope gate, manager repair, and audit | none | resume recovers the framework objective and rejects unscoped work |
| AF-010 | Versioned Agent Runtime Protocol and conformance fixtures | AF-000 | fixture suite defines run/event/artifact/cancellation semantics |
| AF-020 | Pi reference adapter migrated behind the protocol | AF-010 | existing DCI run yields conformant normalized events/artifacts |
| AF-030 | Second runtime adapter vertical slice | AF-010 | the same `research.dci` capability passes its defined cross-runtime acceptance |
| AF-040 | Python and TypeScript host SDK boundaries | AF-020, AF-030 | each host consumes the protocol without adapter-private types |
| AF-050 | Rust executor/sidecar boundary | AF-010, relevant capability design | a controlled tool-execution contract is conformant without duplicating orchestration |
| AF-060 | Workflow, memory, governance, and enterprise packages | AF-020, AF-030 | packages compose through declared capabilities and policy boundaries |

Only AF-000 is authorized by this design document. Later packages require their own plan and acceptance evidence.

## Acceptance for AF-000

- A new session can recover the framework north star and its next active work package from repository files alone.
- An autonomous or manager-driven action without a valid work-package ID is rejected before implementation.
- Pi/Judge reliability work is visibly classified as maintenance under a parent package, deferred, or explicitly authorized; it cannot silently become the roadmap.
- `ai-project-manager` includes the mandatory preflight, stop conditions, and repair-loop instructions.
- The repository audit intentionally detects malformed worklist/resume examples and passes for the valid repository state.

## Non-goals

- Implementing every listed runtime adapter in AF-000.
- Rewriting the existing Pi process integration immediately.
- Promising identical reasoning traces or native tool semantics across runtimes.
- Adding a production multi-tenant control plane before the contract and reference slices are verified.
