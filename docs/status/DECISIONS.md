# Architecture Decisions

## D-001 — Keep Python orchestration with hardened Pi RPC

- Status: 🟡 current situational judgment
- Decided: 2026-07-12
- Evidence: the benchmark, dataset, evaluation, artifact, and reporting paths are Python-heavy; the installed Pi documentation recommends RPC for cross-language integration and process isolation, while its TypeScript SDK is preferred in the same Node.js process.
- Decision: keep `dci-agent-lite` as the Python controller and use the hardened Pi JSONL RPC boundary.
- Rationale: process isolation is useful for benchmark runs, model/tool latency dominates the current workload, and a rewrite would duplicate stable Python evaluation logic without removing the need for a Python data path.
- Revalidate when: Node startup/RPC overhead exceeds roughly 5% of run time; persistent multi-session service behavior becomes central; direct Pi state or programmatic tool/extension customization is required; or Python no longer owns evaluation/reporting.
- If revalidated: prefer a thin persistent TypeScript Pi SDK sidecar before considering a full TypeScript rewrite.
- Rust position: do not use Rust for the controller under current conditions; Pi remains TypeScript-native, so Rust would still require RPC or a TypeScript bridge without a measured performance benefit.

## D-002 — Keep Pi as an independent external checkout

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: the parent repository tracks Pi resolution/setup configuration, not files from the Pi repository itself.
- Implementation: `DCI_PI_DIR` normally points to `./pi`; `./pi-mono` is a legacy fallback/compatibility name; both checkout paths remain ignored by the parent Git repository.
- Boundary: never include local `pi/` changes in DCI-Agent-Lite commits unless a task explicitly scopes a coordinated Pi change.
- Resolved follow-up: D-003 defines the reproducible revision policy and pins the verified fork commit.

## D-003 — Pin Pi through one tracked revision lock

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: `pi-revision.txt` is the sole default Pi revision source and contains a full immutable commit; `DCI_PI_REVISION` remains an explicit override.
- Initial pin: `8479bd84743e8889f728acb21a62794102db0529`, the fork commit used by the verified runtime acceptance run.
- Rationale: a single lock avoids moving-branch nondeterminism and duplicated configuration truth while preserving mirrors, forks, and deliberate upgrade tests.
- Safety boundary: setup may switch a clean mismatched checkout but must fail before changing a dirty mismatch; it never resets, cleans, stashes, or pulls the independent repository.
- Upgrade rule: change the lock in a reviewed commit, run setup-policy regressions plus runtime verification, and record the result before accepting the new baseline.
- Read-only review gate: `bash scripts/setup_pi.sh --check` verifies local commit availability, HEAD equality, and dirty state without clone, fetch, checkout, or build.

## D-004 — Gate Pi upgrades with a model-free RPC probe

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: `make check-pi-rpc` starts the pinned Pi CLI in RPC mode, sends `get_state`, validates the correlated response envelope and stable state-field types, then terminates without a model prompt.
- Rationale: protocol framing and response-shape drift should fail in under a second before a benchmark spends model tokens or creates partial run artifacts.
- Stable probe contract: response type/id/command/success plus boolean `isStreaming`/`isCompacting` and integer `messageCount`/`pendingMessageCount`.
- Boundary: the probe does not replace `make runtime-example`; provider/model execution, prompt acknowledgement, tool events, retries, and judge integration still require the end-to-end acceptance.

## D-005 — Persist actual Pi source provenance in run artifacts

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: every RPC run records `pi_source` in `state.json`, `conversation_full.json`, and `latest_model_context.json`.
- Evidence fields: detected Git root/origin, exact commit, dirty boolean, tracked lock revision, and `lock_match`; custom non-Git package directories use nullable Git fields.
- Rationale: an immutable setup default is insufficient if benchmark artifacts cannot prove which external source and local modification state produced the answer.
- Privacy boundary: artifacts record only the dirty boolean, never the external checkout's diff or credential contents.

## D-006 — Warn on Pi revision mismatch without blocking custom runs

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: before starting RPC, compare the actual Pi commit with `DCI_PI_REVISION` when explicitly set, otherwise `pi-revision.txt`; emit and persist a warning when they differ.
- Rationale: mismatch should be visible before model spend, but package-dir/fork experiments remain legitimate and must not be forcibly blocked.
- Artifact behavior: the warning is added to run notes, and `pi_source.expected_revision_source` distinguishes an explicit override from the tracked default.

## D-007 — Preflight the configured judge through its production transport

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: `make check-judge` sends one fixed trivial grading request through `JudgeConfig` and `judge_answer_sync`, requiring a boolean `is_correct` before a user starts a costly batch evaluation.
- Rationale: a model-free Pi probe cannot detect judge credential, endpoint, request-shaping, or structured-output failures. Reusing the production transport prevents a second, misleading compatibility path.
- Boundary: the preflight is opt-in and does not run automatically before batches. It prints safe configuration, verdict, usage, and cost only; shared HTTP errors retain endpoint/status but never provider response bodies.
- Configuration note: normal project loading intentionally preserves already-exported process variables over `.env`; a user who rotates only `.env` must start without a stale exported judge key until provenance reporting is added.

## D-008 — Preserve judge-key precedence and report it safely

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: judge preflight reports whether its effective key originated in the process environment, `.env`, or neither, and flags a differing `.env` value shadowed by the process environment.
- Rationale: `load_project_env(..., override=False)` deliberately preserves explicit caller configuration, but that behavior can otherwise disguise a rotated `.env` key as a provider authentication failure.
- Privacy boundary: report only a source label and boolean shadowing status—never a key, hash, length, or provider error body.
- Implemented follow-up: H-008 adds `make check-judge-config`, a no-request configuration check that exposes source metadata before the credentialed preflight spends a request.

## D-009 — Keep strict verdict schema opt-in and Responses-only

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: `DCI_EVAL_JUDGE_STRICT_JSON_SCHEMA` defaults to false and adds the fixed strict JSON Schema only to Responses requests when explicitly enabled.
- Rationale: strict schema can eliminate malformed verdicts for supporting Responses backends, but sending it by default would break generic OpenAI-compatible Chat Completions services.
- Cache boundary: the flag is part of all judge-result reuse identities, preventing a verdict generated under one request shape from being reused under another.

## D-010 — Derive judge-result reuse from a canonical safe request fingerprint

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: Persist a SHA-256 digest of `JudgeConfig.public_dict()`, the effective endpoint, and the fully built request. Reuse only a matching digest paired with a boolean `is_correct` verdict.
- Rationale: hand-maintained field comparisons drift as request shaping evolves; a canonical safe identity prevents stale or partial artifacts from silently avoiding a new judgment.
- Compatibility boundary: artifacts from before the fingerprint are deliberately rejudged once. The public configuration remains part of the identity so D-009's strict-schema separation applies consistently, including when a flag is a no-op for a compatible backend.
- Privacy boundary: neither API keys nor raw request content are persisted by the fingerprint.

