# Judge Key Provenance Design

## Context

The successful H-006 preflight exposed a configuration-drift boundary: project
loading intentionally preserves an already exported `DEEPSEEK_API_KEY`, so a user
can rotate `.env` while a stale process value still wins. The 401 looked like a
provider outage until the two non-secret source states were compared.

## Decision

Extend `make check-judge` with safe credential provenance. Its output will state
whether the effective key came from the process environment, `.env`, or is
missing, plus a boolean warning when a different `.env` value is shadowed by a
pre-existing process value. It will never output a key, digest, length, request,
or provider response body.

## Design

- Snapshot the process environment before calling `load_project_env`, then parse
  `.env` only in memory to determine source ownership for the key actually chosen
  by `JudgeConfig`.
- Preserve the existing precedence contract: explicit process values win; H-007
  reports that fact rather than silently overriding it.
- Emit `judge_api_key_source` and `judge_api_key_shadowed_by_environment` beside
  the existing safe preflight payload.
- Unit tests cover process-only, dotenv-only, and conflicting-source cases without
  using a real credential or request.

## Non-goals

- Do not change normal `.env` precedence, store key fingerprints, or alter batch
  evaluator configuration.
