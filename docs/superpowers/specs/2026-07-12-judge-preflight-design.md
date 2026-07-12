# Judge Structured-Output Preflight Design

## Context

H-006 addresses the remaining cheap failure boundary before a batch evaluator spends
tokens: the configured OpenAI-compatible judge may accept a request but fail to
produce the structured verdict that the evaluator requires.

## Decision

Add an opt-in `make check-judge` command. It makes exactly one minimal grading
request through the existing `JudgeConfig` and `judge_answer_sync` transport, then
requires a boolean `is_correct` result. The command is a preflight tool only; batch
evaluators do not invoke it automatically.

This is preferred over an automatic batch gate because that would add spend and
change every evaluation run, and over a second low-level probe because it would
duplicate the request shaping and parsing contract under test.

## Design

- `scripts/check_judge.py` loads the repository `.env`, resolves `JudgeConfig` once,
  and uses `judge_answer_sync` with a fixed, trivial question/gold/prediction trio.
- A zero exit status means the request completed and yielded a boolean
  `is_correct`. Output contains only the safe public configuration, normalized
  verdict, and usage/cost metadata; it never prints an API key or raw request body.
- Invalid JSON, a missing/non-boolean verdict, transport failures, or missing
  credentials fail non-zero with an actionable error. No request or response is
  written to an artifact file.
- `Makefile` exposes the command as `check-judge`, adjacent to `check-pi-rpc`.
- `.env.template` and user-facing documentation describe the command as the
  credentialed complement to the model-free Pi RPC preflight, to run before costly
  batch evaluation.

## Tests and acceptance

- Unit tests patch the HTTP transport and prove the script reuses configured
  Responses and Chat Completions request shaping through `judge_answer_sync`.
- Tests prove a non-boolean/invalid judge result exits non-zero and the displayed
  payload never includes `api_key`.
- Focused tests fail before the command exists, then pass with the implementation.
- Final verification runs the full unit suite, Python compilation, Ruff for touched
  Python files, `make check-pi-rpc`, `git diff --check`, and—only with valid local
  credentials—`make check-judge`.

## Non-goals

- Do not add a new judge API, persistence format, batch retry policy, or automatic
  preflight before evaluators.
- Do not write credentials, raw judge responses, or request prompts to outputs or
  climb state.
