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

- Status: ✅ accepted and implemented decision
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
- Implemented evidence: AF-095-H-001 confirms the authoritative Asterion runtime/host/adapter modules, old/new object identity, one-way dependency rule, and dual-root wheel packaging.
