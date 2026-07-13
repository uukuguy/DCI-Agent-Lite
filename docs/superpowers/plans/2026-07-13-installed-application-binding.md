# Single-Wheel Installed Application Binding Implementation Plan

> **For agentic workers:** Execute inline with test-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one independently installable `asterion` wheel containing the framework, modular DCI capability/application, and canonical resources while keeping `src/dci` as an unpackaged runnable repository baseline.

**Architecture:** Generic provider discovery and execution remain under `asterion.applications`; first-party DCI code lives in `asterion.capabilities.dci_research` and `asterion.applications.dci_agent_lite`. The root project is a non-package uv workspace that exposes the baseline source only for repository development. Asterion imports no `dci`, and the baseline imports no `asterion`.

**Tech Stack:** Python 3.10+, uv workspace, Hatchling, `importlib.metadata`, `importlib.resources`, argparse, unittest.

## Global Constraints

- Build exactly one wheel: distribution `asterion`, import namespace `asterion`.
- Never modify behavior under `src/dci/benchmark/`.
- Never include `src/dci` in a wheel or Asterion dependency.
- Preserve the frozen baseline-owned `dci.framework.*` implementation and existing `.env`, Pi/Judge, evaluation, and security behavior.
- Keep generic provider/discovery/CLI code free of hard-coded DCI identities; register the built-in provider at the Asterion distribution boundary.
- Keep manifests and assemblies in one canonical installed resource tree.
- Use RED → GREEN for every behavior change and run scope/diff gates before each commit.

---

### Task 1: Lock the one-wheel and source-baseline boundary

**Files:**
- Modify: `tests/test_distribution_boundaries.py`
- Modify: `pyproject.toml`
- Modify: `packages/python/asterion-core/pyproject.toml`
- Delete: `capabilities/dci-research/pyproject.toml`

**Interfaces:**
- Produces one uv workspace member named `asterion`.
- Produces no root `dci` build system, project metadata, wheel target, or installed DCI scripts.
- Keeps `src/dci` importable for repository test and source-command execution.

- [ ] **Step 1: Write failing boundary tests**

Replace the old core/baseline/capability wheel assertions with tests that:

```python
self.assertEqual(workspace_members(), {"packages/python/asterion-core"})
self.assertFalse(root_is_buildable_project())
self.assertFalse((ROOT / "capabilities/dci-research/pyproject.toml").exists())
self.assertEqual(built_wheels(), ["asterion"])
self.assertEqual(wheel_top_levels(asterion_wheel), {"asterion"})
self.assertNotIn("dci/", wheel_names)
```

Retain source scans proving neither tree imports the other. Add a subprocess
test using `PYTHONPATH=src` and `python -m dci.benchmark.pi_rpc_runner --help`
to prove the unpackaged baseline remains runnable.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_distribution_boundaries -v`

Expected: failures because the root still defines distribution `dci`, the
capability is a workspace project, and two extra wheels can be built.

- [ ] **Step 3: Make the root a non-package workspace**

Remove root `[build-system]`, `[project]`, `[project.scripts]`, and Hatch wheel
sections. Keep shared dependencies in `[dependency-groups].dev`, keep only the
Asterion workspace source/member, and add uv configuration needed for tests to
see `src` and the Asterion project. Regenerate `uv.lock` with `uv lock`.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
uv run python -m unittest tests.test_distribution_boundaries tests.test_pi_rpc_runner tests.test_judge -v
uv run python -m compileall -q src packages/python/asterion-core/src tests
uv run ruff check src packages/python/asterion-core/src tests
python3 tools/project_scope_check.py
git diff --check
```

Commit: `build: make Asterion the only distribution`

### Task 2: Fold the DCI capability and manifests into Asterion

**Files:**
- Move: `capabilities/dci-research/src/asterion_dci_research/implementation.py` to `packages/python/asterion-core/src/asterion/capabilities/dci_research/implementation.py`
- Move: `capabilities/dci-research/src/asterion_dci_research/manifests/*.json` to `packages/python/asterion-core/src/asterion/capabilities/dci_research/manifests/`
- Create: `packages/python/asterion-core/src/asterion/capabilities/__init__.py`
- Create: `packages/python/asterion-core/src/asterion/capabilities/dci_research/__init__.py`
- Modify: capability, catalog, composition, assembly, runner, TypeScript fixture, host, and architecture references found by `rg 'asterion_dci_research|capabilities/dci-research'`
- Modify: `tests/test_distribution_boundaries.py`

**Interfaces:**
- Produces `asterion.capabilities.dci_research.DciLocalResearchImplementation`.
- Produces canonical installed manifests at `importlib.resources.files("asterion").joinpath("capabilities/dci_research/manifests")`.

- [ ] **Step 1: Write failing namespace/resource tests**

