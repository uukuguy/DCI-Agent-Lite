# Asterion Application Runner Vertical Slice Implementation Plan

> **For agentic workers:** Execute inline task-by-task when repository policy does not authorize delegation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute one resolved DCI application plan through an explicitly supplied runtime client and host-service map, returning immutable normalized events and artifacts.

**Architecture:** Extend the immutable assembly plan with explicit runtime-versus-host capability ownership, then add a small asynchronous Python runner under `asterion.runner`. The runner preflights identities and services, creates one portable request, delegates cancellation to the runtime client, validates the complete normalized stream, and deep-freezes successful output.

**Tech Stack:** Python 3.10+, dataclasses, `typing.Protocol`, `MappingProxyType`, unittest, existing Agent Runtime Protocol validators, TypeScript/Ajv parity checks, Rust/Cargo closure gates, Bash climb adapters.

## Global Constraints

- Active work package is `AF-100`; every climb cycle names it as parent.
- Consume an already resolved `AssemblyPlan`; do not interpret or execute package manifests.
- Runtime and host-service ownership must be explicit and immutable; never infer ownership from capability names.
- Do not discover, construct, authorize, or start host services.
- Public errors must not echo application input, provider payloads, raw tool output, credentials, or service objects.
- Add no scheduler, registry, retry engine, persistence, process manager, TypeScript runner, or control plane.
- Preserve all existing `dci.*` wire literals and `dci.framework.*` compatibility identities.

---

### Task 1: Explicit capability ownership in resolved plans

**Files:**
- Modify: `src/asterion/assembly/protocol.py`
- Modify: `tests/test_application_assembly.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`
- Modify: `tools/climb/hypotheses.yaml`
- Modify: `tests/test_climb_tools.py`
- Modify: generated climb state under `docs/status/climb/`

**Interfaces:**
- Produces: `AssemblyPlan.runtime_capabilities: tuple[str, ...]`
- Produces: `AssemblyPlan.host_capabilities: tuple[str, ...]`
- Preserves: existing application, runtime, package-ref, and composition fields.

- [x] **Step 1: Write RED ownership tests**

Add assertions that a DCI plan records `("filesystem.read", "shell")` as runtime-owned and `()` as host-owned, while the controlled-code plan records `("executor.controlled",)` only as host-owned. Assert tuples are deterministic and source manifests remain unchanged.

- [x] **Step 2: Run the focused RED test**

Run: `uv run python -m unittest tests.test_application_assembly.AssemblyResolverTests tests.test_application_assembly.ReferenceAssemblyTests -v`

Expected: fail because `AssemblyPlan` has no ownership fields.

- [x] **Step 3: Implement immutable ownership fields**

Populate the plan only from the already validated inputs:

```python
return AssemblyPlan(
    application_id=application_id,
    version=version,
    runtime_id=runtime_id,
    package_refs=package_refs,
    composition=composition,
    runtime_capabilities=tuple(sorted(runtime_capabilities)),
    host_capabilities=tuple(_string_edges(assembly, "host_capabilities")),
)
```

Do not derive either field from `composition.provided_capabilities` or capability-name conventions.

- [x] **Step 4: Run GREEN and static checks**

```bash
uv run python -m unittest tests.test_application_assembly -v
uv run python -m compileall -q src/asterion/assembly tests/test_application_assembly.py
uv run ruff check src/asterion/assembly tests/test_application_assembly.py
git diff --check
```

- [x] **Step 5: Add and execute AF-100-H-001**

Add dimensions `runtime_ownership`, `host_ownership`, `immutable_plan`, and `no_name_inference`. Make train run the focused assembly suite and local eval map one deterministic assertion to each dimension. Run the climb cycle only after `python3 tools/project_scope_check.py --climb-hypothesis AF-100-H-001` passes.

- [x] **Step 6: Commit the verified slice**

Commit message: `feat: record application capability ownership`

### Task 2: Minimal plan-driven application runner

**Files:**
- Create: `src/asterion/runner/__init__.py`
- Create: `src/asterion/runner/application.py`
- Create: `tests/test_application_runner.py`
- Modify: `src/asterion/runtime/host.py`
- Modify: `src/asterion/runtime/__init__.py`
- Modify: `src/dci/framework/host.py` only if its explicit re-export list requires the new signal type
- Modify: `tests/test_python_runtime_host.py`
- Modify: climb adapters and tests

**Interfaces:**
- Produces: `CancellationSignal` with read-only `cancelled: bool`.
- Extends: `AgentRuntimeClient.run(request, *, signal=None)` without changing wire data.
- Produces: frozen `ApplicationRunResult` and `run_application(...)`.

- [x] **Step 1: Write RED success and public-contract tests**

Use an async fixture client that records the `RunRequest` and yields `RunEvent` values. Assert runtime identity, run ID, input, requested runtime capabilities, event order, artifact projection, and frozen nested mappings. Assert Asterion runner source contains no adapter-private imports.

- [x] **Step 2: Run the RED runner suite**

Run: `uv run python -m unittest tests.test_application_runner -v`

Expected: import failure for missing `asterion.runner`.

