# Agent Runtime Protocol v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox syntax.

**Goal:** Ship a validated, language-neutral Agent Runtime Protocol v1 with Python reference parsing and executable conformance fixtures.

**Architecture:** JSON Schema and JSONL fixtures are the language-neutral contract. `src/dci/framework/protocol.py` provides a dependency-free Python reference parser that enforces lifecycle and payload rules. Pi integration remains untouched until AF-020.

**Tech Stack:** Python 3.10 standard library, `unittest`, JSON Schema documents, JSON Lines fixtures.

## Global Constraints

- Protocol literal is exactly `dci.agent-runtime/v1`.
- Do not expose credentials, raw provider payloads, hidden reasoning, or adapter-private fields.
- Do not modify `pi/` or migrate `pi_rpc_runner.py` in AF-010.
- Every accepted fixture has contiguous sequences and exactly one terminal event.

---

### Task 1: Define canonical schema and valid conformance fixtures

**Files:**
- Create: `schemas/agent-runtime/v1/run-request.schema.json`
- Create: `schemas/agent-runtime/v1/event.schema.json`
- Create: `tests/fixtures/agent_runtime/v1/valid-research.jsonl`
- Create: `tests/fixtures/agent_runtime/v1/valid-cancelled.jsonl`
- Create: `tests/fixtures/agent_runtime/v1/valid-artifact.jsonl`

- [ ] **Step 1: Write fixture-discovery tests**

Create `tests/test_agent_runtime_protocol.py` with tests that read every `valid-*.jsonl` fixture, parse one JSON object per non-empty line, and expect the later `validate_event_stream` reference API to accept the stream.

- [ ] **Step 2: Prove RED**

```bash
uv run python -m unittest tests.test_agent_runtime_protocol.AgentRuntimeProtocolTests.test_valid_fixtures_conform -v
```

Expected: import failure because `dci.framework.protocol` does not exist.

- [ ] **Step 3: Add schema and fixtures**

`run-request.schema.json` requires protocol, run_id, and input.text. `event.schema.json` requires protocol, run_id, sequence, type, and object payload. The research fixture begins with `run.started`, includes a paired `tool.call`/`tool.result`, and ends with `run.completed`. The cancelled fixture ends with `run.completed` status `cancelled`. The artifact fixture contains `artifact.created` with SHA-256 metadata before terminal completion.

- [ ] **Step 4: Commit the fixture contract**

```bash
git add schemas/agent-runtime tests/fixtures/agent_runtime tests/test_agent_runtime_protocol.py
git commit -m "test: define agent runtime protocol fixtures"
```

### Task 2: Implement Python reference validation test-first

**Files:**
- Create: `src/dci/framework/__init__.py`
- Create: `src/dci/framework/protocol.py`
- Modify: `tests/test_agent_runtime_protocol.py`

- [ ] **Step 1: Add failing lifecycle and payload tests**

Add tests that expect `ProtocolError` for a stream without `run.started`, a sequence gap, an unmatched `tool.result`, and an event after `run.completed`. Add request tests for missing input text and a deadline outside the allowed range.

- [ ] **Step 2: Prove RED**

```bash
uv run python -m unittest tests.test_agent_runtime_protocol -v
```

Expected: failures because the parser has not yet implemented the contract.

- [ ] **Step 3: Implement the reference API**

Export these exact symbols:

```python
PROTOCOL_VERSION = "dci.agent-runtime/v1"

class ProtocolError(ValueError):
    pass
```

Implement `validate_run_request(request: Mapping[str, object]) -> None` and `validate_event_stream(events: Iterable[Mapping[str, object]]) -> None`. Validate the envelope, all v1 payload shapes, contiguous sequence numbers, call/result pairing, and terminal lifecycle rules from the design. Return `None` for valid input; raise `ProtocolError` with a safe descriptive message otherwise.

- [ ] **Step 4: Prove GREEN and commit**

```bash
uv run python -m unittest tests.test_agent_runtime_protocol -v
uv run ruff check src/dci/framework tests/test_agent_runtime_protocol.py
uv run python -m compileall -q src/dci/framework
git add src/dci/framework tests/test_agent_runtime_protocol.py
git commit -m "feat: validate agent runtime protocol streams"
```

### Task 3: Add invalid fixture conformance coverage

**Files:**
- Create: `tests/fixtures/agent_runtime/v1/invalid-sequence-gap.jsonl`
- Create: `tests/fixtures/agent_runtime/v1/invalid-unmatched-tool-result.jsonl`
- Create: `tests/fixtures/agent_runtime/v1/invalid-post-terminal.jsonl`
- Modify: `tests/test_agent_runtime_protocol.py`

- [ ] **Step 1: Write the failing invalid-fixture parametrized test**

The test loads every `invalid-*.jsonl` fixture and asserts `validate_event_stream` raises `ProtocolError`.

- [ ] **Step 2: Prove RED, implement only missing validation, and prove GREEN**

```bash
uv run python -m unittest tests.test_agent_runtime_protocol.AgentRuntimeProtocolTests.test_invalid_fixtures_are_rejected -v
uv run python -m unittest tests.test_agent_runtime_protocol -v
```

Expected after implementation: valid fixtures pass and every invalid fixture is rejected.

- [ ] **Step 3: Commit conformance coverage**

```bash
git add tests/fixtures/agent_runtime tests/test_agent_runtime_protocol.py src/dci/framework/protocol.py
git commit -m "test: cover invalid agent runtime protocol streams"
```

### Task 4: Verify AF-010 and preserve the AF-020 boundary

**Files:**
- Modify: `docs/status/{JOURNAL,WORKLIST,RESUME-NEXT-SESSION}.md`

- [ ] **Step 1: Run complete verification**

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q src
uv run ruff check src/dci/framework tests/test_agent_runtime_protocol.py
python3 tools/project_scope_check.py
git diff --check
```

- [ ] **Step 2: Record results and advance only with evidence**

Append the verification evidence to JOURNAL. Mark AF-010 `completed` only when all conformance fixtures pass, then activate AF-020 and make its next action a Pi-to-protocol mapping design. Otherwise keep AF-010 active and name the failed criterion in RESUME.
