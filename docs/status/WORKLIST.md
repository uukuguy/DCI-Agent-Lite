# Framework Worklist

> Canonical work-package ledger. An `active` lifecycle requires exactly one `in_progress` package; a `complete` lifecycle permits none and forbids autonomous dispatch.

> Project lifecycle: active

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

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: run the full Asterion DCI package through application assemblies, complete the Pi parity matrix, and assess Claude semantic parity only with separately authorized provider-backed evidence.
- Dependencies: AF-180, AF-190, AF-200
- Acceptance: Asterion application execution and package-local operations share one full DCI implementation; Pi parity is complete, while Claude remains explicitly fixture-only until separately authorized provider-backed evidence exists.
- Design: `docs/superpowers/specs/2026-07-13-dci-application-runtime-parity-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-dci-application-runtime-parity.md`
- Closure evidence: AF-210-H-001 through H-004 are confirmed 4/4. The first-party DCI provider binds native Pi execution without generic CLI/runner coupling; installed Pi applications produce body-free native references, redact native failures, and ship the executor/provider in the Asterion wheel. Full Python product tests, compile/Ruff/shell checks, TypeScript tests, Rust checks, scope audit, and diff check pass without Pi, judge, or Claude provider requests. Claude remains a fixture-only protocol path, not a semantic-parity claim.

## AF-220 — Shared configuration and runnable Pi application parity

- Status: completed
- Parent objective: Asterion DCI complete capability-package reference product
- Scope: replace the prior split configuration assumption with the approved shared `.env` contract, carry effective Pi/provider/model/tool/context configuration through Asterion package, benchmark, and installed-application paths, and provide Pi-default Asterion runnable examples.
- Dependencies: AF-180, AF-190, AF-200, AF-210
- Acceptance: Asterion and source DCI share normal `DCI_*` configuration without an Asterion runtime dependency on the source product; package CLI and installed Pi application construct equivalent native requests; configuration/context/resource mappings and two Asterion example launchers pass fixture, installed-wheel, and authorized bounded Pi checks.
- Design: `docs/superpowers/specs/2026-07-13-asterion-dci-complete-product-parity-design.md`
- Plan: `docs/superpowers/plans/2026-07-14-af-220-shared-config-runnable-pi.md`
- Closure evidence: AF-220-H-001 through H-004 remain confirmed 4/4. With process-local shared configuration and no copied data, model-free Pi/Judge configuration checks, both Asterion Pi examples, the project-entrypoint installed application, and one-row Pi-plus-Judge benchmark all exit zero. Native states and evaluation artifacts validate by schema; the application emits one body-free JSON projection. This is AF-220 parity only, not a claim of full source-product parity.

## AF-230 — Complete native operator and artifact parity

- Status: completed
- Parent objective: Asterion DCI complete capability-package reference product
- Scope: close remaining source-DCI single-run, terminal, context/resource, artifact, provenance, and resume controls in independently owned Asterion code.
- Dependencies: AF-220
- Acceptance: every remaining native operator and artifact behavior is explicitly mapped to Asterion-owned implementation or recorded as an approved unsupported boundary; the production path uses one private atomic recorder, credential-safe provenance, isolated attempts, single-writer compatible resume, and a direct TTY-only terminal command, with executable fixture and small-sample acceptance evidence.
- Design: `docs/superpowers/specs/2026-07-13-asterion-dci-complete-product-parity-design.md`
- Plan: `docs/superpowers/plans/2026-07-14-af-230-native-operator-artifact-parity.md`
- Closure evidence: AF-230-H-001 through H-004 are confirmed 4/4. The sole production path uses a private descriptor-relative atomic recorder, complete and processed conversation views, credential-safe Pi provenance, digest-bound isolated protocol attempts, strict single-writer resume validation, complete package-local inputs/resources, and a literal TTY-only Pi terminal command. Full closure passes 529 Python, 11 Node, and 19 Rust tests plus compile, Ruff, shell, scope, and diff gates. One authorized Pi-default `asterion-dci run` completed with 314 raw events, 40 valid protocol events, five externalized tool results, private parseable artifacts, truthful completed latest-context state, safe provenance, a matching final digest, and a body-free application projection; no Judge request was used.

## AF-240 — Complete batch, evaluation, and export parity

