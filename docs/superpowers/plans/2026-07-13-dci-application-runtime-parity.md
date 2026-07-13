# AF-210 DCI Application Runtime Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make asterion run execute the independent Asterion DCI Pi workflow through the selected DCI application assembly while retaining a fixture-only Claude boundary.

**Architecture:** The DCI provider binds its capability implementation to a private native Pi executor. On pi.reference, the implementation maps PackageInvocation to DciRunRequest, executes the existing Asterion-owned workflow, and projects body-free native references. Generic application selection, runner logic, and CLI parsing remain unaware of DCI.

**Tech Stack:** Python 3.11, unittest, Asterion application/provider contracts, Asterion DCI native artifacts, Bash Climb adapter.

## Global Constraints

- Active work package is AF-210; run python3 tools/project_scope_check.py before work and before closure.
- Do not modify, import, execute, or package src/dci.
- Keep DCI-specific configuration and artifact behavior out of asterion.cli and generic runner modules.
- Do not issue Pi, judge, or Claude provider requests; all acceptance evidence is fixture/local only.
- Do not claim Claude semantic parity from fixture behavior.
- Persist only body-free artifact references in composed application results.

---

## File map

| Path | Responsibility |
|---|---|
| packages/python/asterion-core/src/asterion/dci/application_executor.py | Private configured Pi executor for one DCI application invocation. |
| packages/python/asterion-core/src/asterion/capabilities/dci_research/implementation.py | Select native Pi execution or existing protocol-only execution by runtime identity. |
| packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py | Bind the first-party DCI capability to its private native executor. |
| tests/test_asterion_dci_application_executor.py | Environment/configuration-to-native-request tests with a fake runner. |
| tests/test_dci_research_capability.py | Native Pi implementation path, safe failure, and retained Claude fixture path. |
| tests/test_builtin_dci_application.py | Installed provider/assembly composition proof using a fake native executor. |
| tools/climb/train.sh and tools/climb/eval-local.sh | Four bounded AF-210 local acceptance hypotheses. |
| docs/status/climb/ | New AF-210 Climb session, hypotheses, and generated state. |
| README.md and docs/status/WORKLIST.md | Operator boundary and AF-210 plan/closure evidence. |

## Task 1: Provider-owned native Pi executor

**Files:**

- Create: packages/python/asterion-core/src/asterion/dci/application_executor.py
- Create: tests/test_asterion_dci_application_executor.py
- Modify: packages/python/asterion-core/src/asterion/dci/__init__.py

**Interfaces:**

- Consumes: DciRunRequest, DciRunResult, DciPaths, load_asterion_dci_env, resolve_dci_paths, and run_pi_research.
- Produces: EnvironmentDciRunExecutor.run(DciRunRequest) -> DciRunResult and DciRunExecutor compatibility for the DCI capability.

- [ ] **Step 1: Write failing executor configuration tests**

~~~python
class AsterionDciApplicationExecutorTests(unittest.TestCase):
    def test_maps_generic_runtime_cwd_and_native_paths_to_one_pi_run(self) -> None:
        calls = []
        executor = EnvironmentDciRunExecutor(
            repo_root=Path("/repo"),
            run_native=lambda paths, request: calls.append((paths, request)) or result(),
        )
        with patch.dict(os.environ, {"ASTERION_RUNTIME_CWD": "/corpus"}, clear=True):
            executor.run(DciRunRequest(run_id="application-run", question="SECRET", cwd=Path(".")))
        self.assertEqual(calls[0][1].cwd, Path("/corpus"))
        self.assertEqual(calls[0][1].run_id, "application-run")
~~~

- [ ] **Step 2: Run the focused test and verify RED**

Run: uv run python -m unittest tests.test_asterion_dci_application_executor -v

Expected: FAIL because EnvironmentDciRunExecutor is not importable.

- [ ] **Step 3: Implement the smallest private executor**

~~~python
class EnvironmentDciRunExecutor:
    def __init__(self, *, repo_root: Path | None = None, run_native=run_pi_research) -> None:
        self._repo_root = Path.cwd() if repo_root is None else Path(repo_root)
        self._run_native = run_native

    def run(self, request: DciRunRequest) -> DciRunResult:
        root = self._repo_root.resolve()
        load_asterion_dci_env(root)
        cwd = Path(os.environ.get("ASTERION_RUNTIME_CWD", root)).resolve()
        return self._run_native(resolve_dci_paths(root), replace(request, cwd=cwd))
~~~

Export only EnvironmentDciRunExecutor from asterion.dci; do not modify asterion.cli, generic runtimes, or the legacy product.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: uv run python -m unittest tests.test_asterion_dci_application_executor -v

Expected: PASS, including default-CWD and native-path configuration cases.

- [ ] **Step 5: Commit**

~~~bash
git add packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_application_executor.py
git commit -m "feat: add DCI application native executor"
~~~

## Task 2: Bind native Pi execution in the DCI capability

**Files:**

