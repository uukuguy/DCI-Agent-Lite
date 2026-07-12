# Pi Protocol Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox syntax.

**Goal:** Emit conformant Agent Runtime Protocol v1 attempts from the existing Pi RPC runner without changing Pi behavior.

**Architecture:** A focused `PiProtocolAdapter` translates raw Pi events. `RunRecorder` writes per-attempt request and event files and validates the completed stream. Process control remains in `PiRpcClient`.

**Tech Stack:** Python 3.10 standard library, existing protocol validator, `unittest`.

## Global Constraints

- Do not edit `pi/`.
- Do not remove or change raw `events.jsonl` semantics.
- Do not normalize thinking or provider request context.
- Emit completion only from recorder finalization after current settlement checks.

---

### Task 1: Build the event translator test-first

**Files:**
- Create: `src/dci/framework/adapters/__init__.py`
- Create: `src/dci/framework/adapters/pi.py`
- Create: `tests/test_pi_protocol_adapter.py`

- [ ] Write failing tests for capability mapping, text delta, tool start/end, assistant usage, ignored thinking, success with artifact, and safe failure.
- [ ] Run `uv run python -m unittest tests.test_pi_protocol_adapter -v`; expect import failure.
- [ ] Implement `map_pi_capabilities(tools: str | None) -> list[str]` and `PiProtocolAdapter` with `start`, `consume`, `complete`, and `fail` methods. Every emitted event uses the next contiguous sequence and is sent to an injected callable.
- [ ] Re-run focused tests, Ruff, and compile checks; commit `feat: map Pi events to runtime protocol`.

### Task 2: Persist isolated protocol attempts through RunRecorder

**Files:**
- Modify: `src/dci/benchmark/pi_rpc_runner.py`
- Modify: `tests/test_pi_rpc_runner.py`

- [ ] Write failing recorder tests asserting `protocol/attempt-0001.request.json` and `.events.jsonl`, a valid terminal stream, and `attempt-0002` isolation on resume.
- [ ] Run focused recorder tests and confirm failure because protocol attempt files are absent.
- [ ] Initialize the adapter in `RunRecorder` using `resume_count + 1`, map raw events after appending the raw file, and finish it from `finalize`. On success hash `final.txt` and emit it as an artifact before completion. Validate the final event list with `validate_event_stream`.
- [ ] Add the current protocol file paths and run ID to `state.json` without removing existing path keys.
- [ ] Re-run Pi adapter, protocol, and Pi lifecycle tests; commit `feat: persist Pi protocol attempts`.

### Task 3: Verify AF-020 and preserve compatibility

**Files:**
- Modify: `docs/status/{JOURNAL,WORKLIST,RESUME-NEXT-SESSION}.md`

- [ ] Run `uv run python -m unittest discover -v`.
- [ ] Run compile, Ruff, `git diff --check`, and `python3 tools/project_scope_check.py`.
- [ ] Run `make runtime-example` only when valid provider and judge credentials are available; otherwise record that the deterministic mapping is locally verified but the new artifact awaits a provider-backed acceptance.
- [ ] Mark AF-020 complete only when required local acceptance passes; preserve any credentialed runtime acceptance as an explicit follow-up if credentials are unavailable.
