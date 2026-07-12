# Composable Capability Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable Asterion package-implementation contract and execute the DCI local-corpus research capability without importing or modifying the original DCI benchmark.

**Architecture:** `AssemblyPlan` retains immutable selected manifests; an Asterion-owned sequential executor preflights exact implementation bindings and validates package outputs. An independently packaged DCI research implementation delegates research to an explicit runtime client, while a reference application host supplies all bindings directly. Generic installed-application binding and `asterion run` remain deferred to AF-120.

**Tech Stack:** Python 3.10+, frozen dataclasses, `Protocol`, async iterators, `unittest`, JSON manifests, existing Agent Runtime Protocol and package/assembly contracts.

## Global Constraints

- Do not modify any file under `src/dci/benchmark/` or either existing DCI example script.
- `src/asterion/` must never import `dci` or an independently owned capability implementation.
- Package and assembly manifests contain no Python module paths, commands, prompts, credentials, provider configuration, or mutable state.
- Bind implementations by exact `PackageRef(package_id, version)`; do not scan imports, solve versions, or select a highest version.
- AF-110 is sequential only: no parallel scheduler, retry, persistence, recovery, registry, automatic service startup, or generic CLI.
- Public errors may contain structural IDs and failure classes but no input, corpus, provider payload, raw tool output, credentials, or service content.
- Preserve the stable `dci.*` wire protocol literals and all `dci.framework.*` compatibility aliases.
- Use focused `uv run python -m unittest ... -v`, Python compilation, Ruff, Node/Rust checks, scope preflight, and `git diff --check`.

---

## File Structure

- `src/asterion/assembly/protocol.py` — retain immutable selected package manifests in `AssemblyPlan`.
- `src/asterion/packages/execution.py` — package invocation/result values, implementation protocol, exact registry validation, and output validation.
- `src/asterion/runner/composed.py` — deterministic sequential package execution; does not discover implementations.
- `src/asterion/packages/__init__.py`, `src/asterion/runner/__init__.py` — public exports only.
- `capabilities/dci-research/src/asterion_dci_research/implementation.py` — independently owned DCI research package implementation.
- `capabilities/dci-research/src/asterion_dci_research/__init__.py` — capability implementation exports.
- `applications/dci-agent-lite/assemblies/dci-research-capability.json` — minimal executable policy + research application slice.
- `applications/dci-agent-lite/python/dci_research_host.py` — explicit composition root used by integration tests; no generic CLI.
- `src/asterion/runtimes/pi.py` — independent minimal Pi RPC runtime client for Asterion; shares no benchmark code.
- `tests/test_package_execution.py` — package contract, exact binding, redaction, and output validation.
- `tests/test_composed_application_runner.py` — ordering, cancellation, reuse, and host integration.
- `tests/test_dci_research_capability.py` — DCI implementation/runtime parity and baseline isolation.
- `tests/test_asterion_pi_runtime.py` — independent Pi JSONL client process tests.
- `tests/test_asterion_structure.py` — source and distribution boundaries.
- `pyproject.toml` — include the independent capability implementation package; preserve existing scripts.
- `docs/architecture/capability-execution.md` — operator/developer contract and AF-120 deferral.

### Task 0: Activate AF-110 governance before implementation

