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
- Availability evidence: 2026-07-13 probe found the supported Claude Code CLI 2.1.199 but no stored login and no configured compatible gateway. No provider request was sent; this package remains active solely for the externally authorized acceptance.
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

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: execute one resolved DCI application plan through an explicitly supplied runtime client and host services, returning normalized immutable events/artifacts without a general workflow engine.
- Dependencies: AF-020, AF-030, AF-090, AF-095
- Acceptance: Pi and Claude fixture runtimes satisfy the same plan-driven runner contract; runtime/service mismatch, cancellation, malformed streams, and unsafe errors fail closed before accidental execution.
- Design: `docs/superpowers/specs/2026-07-13-application-runner-vertical-slice-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-application-runner-vertical-slice.md`
- Closure evidence: all four hypotheses are confirmed; 284 Python, 11 Node, and 19 Rust tests plus compile, lint, format, shell, scope, and diff gates pass. Formal status waits only for governed successor selection.

## AF-110 — Composable capability execution

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: define exact reusable package-implementation bindings and deterministic sequential execution, then prove the DCI local-corpus research capability through an explicit application host without importing or modifying the DCI benchmark baseline.
- Dependencies: AF-100
- Acceptance: immutable selected declarations, exact implementation preflight, declared event/artifact validation, cancellation and safe failures, independent DCI implementation, Pi/Claude fixture parity, cross-application reuse, and baseline isolation pass all repository gates.
- Design: `docs/superpowers/specs/2026-07-13-composable-capability-execution-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-composable-capability-execution.md`
- Closure evidence: exact implementation binding, immutable declarations/results, sequential artifact routing, cancellation/failure containment, independent DCI capability packaging, independent Pi runtime, explicit host composition, cross-application reuse, and baseline isolation pass 311 Python, 11 Node, and 19 Rust tests plus compile, lint, shell, scope, and diff gates. A provider-backed Asterion probe produced the declared research event/artifact; the separate baseline example completed but scored false after its six-turn limit.

## AF-120 — Installed application binding and generic entry point

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: ship one self-contained Asterion distribution containing modular capability/application implementations, define a security-reviewed provider boundary for built-in and future external applications, expose the generic `asterion run <assembly>` entry point, and keep `src/dci` as a repository-only runnable baseline excluded from all wheels.
- Dependencies: AF-110
- Acceptance: the single Asterion wheel runs its DCI application through exact provider bindings without arbitrary dynamic imports, implicit service discovery, or baseline coupling; canonical resources are included once; `src/dci` remains runnable in-repository and produces no wheel.
- Design: `docs/superpowers/specs/2026-07-13-installed-application-binding-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-installed-application-binding.md`
- Closure evidence: one isolated `asterion==0.1.0` wheel contains framework, DCI capability/application code, four canonical manifests, three canonical assemblies, built-in provider metadata, and the explicit `pi.reference` runtime factory while excluding `dci`. The repository-only baseline remains source-runnable without changes under `src/dci/benchmark/`. Full closure passes 335 Python, 11 Node, and 19 Rust tests plus compile, Ruff, shell, scope, diff, isolated install, `asterion list`, resource, and import-boundary gates.

## AF-130 — Installed application selection and product usability

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: make installed Asterion applications discoverable and runnable by exact application identity without requiring operators to locate package-internal assembly paths, while retaining explicit provider/runtime selection and all AF-120 trust boundaries.
- Dependencies: AF-120
- Acceptance: the installed wheel lists exact application identities and runs the built-in DCI application through a stable application selector; ambiguous or unknown identities fail before provider/runtime work; filesystem assembly selection remains an explicit advanced compatibility path.
- Design: `docs/superpowers/specs/2026-07-13-installed-application-selection-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-installed-application-selection.md`
- Closure evidence: exact immutable selector parsing, selected-provider application listing, `--application`, explicit `--assembly`, legacy positional compatibility, pre-load conflict rejection, DCI-neutral generic modules, and isolated installed-wheel discovery pass 342 Python, 11 Node, and 19 Rust tests plus compile, Ruff, shell, scope, diff, and no-baseline-import gates.