## D-011 — Do not retain provider response bodies in judge errors or results

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: malformed structured-output failures contain only generic diagnostics, and successful judge results persist only parsed verdict fields, usage, cost, and safe configuration.
- Rationale: the same transport feeds preflight stderr and asynchronous evaluation artifacts; retaining provider bodies in either success or failure paths can expose unnecessary untrusted content.
- Boundary: retry behavior and parsed verdict observability remain unchanged; raw provider response text and payloads are intentionally unavailable after the call returns.

## D-012 — Reject credential-bearing judge URLs at configuration ingress

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: reject judge base URLs containing userinfo, query data, or fragments before they reach request construction, public configuration, cache identity, or error text.
- Rationale: these URL components may carry secrets; sanitizing downstream output is weaker than preventing unsafe configuration from entering the transport.
- Boundary: normal scheme/host/path compatible endpoints remain supported; API keys continue to use configured environment variables.

## D-013 — Require absolute HTTP(S) judge origins

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: reject judge base URLs unless they have an `http` or `https` scheme and a host, before endpoint construction, safe configuration, cache identity, or transport setup.
- Evidence: `urlsplit()` accepts unsupported and relative URL forms, while `urllib.request` installs file and FTP handlers by default; H-016's focused tests prove those forms are rejected and normal remote/local HTTP(S) endpoints retain their request paths.
- Rationale: URL parsing alone is not transport validation. A configured judge should never route the authorization header or evaluated input to a non-HTTP handler, a relative path, or an empty authority.
- Boundary: this does not change support for HTTPS hosts, explicitly configured local HTTP judges, path prefixes such as `/v1`, or H-015's credential/query/fragment rejection.

## D-014 — Reject judge endpoint redirects

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: open judge requests through a redirect handler that turns every HTTP redirect into a safe HTTP error instead of following the location.
- Evidence: Python's default handler redirects POST 301/302/303 requests and preserves POST for 307/308; H-017 proves the replacement raises an error without exposing the destination, preserves ordinary configured requests, and keeps existing provider-error redaction intact.
- Rationale: an ingress-validated URL is not a complete origin boundary when a redirect response can forward the bearer authorization header or evaluated input to a different destination.
- Boundary: correctly configured OpenAI-compatible endpoints are expected to serve directly. The standard proxy configuration remains unchanged, and an endpoint that genuinely requires a redirect now fails explicitly instead of silently changing the trust boundary.

## D-015 — Disable official Responses storage by default

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: requests to the exact official OpenAI Responses endpoint include `store: false` unless `DCI_EVAL_JUDGE_RESPONSES_STORE=true` explicitly opts in; compatible Responses backends receive no `store` field.
- Evidence: OpenAI documents 30-day application-state retention for Responses by default or with `store=true`; H-018 verifies default opt-out, the deliberate opt-in path, cache identity separation, environment loading, and a field-free compatible request.
- Rationale: DCI judges may send questions, gold answers, and predictions. Local artifact minimization is incomplete when the official response endpoint stores that request by default.
- Boundary: `store=false` does not alter ordinary abuse-monitoring controls, and the exact-endpoint scope avoids adding an unsupported field to nominally compatible providers.

## D-016 — Verify Pi idle state after settlement

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: after receiving `agent_settled` for a prompt, issue a correlated `get_state` probe within the remaining prompt deadline and reject a streaming, compacting, or pending-message state.
- Evidence: Pi exposes stable idle fields through `get_state`; H-019 verifies the successful postcondition, rejection of queued work, deadline-bound probing, and legacy `agent_end` fallback compatibility.
- Rationale: a settlement event is a useful lifecycle signal but an independently validated idle state detects protocol drift before a run artifact is treated as final.
- Boundary: the additional probe applies only after `agent_settled`; legacy Pi versions that signal completion with an `agent_end` lacking `willRetry` retain the prior fallback behavior.

## D-017 — Build protocol-first with Pi as the reference adapter

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: define a language-neutral Agent Runtime Protocol before adding new runtime adapters; retain the existing hardened Pi JSONL RPC path as the first reference adapter.
- Rationale: this avoids per-language, per-runtime integration matrices while preserving the verified Python benchmark path and direct-corpus DCI capability.
- Boundary: this does not commit the project to a Pi rewrite, nor does it claim feature parity across Pi, Claude Code, Hermes-agent, Pydantic AI, or LangGraph.

## D-018 — Require a work-package parent for autonomous work

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: manager dispatch, climb cycles, maintenance, and experiments must name the single active `WORKLIST` package; unscoped work stops before implementation.
- Rationale: a conversation-only product decision allowed local Pi/Judge reliability improvements to replace the intended framework roadmap.
- Boundary: direct user authorization may amend the worklist or architecture, but it does not permit a hidden or unrecorded parallel roadmap.

## D-019 — Keep Claude Code authentication on the subprocess environment boundary

- Status: 🔴 superseded for restricted application execution by D-050
- Decided: 2026-07-12
- Decision: support both Claude Code's stored login and its environment-configured Anthropic-compatible/cloud backends by copying the complete caller environment to the restricted subprocess.
- Rationale: allowlisting only `ANTHROPIC_*` would break PATH, proxy, Bedrock, Vertex, AWS, and GCP configuration; placing tokens or routing data in CLI arguments or protocol payloads would create persistence and process-inspection risks.
- Privacy boundary: environment names and values are not copied into the command, Agent Runtime Protocol request, normalized events, or runtime result. Credentials remain owned by the caller environment or Claude Code credential store.
- Acceptance boundary: the unavailable local Claude account defers provider-backed UAT but does not block AF-040; model-free conformance and the real safe unauthenticated path remain durable AF-030 evidence.

## D-020 — Keep host APIs schema-backed and adapter-neutral

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: Python and TypeScript hosts expose matching runtime manifest, request, event, and asynchronous client contracts; checked-in JSON Schemas and shared fixtures remain the canonical wire definition.
- Rationale: application code should depend on one portable protocol surface instead of an adapter-by-language matrix, while runtime validation prevents static TypeScript/Python annotations from becoming an unverified parallel contract.
- Boundary: AF-040 adds no transport, provider registry, workflow engine, or adapter selection. Pi and Claude Code private types remain behind their runtime adapters.
- Revalidation trigger: automate type generation only when manual public type maintenance measurably drifts despite shared cross-language fixture gates.

## D-021 — Treat the Rust local executor as policy enforcement, not a sandbox

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-12
- Decision: the first Rust backend enforces a trusted canonical workspace, absolute executable allowlist, direct argument-vector spawning, cleared child environment, deadlines, bounded output, and cancellation; it must not be described as OS-level isolation.
- Rationale: a local child process can still use the network, open absolute paths, spawn descendants, and call platform syscalls unless a real platform/container boundary is installed. Honest capability naming prevents enterprise callers from relying on protections that do not exist.
- Implemented evidence: `dci.executor/v1` schemas/reference validation plus the runnable Rust sidecar prove trusted policy, no-shell execution, capped stream draining, deadline/cancel kill-and-reap, duplicate-ID enforcement, responsive JSONL correlation, EOF completion, and documented operator boundaries.
- Extension boundary: containers, remote workers, Linux namespace/seccomp/cgroup isolation, macOS sandbox profiles, or Windows job objects must be replaceable executor backends behind the same versioned contract.