**Files:**
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md` append-only
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- Consumes: approved design `docs/superpowers/specs/2026-07-13-composable-capability-execution-design.md` and this plan.
- Produces: exactly one active package, AF-110, with AF-100 completed and AF-120 recorded as a dependency-blocked successor.

- [ ] **Step 1: Add the governed successor packages**

In `WORKLIST.md`, mark AF-100 `completed`; add AF-110 as `in_progress` with
outcome, scope, AF-100 dependency, exact design/plan links, and acceptance copied
from the approved spec. Add AF-120 as `pending`, dependent on AF-110, scoped only
to secure installed-application binding and the generic `asterion run` entry
point.

- [ ] **Step 2: Record the architecture decision**

Append a new decision stating that capability packages are reusable executable
units, applications are executable composition boundaries, baseline DCI remains
independent, and generic implementation distribution/binding is deferred to
AF-120 because Asterion core cannot safely discover independently owned code
without a reviewed binding mechanism.

- [ ] **Step 3: Refresh structural and recovery markers**

Set `Project route: managed`, `Canonical worklist: docs/status/WORKLIST.md`, and
`Active work package: AF-110` in `CURRENT-STATE.md`. Append one journal line for
the atomic transition and refresh the live RESUME checkpoint with AF-110's first
test-first action.

- [ ] **Step 4: Verify governance before code**

Run: `python3 tools/project_scope_check.py`

Expected: `{"active_package":"AF-110","errors":[],"ok":true}`.

- [ ] **Step 5: Commit the transition atomically**

```bash
git add docs/status/WORKLIST.md docs/status/DECISIONS.md docs/status/CURRENT-STATE.md docs/status/JOURNAL.md docs/status/RESUME-NEXT-SESSION.md
git commit -m "docs: activate composable capability execution"
```

### Task 1: Preserve selected package declarations in the assembly plan

**Files:**
- Modify: `src/asterion/assembly/protocol.py`
- Modify: `tests/test_application_assembly.py`

**Interfaces:**
- Consumes: `PackageCatalog.select(refs) -> tuple[Mapping[str, object], ...]`.
- Produces: `AssemblyPlan.package_manifests: tuple[Mapping[str, object], ...]`, ordered exactly like `composition.package_ids` and deeply immutable.

- [ ] **Step 1: Write failing immutable-manifest tests**

Add imports for `MappingProxyType` and tests equivalent to:

```python
def test_plan_retains_deeply_immutable_manifests_in_execution_order(self) -> None:
    plan = resolve_assembly(
        self.assembly(),
        catalog=discover_packages(MANIFESTS),
        runtime_manifest=self.runtime(),
    )
    self.assertEqual(
        tuple(item["package_id"] for item in plan.package_manifests),
        plan.composition.package_ids,
    )
    self.assertIsInstance(plan.package_manifests[0], MappingProxyType)
    with self.assertRaises(TypeError):
        plan.package_manifests[0]["kind"] = "workflow"
    required = plan.package_manifests[-1]["requires_capabilities"]
    self.assertIsInstance(required, tuple)
```

Also mutate the fresh catalog selection after resolution and assert the plan is unchanged.

- [ ] **Step 2: Run the focused test and confirm the contract is absent**

Run: `uv run python -m unittest tests.test_application_assembly.AssemblyResolverTests.test_plan_retains_deeply_immutable_manifests_in_execution_order -v`

Expected: `ERROR` because `AssemblyPlan` has no `package_manifests`.

- [ ] **Step 3: Add immutable manifest storage**

Extend the dataclass and resolve path:

```python
@dataclass(frozen=True)
class AssemblyPlan:
    application_id: str
    version: str
    runtime_id: str
    package_refs: tuple[PackageRef, ...]
    package_manifests: tuple[Mapping[str, object], ...]
    composition: PackageComposition
    runtime_capabilities: tuple[str, ...]
    host_capabilities: tuple[str, ...]