- Status: completed
- Parent objective: Asterion DCI complete capability-package reference product
- Scope: transplant concurrent BCPlus, QA, and BRIGHT orchestration, Judge/evaluation behavior, IR metrics, summaries, exports, and result analysis into independently owned Asterion code.
- Dependencies: AF-230
- Acceptance: bounded concurrent Asterion batch paths reuse the native run/evaluator boundaries, preserve deterministic cache and per-query state, and reproduce source-product dataset, metric, summary, export, and analysis semantics without importing or launching `src/dci`.
- Design: `docs/superpowers/specs/2026-07-13-asterion-dci-complete-product-parity-design.md`
- Plan: `docs/superpowers/plans/2026-07-14-af-240-batch-evaluation-export-parity.md`
- Closure evidence: AF-240-H-001 through H-004 are confirmed 4/4 and all 533 inventory rows have resolvable executable Asterion evidence. Concurrent QA/IR batches, exact reuse, Judge caching, aggregates, detailed analysis/figures, exports, installed profiles, and all 12 launchers pass 1204 Python, 11 TypeScript, and 19 Rust tests plus compile, Ruff, shell, scope, diff, and isolated-wheel gates. A bounded one-row Pi-plus-Judge batch completed with one correct verdict and 28 credential-clean private artifacts; an exact reuse rerun preserved native/Judge hashes and mtimes, kept one protocol attempt, and created no second generation or external request. No full dataset ran.

## AF-250 — Product acceptance matrix

- Status: completed
- Parent objective: Asterion DCI complete capability-package reference product
- Scope: make every complete-product parity matrix row executable and record reproducible local, Pi, and Pi-plus-Judge evidence.
- Dependencies: AF-240
- Acceptance: the checked-in matrix has no unsupported source behavior and every row has reproducible fixture or bounded provider-backed evidence before any full-parity conclusion.
- Closure evidence: all eight local/model-free rows pass; all 533 delegated batch selectors, twelve launcher pairs, six batch extras, and AF-250-H-001 through H-005 pass. Seven bounded real source/Asterion/application/Pi-plus-Judge/reuse cases completed successfully; the credential-clean body-free manifest is digest-bound into the product matrix, and the private-artifact verifier independently recomputes its modes/hashes plus completion, Judge, and exact-reuse invariants. Final terminal closure passes 1275 Python, 11 TypeScript, and 19 Rust tests plus compile, Ruff, shell, scope, terminal-dispatch rejection, diff, installed-wheel/application, and both acceptance-verifier modes; independent review has no Critical or Important findings. No full dataset ran. The complete procedure is `asterion/docs/verification/asterion-dci-validation-guide.md`.
- Design: `docs/superpowers/specs/2026-07-13-asterion-dci-complete-product-parity-design.md`
- Plan: `docs/superpowers/plans/2026-07-15-af-250-product-acceptance-matrix.md`

## AF-270 — Capability discovery and unified verification

- Status: completed
- Parent objective: Asterion capability-package product usability
- Scope: add generic provider-selected `asterion describe` and structured `asterion verify` commands, then prove them with DCI preflight, basic, acceptance, and complete profiles.
- Dependencies: AF-130, AF-220, AF-250
- Acceptance: users discover DCI functions and required configuration without reading code; one generic command runs two bounded basic cases or the complete no-full-dataset verification; outputs are redacted, installed-wheel safe, and reusable by future providers.
- Design: `docs/superpowers/specs/2026-07-15-asterion-capability-discovery-verification-design.md`
- Plan: `docs/superpowers/plans/2026-07-15-asterion-capability-discovery-verification.md`
- Closure evidence: generic provider-selected `asterion describe` and `asterion verify` expose DCI functions, shared configuration, and four verification levels without loading adjacent providers. Trusted source discovery prevents installed-wheel/current-directory verifier execution; both basic Pi cases have six-turn limits; private retained evidence is actually revalidated with body-free failures; cost output distinguishes three provider-backed operations from underlying API requests. One real `complete` run passed both Pi cases, Judge, 8/8 product rows, 533/533 delegated selectors, 12/12 launcher pairs, 6/6 extras, and 7/7 bounded acceptance with no full dataset. Final closure passes 1297 Python, 11 TypeScript, and 19 Rust tests plus compile, Ruff, shell, scope, diff, fmt, and Clippy gates; final independent review reports no Critical or Important findings. The beginner guide is `asterion/docs/guides/asterion-capability-usage.md`.

## AF-280 — Makefile capability verification entry points

