# Controlled-Code Executable Application Implementation Plan

> **For agentic workers:** Execute inline with test-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a second bundled executable Asterion application whose fixed host-owned validation request runs through an explicitly injected controlled-executor service.

**Architecture:** A typed Python service contract isolates logical validation from host-enforced policy. Three exact executable package implementations transform one bounded execution result through workflow, verdict, and audit artifacts; the policy package remains declarative. A separate built-in provider binds canonical manifests/assembly; a JSONL client connects only to an already running Rust sidecar.

**Tech Stack:** Python 3.10+, asyncio JSONL, immutable dataclasses, existing package runner/provider contracts, existing Rust `dci.executor/v1` service.

## Global Constraints

- Application input and manifests never choose executable, arguments, workspace, environment, deadline, or limits.
- `executor.controlled` is explicitly injected and never automatically started.
- Generic CLI/provider/runner modules contain no controlled-code special case.
- No shell, scheduler, repair loop, sandbox claim, or DCI baseline change.

---

### Task 1: Controlled executor host-service contract

**Files:**
- Create: `packages/python/asterion-core/src/asterion/services/controlled_executor.py`
- Create: `tests/test_controlled_executor_service.py`

**Interfaces:** frozen logical request/result values, async `ControlledExecutorService.execute(request, signal=None)`, strict validation and safe failures.

- [ ] Write RED tests for immutability, closed types, cancellation, bounded normalized results, and secret-free errors.
- [ ] Implement the minimal Protocol/value validation.
- [ ] Run focused tests, compile, Ruff, scope, diff, and commit `feat: define controlled executor host service`.

### Task 2: Controlled-code executable package implementations

**Files:**
- Move: `capabilities/controlled-code/manifests/*.json` to `packages/python/asterion-core/src/asterion/capabilities/controlled_code/manifests/`
- Create: `packages/python/asterion-core/src/asterion/capabilities/controlled_code/implementation.py`
- Create: `tests/test_controlled_code_application.py`

**Interfaces:** three exact implementations for workflow/evaluation/observability; declarative policy; one executor call; declared report/verdict/audit outputs.

- [ ] Write RED order/service/output/failure tests using a fixture runtime/service.
- [ ] Move canonical manifests and implement minimal deterministic transformations.
- [ ] Update catalog/composition/TypeScript paths atomically.
- [ ] Verify and commit `feat: execute controlled-code packages`.

### Task 3: Independent bundled provider and application

**Files:**
- Move: controlled-code assembly to `asterion/applications/controlled_code/assemblies/`
- Create: `asterion/applications/controlled_code/provider.py`
- Modify: Asterion `pyproject.toml`
- Modify: provider/distribution/application tests.

**Interfaces:** entry point/provider `controlled-code`; exact application `code.quality@1.0.0`; four bindings; explicit `executor.controlled` service requirement.

- [ ] Write RED installed metadata/resource/binding tests.
- [ ] Implement provider and second entry point without generic special cases.
- [ ] Verify isolated list/select plus focused suites and commit `feat: bundle controlled-code application`.

### Task 4: JSONL sidecar client and closure

**Files:**
- Create: `asterion/services/controlled_executor_jsonl.py`
- Create: `tests/test_controlled_executor_jsonl.py`
- Create: `applications/controlled-code/python/controlled_code_host.py`
- Modify: architecture/status documentation.

**Interfaces:** client over caller-owned reader/writer correlates one closed `dci.executor/v1` request/response and never starts a process; explicit host example injects it.

- [ ] Write RED correlation/malformed/cancel/redaction tests.
- [ ] Implement minimal transport and explicit host example.
- [ ] Run full Python/Node/Rust/compile/lint/shell/scope/diff/isolated-wheel gates.
- [ ] Close AF-140 with evidence and governed successor; commit `docs: close controlled-code executable application`.