## AF-140 — Controlled-code executable application vertical slice

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: turn the existing controlled-code policy/workflow/evaluation/observability graph into a second executable bundled Asterion application using explicit package implementations and the existing controlled-executor host-service boundary.
- Dependencies: AF-050, AF-070, AF-110, AF-130
- Acceptance: the second installed application is discoverable by exact identity and executes through the same generic provider/runner contracts without DCI-specific coupling; executor authority remains explicit and no sandbox claim, automatic service startup, or workflow scheduler is introduced.
- Design: `docs/superpowers/specs/2026-07-13-controlled-code-executable-application-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-controlled-code-executable-application.md`
- Closure evidence: the separate `controlled-code` provider binds declarative policy plus exact workflow/evaluation/observability implementations; one logical target reaches one explicitly injected service and produces declared report/verdict/audit outputs. Caller-owned JSONL transport connects to the existing Rust sidecar without process startup or output-body persistence. Closure passes 352 Python, 11 Node, and 19 Rust tests plus compile, Ruff, shell, scope, diff, isolated wheel, two-provider listing, and no-baseline-import gates.

## AF-150 — Controlled executor operator lifecycle

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: define an explicit operator-authorized lifecycle for connecting or starting the controlled-executor service so the installed `controlled-code` application can run through the generic CLI without weakening host-owned policy.
- Dependencies: AF-050, AF-140
- Acceptance: one reviewed CLI/configuration flow establishes trusted policy, process ownership, readiness, injection, cancellation, and shutdown; failures are redacted and no agent/provider/manifest can select commands or silently start services.
- Design: `docs/superpowers/specs/2026-07-13-controlled-executor-operator-lifecycle-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-controlled-executor-operator-lifecycle.md`
- Closure evidence: explicit all-or-none binary/policy/validation configuration is validated before runtime or child construction; the CLI starts exactly one direct-argv, minimal-environment sidecar, injects it only for the selected controlled-code plan, forwards correlated cancellation, drains diagnostics in bounded chunks, and reaps on shutdown. Full closure passes 362 Python, 11 Node, and 19 Rust tests plus compile, Ruff, shell, scope, and diff gates. A fresh isolated wheel lists both providers, excludes `dci`, and completes `code.quality@1.0.0` with the Rust sidecar.

## AF-160 — Installed Claude runtime interface verification

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: expose the existing Claude Code runtime through the installed Asterion runtime-factory boundary and prove its command, capability, environment, fixture-normalization, and unauthenticated safe-failure contracts without sending a provider request.
- Dependencies: AF-030, AF-120
- Acceptance: an installed wheel exposes exact `claude-code.reference` factory selection and preserves the existing restricted subprocess/normalization/redaction contract under fixture execution; no account, gateway, prompt, or provider request is required, and a future real invocation remains deferred.
- Design: `docs/superpowers/specs/2026-07-13-installed-claude-runtime-interface-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-installed-claude-runtime-interface.md`
- Closure evidence: exact `claude-code.reference` selection, fixture-only normalized events/redaction/pre-cancel, safe factory construction, isolated-wheel import boundary, documentation, and full Python/Node/Rust closure gates pass without a Claude request.

## AF-170 — Installed DCI Claude compatibility

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: design an explicit, fixture-verifiable `claude-code.reference` compatibility declaration for the installed DCI application while preserving Pi behavior and deferring real provider UAT.
- Dependencies: AF-120, AF-160
- Acceptance: approved design and plan define exact provider declaration, fixture-only generic CLI proof, Pi compatibility preservation, and the boundary for future real authorization.
- Design: `docs/superpowers/specs/2026-07-13-installed-dci-claude-compatibility-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-installed-dci-claude-compatibility.md`
- Closure evidence: generic runtime-specific assembly selection, paired immutable DCI Pi/Claude assemblies, bundled fixture-only generic CLI proof, isolated-wheel resources, Python/Node/Rust closure, compile/lint/shell/scope/diff gates all pass without a Claude request. A real provider-backed Claude run is not implied by this fixture contract; it is re-scoped under AF-210 only after the complete DCI implementation exists and authorization is supplied.

