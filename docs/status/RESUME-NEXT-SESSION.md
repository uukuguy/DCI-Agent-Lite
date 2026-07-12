# Recovered Session Checkpoint

> Updated: 2026-07-12 17:34 +0800. **Active H-009 strict-schema checkpoint — session remains active, not a final handoff.**

## TL;DR

- Autonomous climb confirmed and committed H-001 through H-005 at 4/4 each: immutable Pi lock, read-only pin review, model-free RPC preflight, run provenance, and pre-run revision warning.
- The exact Pi default is `8479bd84743e8889f728acb21a62794102db0529`; the independent dirty `pi/` checkout was never modified.
- H-006 is confirmed 4/4 against the real configured DeepSeek backend after using the new `.env` key without the stale inherited process value. The pool is empty, so Knowledge Layer is active.
- H-007 confirmed 4/4 and now reports safe dotenv/process/shadow provenance on successful preflight output.
- Knowledge Layer added H-008: an offline configuration check will expose the same source information before a credentialed preflight request.
- H-008 confirmed 4/4; Knowledge Layer added H-009 for default-off strict JSON Schema on supporting Responses backends.
- H-008 is locally verified: its config-only path makes no request and emits safe dotenv/process/shadow metadata through a four-dimension climb adapter.
- H-006 scope and a test-first inline plan are committed; work proceeds in the clean shared checkout without touching the independent `pi/` repository.
- The safe standalone preflight, Make target, documentation, and four-dimension climb adapter are fully verified and H-006 is recorded as cycle 6.
- The earlier HTTP 401 was caused by a stale exported `DEEPSEEK_API_KEY` overriding the rotated `.env` value; `load_project_env` deliberately uses `override=False`.
- Shared judge HTTP errors now retain endpoint/status while suppressing provider response bodies, preventing provider-side credential echoes from entering stderr or batch artifacts.
- A real preflight with `env -u DEEPSEEK_API_KEY make check-judge` passed, returning `is_correct: true`; no API key, request prompt, or provider response body was emitted.

## Committed state

- Branch: `main`; the last recorded boundary said 18 commits ahead of `origin/main` before the handoff-state commit, with nothing pushed. The working tree is clean at recovery.
- Latest feature commit: `b5b29b8 feat: warn on Pi revision drift before RPC runs`.
- Key earlier commits: `09d677d` run provenance, `e53822f` RPC probe, `862a51e` read-only pin check, `27a68a6` immutable setup lock.
- `docs/status/climb/research-tree.md` contains five confirmed runs and H-006 pending; `session-state.json` has no in-flight cycle or process.
- The climb post-commit hook is installed and recorder replay is idempotent.

## Verification evidence

- Latest full suite: 48 tests, 0 failures; Ruff, compileall, all touched Bash syntax, and `git diff --check` passed.
- `make check-pi-rpc` returned a valid model-free `get_state` response.
- H-004 runtime acceptance answered `Adaku`, judge `is_correct: true`; `state.json.pi_source` recorded commit `8479…`, `lock_match=true`, `dirty=true`.
- Real `pi/` HEAD and dirty file list remained unchanged across setup, probe, and runtime checks.

## Next action

1. Execute H-009 in RED: add opt-in Responses strict-schema request shaping and cache identity without altering compatible defaults.
2. Prefer reusing `JudgeConfig`/`judge_answer_sync`; do not introduce a second request-shaping path.
3. Keep credentials out of artifacts/output, add a Make target and docs, then run the climb cycle and full verification.
4. If the pool empties after H-006, trigger Knowledge Layer again rather than stopping.

## Ruled-out paths

- No duplicated authoritative Pi pin, submodule/vendor ownership, destructive dirty-checkout reconciliation, or blocking custom-package runs.
- Do not treat the unavailable Gemini/OpenCode consult stub as independent evidence.
- Do not replace `make runtime-example` with the model-free RPC probe; they cover different contracts.
- Do not change `.env` precedence globally: exported process variables intentionally win. Address the observed confusion with safe provenance reporting rather than silently overriding caller configuration.

## Boundary and exceptions

- No processes are in flight. Temporary root planning files from this session have been removed.
- `pi/` is an independent, deliberately excluded checkout at `8479bd84743e8889f728acb21a62794102db0529`; it remains dirty in user-owned provider manifest/model files plus `.pi/agent/`. Do not reset, clean, stage, or commit it from this repository.
- No credentials, judge requests, or runtime output need recovery from this session.

## Ready commands

```bash
project-state resume
cat docs/status/climb/research-tree.md
uv run python -m unittest discover -v
make check-pi-rpc
```