- Modify: packages/python/asterion-core/src/asterion/capabilities/dci_research/implementation.py
- Modify: packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py
- Modify: tests/test_dci_research_capability.py

**Interfaces:**

- Consumes: optional DciRunExecutor from asterion.dci.bridge, PackageInvocation, and runtime identity.
- Produces: DciLocalResearchImplementation(native_executor=...); execute() uses it only for pi.reference and returns project_dci_run().

- [ ] **Step 1: Write failing native-Pi and Claude-regression tests**

~~~python
async def test_pi_invocation_executes_the_bound_native_executor(self) -> None:
    executor = RecordingExecutor(fixture_result(output_dir))
    implementation = DciLocalResearchImplementation(native_executor=executor)
    result = await implementation.execute(invocation(FixtureRuntime("pi.reference")))
    self.assertEqual(executor.requests[0].run_id, "research-run")
    self.assertEqual(executor.requests[0].question, "SECRET-APPLICATION-INPUT")
    self.assertEqual(result.artifacts[0]["value"]["state_artifact_uri"], "state.json")

async def test_claude_fixture_keeps_protocol_execution_without_native_executor(self) -> None:
    implementation = DciLocalResearchImplementation(native_executor=FailIfCalled())
    result = await implementation.execute(invocation(ClaudeFixtureRuntime()))
    self.assertEqual(result.events[0]["type"], "research.completed")
~~~

- [ ] **Step 2: Run the focused test and verify RED**

Run: uv run python -m unittest tests.test_dci_research_capability -v

Expected: FAIL because the implementation constructor does not accept native_executor and Pi invocations still call runtime.run().

- [ ] **Step 3: Implement runtime-scoped native dispatch**

~~~python
class DciLocalResearchImplementation:
    def __init__(self, *, native_executor: DciRunExecutor | None = None) -> None:
        self._native_executor = native_executor

    async def execute(self, invocation: PackageInvocation) -> PackageExecutionResult:
        if invocation.runtime.manifest.runtime_id == "pi.reference" and self._native_executor:
            return self.execute_completed_native_run(self._native_executor.run(
                DciRunRequest(run_id=invocation.run_id, question=invocation.input_text, cwd=Path.cwd())
            ))
        # Preserve the existing protocol-only implementation below.
~~~

In create_provider(), bind EnvironmentDciRunExecutor() to the existing DciLocalResearchImplementation. Keep claude-code.reference assembly selection and fixture behavior unchanged.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: uv run python -m unittest tests.test_dci_research_capability tests.test_asterion_dci_bridge -v

Expected: PASS; a Pi result contains native durable references and no answer body, while Claude remains a protocol fixture only.

- [ ] **Step 5: Commit**

~~~bash
git add packages/python/asterion-core/src/asterion/capabilities/dci_research/implementation.py \
  packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py \
  tests/test_dci_research_capability.py
git commit -m "feat: run native DCI through Pi applications"
~~~

## Task 3: Prove installed application parity and safe failures

**Files:**

- Modify: tests/test_builtin_dci_application.py
- Modify: tests/test_asterion_cli.py
- Modify: tests/test_distribution_boundaries.py

**Interfaces:**

- Consumes: create_provider(native_executor=...), a pi.reference fixture runtime, and fake native DciRunResult values.
- Produces: installed asterion run evidence that projects the native result without exposing protected bodies or DCI behavior in generic modules.

- [ ] **Step 1: Write the failing installed-application test**

~~~python
def test_installed_pi_application_uses_the_provider_bound_native_executor(self) -> None:
    native = RecordingExecutor(fixture_result(self.output_dir, final_text="SECRET-ANSWER"))
    entry = FakeEntryPoint(name="dci-agent-lite", factory=lambda: create_provider(native_executor=native))
    code = main([
        "run", "--provider", "dci-agent-lite", "--application", "dci.research-capability@1.0.0",
        "--runtime", "pi.reference", "--run-id", "installed-run", "--input", "SECRET-INPUT",
    ], entry_points=(entry,), runtime_factories=pi_fixture_registry(), stdout=stdout, stderr=stderr)
    self.assertEqual(code, 0)
    self.assertEqual(native.requests[0].run_id, "installed-run")
    self.assertNotIn("SECRET", stdout.getvalue())
~~~

Add a companion test where the native executor raises DciRunError; assert that main() returns 2 and neither input nor protected diagnostics appear.

- [ ] **Step 2: Run focused tests and verify RED**

Run: uv run python -m unittest tests.test_builtin_dci_application tests.test_asterion_cli -v

Expected: FAIL because the built-in provider cannot accept a fake native executor and the installed path does not invoke it.

- [ ] **Step 3: Make provider injection testable without changing the entry point**

~~~python
def create_provider(*, native_executor: DciRunExecutor | None = None) -> InstalledApplicationProvider:
    executor = EnvironmentDciRunExecutor() if native_executor is None else native_executor
    implementation = DciLocalResearchImplementation(native_executor=executor)
    # Retain the existing immutable InstalledApplication declaration.
