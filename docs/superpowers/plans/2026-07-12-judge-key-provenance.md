# Judge Key Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute inline with test-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `check-judge` identify safe credential provenance before it spends a request.

**Architecture:** A small helper snapshots the environment, parses `.env` in memory, resolves the normal `JudgeConfig`, and returns only a source label plus a shadowing boolean. The existing preflight output includes those fields without changing request construction or precedence.

**Files:** Modify `scripts/check_judge.py` and `tests/test_check_judge.py`; update `.env.template` and `README.md`; extend the H-007 climb adapter.

### Task 1: Red/green provenance helper

- [ ] Add failing unit tests for dotenv-only, process-only, and conflicting key sources. Each test asserts source labels and the shadowing boolean but never compares or prints a secret.
- [ ] Run `uv run python -m unittest tests.test_check_judge -v` and confirm the new provenance assertions fail.
- [ ] Add `load_judge_config_with_provenance()` that snapshots `os.environ`, parses `.env` with `dotenv_values`, calls the existing loader/configuration path once, and returns `(JudgeConfig, provenance)`.
- [ ] Include `judge_api_key_source` and `judge_api_key_shadowed_by_environment` in the safe JSON result; keep process-environment precedence unchanged.
- [ ] Re-run the focused test module and commit the tested helper.

### Task 2: Document and record H-007

- [ ] Add a brief `.env.template` and README explanation that exported credentials intentionally override `.env`, and `make check-judge` reports that source safely.
- [ ] Add an H-007 train/eval contract that runs the provenance test module and validates four dimensions: dotenv source, process source, shadow warning, and safe output.
- [ ] Run the full unit suite, Python compilation, Ruff, Bash syntax, `make check-pi-rpc`, then `env -u DEEPSEEK_API_KEY make check-judge`.
- [ ] Run `env -u DEEPSEEK_API_KEY bash tools/climb/cycle.sh H-007`, regenerate tracked state, journal the outcome, and commit the verified evidence.
