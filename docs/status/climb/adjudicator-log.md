# Climb Adjudicator Log

Append-only decision-gate record.

## 2026-07-12 H-001

- Decision: pursue a single tracked revision lock with exact-commit override support.
- Evidence: moving `main` is non-reproducible; duplicate pins can drift; submodule/vendor conflicts with the external-checkout boundary.
- Vote: autonomous climb adjudication — PUSH to deterministic local acceptance.

## 2026-07-12 Knowledge Layer after H-003

- External search: no usable official search result returned; pinned Pi source/docs remained the primary source.
- Multi-AI adapter: Gemini and OpenCode unavailable; the local stub returned PUSH and was not treated as independent evidence.
- Ranked pool: H-004 run provenance, H-005 mismatch diagnosis, H-006 judge live preflight.
- Decision: advance H-004 because immutable setup is incomplete unless each result records the actual Pi source state.

## 2026-07-12 Knowledge Layer after H-006

- External reference: python-dotenv documents that `load_dotenv(..., override=False)` preserves process environment values.
- Local evidence: a stale exported `DEEPSEEK_API_KEY` differed from the newly rotated `.env` value and caused the first preflight retries to return 401; unsetting only the inherited variable made the same preflight pass.
- Ranked pool: H-007 judge credential provenance (rank 0.70).
- Decision: expose safe effective-source and shadowing metadata in the explicit preflight, preserving the intentional precedence contract.

## 2026-07-12 Knowledge Layer after H-007

- Local evidence: H-007 provenance is emitted only after the credentialed request succeeds, so a shadowed invalid process key still hides its source on the failing path.
- Ranked pool: H-008 no-request judge configuration check (rank 0.65).
- Decision: provide an offline `check-judge-config` target that reuses the normal resolver and reports only safe public configuration/provenance.

## 2026-07-12 Knowledge Layer after H-008

- External reference: OpenAI documents `json_schema` as the preferred structured-output mode for supporting APIs, while JSON object mode remains the compatibility fallback.
- Local evidence: the current generic Responses request relies on prompt-directed JSON and parser retries; no strict schema request shape exists.
- Ranked pool: H-009 opt-in Responses strict schema (rank 0.60).
- Decision: add an explicit default-off flag restricted to Responses and include it in cached evaluation identity.

## 2026-07-12 Knowledge Layer after H-015

- Local evidence: `JudgeConfig` accepts `file:`, `ftp:`, `mailto:`, relative, and hostless URLs, then exposes their derived endpoints through safe metadata and transport errors.
- External references: Python documents that `urlsplit()` does not validate inputs and that `urllib.request` installs file and FTP handlers by default; OpenAI documents that Responses are retained for 30 days unless storage is disabled.
- Multi-AI adapter: Gemini and OpenCode remain unavailable; the local stub returned PUSH and is not independent evidence.
- Ranked candidate: H-016 absolute HTTP(S) judge-origin validation (rank 0.95).
- Held for the next Knowledge Layer: reject automatic judge redirects (H-017 candidate) and opt out of official Responses retention without changing generic-compatible request shapes (H-018 candidate).
- Decision: advance H-016 first because it removes already-proven unsupported URL schemes before an authorization header or evaluated input can reach `urllib` handlers.

## 2026-07-12 Knowledge Layer after H-016

- Local evidence: `judge_answer_sync()` calls the default `urllib.request.urlopen()` handler chain after configuration ingress; it does not constrain a later redirect response.
- External reference: Python documents that its default redirect handler automatically redirects POST 301/302/303 responses and retains POST for 307/308; standard OpenAI-compatible judge endpoints do not require redirects.
- Multi-AI adapter: Gemini and OpenCode remain unavailable; the local stub returned PUSH and is not independent evidence.
- Ranked candidate: H-017 judge redirect containment (rank 0.92).
- Held for the next Knowledge Layer: opt out of official Responses retention without changing generic-compatible request shapes (H-018 candidate).
- Decision: advance H-017 because a configured origin boundary is incomplete if a transport redirect can move authorization or evaluated input elsewhere.

## 2026-07-12 Knowledge Layer after H-017

- External reference: OpenAI documents a 30-day Responses application-state retention period by default or when `store=true`; `store=false` opts out of that response storage.
- Local evidence: DCI's official Responses payload contains evaluated input but omits `store`, while the generic-compatible Responses request intentionally uses only a minimal shared shape.
- Multi-AI adapter: Gemini and OpenCode remain unavailable; the local stub returned PUSH and is not independent evidence.
- Ranked candidate: H-018 official Responses storage opt-out (rank 0.90).
- Decision: send `store=false` by default only to the exact official OpenAI Responses endpoint, permit an explicit opt-in, and omit the field entirely for compatible endpoints.

## 2026-07-12 Knowledge Layer after H-018

- External reference: the Pi upstream settlement discussion identifies session-level `agent_settled` as ambiguous for overlapping lifecycle requests and calls request-scoped correlation necessary.
- Local evidence: DCI correlates its prompt acknowledgement and waits for `agent_settled`, but returns immediately without checking Pi's independently available `get_state` idle fields.
- Multi-AI adapter: Gemini and OpenCode remain unavailable; the local stub returned PUSH and is not independent evidence.
- Ranked candidate: H-019 RPC settlement postcondition (rank 0.88).
- Decision: after an `agent_settled` event only, issue a bounded correlated `get_state` probe and reject streaming, compaction, or queued messages without weakening the legacy `agent_end` fallback.

## 2026-07-12 Knowledge Layer after H-019

- Local review: validated settlement state is available during a run, but persisting it would expand artifacts rather than close an unverified runtime, protocol, or judge-transport invariant.
- Ruled out: proxy policy needs an explicit deployment trust decision; broader Pi concurrency handling does not apply while DCI issues one lifecycle-changing prompt at a time; no additional compatible judge request field is independently justified.
- Decision: hard-pause the autonomous loop. Resume only with a new Pi protocol observation, a judge-provider transport failure, or an explicit artifact-provenance requirement.