## D-022 — Establish package composition before workflow execution

- Status: ✅ accepted decision
- Decided: 2026-07-12
- Decision: AF-060 first defines `dci.package/v1` manifests and a deterministic static capability/policy composer, then proves a DCI reference graph.
- Rationale: a workflow engine or enterprise control plane built first would invent package, policy, event, and artifact semantics implicitly and couple them to one host.
- Boundary: AF-060 does not implement scheduling, persistent memory storage, multi-tenant administration, or adapter-specific package variants.
- Revalidation trigger: add an execution engine only after two independently useful package graphs cannot be expressed or validated by the static contract.
- Implemented evidence: the manifest contract, deterministic composer, DCI reference graph, and cross-language parity are confirmed. AF-070 then expressed and validated a second independently useful controlled-code graph without changing the composer, so the execution-engine trigger is not met.

## D-023 — Challenge composition with controlled code validation

- Status: ✅ accepted decision
- Decided: 2026-07-12
- Decision: AF-070 will model controlled local code validation as a second portable policy/workflow/observability/evaluation graph before adding execution or registry infrastructure.
- Rationale: the graph exercises a different dependency shape, the unused `workflow` kind, and the existing Rust executor boundary as a shared host capability without conflating static validation with scheduling.
- Boundary: `executor.controlled` comes from the shared host service, not from Pi or Claude Code natively; AF-070 does not execute commands, repair code, add persistent memory, or build a registry/control plane.
- Revalidation trigger: consider an execution layer only if this second graph cannot be expressed through the existing package, policy, event, and artifact edges.
- Implemented evidence: AF-070-H-001 confirms the four closed manifests, `workflow` kind, stable dependency order, and exclusion of runtime-controlled fields; H-002 confirms cross-host equality, permutation stability, portable outputs, and every missing edge rejection without a composer change; H-003 confirms canonical TypeScript validation for all eight manifests without a second composer.
- Closure evidence: H-004 documents the shared host-service/non-sandbox boundary and passes 189 Python, 7 Node, and 21 Rust tests plus every compile, lint, format, scope, shell, and diff gate.

## D-024 — Discover packages locally before assembly or distribution

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: AF-080 adds a Python-only catalog over explicit local directories with direct JSON discovery and exact `package_id@version` selection.
- Rationale: both static graphs are useful only as checked-in file lists today; deterministic validated discovery is the smallest next framework capability and precedes application assembly or distribution infrastructure.
- Boundary: roots are trusted operator input; discovery rejects symlinks and ambiguity, does not recurse, load code, access a network, install packages, choose version ranges, or execute a graph.
- Revalidation trigger: add an assembly manifest only after catalog selections need a portable binding to runtime and host-service identities; add distribution only when a real remote source is required.
- Implemented evidence: AF-080-H-001 confirms root/file permutation stability, canonical manifest validation, direct-child filtering, and non-recursive discovery; H-002 confirms fail-closed root/document/symlink/identity boundaries and content-free public errors; H-003 confirms deterministic exact selection, deep-fresh manifests, both graph integrations, and duplicate/unknown rejection.
- Closure evidence: H-004 documents the catalog trust/language boundaries and passes 213 Python, 7 Node, and 21 Rust tests plus every clean-install, compile, lint, format, shell, scope, and diff gate.

## D-025 — Assemble statically before running applications

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: AF-090 defines `dci.assembly/v1` and a pure plan resolver over one runtime manifest, exact catalog refs, and explicit host-service edges.
- Rationale: the catalog now supplies stable identities; a portable static binding is required before any runner can safely consume runtime/package/service choices.
- Boundary: resolution performs no runtime, executor, tool, or workflow execution and carries no prompts, credentials, provider/model settings, commands, transports, or mutable state.
- Revalidation trigger: propose a runner only after static plans for both reference applications are portable, safe, and insufficient for a concrete execution use case.
- Implemented evidence: H-001 confirms the closed protocol and canonical refs/edges; H-002 confirms immutable safe resolution; H-003 confirms both reference applications, runtime parity, and service separation; H-004 confirms TypeScript validation ownership, non-execution documentation, and full repository closure.
- Closure evidence: 237 Python, 11 Node, and 19 Rust tests plus compile, Ruff, clean npm install, fmt, Clippy, shell, scope, and diff gates pass. Formal package closure waits only for an approved successor package.

## D-026 — Execute resolved plans before adding workflow infrastructure

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: AF-100 adds a minimal Python runner that consumes one resolved `AssemblyPlan`, an explicit runtime client, application input, and explicit host services.
- Rationale: AF-090 proves static application identity and boundaries; the smallest next product proof is one end-to-end DCI run through those contracts, not a scheduler or registry.
- Boundary: no package interpreter, general workflow engine, automatic service startup, provider/model selection, retry engine, persistence, registry, API server, tenancy, or control plane.
- Revalidation trigger: add scheduling only when a second executable application cannot be represented by one runtime invocation; add distribution only for a real remote source.

## D-027 — Asterion is the framework; DCI is a capability

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: name the independent framework Asterion and extract its sole generic implementation to `src/asterion/`; retain DCI as a dependent capability, benchmark, CLI, and reference application.
- Rationale: keeping framework modules under `src/dci/framework/` reverses the intended dependency direction and would make AF-100 reinforce the wrong product boundary.
- Packaging: use the bare `asterion` distribution/import name; exact PyPI and npm registry probes returned 404 on 2026-07-13, though publication remains out of scope.
- Compatibility: preserve `dci-agent-lite`, both `scripts/examples/` entry paths, `dci.framework.*` re-exports, and current `dci.*` protocol literals during extraction.
- Revalidation trigger: rename protocol literals only through a separate versioned compatibility decision; remove old imports only after downstream usage is measured.
- Implemented evidence: H-001 confirms authoritative runtime/host/adapter modules, object identity, dependency direction, and dual-root packaging; H-002 confirms package/assembly/executor extraction, stable wire literals, and definition-free compatibility modules; H-003 confirms product-level capability/application assets and Asterion-owned TypeScript/Rust working directories without identity drift.
- Closure evidence: H-004 confirms DCI console scripts, isolated model-free example commands, architecture ownership, and full closure with 258 Python, 11 Node, and 19 Rust tests plus compile, lint, clean install, format, shell, scope, and diff gates.