```

Build a `package_id -> manifest` mapping from `catalog.select`, order it by
`composition.package_ids`, and freeze mappings recursively with tuples for
arrays. Reuse a private `_freeze` helper; do not expose mutable catalog values.

- [ ] **Step 4: Run assembly and runner regression tests**

Run: `uv run python -m unittest tests.test_application_assembly tests.test_application_runner -v`

Expected: all tests pass and existing `AssemblyPlan` consumers remain compatible.

- [ ] **Step 5: Commit**

```bash
git add src/asterion/assembly/protocol.py tests/test_application_assembly.py
git commit -m "feat: retain executable package declarations"
```

### Task 2: Define the exact package-implementation contract

**Files:**
- Create: `src/asterion/packages/execution.py`
- Modify: `src/asterion/packages/__init__.py`
- Create: `tests/test_package_execution.py`

**Interfaces:**
- Consumes: `PackageRef`, frozen manifest mappings, `AgentRuntimeClient`, `CancellationSignal`.
- Produces: `PackageInvocation`, `PackageExecutionResult`, `PackageImplementation`, `PackageExecutionError`, `validate_implementation_bindings`, and `validate_package_result`.

- [ ] **Step 1: Write failing value and registry tests**

Cover exact binding, duplicate iterable bindings, missing executable kinds,
declarative policy exemption, deep immutability, and redaction. Use this public
shape:

```python
invocation = PackageInvocation(
    package_ref=PackageRef("dci.research", "1.0.0"),
    manifest=manifest,
    run_id="package-run-1",
    input_text="SECRET-INPUT",
    upstream_artifacts=(),
    runtime=FixtureRuntime(),
    host_services={},
    signal=None,
)
result = PackageExecutionResult(
    events=({"type": "research.completed", "payload": {}},),
    artifacts=({
        "artifact_id": "research-result",
        "media_type": "application/vnd.dci.research+json",
        "value": {"answer_artifact_uri": "final.txt"},
    },),
)
```

Use an iterable of `(PackageRef, implementation)` pairs for validation so a
duplicate exact identity can be detected before conversion to a mapping.

- [ ] **Step 2: Run tests and confirm the module is missing**

Run: `uv run python -m unittest tests.test_package_execution -v`

Expected: import failure for `asterion.packages.execution`.

- [ ] **Step 3: Implement frozen values and protocol**

Define:

```python
EXECUTABLE_PACKAGE_KINDS = frozenset(
    {"capability", "workflow", "memory", "observability", "evaluation"}
)

class PackageExecutionError(RuntimeError):
    pass

@dataclass(frozen=True)
class PackageInvocation:
    package_ref: PackageRef
    manifest: Mapping[str, object]
    run_id: str
    input_text: str
    upstream_artifacts: tuple[Mapping[str, object], ...]
    runtime: AgentRuntimeClient
    host_services: Mapping[str, object]
    signal: CancellationSignal | None = None

@dataclass(frozen=True)
class PackageExecutionResult:
    events: tuple[Mapping[str, object], ...]
    artifacts: tuple[Mapping[str, object], ...]

class PackageImplementation(Protocol):
    async def execute(
        self, invocation: PackageInvocation
    ) -> PackageExecutionResult: ...
```

Freeze manifest, artifacts, events, and host-service mapping containers in
`__post_init__`; retain service object identities but never expose their repr.

- [ ] **Step 4: Implement preflight and declared-output validation**

`validate_implementation_bindings(plan, bindings)` must return an immutable
exact mapping and reject duplicate, unknown, or missing executable refs before
invocation. `policy` packages require no implementation in AF-110.

`validate_package_result(manifest, result)` must require event objects with
exact fields `type` and `payload`, artifact objects with exact fields
`artifact_id`, `media_type`, and `value`, unique non-empty artifact IDs, declared
event types, and declared media types. Raise only messages such as
`"package output event is undeclared"`; never include values.

- [ ] **Step 5: Run contract tests**

Run: `uv run python -m unittest tests.test_package_execution -v`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/asterion/packages/execution.py src/asterion/packages/__init__.py tests/test_package_execution.py
git commit -m "feat: define package implementation contract"
```

### Task 3: Execute packages sequentially through explicit bindings

**Files:**
- Create: `src/asterion/runner/composed.py`
- Modify: `src/asterion/runner/__init__.py`
- Create: `tests/test_composed_application_runner.py`

**Interfaces:**
- Consumes: `AssemblyPlan`, binding pairs, runtime, host services, input, cancellation.
- Produces: `run_composed_application(...) -> ApplicationRunResult`; preserves AF-100 `run_application` unchanged.

- [ ] **Step 1: Write failing ordering and preflight tests**

Build frozen recording implementations and assert:

```python
result = await run_composed_application(
    plan,
    implementations=((PackageRef("dci.research", "1.0.0"), research),),
    runtime=runtime,
    run_id="composed-run",
    input_text="Read the corpus",
    host_services={},
)
self.assertEqual(research.calls, ["dci.research"])
self.assertEqual(result.application_id, plan.application_id)
```

Add cases proving all missing/duplicate bindings fail with zero calls, policy
packages do not execute, output feeds only compatible downstream consumers,
failure stops later packages, pre/in-run cancellation stops later packages,
and public messages omit sentinel input/output/service values.

