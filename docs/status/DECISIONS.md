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
