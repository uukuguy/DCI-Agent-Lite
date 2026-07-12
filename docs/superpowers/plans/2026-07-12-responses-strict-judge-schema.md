# Responses Strict Judge Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute inline with test-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Offer strict JSON Schema verdict generation for explicitly configured OpenAI Responses judges without changing compatible defaults.

**Architecture:** Add one opt-in `JudgeConfig` field; use it only in the Responses request builder. Include its safe public value in result-reuse identity and preserve existing Chat Completions JSON mode.

**Files:** Modify `src/dci/benchmark/judge.py`, `scripts/bcplus_eval/run_bcplus_eval.py`, `tests/test_judge.py`, evaluator tests, `.env.template`, `README.md`, and H-009 climb adapter scripts.

### Task 1: Red/green request and cache identity

- [ ] Write failing tests for opt-in Responses `text.format` JSON Schema and result reuse invalidation when the flag differs.
- [ ] Implement the validated environment flag, public metadata, opt-in schema request, and cache-identity comparison.
- [ ] Verify focused judge/evaluator tests pass while default Responses and Chat Completions payloads are unchanged.

### Task 2: Document and record H-009

- [ ] Document the default-off, Responses-only compatibility boundary.
- [ ] Add four H-009 local dimensions: opt-in request shape, default compatibility, cache identity, and docs/adapter integration.
- [ ] Run full verification and, only if the selected backend is compatible with Responses strict schema, run the live acceptance cycle; otherwise record a local-only compatibility result without changing defaults.