- [ ] **Step 2: Run tests and confirm the executor is missing**

Run: `uv run python -m unittest tests.test_composed_application_runner -v`

Expected: import failure for `asterion.runner.composed`.

- [ ] **Step 3: Implement deterministic traversal**

Add:

```python
async def run_composed_application(
    plan: AssemblyPlan,
    *,
    implementations: Iterable[tuple[PackageRef, PackageImplementation]],
    runtime: AgentRuntimeClient,
    run_id: str,
    input_text: str,
    host_services: Mapping[str, object],
    signal: CancellationSignal | None = None,
) -> ApplicationRunResult:
    ...
```

Preflight runtime and service identity using the same structural rules as
`run_application`, then validate all implementation bindings. Traverse
`plan.package_manifests` in order; skip policy manifests; select upstream
artifacts only when their `media_type` appears in `consumes_artifacts`; call the
exact implementation; validate results; accumulate normalized package events
and artifacts; stop immediately on cancellation or exception. Convert every
implementation exception to `ApplicationRunError("application package execution failed")`.

- [ ] **Step 4: Run composed and legacy runner suites**

Run: `uv run python -m unittest tests.test_package_execution tests.test_composed_application_runner tests.test_application_runner -v`

Expected: all tests pass and AF-100 behavior remains unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/asterion/runner/composed.py src/asterion/runner/__init__.py tests/test_composed_application_runner.py
git commit -m "feat: execute composed package implementations"
```

### Task 4: Add the independent DCI research capability implementation

**Files:**
- Create: `capabilities/dci-research/src/asterion_dci_research/__init__.py`
- Create: `capabilities/dci-research/src/asterion_dci_research/implementation.py`
- Modify: `pyproject.toml`
- Create: `tests/test_dci_research_capability.py`

**Interfaces:**
- Consumes: `PackageInvocation`, `RunRequest`, normalized runtime event stream.
- Produces: `DciLocalResearchImplementation.execute(...) -> PackageExecutionResult` for `dci.research@1.0.0`.

- [ ] **Step 1: Write failing capability tests**

Assert the implementation sends one request containing only the declared
runtime capabilities, forwards cancellation, validates the runtime stream,
emits `research.completed`, produces
`application/vnd.dci.research+json`, works with fixture clients whose IDs are
`pi.reference` and `claude-code.reference`, and redacts provider/input sentinels.

Also scan every Python file under `src/asterion` and
`capabilities/dci-research/src` and assert none contains an import matching
`dci.benchmark`.

- [ ] **Step 2: Run tests and confirm the capability package is absent**

Run: `uv run python -m unittest tests.test_dci_research_capability -v`

Expected: import failure for `asterion_dci_research`.

- [ ] **Step 3: Implement the runtime-neutral research behavior**

Implement a stateless class:

```python
class DciLocalResearchImplementation:
    async def execute(
        self, invocation: PackageInvocation
    ) -> PackageExecutionResult:
        request = RunRequest(
            run_id=invocation.run_id,
            input_text=invocation.input_text,
            requested_capabilities=tuple(
                invocation.manifest["requires_capabilities"]
            ),
        )
        events = tuple(
            event.to_mapping()
            async for event in invocation.runtime.run(
                request, signal=invocation.signal
            )
        )
        validate_event_stream(events)
        answer = next(
            event["payload"]["artifact"]
            for event in events
            if event["type"] == "artifact.created"
        )
        return PackageExecutionResult(
            events=({"type": "research.completed", "payload": {"status": "completed"}},),
            artifacts=({
                "artifact_id": "dci-research-result",
                "media_type": "application/vnd.dci.research+json",
                "value": {"answer_artifact_uri": answer["uri"]},
            },),
        )