## AF-180 — Complete DCI capability execution parity

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: establish the independently owned Asterion DCI domain module and package-local operator CLI, transplant the original DCI single-run/Pi RPC/system-prompt/corpus/tool/final-answer behavior, and prove interactive Pi run parity without importing or executing `src/dci`.
- Dependencies: AF-110, AF-120, AF-170
- Acceptance: the Asterion-owned DCI implementation has a deterministic single-run Pi parity matrix, separate `ASTERION_DCI_*` configuration/output ownership, package-local run CLI, safe native artifacts, capability-contract bridge, and no runtime dependency on the legacy DCI product.
- Design: `docs/superpowers/specs/2026-07-13-complete-dci-capability-package-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-complete-dci-capability-execution.md`
- Closure evidence: AF-180-H-001 through H-004 are confirmed 4/4. The one Asterion wheel owns isolated `ASTERION_DCI_*` configuration, direct Pi JSONL single-run transport, minimal native artifacts and normalized protocol projection, `asterion-dci` operator commands, and a body-free capability-result bridge. Focused parity tests, full Python discovery, Python compile/Ruff, TypeScript tests, Rust tests, shell syntax, installed command help, scope audit, wheel proof, and diff check pass without a Pi, judge, or Claude provider request.

## AF-190 — Complete DCI durable run and resume parity

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: transplant native run-directory, raw-event, transcript, final-answer, state, and resume semantics and map their durable evidence to Asterion artifacts/events.
- Dependencies: AF-180
- Acceptance: stable fixture comparisons prove native artifact and resume parity while retaining the generic framework privacy boundary.
- Design: `docs/superpowers/specs/2026-07-13-complete-dci-capability-package-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-asterion-dci-durable-resume.md`
- Closure evidence: AF-190-H-001 through H-004 are confirmed 4/4. The independent Asterion DCI package records original-style transcripts, processed conversation/context, raw events, final/state/stderr, tool-result references, and isolated protocol attempts; `asterion-dci resume --output-dir` reconstructs only compatible failed/incomplete native state before Pi construction; package projections expose durable references without bodies. Focused parity/boundary tests, full Python discovery, Python compile/Ruff, TypeScript tests, Rust tests, shell syntax, workspace command help, scope audit, wheel proof, and diff check pass without Pi, judge, or Claude provider requests.

## AF-200 — Complete DCI evaluation and benchmark parity

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: transplant judge, cache identity, batch/dataset orchestration, result/export behavior, and package-local evaluation/benchmark entry points onto the Asterion DCI execution implementation.
- Dependencies: AF-180, AF-190
- Acceptance: focused fixture tests prove safe evaluation/cache behavior and batch paths reuse the Asterion DCI implementation rather than `src/dci`.
- Design: `docs/superpowers/specs/2026-07-13-complete-dci-capability-package-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-asterion-dci-evaluation-benchmark.md`
- Closure evidence: AF-200-H-001 through H-004 are confirmed 4/4. Independent judge configuration/request fingerprinting, cache-safe run-directory evaluation, deterministic explicit-JSONL benchmarking, product-local evaluate/benchmark commands, and conditional body-free evaluation projection pass all local gates without provider requests.

## AF-210 — Complete DCI application and runtime semantic parity

- Status: in_progress
- Parent objective: Asterion Agent Application Framework
- Scope: run the full Asterion DCI package through application assemblies, complete the Pi parity matrix, and assess Claude semantic parity only with separately authorized provider-backed evidence.
- Dependencies: AF-180, AF-190, AF-200
- Acceptance: Asterion application execution and package-local operations share one full DCI implementation; Pi parity is complete and any Claude claim has matching authorized evidence.
- Design: `docs/superpowers/specs/2026-07-13-complete-dci-capability-package-design.md`
- Plan: deferred until AF-200 acceptance.

## AF-095 — Asterion framework identity and extraction

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: establish Asterion as the independent top-level framework, extract generic Python modules from `dci`, and preserve existing DCI imports, CLI, examples, and wire literals through compatibility boundaries.
- Dependencies: AF-090
- Acceptance: Asterion owns the sole generic implementation; DCI depends on it as a capability/application; both verified DCI examples and all cross-language gates remain compatible.
- Design: `docs/superpowers/specs/2026-07-13-asterion-framework-extraction-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-asterion-framework-extraction.md`
