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