- Status: completed
- Parent objective: Asterion capability-package product usability
- Scope: expose the accepted DCI capability discovery and four verification levels through explicit Make targets with documented, overridable repository defaults.
- Dependencies: AF-270
- Acceptance: five explicit Make targets map exactly to `asterion describe` and the preflight/basic/acceptance/complete verification levels; provider-backed targets remain visibly explicit; defaults use the shared root `.env`, repository corpus, and Asterion verification output; README and beginner guide document the targets; dry-run and focused tests prove exact argv without running models.
- Design: `docs/superpowers/specs/2026-07-16-asterion-make-entry-points-design.md`
- Plan: `docs/superpowers/plans/2026-07-16-asterion-make-entry-points.md`
- Closure evidence: five explicit phony targets map exactly to capability description and preflight/basic/acceptance/complete verification, with overridable provider, `.env`, corpus, and output defaults. No ambiguous verification alias exists. Exact dry-run argv tests pass; live `make asterion-describe` and provider-free `make asterion-verify-acceptance` pass with zero provider-backed operations and no full dataset. README and the beginner guide document cost-visible usage. Closure passes 15 focused tests, compile, Ruff, scope, and diff gates.

## AF-290 — Complete product, framework, and extraction documentation

- Status: completed
- Parent objective: Asterion product comprehensibility and independent-project readiness
- Scope: create a complete Asterion DCI product reference, framework/capability integration guide, and standalone extraction design; reconcile misleading context-management and benchmark claims without moving implementation directories.
- Dependencies: AF-250, AF-270, AF-280
- Acceptance: the documents distinguish implemented behavior, executable verification, external-Pi limitations, and unrerun full-dataset evidence; explain every canonical Asterion layer and the current top-level compatibility/reference directories; provide a complete capability-to-application integration path; enumerate the self-contained wheel and external dependencies; define a phased standalone repository extraction with gates and non-goals; README and documentation indexes link the set; stale contradictory context-management guidance is corrected.
- Design: `docs/superpowers/specs/2026-07-16-asterion-documentation-set-design.md`
- Plan: `docs/superpowers/plans/2026-07-16-asterion-complete-documentation.md`
- Closure evidence: three canonical documents now cover the complete DCI product, all framework/capability/application integration layers, and a seven-phase standalone extraction. They label implementation, verification, current external-Pi runtime-context limits, and unrerun full-dataset results separately; the documentation hub and root README expose the set, and stale Pi context-level commands are removed. Closure passes 16 focused documentation/distribution tests, compile, Ruff, CLI help/description, local-link, scope, and diff gates without provider requests or a full dataset.

## AF-300 — Asterion top-level project root convergence

- Status: completed
- Parent objective: Asterion framework comprehensibility and standalone readiness
- Scope: converge the Python product, TypeScript/Rust packages, schemas, examples, Asterion scripts, product documentation, and Asterion-owned tests beneath a complete top-level `asterion/` project root while retaining original DCI and cross-product evidence at the repository root.
- Dependencies: AF-290
- Acceptance: `asterion/` is the sole complete Asterion project root and independently buildable/testable without `src/dci`; obsolete product roots disappear; root parity still validates original DCI against Asterion; Python, TypeScript, Rust, schemas, examples, scripts, docs, 533 selectors, 12 launchers, distribution/isolated-wheel, static, and governance gates pass without provider requests; full datasets and release packaging remain deferred.
- Design: `docs/superpowers/specs/2026-07-16-asterion-repository-directory-convergence-design.md`
- Plan: `docs/superpowers/plans/2026-07-16-af-300-asterion-project-root-convergence.md`
- Closure evidence: Tasks 1–5 are committed through `6fd4a0b`; Task 6 rejects every obsolete product root, repairs trusted-source discovery to the converged subtree, and passes 90 project-local plus 1230 root Python tests, 11 TypeScript tests, 19 Rust tests, compile, Ruff, fmt, Clippy, shell, diff, and governance gates. Provider-free acceptance is 8/8 product rows, 533/533 delegated selectors, 12/12 launcher pairs, 6/6 extras, 7/7 retained bounded cases, and zero provider-backed operations. An isolated `asterion-0.1.0-py3-none-any.whl` installs both CLIs/providers, contains all four capability/application resource groups, and excludes original DCI, examples, tests, and repository paths. The immutable acceptance record, its seven-case count, private artifact hashes, and full-dataset status are unchanged; the Task 6 implementation hash is recorded by the immediately following append-only JOURNAL commit.
- Review remediation: `d5b5cd6` corrects the three final-review documentation/CWD contracts and the mixed-root structural snapshot. Focused documentation/distribution/path tests, both CWD probes, CLI/config dry checks, compile, Ruff, scope, and diff pass without production behavior changes, provider/Judge execution, datasets, or release work.
- Final command remediation: `147d1d7` replaces the standalone guide's invalid `provider-free` level with the real provider-free `acceptance` profile; exact argv, focused docs/distribution/CLI, parser/profile dry, compile, Ruff, scope, and diff checks pass.