```

Harden the concrete code for missing/malformed/failing terminal streams without
including raw values in exceptions. Do not copy prompt-building, judge,
conversation, or recorder behavior from the baseline.

- [ ] **Step 4: Package the independent implementation**

Add `capabilities/dci-research/src/asterion_dci_research` to Hatch's explicit
wheel package paths while keeping `src/asterion` and `src/dci`. Add no console
script and no import from Asterion core.

- [ ] **Step 5: Run capability and wheel tests**

Run: `uv run python -m unittest tests.test_dci_research_capability tests.test_asterion_structure -v`

Expected: all tests pass; existing console scripts remain present.

- [ ] **Step 6: Commit**

```bash
git add capabilities/dci-research/src pyproject.toml tests/test_dci_research_capability.py tests/test_asterion_structure.py
git commit -m "feat: add independent DCI research capability"
```

### Task 5: Add an independent Asterion Pi runtime client

**Files:**
- Create: `src/asterion/runtimes/pi.py`
- Modify: `src/asterion/runtimes/__init__.py`
- Create: `tests/test_asterion_pi_runtime.py`

**Interfaces:**
- Consumes: an explicit Pi RPC command, cwd, environment copy, `RunRequest`, and cancellation signal.
- Produces: `PiRuntimeClient`, an `AgentRuntimeClient` with runtime ID `pi.reference` and normalized `RunEvent` output.

- [ ] **Step 1: Write failing fake-process tests**

Use a temporary executable JSONL fixture process. It must acknowledge `prompt`,
emit `agent_start`, text deltas, tool events, `agent_end`, and respond to `abort`.
Test successful normalization, stderr draining, malformed JSON, non-object JSON,
early EOF, cancellation, timeout, process reap, one active run at a time, and
redacted exceptions. Assert the client source has no `dci` import.

- [ ] **Step 2: Run tests and confirm the client is absent**

Run: `uv run python -m unittest tests.test_asterion_pi_runtime -v`

Expected: import failure for `asterion.runtimes.pi`.

- [ ] **Step 3: Implement the minimal RPC transport**

Define:

```python
class PiRuntimeClient:
    def __init__(
        self,
        *,
        command: Sequence[str],
        cwd: Path,
        capabilities: tuple[str, ...],
        env: Mapping[str, str] | None = None,
    ) -> None: ...

    @property
    def manifest(self) -> RuntimeManifest:
        return RuntimeManifest("pi.reference", self._capabilities)

    async def run(
        self,
        request: RunRequest,
        *,
        signal: CancellationSignal | None = None,
    ) -> AsyncIterator[RunEvent]: ...
```

Start one subprocess with stdin/stdout/stderr pipes; send one canonical compact
JSON `prompt` request; translate only lifecycle, text completion, and tool
start/end events through `PiProtocolAdapter`; send `abort` when cancelled; drain
both output streams; terminate then kill on bounded shutdown; validate the
complete normalized stream before returning its final event. Public errors use
fixed structural messages only.

- [ ] **Step 4: Run runtime, adapter, and host suites**

Run: `uv run python -m unittest tests.test_asterion_pi_runtime tests.test_pi_protocol_adapter tests.test_python_runtime_host -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/asterion/runtimes/pi.py src/asterion/runtimes/__init__.py tests/test_asterion_pi_runtime.py
git commit -m "feat: add independent Pi runtime client"
```

### Task 6: Prove explicit host composition and capability reuse

**Files:**
- Create: `applications/dci-agent-lite/assemblies/dci-research-capability.json`
- Create: `applications/dci-agent-lite/python/dci_research_host.py`
- Modify: `tests/test_composed_application_runner.py`
- Modify: `tests/test_application_assembly.py`
- Modify: `tests/test_asterion_structure.py`

**Interfaces:**
- Consumes: explicit catalog roots, assembly path, runtime client, DCI implementation object.
- Produces: `run_dci_research_application(...) -> ApplicationRunResult` as a reference composition root, not a console script.

- [ ] **Step 1: Write failing host integration tests**

The reference host must resolve the new assembly and call:

```python
return await run_composed_application(
    plan,
    implementations=((
        PackageRef("dci.research", "1.0.0"),
        DciLocalResearchImplementation(),
    ),),
    runtime=runtime,
    run_id=run_id,
    input_text=input_text,
    host_services={},
    signal=signal,
)
```

Test the checked-in application plus a temporary application containing the
same research package and an additional declarative policy package. Assert the
same implementation object succeeds in both contexts. Assert Asterion core does
not import the host or capability package.

- [ ] **Step 2: Add the minimal executable assembly**

Create a closed `dci.assembly/v1` document with sorted exact refs for
`dci.research@1.0.0` and `policy.local-corpus@1.0.0`, runtime ID
`pi.reference`, host events `artifact.created`, `run.completed`, `run.started`,
and `tool.result`, host artifact `text/plain`, and no host capabilities.

- [ ] **Step 3: Implement the explicit composition root**

Load only caller-supplied/checked-in paths; construct the catalog, resolve the
assembly against `runtime.manifest.to_mapping()`, bind the DCI implementation
explicitly, and call the composed runner. Do not parse `.env`, discover plugins,
or add a CLI.

- [ ] **Step 4: Run integration and structure tests**

Run: `uv run python -m unittest tests.test_composed_application_runner tests.test_application_assembly tests.test_asterion_structure -v`

Expected: both application contexts pass and baseline files are unchanged.

- [ ] **Step 5: Commit**

```bash
git add applications/dci-agent-lite/assemblies/dci-research-capability.json applications/dci-agent-lite/python/dci_research_host.py tests/test_composed_application_runner.py tests/test_application_assembly.py tests/test_asterion_structure.py
git commit -m "feat: compose the DCI research application"
```

### Task 7: Document, compare, and close AF-110 acceptance

**Files:**
- Create: `docs/architecture/capability-execution.md`
- Modify: `docs/architecture/agent-framework.md`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md` append-only

