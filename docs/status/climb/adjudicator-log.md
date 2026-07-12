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