## D-028 — Keep the first runner plan-driven and caller-owned

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-13
- Decision: execute one resolved `AssemblyPlan` through an explicitly supplied Python runtime client, cancellation signal, input, and host-service mapping.
- Rationale: this proves the static-plan-to-runtime boundary while keeping runtime selection, service authorization, package loading, and process ownership outside the runner.
- Boundary: Asterion validates runtime identity/capabilities, required service presence, request/event lifecycle, cancellation, and immutable result projection; it adds no scheduler, registry, retry engine, automatic service startup, TypeScript runner, or control plane.
- Revalidation trigger: add scheduling only when a second executable application needs sequencing that one runtime invocation cannot express; add automatic service startup only for a concrete operator workflow with an explicit authorization model.
- Closure evidence: AF-100 H-001 through H-004 confirm ownership, invocation, parity/safety, and documentation with 284 Python, 11 Node, and 19 Rust tests plus every compile, lint, format, shell, scope, and diff gate.

## D-029 — Make capabilities executable composition units

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-13
- Decision: capability packages are reusable executable units; applications are the executable boundaries that bind exact packages, a runtime, host services, and operator input.
- Rationale: treating each package as an application breaks policy/evaluation/observability composition, while application-private plug-ins make manifests descriptive metadata and recreate DCI-specific coupling.
- Baseline boundary: Asterion and its DCI capability implementation must not import or modify `src/dci/benchmark/`; the existing `dci-agent-lite` path remains an independent external baseline.
- Delivery boundary: AF-110 adds explicit exact implementation binding and sequential execution. Secure installed-application binding and the generic `asterion run <assembly>` command are deferred to AF-120 because core cannot safely discover independently owned executable code without a reviewed binding mechanism.
- Revalidation trigger: add scheduling only for a measured multi-branch execution need; add dynamic discovery only with an explicit distribution and authorization contract.
- Implemented evidence: AF-110 adds immutable selected manifests, exact implementation bindings, declared output validation, deterministic sequential execution, an independently packaged DCI research implementation, an independent Pi runtime client, and an explicit application composition root. The same DCI implementation runs in two application graphs without Asterion importing DCI or the baseline.

## D-030 — Ship one Asterion wheel and keep DCI as a source baseline

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: Asterion is the only buildable Python distribution. Framework core, modular DCI capability code, the DCI application provider, and canonical resources ship in the single `asterion` wheel.
- Rationale: capability and application boundaries are architectural interfaces, not reasons to force operators to manage several first-party wheels. One product wheel preserves composition while minimizing packaging and installation complexity.
- Baseline boundary: `src/dci` keeps the verified `.env`, Pi/Judge, CLI, evaluation, and security extensions as a repository-only runnable comparison baseline. It is excluded from every wheel, is not published, and neither imports nor is imported by Asterion.
- Extension boundary: the versioned installed-provider contract remains for future independently installed third-party applications, but first-party DCI does not require a separate entry-point distribution.
- Revalidation trigger: split a capability into its own distribution only when an independently versioned external consumer or deployment requirement justifies the additional artifact.
- Implemented evidence: AF-120 ships one `asterion` wheel with bundled modular DCI capability/application resources and an explicit Pi runtime factory. The root is a non-buildable uv workspace, `src/dci` is source-only, and isolated installation confirms Asterion works while `dci` is absent.

## D-031 — Select installed applications by exact identity

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: the preferred installed-product command selects one application as exact `application_id@version` within one explicitly selected provider. Internal assembly paths are not part of the normal operator experience.
- Rationale: requiring users to discover wheel-internal resource paths defeats independent installation, while global application scanning would load unselected executable providers.
- Compatibility: explicit `--assembly` remains the advanced path and the AF-120 positional assembly spelling remains temporarily supported. Plain `asterion list` stays metadata-only; `list --provider` explicitly authorizes loading one provider's application declarations.
- Boundary: no aliases, implicit latest version, version ranges, global provider loading, or multi-assembly default selection.
- Revalidation trigger: add assembly variants or version resolution only for a concrete application that cannot use one exact identity and one canonical assembly.
- Implemented evidence: AF-130 adds pure exact selector parsing, selected-provider application listing, preferred `--application`, advanced `--assembly`, and legacy positional compatibility. Isolated wheel verification lists `dci.research-capability@1.0.0` without exposing resource paths.

## D-032 — Keep controlled-code execution host-owned

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: the controlled-code workflow submits one logical validation request to an explicitly injected `executor.controlled` host service; executable, arguments, workspace, environment, deadlines, and limits remain trusted host configuration.
- Rationale: allowing Pi or portable manifests to generate commands would enlarge the agent-to-executor authority boundary and conflate composition with dynamic workflow planning.
- Provider boundary: the second application uses built-in provider ID `controlled-code`, separate from the DCI application provider, while shipping in the same Asterion wheel.
- Process boundary: Asterion may provide a JSONL client for an already authorized Rust sidecar but does not automatically start it or claim operating-system sandboxing.
- Revalidation trigger: add typed agent-proposed actions or generic CLI service startup only through separately reviewed authorization and lifecycle designs.
- Policy-package boundary: `policy.controlled-code-check` remains declarative and is not added to the runner's executable package kinds. The resolved graph plus host service trusted policy enforce it; only workflow, evaluation, and observability receive implementations.
- Implemented evidence: AF-140 ships the independent `controlled-code` provider, three exact implementations, closed logical service values, and a caller-owned JSONL client. One fixture execution produces report/verdict/audit outputs with one service call; the wheel lists both applications while excluding `dci`.

## D-033 — Manage one explicit executor sidecar per CLI run

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: a controlled-code CLI run may start exactly one stdio sidecar only when the operator explicitly supplies binary, Rust policy, and trusted validation configuration. Asterion owns readiness, injection, cancellation, shutdown, and reap for that invocation.
- Rationale: connect-only transport requires a new supervised socket boundary, while accepting arbitrary wrapper commands or automatic discovery would weaken executable authority.
- Ordering boundary: sidecar startup occurs only after provider, application, runtime compatibility, assembly/catalog, exact binding, and complete lifecycle-configuration preflight.
- Security boundary: direct argv is `[binary, policy_path]`, the environment is minimal, no shell is used, and readiness means pipe/process availability rather than a false policy-health claim.
- Revalidation trigger: add supervised connection, persistent reuse, or protocol health only for a concrete deployment through separately versioned lifecycle/protocol designs.
- Implemented evidence: AF-150 validates all three operator inputs before runtime/child construction, starts exactly one direct-argv stdio sidecar with a minimal environment, injects it only into the controlled-code run, forwards correlated protocol cancellation, discards stderr in bounded chunks, and reaps on exit. The isolated wheel runs `code.quality@1.0.0` successfully against the Rust sidecar while excluding `dci`.

## D-034 — Expose Claude runtime explicitly without provider authorization

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: the installed runtime registry may expose `claude-code.reference` by exact runtime ID even when no Claude account or gateway is available; constructing it is an interface operation, never a provider request.
- Rationale: installed-product runtime selection needs the same explicit, testable boundary as Pi, while unavailable authorization must not block protocol, command, environment, or redaction conformance.
- Boundary: no bundled application is implicitly made Claude-compatible, and AF-160 does not automate login, configure credentials, attempt a prompt, add dynamic selection, or change the existing DCI provider runtime list.
- Revalidation trigger: add a real provider-backed invocation only when an operator supplies authorization and an application explicitly declares `claude-code.reference`.