~~~

Do not add DCI options to _parser() or DCI names to generic CLI/runner source. Add source-boundary assertions that those generic files still omit DCI provider, artifact, and executor names.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: uv run python -m unittest tests.test_builtin_dci_application tests.test_asterion_cli tests.test_distribution_boundaries -v

Expected: PASS; installed Pi application results match body-free native projection, failure is redacted, and generic modules remain DCI-neutral.

- [ ] **Step 5: Commit**

~~~bash
git add tests/test_builtin_dci_application.py tests/test_asterion_cli.py tests/test_distribution_boundaries.py
git commit -m "test: prove installed DCI application parity"
~~~

## Task 4: Register AF-210 Climb evidence and close local parity gates

**Files:**

- Modify: tools/climb/train.sh
- Modify: tools/climb/eval-local.sh
- Modify: docs/status/climb/hypotheses.yaml
- Modify: docs/status/climb/session-state.json
- Modify: docs/status/climb/session-target.md
- Modify: docs/status/WORKLIST.md
- Modify: README.md

**Interfaces:**

- Consumes: focused test modules from Tasks 1-3 and the AF-210 work-package ID.
- Produces: four deterministic AF-210 local acceptance cycles, regenerated Climb summary, worklist plan/closure evidence, and operator documentation that distinguishes Pi parity from Claude authorization.

- [ ] **Step 1: Register the four planned hypotheses before running them**

~~~yaml
- id: AF-210-H-001
  work_package_id: AF-210
  description: Bind the DCI capability to one configured native Pi executor.
  parent_paradigm: application-runtime-parity
  expected_lift: native executor contract
  cost_h: 0.01
  ranking: 1.00
  status: pending
  results: []
~~~

Add H-002 for native Pi capability dispatch, H-003 for installed assembly projection/redaction, and H-004 for the full local closure matrix. Set the session package to AF-210, set next_hypothesis to H-001, update the session target prose, then run python3 tools/climb/regen-tree.py.

- [ ] **Step 2: Extend the deterministic Climb adapter**

~~~bash
elif [ "$1" = "AF-210-H-001" ]; then
    uv run python -m unittest tests.test_asterion_dci_application_executor -v >"$run_dir/train.log" 2>&1
elif [ "$1" = "AF-210-H-002" ]; then
    uv run python -m unittest tests.test_dci_research_capability tests.test_asterion_dci_bridge -v >"$run_dir/train.log" 2>&1
elif [ "$1" = "AF-210-H-003" ]; then
    uv run python -m unittest tests.test_builtin_dci_application tests.test_asterion_cli -v >"$run_dir/train.log" 2>&1
~~~

Give eval-local.sh four named dimensions per hypothesis and use H-004 for the complete local gate matrix: focused/full Python, compilation, Ruff, TypeScript, Rust, shell syntax, scope check, wheel proof, and diff check.

- [ ] **Step 3: Run each Climb cycle and verify all deterministic evidence**

Run:

~~~bash
python3 tools/project_scope_check.py --climb-hypothesis AF-210-H-001
bash tools/climb/cycle.sh AF-210-H-001
bash tools/climb/cycle.sh AF-210-H-002
bash tools/climb/cycle.sh AF-210-H-003
bash tools/climb/cycle.sh AF-210-H-004
~~~

Expected: every local evaluation reports total: 4, runs.csv receives one append-only row per cycle, research-tree.md is regenerated, and no provider request is made.

- [ ] **Step 4: Update closure documentation and verify repository gates**

Update README.md to state that generic Pi application execution now shares the Asterion DCI implementation while Claude remains authorization-gated. Set the AF-210 plan link in WORKLIST.md; only mark the package completed after all H-001 through H-004 evidence and the full closure matrix pass.

Run:

~~~bash
uv run python -m unittest discover -v
uv run python -m compileall -q packages/python/asterion-core/src tests
uv run ruff check packages/python/asterion-core/src tests
bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
python3 tools/project_scope_check.py
git diff --check
~~~

Expected: all commands pass without Pi, judge, or Claude provider requests.

- [ ] **Step 5: Commit bounded evidence and journal each result**

~~~bash
git add tools/climb docs/status/climb README.md docs/status/WORKLIST.md
git commit -m "docs: record AF-210 application parity closure"
~~~

Append a docs/status/JOURNAL.md line immediately after each durable commit or verified/falsified hypothesis; refresh the live checkpoint after the third durable event or when the immediate recovery action changes.

## Plan self-review

- Spec coverage: Tasks 1-3 implement the approved provider-bound Pi path, preserve generic/Claude boundaries, and prove safe native projection. Task 4 records the required governed evidence and closure verification.
- Placeholder scan: no unfinished markers or unspecified test commands remain.
- Type consistency: DciRunExecutor.run(DciRunRequest) -> DciRunResult is consumed by the capability and supplied by the provider-bound executor.