Update `tests/test_dci_research_capability.py` and distribution tests to import
the new namespace and assert four manifests exist in the built Asterion wheel,
each exactly once. Assert the former nested package directory is absent.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_dci_research_capability tests.test_distribution_boundaries -v`

Expected: import/resource failures for the new namespace.

- [ ] **Step 3: Move code/resources and update consumers**

Move rather than copy the implementation and JSON files. Update imports and
repository test paths atomically. Preserve all manifest bytes and stable
`dci.*` identities.

- [ ] **Step 4: Verify GREEN and commit**

Run focused capability/catalog/composition/assembly/execution tests, TypeScript
fixture tests, compile, Ruff, scope, and diff checks.

Commit: `refactor: bundle DCI research with Asterion`

### Task 3: Add the built-in DCI application provider and resources

**Files:**
- Create: `packages/python/asterion-core/src/asterion/applications/dci_agent_lite/__init__.py`
- Create: `packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py`
- Move: `applications/dci-agent-lite/assemblies/*.json` to `packages/python/asterion-core/src/asterion/applications/dci_agent_lite/assemblies/`
- Modify: `packages/python/asterion-core/pyproject.toml`
- Modify: `packages/python/asterion-core/src/asterion/runtime/factory.py`
- Create: `tests/test_builtin_dci_application.py`
- Modify: assembly/runner/structure/TypeScript fixture documentation references found by `rg 'applications/dci-agent-lite/assemblies'`

**Interfaces:**
- Produces `create_provider() -> InstalledApplicationProvider` for provider ID `dci-agent-lite`.
- Registers `[project.entry-points."asterion.applications"] dci-agent-lite = "asterion.applications.dci_agent_lite:create_provider"`.
- Exposes canonical assemblies and DCI manifests beneath one `asterion` resource root.
- Provides explicit `pi.reference` runtime binding through Asterion-owned factory configuration.

- [ ] **Step 1: Write failing built-in provider tests**

Test installed metadata discovery without provider load, exact selected loading,
resource-root containment, exact DCI implementation binding, runtime identity,
and successful wheel-isolated resource discovery. Assert generic discovery and
CLI modules contain no DCI import or identity literal.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_builtin_dci_application -v`

Expected: missing built-in provider and entry point.

- [ ] **Step 3: Implement the provider and move assemblies**

Build provider paths through `importlib.resources.files("asterion")`, bind
`dci.research@1.0.0` to `DciLocalResearchImplementation`, and declare only
`pi.reference`. Register the provider in Asterion metadata. Do not add DCI
fallback logic to discovery or CLI.

- [ ] **Step 4: Verify GREEN and commit**

Run provider/discovery/CLI/assembly/composed-runner tests plus wheel inspection,
compile, Ruff, scope, and diff checks.

Commit: `feat: bundle the DCI application provider`

### Task 4: Preserve repository baseline workflows without packaging

**Files:**
- Modify: `README.md`
- Modify: `assets/docs/*.md`
- Modify: `scripts/examples/dci_*_example.sh`
- Modify: `scripts/bcplus_eval/run_bcplus_eval.py`
- Modify: `Makefile` if a shared source-command wrapper is needed
- Modify: `tests/test_asterion_structure.py`

**Interfaces:**
- Produces one documented source invocation, `PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner`, reused by repository scripts.
- Does not change any Python file below `src/dci/benchmark/`.

- [ ] **Step 1: Write failing source-workflow tests**

Update structural tests to reject `uv run dci-agent-lite` as an installed
command and require the source invocation in maintained examples/evaluator.
Record hashes of files under `src/dci/benchmark/` before this task and assert
they remain unchanged in the task diff.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_asterion_structure -v`

Expected: old installed-command assertions and script contents fail.

- [ ] **Step 3: Update wrappers and documentation**

Replace repository invocations with the source command while preserving every
existing CLI argument, environment default, stdin flow, and evaluation
behavior. Do not edit baseline implementation files.

- [ ] **Step 4: Verify GREEN and commit**

Run structure, Pi runner, judge, evaluator tests; `bash -n` on all touched shell
scripts; compile, Ruff, scope, and diff checks.

Commit: `docs: run the DCI baseline from repository source`

### Task 5: Close AF-120 with full verification

**Files:**
- Modify: `docs/architecture/asterion-framework-layout.md`
- Modify: `docs/architecture/capability-execution.md`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md` only if a recovery checkpoint is due

**Interfaces:**
- Produces AF-120 acceptance evidence and either a governed successor package or explicit terminal roadmap state.

- [ ] **Step 1: Run full verification**

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q src packages/python/asterion-core/src tests
uv run ruff check src packages/python/asterion-core/src tests
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
bash -n scripts/examples/*.sh scripts/bcplus_eval/*.sh
python3 tools/project_scope_check.py
git diff --check
```

Build `asterion` into a temporary directory, install it into an isolated
environment, run `asterion list`, and verify the DCI provider/resources are
available while `import dci` fails.

- [ ] **Step 2: Update architecture and package state**

Document the one-wheel layout, source-only baseline, provider trust boundary,
verification counts, and successor state. Run scope preflight again after the
ledger transition.

- [ ] **Step 3: Commit closure**

Commit: `docs: close single-wheel application binding`