## AF-310 — Paper-aligned runtime context management

- Status: completed
- Parent objective: Paper-aligned complete DCI implementation in Asterion
- Scope: implement and ship the exact DCI paper L0–L4 live context-management contract through an Asterion-owned Pi extension, then expose one immutable implementation through run, benchmark, resume, installed application, and isolated-wheel execution without modifying external Pi.
- Dependencies: AF-300
- Acceptance: Asterion owns and ships exact L0–L4 profiles; every public surface selects the same implementation; fixtures prove model-visible transformations and failure boundaries; bounded Pi runs force and observe L3 compaction and L4 summarization; external `pi/` remains unmodified; documentation distinguishes implemented, model-free verified, bounded provider verified, and experiment-reproduced evidence.
- Design: `docs/superpowers/specs/2026-07-16-paper-aligned-dci-complete-implementation-design.md`
- Plan: `docs/superpowers/plans/2026-07-16-af-310-paper-aligned-runtime-context-management.md`
- Closure evidence: AF-310-H-001 through H-005 are confirmed 4/4. The shipped dependency-free extension and Python consumers use closed telemetry/state/public-evidence v2 schemas, expose identical digest-bound L0–L4 policy through CLI, benchmark, resume, installed application, and isolated wheel, and preserve cancellation/deadline boundaries. Final clean-checkout r9 forced one L3 compaction with twelve observed preserved user turns and no summary plus one L4 compaction with one successful unsuppressed summary in exactly two bounded Pi operations and thirteen user turns per case. The 0600 body-free report and six private artifact digests are rehashed into immutable Climb evidence; the external `pi/` was not modified, no Judge or full dataset ran. Closure passes 1288 Python and 11 TypeScript tests, Ruff, compile, product 8/8, 533/533 delegated selectors, 12/12 launcher pairs, 6/6 extras, installed application/wheel, scope, and diff gates.

## AF-320 — Paper benchmark and metric parity

- Status: completed
- Parent objective: Paper-aligned complete DCI implementation in Asterion
- Scope: ship the paper's exact thirteen-dataset inventory and experiment-specific selection identities, correct BEIR NDCG@10, trajectory coverage/localization/retained-evidence analysis, and deterministic paper-declared plus bounded ablation surfaces through the existing Asterion DCI product.
- Dependencies: AF-310
- Acceptance: schema-closed dataset/scope resources and product surfaces pass source/installed/wheel parity; unpublished BrowseComp samples remain explicitly Asterion-defined, unpublished FineWeb distractor selections remain explicitly unbound, and Bamboogle full-125 remains distinct from the migrated sample-50 profile; native immutable evidence produces exact coverage and matched-gold localization metrics; full paper rows remain unconditionally non-executable before AF-340; bounded functional acceptance uses exactly two Pi agent operations and one configured Judge operation, binds the effective Judge identity without a full dataset or score-reproduction claim, and reserves paper-model/score comparability for AF-340.
- Design: `docs/superpowers/specs/2026-07-17-af-320-paper-benchmark-metric-parity-design.md`
- Plan: `docs/superpowers/plans/2026-07-17-af-320-paper-benchmark-metric-parity.md`
- Closure evidence: AF-320-H-001 through H-004 are confirmed 4/4. Asterion ships the exact thirteen-dataset and sixteen-scope inventory, corrected BEIR NDCG@10, exact coverage/localization/retained-evidence metrics, conservative native trajectory alignment, a closed deterministic paper/bounded ablation matrix, product/CLI/export/installed-wheel parity, and a model-free default verifier. Final bounded evidence ran exactly two Pi agent operations and one configured DeepSeek Judge operation against a clean checkout at the locked revision; no full dataset ran. The v2 report binds safe Judge request identity and private artifact digests, and the terminal binder rehashes them into tracked evidence `0d48c9f24a6a54335c8e80d4569ddb0e8ad6635c10c4849e6ec1cb3f171ccd55`. Closure passes 1394 full Python tests, 246 final selectors, product 8/8, 533/533 delegated selectors, 12/12 launcher pairs, 6/6 extras, 7/7 retained bounded cases, isolated wheel, compile, Ruff, scope, diff, clean-runtime, idempotence, and credential/body-free gates. GPT-4.1 and published-score comparability remain AF-340 experiment provenance, not AF-320 functional acceptance.