## D-035 — Model DCI runtime compatibility as paired immutable assemblies

- Status: ✅ accepted design decision
- Decided: 2026-07-13
- Decision: one installed DCI application may declare exact Pi and Claude runtime compatibility only through paired canonical assemblies whose immutable compositions match and whose runtime IDs differ.
- Rationale: `dci.assembly/v1` binds one exact runtime ID, so mutating or dynamically interpreting one assembly would obscure the selected product contract. A generic runtime-to-assembly selector preserves the established explicit selection boundary without coupling the CLI to DCI.
- Boundary: the DCI provider owns its allowed runtime IDs; controlled-code remains Pi-only. Fixture verification must not authorize, invoke, or configure Claude. `src/dci/benchmark/` remains untouched and excluded from the wheel.
- Revalidation trigger: revise the selection contract only if one application needs multiple canonical assemblies for the same runtime or runtime compatibility gains its own versioning policy.

## D-036 — Make complete DCI the first Asterion capability-package reference product

- Status: ✅ accepted decision
- Decided: 2026-07-13
- Decision: Asterion will own a complete DCI domain implementation inside its single wheel. The implementation is a capability package with an Asterion contract/application bridge and a package-local operator CLI. The old `src/dci` product remains unchanged, source-only, and independent; neither side is a runtime dependency of the other.
- Rationale: the existing Asterion DCI vertical slice proves framework mechanics but does not provide the original product's full run, artifact, resume, judge, cache, or benchmark behavior. A behavior-preserving domain transplant makes DCI the first complete capability-package example without polluting generic framework code or rewriting mature research logic.
- Delivery boundary: AF-180 through AF-210 separately accept interactive execution, durable/resume behavior, evaluation/benchmark behavior, and application/runtime semantic parity. Pi is the required original-DCI parity baseline. Claude fixture compatibility is not a full-DCI claim and real provider evidence remains operator-authorized.
- Distribution boundary: D-030 remains in force. `asterion.dci` is independently owned code within the one `asterion` wheel; it is not a second first-party wheel. Its public configuration and output roots are separate from the old product.
- Revalidation trigger: split the package only for a concrete separately versioned consumer/deployment need; alter native DCI artifact formats only with an explicit migration policy and parity test; claim a runtime-specific DCI semantic only with matching evidence.
- Implemented evidence: AF-180 establishes isolated configuration, direct Pi execution, package-local commands, and an initial body-free projection. AF-190 completes durable native artifacts, compatible failed/incomplete resume through `asterion-dci resume`, isolated protocol attempts, and durable body-free references; all eight hypotheses pass locally without provider requests.

## D-037 — Bind native DCI execution at the first-party provider boundary

- Status: ✅ accepted design decision
- Decided: 2026-07-13
- Decision: the first-party DCI provider will bind its capability implementation to a private native Pi executor. The `pi.reference` application path maps an immutable package invocation to `DciRunRequest`, invokes the independent Asterion DCI workflow, and projects body-free native references; the existing Claude path remains protocol-fixture-only.
- Rationale: this makes the installed application and `asterion-dci` share one complete DCI implementation without adding DCI parsing, artifacts, or configuration to generic CLI/runner/runtime layers.
- Boundary: no new generic host-service protocol, no `src/dci` dependency, no DCI-specific generic CLI flag, no provider request, and no Claude semantic-parity claim.
- Revalidation trigger: introduce a generic application-executor extension only when a second independently owned application requires the same provider-bound native execution pattern.

## D-038 — Share normal DCI runtime configuration across the source and Asterion products

- Status: ✅ accepted design decision
- Decided: 2026-07-13
- Decision: normal Pi, provider/model, deadline, judge, and provider-authentication configuration is shared through the repository `.env` and inherited process environment.  Asterion reads the same `DCI_*` values as the source product; `ASTERION_DCI_OUTPUT_ROOT` is reserved for Asterion output location, while existing `ASTERION_DCI_PI_*` values become backward-compatible aliases rather than a required parallel surface.
- Rationale: both products intentionally use the same external Pi and service credentials.  Separate mandatory configuration made the installed Asterion application unable to reproduce a normal source DCI run and obscured missing request forwarding.
- Boundary: explicit package CLI options still override environment defaults; generic framework modules remain DCI-neutral; Asterion remains independently implemented and never imports or executes `src/dci`.
- Revalidation trigger: introduce a separate Asterion runtime namespace only if the products need intentionally divergent credentials, Pi checkouts, or security policy, with a versioned migration and parity update.

## D-039 — Treat runtime-context level as capability-gated, not a fabricated Pi flag

- Status: ✅ accepted and implemented decision
- Decided: 2026-07-14
- Decision: Asterion forwards only controls exposed by the configured current Pi CLI. Pi currently exposes `--thinking`, session, tool, and Node controls but no runtime context-management level. A requested `DCI_RUNTIME_CONTEXT_LEVEL` or package `--runtime-context-level` remains in native state with an `unsupported` diagnostic and produces no Pi argv flag.
- Rationale: Asterion's former `--context-management-level` mapping made the runtime-context example fail before its prompt. The source runtime-context example itself uses Pi's supported `--thinking` control, so mapping its level to an invented context flag is neither source-compatible nor safe.
- Boundary: this does not change source DCI or external Pi. Thinking, session, heap, and conversation artifact controls remain effective. An operator may still pass arbitrary Pi arguments with explicit `--extra-arg`, whose validity remains Pi's responsibility.
- Revalidation trigger: when the selected Pi version documents a runtime context-level control, add a capability test and an exact typed mapping before forwarding it.

## D-040 — Make the native DCI recorder a private single-writer boundary

- Status: ✅ accepted design decision
- Decided: 2026-07-14
- Decision: Asterion DCI uses one production recorder for raw events, full and processed conversations, latest provider context, final answer, state, stderr, provenance, notes, and isolated protocol attempts. Native JSON is atomically replaced, run directories are private, and a nonblocking OS advisory lock held on the verified run-directory descriptor prevents concurrent Pi construction and artifact writers.
- Resume boundary: the directory descriptor is locked before metadata validation, Pi construction, or artifact writes; all recorder I/O is descriptor-relative so namespace rebinding cannot redirect evidence; descriptor/process close releases authority. Private lock metadata is diagnostic only, never authorizes PID/pathname reclamation, and is never removed on release. Foreign, malformed, symlink metadata or unavailable advisory locking fails closed. Artifact resume without `keep_session` is directory continuation, not a claim of Pi session identity.
- Provenance boundary: record revision/match booleans and a sanitized Git origin only. Never persist URL credentials, Git status/diff contents, environment values, arbitrary extra-argument values, or unredacted commands. Framework/application projections remain URI-only.
- Terminal boundary: `asterion-dci terminal` is a direct TTY-only Pi invocation, returns the child status, and intentionally creates no RPC run artifacts.
- Rationale: the previous production run path and richer recorder were disconnected, so actual runs lacked promised transcript/context/provenance evidence and could not safely recover from concurrent or interrupted writers.
- Revalidation trigger: change the locking/staleness or native-evidence privacy model only with a versioned artifact migration and adversarial recovery tests.

