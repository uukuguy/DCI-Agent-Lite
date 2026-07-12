# Installed Application Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Asterion, the DCI capability, the DCI application, and the enhanced DCI baseline into independent distributions, then run explicitly selected installed applications through a safe generic `asterion` entry point.

**Architecture:** Asterion core discovers metadata in the fixed `asterion.applications` entry-point group and loads only one explicitly selected provider. Exact provider/resource/runtime/package preflight precedes runtime construction. The DCI capability and application own their canonical resources in separate wheels; the runnable baseline retains frozen `dci.framework.*` implementations and no Asterion dependency.

**Tech Stack:** Python 3.10+, uv workspaces, Hatchling wheels/sdists, `importlib.metadata`, `importlib.resources`, frozen dataclasses, argparse, unittest, existing Agent Runtime Protocol/package execution contracts.

## Global Constraints

- Do not change behavior in `src/dci/benchmark/`, baseline CLI commands, `.env` extensions, Pi/Judge reliability, evaluation, or existing example scripts.
- Asterion core, `asterion-dci-research`, and `asterion-dci-agent-lite` must never import `dci`.
- The baseline distribution must never import `asterion`; `dci.framework.*` becomes frozen baseline-owned code while benchmark imports stay unchanged.
- Preserve all current `dci.*` wire literals and shared JSON fixture conformance; Python object identity between baseline and Asterion is intentionally removed.
- Package-owned manifests and assemblies have exactly one canonical source copy; former resource paths disappear.
- Provider selection uses only `asterion.applications`, exact entry-point name, and one explicit provider ID; `list` never calls `load()`.
- No arbitrary module argument, import path in manifests, remote registry, automatic install, dependency solver, provider sandbox claim, runtime/service auto-discovery, or control plane.
- Credentials remain in the caller environment and never enter provider values, portable manifests, public errors, or normalized output.
- Use TDD for every behavior change and commit each task only after focused regression, compile, Ruff, shell, and diff checks.

---

## File Structure

- `packages/python/asterion-core/pyproject.toml` — independent `asterion` distribution and console script.
- `packages/python/asterion-core/src/asterion/` — sole Asterion implementation, moved from `src/asterion/`.
- `packages/python/asterion-core/src/asterion/applications/provider.py` — versioned immutable provider contract and validation.
- `packages/python/asterion-core/src/asterion/applications/discovery.py` — metadata-only listing and selected-only loading.
- `packages/python/asterion-core/src/asterion/cli.py` — `list` and `run` commands.
- `packages/python/asterion-core/src/asterion/runtime/factory.py` — host-owned exact runtime factory registry.
- `capabilities/dci-research/pyproject.toml` — independent capability distribution.
- `capabilities/dci-research/src/asterion_dci_research/manifests/` — canonical DCI manifests moved from the old directory.
- `applications/dci-agent-lite/pyproject.toml` — independent installed application distribution and entry point.
- `applications/dci-agent-lite/src/asterion_dci_application/provider.py` — DCI installed-provider factory.
- `applications/dci-agent-lite/src/asterion_dci_application/assemblies/` — canonical assemblies moved from the old directory.
- `src/dci/framework/` — frozen baseline-owned protocol/adapter/package implementations with no Asterion imports.
- `pyproject.toml` — baseline-only root distribution plus uv workspace/development wiring.
- `tests/test_distribution_boundaries.py` — wheel contents, isolated installs, import direction, baseline behavior.
- `tests/test_installed_application_provider.py` — provider values, resource safety, exact contract.
- `tests/test_application_discovery.py` — metadata-only list, exact selected load, ambiguity/redaction.
- `tests/test_asterion_cli.py` — generic CLI preflight and normalized execution.
- Existing framework tests — migrate product imports to `asterion.*`; retain separate baseline tests on `dci.framework.*`.

### Task 1: Split the Asterion core and freeze the enhanced baseline

**Files:**
- Create: `packages/python/asterion-core/pyproject.toml`
- Move: `src/asterion/` to `packages/python/asterion-core/src/asterion/`
- Modify: `src/dci/framework/**/*.py`
- Modify: root `pyproject.toml`
- Create: `tests/test_distribution_boundaries.py`
- Modify: `tests/test_asterion_structure.py`

