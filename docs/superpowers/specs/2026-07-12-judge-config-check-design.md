# Judge Configuration Check Design

## Context

H-007 makes successful judge-preflight output show safe key provenance, but a
stale process key still causes the request itself to fail before the JSON output
is available. Users need the same non-secret provenance before deciding whether
to spend a request.

## Decision

Add `scripts/check_judge.py --config-only` and `make check-judge-config`. The
command resolves the normal judge configuration and provenance, prints the same
safe public fields plus `request_performed: false`, and performs no HTTP request.

## Design

- Parse `--config-only` with `argparse` after the normal configuration resolver.
- Reuse `load_judge_config_with_provenance` and `config.public_dict`; no second
  configuration path and no key material in memory beyond normal resolution.
- Keep `make check-judge` unchanged for real structured-output validation.
- Test that config-only output is safe, reports provenance, and never calls
  `run_preflight`.

## Non-goals

- Do not alter process-environment precedence or add an API call to the
  configuration check.