## D-041 — Make capability products self-describing and uniformly verifiable

- Status: ✅ accepted design decision
- Decided: 2026-07-15
- Decision: the generic installed Asterion CLI exposes provider-selected `describe` and `verify` commands. Providers may declare immutable capability descriptions, configuration requirements, and structured verification profiles; DCI supplies provider-free preflight/acceptance, two-case bounded basic, and aggregate complete profiles.
- Rationale: capability implementation is not product usability when users must inspect source code or decode audit documentation to learn functions, environment variables, and verification commands.
- Security boundary: exact provider selection loads no adjacent provider; verification never evaluates shell strings or a verifier discovered from the current working directory; source acceptance is available only from a trusted ancestor of the installed verifier module; secret values and provider bodies never enter descriptors/results; provider-backed levels are turn-bounded and explicitly selected; full datasets are excluded from complete verification.
- Cost terminology: public results count provider-backed operations (two Pi run operations and one Judge operation for `basic`/`complete`), not provider API requests inside a multi-turn Pi run. Both Pi cases carry an explicit six-turn limit; the actual provider request count depends on their tool/turn behavior.
- Compatibility boundary: verification metadata is optional for existing providers, original `src/dci` and its scripts remain unchanged, and package-specific CLIs continue to work.
- Revalidation trigger: any remote verifier, arbitrary command descriptor, secret-management feature, implicit provider request, or full-dataset profile requires a separate reviewed decision.

## D-042 — Converge repository-only hosts under an explicit example namespace

- Status: 🔴 superseded before implementation by D-043
- Decided: 2026-07-16
- Decision: move both top-level repository-only application composition hosts into `examples/asterion/applications/`; keep package-local `asterion/applications/` and `asterion/capabilities/` as the only authoritative product implementations.
- Rationale: top-level `applications/` resembles an installable product root even though it contains only two reference hosts, while the local top-level `capabilities/` directory has no tracked product content. An explicit example namespace makes ownership readable without sacrificing integration examples.
- Compatibility boundary: preserve both example functions and behavior, but leave no old-path stubs. Update tests, parity metadata, and documentation because these are repository-internal paths rather than installed APIs.
- Delivery boundary: AF-300 changes no wheel code, protocol, CLI, DCI semantics, external Pi checkout, provider-backed evidence, or package split.
- Sequencing: full-dataset validation, published-score reproduction, standalone release packaging, and a separately versioned DCI plugin remain deferred until the broader Asterion framework converges and receives new scoped decisions.
- Revalidation trigger: introduce a different example/package layout only when standalone extraction or a concrete third-party distribution supplies a tested build and versioning requirement.

## D-043 — Establish Asterion as a complete top-level project subtree

- Status: ✅ accepted design decision
- Decided: 2026-07-16
- Decision: converge all Asterion-owned Python, TypeScript, Rust, schemas, examples, scripts, product documentation, and project tests beneath a top-level `asterion/` project root. The primary Python project becomes `asterion/pyproject.toml` with `asterion/src/asterion`; auxiliary language packages remain under `asterion/packages/`.
- Rationale: `packages/python/asterion-core` is a valid monorepo path but misrepresents Asterion as an incidental core package even though it owns the framework, bundled products, CLIs, and multi-language contracts. A complete subtree makes ownership visible and allows future standalone promotion without a second source re-layout.
- Mixed-repository boundary: original `src/dci`, cross-product parity/acceptance evidence, and repository governance remain at the DCI-Agent-Lite root. Asterion project-only tests must pass without importing or locating the baseline.
- Documentation boundary: `asterion/docs/` owns the product hub, architecture north star, guides, verification, and operator material; mixed-repository status, migration plans, original DCI documentation, and acceptance assets remain rooted outside the Asterion project and must be labeled when linked.
- Compatibility boundary: installed distribution/import/CLI/provider/package/application/protocol identities and runtime behavior remain unchanged. Obsolete repository paths receive no forwarding projects, symlinks, or stubs.
- Sequencing: full datasets, published-score reproduction, release automation/publication, remote repository switching, and separately versioned DCI plugins remain deferred until framework convergence is complete and separately authorized.
- Revalidation trigger: alter the target root only for a concrete standalone build/release constraint that cannot be satisfied by promoting the subtree contents to repository root.

## D-044 — Stage paper-aligned DCI and own live context policy in Asterion

- Status: ✅ accepted design decision
- Decided: 2026-07-17
- Decision: close paper-aligned DCI through AF-310 runtime context management, AF-320 benchmark/metric parity, AF-330 complete application and dual-runtime exposure, then separately budget-authorized AF-340 experiment reproduction.
- Runtime boundary: AF-310 ships one dependency-free Asterion TypeScript extension through Pi's documented explicit extension and compaction hooks. It does not patch, vendor, or write to the external `pi/` checkout and does not fabricate a Pi-native context-level flag.
- Evidence boundary: claims remain separated into implemented, model-free verified, bounded provider verified, and full experiment reproduced. Earlier 8/8 source-product parity and 533/533 delegated selectors do not prove paper completeness.
- Compatibility boundary: D-039 remains valid when no exact Asterion paper profile is selected. Explicit `level0` through `level4` now select the Asterion-owned implementation; legacy, level5, and unknown values fail closed.
- Sequencing: AF-310 may not absorb BEIR/metrics, Claude semantic acceptance, full datasets, or score reproduction. Each successor requires its own governed plan and fresh Climb session.
- Revalidation trigger: change extension ownership or the four-layer evidence model only if the selected runtime exposes an equally exact, versioned, integrity-bound native contract with executable semantic evidence.

## D-045 — Separate paper benchmark identity from executable authorization

- Status: ✅ accepted design decision
- Decided: 2026-07-17
- Decision: AF-320 owns schema-closed dataset and experiment-scope registries, exact evidence-derived coverage/localization metrics, corrected bounded NDCG@10, and paper-declared ablation rows. Dataset identity and experiment selection identity are separate contracts.
- Paper boundary: BrowseComp main all-830, its distinct analysis/context n=100 scopes, Appendix random-50, full BRIGHT/Bamboogle, and applicable random-50 selections retain separate seed-provenance/algorithm/selected-ID identities. An unreported paper seed is represented as unreported and verified through the exact published selected-ID manifest, never fabricated. Parameterized localization never invents an undocumented universal segment width.
- Execution boundary: `paper-full` rows may be listed, validated, rendered, and packaged but cannot execute in AF-320 under any generic option or environment value. AF-340 alone may add a separately reviewed authorization and budget surface.
- Evidence boundary: analysis identity rehashes the exact protocol stream, every consumed external tool blob, final model-visible context, gold manifest, and opened corpus/gold files. Public projections remain body-free.
- Revalidation trigger: change selection scopes, aggregation, evidence identity, or full-run authority only after reconciling the paper version, design, worklist, cache migration, and security review.

## D-046 — Preserve unavailable paper selection provenance without substitution