**Interfaces:**
- Consumes: all verified AF-110 commits and test evidence.
- Produces: documented package execution boundary, acceptance evidence, and governed AF-120 successor.

- [ ] **Step 1: Write documentation assertions before the guide**

Add tests asserting the guide states: package vs application ownership,
explicit exact implementation binding, deterministic sequential execution,
baseline isolation, error/security rules, and AF-120 ownership of generic CLI
and distribution binding.

- [ ] **Step 2: Write the architecture guide**

Document one reference code sample using `PackageRef`,
`DciLocalResearchImplementation`, and `run_composed_application`; document all
AF-110 non-goals and the external-only baseline comparison.

- [ ] **Step 3: Run focused and full verification**

Run:

```bash
uv run python -m unittest tests.test_package_execution tests.test_composed_application_runner tests.test_dci_research_capability tests.test_asterion_pi_runtime tests.test_application_assembly tests.test_asterion_structure -v
uv run python -m unittest discover -v
uv run python -m compileall -q src capabilities/dci-research/src applications/dci-agent-lite/python tests
uv run ruff check src capabilities/dci-research/src applications/dci-agent-lite/python tests
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
bash -n scripts/examples/dci_basic_example.sh scripts/examples/dci_runtime_context_example.sh
python3 tools/project_scope_check.py
git diff --check
```

Expected: all tests and gates pass. If valid provider credentials are available,
run `make runtime-example` as external baseline evidence and a focused
provider-backed `PiRuntimeClient` application probe; otherwise record the exact
credential-dependent item as deferred without weakening fixture/process tests.

- [ ] **Step 4: Govern package closure and successor transition**

Run `python3 tools/project_scope_check.py` again. Record acceptance evidence and
the architecture decision, mark AF-110 completed, and activate the existing pending AF-120 with
outcome “secure installed-application implementation binding and generic
`asterion run` entry point,” depending on AF-110. Update structural state only
where architecture changed and append journal facts without editing old lines.

- [ ] **Step 5: Commit closure atomically**

```bash
git add docs/architecture/capability-execution.md docs/architecture/agent-framework.md docs/status/DECISIONS.md docs/status/WORKLIST.md docs/status/CURRENT-STATE.md docs/status/JOURNAL.md tests
git commit -m "docs: close composable capability execution"
```

- [ ] **Step 6: Checkpoint the AF-120 boundary**

Refresh `docs/status/RESUME-NEXT-SESSION.md` as a live checkpoint containing the
verified AF-110 evidence and the first AF-120 design question. Do not perform a
final handoff unless the user ends the session.