- [x] **Step 3: Implement the minimal boundary**

Preflight the plan, runtime manifest, input, run ID, host services, and pre-cancel state before calling `runtime.run`. Consume the async iterator completely, convert events to mappings, validate with `validate_event_stream`, project `artifact.created` payloads, and recursively freeze mappings/lists before returning.

Wrap protocol, type, and runtime exceptions as content-free `ApplicationRunError`; never return partial events as success.

- [x] **Step 4: Run focused GREEN and compatibility checks**

```bash
uv run python -m unittest tests.test_application_runner tests.test_python_runtime_host tests.test_application_assembly tests.test_asterion_structure -v
uv run python -m compileall -q src/asterion src/dci/framework tests/test_application_runner.py
uv run ruff check src/asterion src/dci/framework tests/test_application_runner.py tests/test_python_runtime_host.py
git diff --check
```

- [x] **Step 5: Add and execute AF-100-H-002**

Dimensions: `portable_request`, `runtime_invocation`, `immutable_events`, `artifact_projection`.

- [x] **Step 6: Commit the verified slice**

Commit message: `feat: run resolved Asterion applications`

### Task 3: Runtime parity, cancellation, and fail-closed behavior

**Files:**
- Modify: `tests/test_application_runner.py`
- Modify: `src/asterion/runner/application.py`
- Modify: runtime-host contract tests as required
- Modify: climb adapters and tests

**Interfaces:**
- Consumes: Task 2 runner and cancellation protocol.
- Guarantees: every preflight failure occurs before runtime invocation; in-run cancellation is delegated unchanged; only a valid terminal stream succeeds.

- [x] **Step 1: Write RED failure-matrix tests**

Cover Pi/Claude fixture parity, runtime mismatch, each missing host capability, invalid input/run ID, pre-cancel, in-run cancellation, runtime exception, empty/malformed/incomplete/post-terminal streams, mismatched run IDs, and controlled-code without `executor.controlled`. Add sentinels to input, event payload, exception, and service objects and assert no public error contains them.

- [x] **Step 2: Run RED**

Run: `uv run python -m unittest tests.test_application_runner -v`

Expected: new failure cases expose missing preflight or error normalization behavior.

- [x] **Step 3: Implement only the missing safety behavior**

Keep validation in `application.py`; do not add a retry loop, service registry, background task, or process control. Pass the same signal object to the runtime and require its stream to end in normalized `completed`, `cancelled`, or `failed` lifecycle semantics.

- [x] **Step 4: Run focused and protocol gates**

```bash
uv run python -m unittest tests.test_application_runner tests.test_agent_runtime_protocol tests.test_python_runtime_host tests.test_pi_protocol_adapter tests.test_claude_code_protocol_adapter -v
uv run python -m compileall -q src tests/test_application_runner.py
uv run ruff check src tests/test_application_runner.py
git diff --check
```

- [x] **Step 5: Add and execute AF-100-H-003**

Dimensions: `runtime_parity`, `cancellation`, `preflight_safety`, `error_redaction`.

- [x] **Step 6: Commit the verified slice**

Commit message: `test: harden application runner failures`

### Task 4: Operator documentation and framework closure

**Files:**
- Create: `docs/architecture/application-runner.md`
- Modify: `README.md`
- Modify: `tests/test_application_runner.py`
- Modify: `tests/test_asterion_structure.py`
- Modify: `Makefile` only if a representative runner target is justified by the existing target style
- Modify: climb adapters/tests and repository status files

**Interfaces:**
- Documents: caller ownership, explicit services, cancellation, immutable results, safe errors, and non-goals.
- Closes: AF-100 only with fresh whole-repository evidence and a governed successor or explicit no-successor state.

- [ ] **Step 1: Write RED documentation and source-boundary tests**

Assert the guide names `AssemblyPlan`, `AgentRuntimeClient`, explicit host services, cancellation, immutable normalized events/artifacts, and fail-closed behavior. Assert no scheduler, registry, TypeScript runner, automatic service startup, or Rust subprocess launch entered the runner boundary.

- [ ] **Step 2: Write the guide and concise README entry**

Show construction from an already resolved plan and fixture client. State clearly that host-service presence is not authorization and the controlled executor remains caller-owned.

- [ ] **Step 3: Add and execute AF-100-H-004**

Dimensions: `runner_docs`, `boundary_integrity`, `language_ownership`, `framework_closure`.

- [ ] **Step 4: Run fresh closure gates**

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q src tests tools
uv run ruff check src tests tools
npm --prefix packages/typescript/asterion-runtime ci
npm --prefix packages/typescript/asterion-runtime test
make test-rust-executor
make check-rust-executor
bash -n scripts/examples/*.sh tools/climb/*.sh
python3 tools/project_scope_check.py --climb-hypothesis AF-100-H-004
git diff --check
```

- [ ] **Step 5: Close and checkpoint**

Update `WORKLIST.md`, `CURRENT-STATE.md`, `DECISIONS.md`, climb state, and JOURNAL from fresh evidence. Re-run the scope preflight before the closure commit.

Commit message: `docs: close application runner acceptance`