- Status: ✅ accepted design decision
- Decided: 2026-07-17
- Decision: the paper does not publish selected IDs or seeds for its sampled BrowseComp analysis scopes. AF-320 binds those scopes to explicitly `asterion-defined` reproducible seeds, algorithms, and digests; it does not describe those IDs as paper-published. Published DCI-Bench random-50 files remain `paper-unreported` with exact packaged selected-ID manifests.
- Bamboogle boundary: the paper-full identity is 125 test rows. The migrated `qa.bamboogle` profile, local file, and launcher are a separate 50-row sample and cannot satisfy or execute that paper-full identity, so the inventory leaves its full row unbound until AF-340 provides a reviewed source/authorization surface.
- Fixture boundary: bounded-fixture declarations bind hash-verified packaged dataset and corpus artifacts. They do not authorize a paper-full scope or imply score reproduction.
- Revalidation trigger: replace an Asterion-defined scope only when a primary paper artifact supplies the exact published seed or selected IDs; bind Bamboogle full execution only through AF-340 governance.

## D-047 — Keep unpublished FineWeb distractor selections unbound

- Status: ✅ accepted design correction
- Decided: 2026-07-17
- Decision: the paper declares random FineWeb distractor injection and the 100K/200K/400K corpus targets, but does not publish a FineWeb revision, seed, selection algorithm, selected IDs, or manifest digest. AF-320 records those fields as `paper-unreported` and null instead of manufacturing an identity.
- Execution boundary: every affected corpus-scale row remains `paper-full` and unconditionally non-executable. A bounded analogue binds only packaged synthetic distractor fixtures and is never described as the paper selection.
- Revalidation trigger: AF-340 may bind a FineWeb selection only from a reviewed primary artifact that makes the complete source and selected-document identity reproducible.

## D-048 — Separate functional reproduction from literal experiment configuration

- Status: ✅ accepted design correction
- Decided: 2026-07-17
- Decision: paper-aligned implementation means reproducing capabilities, contracts, execution paths, evidence, and verifiable behavior. A model, endpoint, sample count, seed, or published number is not an implementation prerequisite merely because the paper used it.
- Judge boundary: AF-320 bounded acceptance may use any configured supported Judge, including DeepSeek, when the production evaluator executes and evidence truthfully binds the effective provider/model/API/endpoint/request-shaping identity. It may not relabel that evidence as GPT-4.1 or paper-score comparable.
- Experiment boundary: AF-340 owns claims that reproduce or directly compare paper scores; those claims must bind every material paper experiment identity, including the paper-declared Judge model where applicable.
- Revalidation trigger: make a literal experiment value an implementation gate only when it changes the capability contract itself, not solely the reported experimental outcome.

## D-049 — Keep agent selection shared and translate it inside runtime adapters

- Status: 🔴 superseded in configuration precedence and defaults by D-051; its adapter-translation and role-separation boundaries remain historical inputs
- Decided: 2026-07-17
- Decision: `DCI_PROVIDER` and `DCI_MODEL` select the agent backend independently of the application-selected Pi or Claude Code runtime. Runtime-native environment names are adapter internals, not required user configuration.
- MiniMax boundary: `minimax` and `minimax-cn` reuse Pi's existing provider IDs and single provider credential variables. The Claude adapter derives its Anthropic-compatible URL, model, and aliases only in the private subprocess environment; documented `sk-cp-` Token Plan credentials use bearer auth while ordinary API keys use the API-key header matching locked Pi. It never persists either derived credential.
- Failure boundary: a runtime/provider pair without an explicit adapter mapping fails before provider construction. Asterion does not guess that an OpenAI-compatible provider is Claude-compatible and does not silently fall back to stored OAuth.
- Judge boundary: `DCI_EVAL_JUDGE_*` remains independent because Judge evaluation is a separate role and operation from the selected agent runtime.
- Revalidation trigger: add another shared provider only after both runtime adapters have an explicit tested mapping and credential-redaction coverage.

## D-050 — Bind restricted application authority from execution through verification

- Status: ✅ accepted design correction
- Decided: 2026-07-17
- Decision: a restricted Claude run persists its resolved working-directory identity in private policy evidence, and the terminal auditor requires that identity to equal the explicitly supplied corpus root before interpreting any relative tool path. A successful normalized stream cannot override a nonzero child exit.
- Environment boundary: restricted execution uses a minimal operational allowlist plus adapter-derived provider variables. Judge credentials, arbitrary caller secrets, stored-OAuth selectors, and competing Claude/Anthropic authentication variables are excluded unless the selected adapter derives them for this run. This narrows D-019's historical complete-environment behavior for the AF-330 restricted path.
- Cancellation boundary: the runtime owns the Claude child process and must terminate, reap, and fail safely when cancellation arrives after start; deadline and cancellation evidence cannot claim completion while provider work survives. Native Pi application execution retains the existing Asterion DCI cancellation/deadline and durable native-resume contracts.
- Descendant boundary: POSIX cleanup retains the started session/process-group identity, escalates that group to SIGKILL whenever the bounded SIGTERM drain times out even if the direct parent already exited, and never performs an unbounded final pipe drain. A descendant ignoring SIGTERM while retaining inherited pipes is the required regression.
- Artifact boundary: every stage validates the complete-application schema and implementation digest of its sole upstream artifact before evaluation or mutation. Generic application composition remains one invocation, not a new persistent workflow control plane; `asterion-dci resume` remains the authoritative original-DCI restart path.
- Evidence boundary: closure reruns the independent auditor over retained private artifacts, reparses the raw Claude JSONL and replays it through the production protocol adapter for exact normalized-event equality, derives the one agent operation plus safe provider/model/Claude-version identity from private runtime evidence, compares report and implementation/source identities with the tracked body-free record, and rejects path, mode, digest, or identity substitution. A tracked counter-only JSON assertion is not terminal rebinding.
- Implemented evidence: fresh r12 binds MiniMax-M3 through Claude Code 2.1.212, one corpus-contained Grep, five application stages, and one correct configured DeepSeek evaluation to report `07a69074…bce2`, tracked record `a62e62cd…ae89`, implementation `613578bd…6477`, and descendant-safe source `f3e2528`; Climb cycle 103 independently invokes the terminal verifier.
- Revalidation trigger: broaden the child environment, change working-directory authority, add mid-graph workflow persistence, or weaken terminal evidence only through a new reviewed security/protocol decision and adversarial tests.

## D-051 — Resolve one layered configuration contract through runtime-owned provider semantics