**Interfaces:**
- Produces distribution `asterion==0.1.0` containing only `asterion`.
- Produces baseline distribution `dci==0.1.0` containing only `dci` and depending on no Asterion package.
- Preserves baseline imports such as `dci.framework.protocol` and `dci.framework.adapters.pi` as independent implementations.

- [ ] **Step 1: Write failing distribution-boundary tests**

Tests must inspect built wheels and source imports:

```python
self.assertEqual(wheel_top_levels(asterion_wheel), {"asterion"})
self.assertEqual(wheel_top_levels(dci_wheel), {"dci"})
self.assertNotIn("Requires-Dist: dci", metadata(asterion_wheel))
self.assertNotIn("Requires-Dist: asterion", metadata(dci_wheel))
self.assert_no_import(ROOT / "packages/python/asterion-core/src", "dci")
self.assert_no_import(ROOT / "src/dci", "asterion")
```

Add a baseline test proving `PiProtocolAdapter`, request/event validation, and
`dci-agent-lite --help` still work after uninstalling Asterion from an isolated
environment.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_distribution_boundaries -v`

Expected: failures because Asterion is still inside the root wheel and baseline framework modules import Asterion.

- [ ] **Step 3: Create the Asterion core project and move code**

Use Hatchling project metadata:

```toml
[project]
name = "asterion"
version = "0.1.0"
requires-python = ">=3.10"

[tool.hatch.build.targets.wheel]
packages = ["src/asterion"]
```

Move the complete authoritative tree; do not copy it. Update test/import paths
and Python compilation roots.

- [ ] **Step 4: Freeze baseline-owned framework behavior**

Replace every Asterion re-export under `src/dci/framework/` with the current
stable implementation required by baseline tests. Internal imports target
`dci.framework.*`, never `asterion.*`. Preserve benchmark files and their import
statements unchanged. Shared wire constants remain byte-equal, but tests must
assert behavior/conformance rather than object identity.

- [ ] **Step 5: Make the root distribution baseline-only**

Root Hatch packages become `packages = ["src/dci"]`. Preserve every existing
`[project.scripts]` entry and runtime dependency. Add uv workspace membership
for the three Asterion-side projects without making baseline runtime metadata
depend on them.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run python -m unittest tests.test_distribution_boundaries tests.test_asterion_structure tests.test_pi_rpc_runner tests.test_agent_runtime_protocol -v
uv run python -m compileall -q packages/python/asterion-core/src src/dci tests
uv run ruff check packages/python/asterion-core/src src/dci tests
git diff --check
```

Commit: `refactor: split Asterion from the DCI baseline`

### Task 2: Make the DCI capability an independent resource-owning distribution

**Files:**
- Create: `capabilities/dci-research/pyproject.toml`
- Move: `capabilities/dci-research/manifests/*.json` to `capabilities/dci-research/src/asterion_dci_research/manifests/`
- Modify: capability/catalog/assembly tests and docs referencing old paths
- Modify: root workspace development configuration
- Modify: `tests/test_distribution_boundaries.py`

**Interfaces:**
- Produces distribution `asterion-dci-research==0.1.0`, depending only on `asterion>=0.1.0`.
- Produces `manifest_root() -> Traversable` or context-managed canonical resource access from `importlib.resources`.

- [ ] **Step 1: Write failing wheel/resource tests**