## AF-330 — Complete application and dual-runtime exposure

- Status: completed
- Parent objective: Paper-aligned complete DCI implementation in Asterion
- Scope: make research, evaluation, benchmark, analysis, and export distinct executable capability/application units with exact event/artifact edges, then prove the restricted local-corpus application with bounded real Pi and Claude Code runs.
- Dependencies: AF-320
- Acceptance: product CLI, generic application, installed application, and isolated wheel share implementation/artifact identity; Pi and Claude Code share domain contracts and one `DCI_PROVIDER`/`DCI_MODEL` agent selection with adapter-owned provider translation; both real bounded runtimes prove attempt-local corpus access without web, subagents, Bash, outside answer-bearing access, or public body/path leakage; cancellation, deadline, failure, resume, privacy, configuration redaction, and evidence binding pass; fixture-only Claude evidence and full datasets cannot close the package.
- Design: `docs/superpowers/specs/2026-07-17-af-330-complete-application-dual-runtime-design.md`
- Plan: `docs/superpowers/plans/2026-07-17-af-330-complete-application-dual-runtime.md`
- Closure evidence: AF-330-H-001 through H-004 are confirmed 4/4. One exact five-stage research/evaluation/benchmark/analysis/export graph executes through Pi and Claude Code with shared domain contracts, adapter-owned provider translation, exact stage identities, cancellation/deadline/failure safety, original `asterion-dci resume`, and body-free public evidence. Bounded real Pi and final r12 MiniMax-M3 Claude Code runs each stayed inside an attempt-local corpus without Bash, web, subagents, or a full dataset and completed one configured DeepSeek evaluation. The r12 terminal verifier replays raw Claude JSONL through the production adapter and binds report `07a69074…bce2`, tracked record `a62e62cd…ae89`, implementation `613578bd…6477`, and descendant-safe source `f3e2528`; Climb cycle 103 independently confirms it. Closure passes 1396 root Python, 123 Asterion, 11 TypeScript, 19 Rust, product 8/8, 533/533 delegated selectors, 12/12 launchers, 6/6 extras, 7/7 bounded cases, isolated wheel, compile, Ruff, shell, fmt, Clippy, scope, diff, and actual-key privacy gates. Final independent review reports no Critical, Important, or Minor findings. Full-dataset and paper-score reproduction remain outside this completed lifecycle pending separately authorized AF-340 governance.

## AF-340 — README reproduction and runtime-result parity

- Status: in_progress
- Parent objective: Reproduce the documented DCI product and establish Asterion runtime-result parity
- Scope: implement one layered `.env`/environment/CLI/application configuration contract with runtime-aware agent defaults and an independent DeepSeek Judge default; make the original README Quick Start, Context Management Strategies, and Benchmark DCI-Agent-Lite paths executable; then run the same Pi experiment contract and the paper's Claude Code path through Asterion source, application, and installed-wheel surfaces with bounded and explicitly authorized full-result comparison.
- Dependencies: AF-330
- Acceptance: original DCI and Asterion independently emit the same safe effective-configuration schema; Pi defaults to `openai-codex`/`gpt-5.6-luna`, Claude Code supports local subscription login and explicit compatible MiniMax Coding Plan translation, and Judge defaults to DeepSeek V4 Flash while every value remains overrideable through the unified precedence layers; all eleven documented benchmark launchers, Quick Start, and L0-L4 paths pass local and bounded gates; full execution requires explicit invocation authorization and records exact per-query evidence, 95% confidence intervals, paired original/Asterion Pi non-inferiority, and separately identified Asterion Claude Code target comparison without credential or body leakage.
- Design: `docs/superpowers/specs/2026-07-18-af-340-readme-reproduction-runtime-parity-design.md`
- Plan: gated by user review of the committed design; `writing-plans` is the next authorized action.

## AF-095 — Asterion framework identity and extraction

- Status: completed
- Parent objective: Asterion Agent Application Framework
- Scope: establish Asterion as the independent top-level framework, extract generic Python modules from `dci`, and preserve existing DCI imports, CLI, examples, and wire literals through compatibility boundaries.
- Dependencies: AF-090
- Acceptance: Asterion owns the sole generic implementation; DCI depends on it as a capability/application; both verified DCI examples and all cross-language gates remain compatible.
- Design: `docs/superpowers/specs/2026-07-13-asterion-framework-extraction-design.md`
- Plan: `docs/superpowers/plans/2026-07-13-asterion-framework-extraction.md`