- Status: ✅ accepted design decision
- Decided: 2026-07-18
- Decision: `.env`, exported environment, CLI options, and application request fields are ordered layers of one DCI configuration contract. Explicit invocation values override exported process values; exported values override repository `.env`; both override defaults owned by the selected runtime or Judge role. Runtime resolves first; shared `DCI_PROVIDER` and `DCI_MODEL` fields are then interpreted by that runtime's explicit compatibility and translation table.
- Runtime defaults: original DCI permits only Pi. Pi defaults to `openai-codex` with `gpt-5.6-luna` and retains its broader provider registry. Claude Code defaults to its local subscription login and native model selection, while explicit MiniMax selections use only the tested Claude-Code-compatible Coding Plan translation. A future Claude Agent SDK must join the same layered contract through its own adapter rather than inheriting Pi or Claude Code assumptions.
- Judge boundary: the independent default Judge is DeepSeek V4 Flash over the OpenAI-compatible Chat Completions API. `DCI_EVAL_JUDGE_*` and Judge CLI fields remain separate from agent configuration; the safe request-shaping and prompt identity participates in evaluation cache identity.
- Reproduction boundary: original README Quick Start, Context Management Strategies, and Benchmark DCI-Agent-Lite are executable product contracts. Asterion must reproduce the same Pi experiment inputs and expose the paper's Claude Code path independently. Bounded evidence cannot claim full results, and `.env` alone cannot authorize a full dataset.
- Evidence boundary: both products emit `dci.effective-config/v1` without secrets, private paths, prompts, answers, or bodies. Full comparison retains query-level evidence and versioned confidence/non-inferiority criteria.
- Rationale: one precedence framework preserves simple `.env` defaults and precise CLI overrides while allowing runtime-specific provider capabilities and authentication. Runtime-specific public variable families would fragment the contract; a universal provider compatibility claim would be false.
- Revalidation trigger: change the public precedence order, runtime defaults, Judge default, full-run authorization, or result-comparison margins only through a versioned configuration/evidence migration and renewed README/Asterion parity acceptance.

## D-052 — Bind paper result targets in a separate versioned registry

- Status: ✅ accepted design clarification
- Decided: 2026-07-20
- Decision: AF-340 stores published DCI-Agent-CC main-result values in a separate immutable `dci.reproduction-target/v1` resource keyed by `paper-reference/claude-code`; comparison reports bind both the existing experiment-profile identity and this target identity. The experiment-profile/v1 shape and the Task 6 profile digests are not silently redefined.
- Primary-source boundary: the registry binds arXiv:2605.05242v1 and records BrowseComp-Plus accuracy `0.800`, the six QA per-dataset values plus aggregate `0.830`, and the six IR NDCG@10 values plus aggregate `0.685`. Dataset IDs map only to the AF-320 inventory identities.
- Current-default boundary: Claude subscription and MiniMax profiles have no published numeric targets. Their reports remain `target-comparison` against exact profile identity and explicitly record `published_target_status: not-applicable`; they never inherit Sonnet 4.6 paper values or claim source parity.
- Statistical boundary: Claude reports retain single-run point estimates and 95% intervals without manufacturing original-product pairs. Pi remains the only paired original/Asterion non-inferiority comparison.
- Revalidation trigger: change target values, source revision, dataset mapping, or target aggregation only after reconciling a newer primary paper artifact and versioning the target registry.

## D-053 — Close on DCI capability-package usability, not strict paper reproduction

- Status: ✅ accepted design decision
- Decided: 2026-07-21
- Decision: the project's primary objective is a complete usable Asterion DCI capability package that proves the Asterion capability-package framework. Strict DCI paper reproduction is optional evidence and is not a prerequisite for AF-340 or framework closure.
- Core-capability boundary: acceptance covers research execution, L0–L4 live context and conversation processing, private artifacts and exact resume, Judge/cache/QA/IR evaluation, benchmark datasets/profiles/launchers/reuse, analysis/figures/exports, source/application/wheel delivery, Pi and Claude Code runtime integration, and configuration/privacy/body-free evidence safety.
- Functional evidence boundary: AF-340-H-004 requires retained Pi r14 and Claude MiniMax r6 evidence covering `original-pi`, `asterion-pi`, and `asterion-claude-minimax`. Claude subscription remains a supported optional authentication path; the absence of a valid local subscription account cannot block functional acceptance when the compatible MiniMax backend has already proven the Claude Code path.
- Claim boundary: bounded MiniMax evidence proves capability-package and adapter functionality only. It cannot be relabeled as the paper's Claude model, published-score reproduction, or full-result parity.
- Full-execution boundary: AF-340-H-005 is removed from AF-340 closure. Paper models, full datasets, published targets, statistical non-inferiority, and complete result reproduction may run only under a new active work package with explicit invocation authorization, exact profiles, fresh private roots, and a finite budget.
- Rationale: framework usefulness depends on complete contracts, domain behavior, installation, runtime integration, safety, and verifiable execution. Tying closure to an unavailable account or expensive paper experiment would confuse backend availability and optional research evidence with product completeness.
- Revalidation trigger: make strict paper reproduction a product gate only if the user explicitly changes the project objective and approves a new work package, acceptance contract, and budget authority.

## D-054 — Normalize only same-file Python aliases in retained plan identity

- Status: ✅ accepted design clarification
- Decided: 2026-07-22
- Decision: AF-340 retained bounded inspection may match a report against conventional `python`, `python3`, and versioned Python aliases located in the current interpreter's environment `bin/` directory only when `samefile()` proves every candidate resolves to the identical interpreter inode.
- Evidence boundary: the validator selects one complete candidate plan whose plan SHA matches the signed report, then uses that exact plan for every operation/configuration hash check. A different executable, directory, argument, operation, resource manifest, artifact, signature, or permission remains fail-closed.
- Rationale: Pi r14 recorded `.venv/bin/python3`, while the documented and Climb inspection path uses `uv run python` and exposes `.venv/bin/python`; both names resolve to the same interpreter file, but literal-path hashing alone made valid retained evidence unusable. Same-file alias matching preserves executable identity without accepting arbitrary command drift.
- Revalidation trigger: any broader path normalization, interpreter upgrade, cross-environment reuse, or removal of per-operation command-template checks requires a new evidence schema and security review.

## D-055 — Bind dormant full execution to explicit successor governance

- Status: ✅ accepted security correction
- Decided: 2026-07-22
- Decision: AF-340's dormant `full` command may expose plan-only dry-runs in a completed lifecycle, but actual `--authorize-full` execution must name `--work-package-id` and fail closed unless the canonical scope audit reports one matching active package other than AF-340.
- Authority boundary: the matching worklist entry must contain the exact structured field `Full execution authority: AF-340`. That package marker, a matching invocation ID, an active lifecycle, the existing exact profile, explicit CLI authorization, fresh private root, and finite budget are all necessary; none is sufficient alone.
- Ordering boundary: governance validation occurs before credential checks, output-root creation, Task 6 capability authorization, provider construction, or any Agent/Judge operation. `dry-run`, retained inspection, and historical full-report inspection remain provider-free and do not require an active package.
- Rationale: preserving dormant research tooling must not let a completed repository bypass D-053 merely by supplying `--authorize-full`. A structured ledger marker makes future authority reviewable and machine-checkable without selecting or creating a successor now.
- Revalidation trigger: change the authority marker, permit AF-340 itself, accept multiple/implicit packages, or move governance after credential/filesystem effects only through a reviewed security migration and adversarial tests.
