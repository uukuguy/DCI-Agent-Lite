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
