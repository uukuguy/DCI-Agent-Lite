# Judge Configuration Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute inline with test-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users inspect effective judge configuration and credential provenance without a network request.

**Architecture:** The existing provenance loader remains the single configuration path. An `argparse` flag prints a safe `request_performed: false` payload and returns before `run_preflight`; a Make target and H-008 adapter expose it.

**Files:** Modify `scripts/check_judge.py`, `tests/test_check_judge.py`, `Makefile`, `README.md`, `.env.template`, `tools/climb/train.sh`, and `tools/climb/eval-local.sh`.

### Task 1: Red/green config-only command

- [ ] Write a failing test invoking `--config-only`, asserting `request_performed: false`, safe provenance, and no call to `run_preflight`.
- [ ] Run `uv run python -m unittest tests.test_check_judge -v` and observe the failure.
- [ ] Add `--config-only` via `argparse`; emit only `config.public_dict()`, provenance, `ok`, and `request_performed: false` before any request.
- [ ] Re-run focused tests and commit the command.

### Task 2: Document and record H-008

- [ ] Add `make check-judge-config`, document it beside `make check-judge`, and explain that it performs no HTTP request.
- [ ] Add the H-008 local dimensions: config-only safety, dotenv source, shadow warning, and Make/adapter integration.
- [ ] Run the full unit suite, compilation, Ruff, Bash syntax, `make check-pi-rpc`, and `env -u DEEPSEEK_API_KEY make check-judge-config`.
- [ ] Run `env -u DEEPSEEK_API_KEY bash tools/climb/cycle.sh H-008` and commit the regenerated evidence.