Build the capability wheel, install it with the Asterion wheel into an isolated
environment, and assert all four validated manifests are discoverable through
`importlib.resources.files("asterion_dci_research").joinpath("manifests")`.
Assert the former `capabilities/dci-research/manifests` path does not exist and
the wheel contains each JSON basename once.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_distribution_boundaries.DciCapabilityDistributionTests -v`

Expected: missing nested project/resources and duplicate root packaging assumptions.

- [ ] **Step 3: Create distribution and move canonical resources**

The nested project declares `asterion>=0.1.0`, includes
`src/asterion_dci_research`, and includes `manifests/*.json` as wheel/sdist data.
Remove the capability path from root Hatch packages. Update catalog consumers to
resolve installed resources rather than repository-relative old paths.

- [ ] **Step 4: Verify and commit**

Run capability, catalog, composition, assembly, wheel, compile, and Ruff suites.

Commit: `refactor: package DCI research independently`

### Task 3: Define and validate the installed application provider contract

**Files:**
- Create: `packages/python/asterion-core/src/asterion/applications/__init__.py`
- Create: `packages/python/asterion-core/src/asterion/applications/provider.py`
- Create: `tests/test_installed_application_provider.py`

**Interfaces:**
- Produces `APPLICATION_PROVIDER_PROTOCOL = "asterion.application-provider/v1"`.
- Produces frozen `InstalledApplicationProvider`, `InstalledApplication`, `ApplicationProviderError`, and `validate_installed_provider`.

- [ ] **Step 1: Write failing contract and filesystem tests**

Use this API:

```python
provider = InstalledApplicationProvider(
    protocol="asterion.application-provider/v1",
    provider_id="example-app",
    resource_root=root,
    applications=(InstalledApplication(
        application_id="example.research",
        version="1.0.0",
        assembly_paths=(root / "assemblies/research.json",),
        catalog_roots=(root / "manifests",),
        implementations=((PackageRef("example.research", "1.0.0"), implementation),),
        runtime_ids=("pi.reference",),
    ),),
)
validated = validate_installed_provider(provider, selected_id="example-app")
```

Test protocol/ID mismatch, duplicates, mutable/wrong types, empty runtime set,
unknown binding, symlink root/path, missing path, canonical escape, and safe
messages without object/module/sentinel content.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_installed_application_provider -v`

Expected: provider module missing.

- [ ] **Step 3: Implement immutable validation**

Canonicalize with `resolve(strict=True)`, reject symlinks before resolution,
require resources beneath `resource_root`, validate assembly identity against
the declared `application_id@version`, and reuse AF-110 exact implementation
preflight after assembly resolution. Return a deeply immutable validated value;
never include reprs, module paths, or unsafe contents in errors.

- [ ] **Step 4: Verify and commit**

Run provider, package execution, assembly, compile, and Ruff tests.

Commit: `feat: define installed application providers`

### Task 4: Discover metadata and load only the selected provider

**Files:**
- Create: `packages/python/asterion-core/src/asterion/applications/discovery.py`
- Create: `tests/test_application_discovery.py`

**Interfaces:**
- Produces `InstalledProviderMetadata`, `list_application_providers(entry_points=None)`, and `load_application_provider(provider_id, entry_points=None)`.

- [ ] **Step 1: Write failing metadata/load tests**

Use fake entry-point objects with counters. Assert list sorts provider and
distribution metadata without `load()`. Assert load validates provider ID first,
loads exactly one exact-name match, rejects zero/duplicates, does not load
adjacent entries, invokes one no-argument factory, validates its result, and
redacts import/factory exceptions.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_application_discovery -v`

Expected: discovery module missing.

- [ ] **Step 3: Implement selected-only discovery**

Query only group `asterion.applications`. Metadata output contains provider ID,
distribution name, and distribution version; never entry-point value/module.
Require the provider factory to be callable and convert every load/factory
exception into `ApplicationProviderError("installed application provider failed to load")`.

- [ ] **Step 4: Verify and commit**

Run discovery/provider tests, compile, Ruff, and diff checks.

Commit: `feat: load explicit installed applications`

### Task 5: Add host-owned runtime factories and the generic Asterion CLI

**Files:**
- Create: `packages/python/asterion-core/src/asterion/runtime/factory.py`
- Create: `packages/python/asterion-core/src/asterion/cli.py`
- Modify: `packages/python/asterion-core/pyproject.toml`
- Create: `tests/test_asterion_cli.py`

**Interfaces:**
- Produces exact `RuntimeFactoryRegistry` and console script `asterion = "asterion.cli:main"`.
- Produces commands `asterion list` and `asterion run --provider ID --runtime ID ASSEMBLY`.

- [ ] **Step 1: Write failing CLI ordering/privacy tests**

Patch discovery and runtime factories with recording fakes. Prove list does not
load, run loads only the selected provider, all provider/resource/assembly/
binding/runtime compatibility checks precede factory invocation, stdin/input is
not echoed on failure, and stdout is exactly one JSON object containing
application/runtime/run IDs plus normalized events/artifacts.

- [ ] **Step 2: Verify RED**

Run: `uv run python -m unittest tests.test_asterion_cli -v`

Expected: CLI/factory modules missing and no `asterion` script.

- [ ] **Step 3: Implement exact runtime registry and CLI**

The registry accepts iterable `(runtime_id, factory)` bindings and rejects
duplicates/unknown IDs. `main(argv=None, *, entry_points=None,
runtime_factories=None)` supports deterministic dependency injection for tests.
Use argparse without exposing provider module values. Construct runtime only
after complete provider and assembly preflight, then call
`run_composed_application`.

- [ ] **Step 4: Verify and commit**

Run CLI, discovery, provider, runner, console-script wheel, compile, and Ruff tests.

Commit: `feat: run installed Asterion applications`

### Task 6: Package and register the DCI installed application

**Files:**
- Create: `applications/dci-agent-lite/pyproject.toml`
- Create: `applications/dci-agent-lite/src/asterion_dci_application/__init__.py`
- Create: `applications/dci-agent-lite/src/asterion_dci_application/provider.py`
- Move: `applications/dci-agent-lite/assemblies/*.json` to `applications/dci-agent-lite/src/asterion_dci_application/assemblies/`
- Replace/remove: `applications/dci-agent-lite/python/dci_research_host.py`
- Modify: integration and distribution tests/docs

**Interfaces:**
- Registers `[project.entry-points."asterion.applications"] dci-agent-lite = "asterion_dci_application.provider:create_provider"`.
- Produces one provider for `dci.research-capability@1.0.0` with exact DCI implementation and `pi.reference` compatibility.

- [ ] **Step 1: Write failing independent-wheel and generic-run tests**

Build/install Asterion core, DCI capability, and DCI application wheels into an
isolated environment. Assert metadata listing does not import DCI provider,
selected load returns canonical resources, assemblies occur exactly once, old
paths do not exist, and a fixture runtime executes the DCI app through the same
generic CLI used by a synthetic independent provider.

- [ ] **Step 2: Verify RED**

Run DCI application distribution and generic CLI integration tests.

Expected: no nested distribution/entry point and resources remain at old paths.

- [ ] **Step 3: Implement provider and move canonical resources**

Use `importlib.resources.files` for application assemblies and the capability's
manifest root. Return immutable provider values only; do not construct runtime,
load `.env`, start services, import `dci`, or reference repository-root paths.

- [ ] **Step 4: Verify baseline and product paths**

Run isolated wheel integration, DCI capability/app, generic CLI, baseline
`dci-agent-lite --help`, both baseline example command-construction tests, and
source import-boundary checks.

- [ ] **Step 5: Commit**

Commit: `feat: register the installed DCI application`

### Task 7: Document and close AF-120

**Files:**
- Create: `docs/architecture/installed-applications.md`
- Modify: `docs/architecture/agent-framework.md`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md` append-only
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- Produces operator documentation, four-wheel dependency evidence, AF-120 acceptance, and a governed successor or explicit terminal state.

- [ ] **Step 1: Add failing documentation assertions**

Assert the guide documents entry-point trust, metadata-only list, selected-only
load, resource roots, runtime authority, four distributions, frozen enhanced
baseline, privacy failures, and all non-goals.

- [ ] **Step 2: Write guide and migration notes**

Include install/build commands for each wheel, `asterion list/run` examples,
baseline comparison commands, dependency graph, and the removal of Python object
identity between baseline and Asterion.

- [ ] **Step 3: Run full verification**

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q packages/python/asterion-core/src capabilities/dci-research/src applications/dci-agent-lite/src src/dci tests
uv run ruff check packages/python/asterion-core/src capabilities/dci-research/src applications/dci-agent-lite/src src/dci tests
uv build --package asterion
uv build --package asterion-dci-research
uv build --package asterion-dci-agent-lite
uv build --package dci
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
cargo fmt --manifest-path packages/rust/controlled-executor/Cargo.toml --check
cargo clippy --manifest-path packages/rust/controlled-executor/Cargo.toml --all-targets -- -D warnings
bash -n tools/climb/eval-local.sh scripts/examples/dci_basic_example.sh scripts/examples/dci_runtime_context_example.sh
python3 tools/project_scope_check.py
git diff --check
```

Install the four built wheels into separate temporary environments and rerun
import/content/entry-point smoke tests outside the checkout. When credentials
are valid, run the Asterion DCI provider probe and the independent baseline
example; record correctness separately rather than treating process exit as an
answer-quality pass.

- [ ] **Step 4: Govern closure**

Rerun scope preflight, record exact test/build/provider/baseline evidence,
complete AF-120, select the dependency-ready successor or terminal state, update
structural state and D-030, append journal facts, and refresh a live checkpoint.

- [ ] **Step 5: Commit closure atomically**

Commit: `docs: close installed application binding`
