# Asterion Framework Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or execute inline task-by-task when repository policy prohibits delegation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish `asterion` as the sole authoritative Python framework implementation while preserving DCI imports, CLI behavior, examples, wire literals, and cross-language verification.

**Architecture:** Move generic modules from `src/dci/framework/` into focused `src/asterion/` packages, then make `dci.framework.*` thin object-identity compatibility re-exports. Reorganize declarative capability/application assets only after loaders accept explicit new roots; keep all `dci.*` protocol literals unchanged in AF-095.

**Tech Stack:** Python 3.10+, hatchling, unittest, Ruff, JSON Schema Draft 2020-12, TypeScript 6/Ajv, Rust/Cargo, Bash.

## Global Constraints

- Product, distribution, import root, and private TypeScript working namespace use `Asterion` / `asterion`.
- `asterion` must never import `dci`; DCI may import Asterion.
- Preserve `dci-agent-lite`, `dci-run-pi-rpc`, both `scripts/examples/` entry paths, and all current CLI flags.
- Preserve current `dci.agent-runtime/v1`, `dci.package/v1`, `dci.assembly/v1`, and `dci.executor/v1` wire literals.
- Keep `.env` credentials private and leave the independent `pi/` checkout untouched.
- Do not implement AF-100 runner, registry, publication, workflow scheduling, or protocol renaming.

---

### Task 1: Authoritative Asterion runtime boundary

**Files:**
- Create: `src/asterion/__init__.py`
- Create: `src/asterion/runtime/__init__.py`
- Create: `src/asterion/runtime/protocol.py`
- Create: `src/asterion/runtime/host.py`
- Create: `src/asterion/adapters/__init__.py`
- Create: `src/asterion/adapters/pi.py`
- Create: `src/asterion/adapters/claude_code.py`
- Create: `src/asterion/runtimes/__init__.py`
- Create: `src/asterion/runtimes/claude_code.py`
- Modify: matching modules under `src/dci/framework/`
- Modify: `pyproject.toml`
- Test: `tests/test_asterion_structure.py`
- Test: existing runtime/adapter/host suites

**Interfaces:**
- Produces: authoritative `asterion.runtime.protocol`, `asterion.runtime.host`, `asterion.adapters.*`, and `asterion.runtimes.*` public objects.
- Compatibility: every former `dci.framework` symbol is imported directly from Asterion so `old_symbol is new_symbol`.

- [ ] **Step 1: Write failing ownership and compatibility tests**

```python
from pathlib import Path

from asterion.runtime.protocol import PROTOCOL_VERSION as new_version
from dci.framework.protocol import PROTOCOL_VERSION as old_version
from asterion.runtime.host import AgentRuntimeClient as NewClient
from dci.framework.host import AgentRuntimeClient as OldClient

ROOT = Path(__file__).resolve().parents[1]

class AsterionStructureTests(unittest.TestCase):
    def test_runtime_objects_are_authoritative_and_compatible(self) -> None:
        self.assertEqual(new_version, "dci.agent-runtime/v1")
        self.assertIs(OldClient, NewClient)
        self.assertEqual(old_version, new_version)

    def test_asterion_never_imports_dci(self) -> None:
        source = "\n".join(
            path.read_text() for path in (ROOT / "src/asterion").rglob("*.py")
        )
        self.assertNotRegex(source, r"(?:from|import)\s+dci(?:\.|\s|$)")
```

- [ ] **Step 2: Run RED tests**

Run: `uv run python -m unittest tests.test_asterion_structure -v`

Expected: import failure for missing `asterion`.

- [ ] **Step 3: Move runtime implementations and add direct re-exports**

Use the existing module contents unchanged under Asterion except for intra-framework imports, which become relative Asterion imports. Each old module contains only direct imports and `__all__`, for example:

```python
from asterion.runtime.protocol import *  # noqa: F403
from asterion.runtime.protocol import __all__
```

If an authoritative module lacks `__all__`, add an explicit tuple naming its existing public API before creating the compatibility module.

- [ ] **Step 4: Package both transition roots**

Change the wheel configuration to:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/asterion", "src/dci"]
```

Keep `[project].name = "dci"` and every existing console script during AF-095; distribution renaming requires a separate packaging release decision.

- [ ] **Step 5: Run focused runtime gates**

Run:

```bash
uv run python -m unittest tests.test_asterion_structure tests.test_agent_runtime_protocol tests.test_python_runtime_host tests.test_pi_protocol_adapter tests.test_claude_code_protocol_adapter tests.test_claude_code_runtime -v
uv run python -m compileall -q src/asterion src/dci/framework tests/test_asterion_structure.py
uv run ruff check src/asterion src/dci/framework tests/test_asterion_structure.py
```

Expected: all pass and no Asterion-to-DCI import exists.

- [ ] **Step 6: Add AF-095-H-001 climb dimensions and run the cycle**

Dimensions: `authoritative_import`, `object_identity`, `dependency_direction`, `packaging_compatibility`. Train runs the focused gates above; local eval maps one deterministic test to each dimension.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/asterion src/dci/framework tests/test_asterion_structure.py tools/climb docs/status
git commit -m "refactor: establish Asterion runtime package"
```

### Task 2: Extract packages, assembly, and executor protocols

**Files:**
- Create: `src/asterion/packages/__init__.py`
- Create: `src/asterion/packages/protocol.py`
- Create: `src/asterion/packages/catalog.py`
- Create: `src/asterion/packages/composition.py`
- Create: `src/asterion/assembly/__init__.py`
- Create: `src/asterion/assembly/protocol.py`
- Create: `src/asterion/services/__init__.py`
- Create: `src/asterion/services/executor_protocol.py`
- Modify: matching modules under `src/dci/framework/`
- Modify: framework-internal imports
- Test: `tests/test_asterion_structure.py`
- Test: package/catalog/assembly/executor suites

**Interfaces:**
- Consumes: Task 1 Asterion runtime protocol and compatibility pattern.
- Produces: `asterion.packages.*`, `asterion.assembly.*`, and `asterion.services.executor_protocol` as sole implementations.

- [ ] **Step 1: Extend RED object-identity tests**

```python
from asterion.assembly.protocol import AssemblyPlan as NewPlan
from asterion.packages.catalog import PackageCatalog as NewCatalog
from dci.framework.assembly import AssemblyPlan as OldPlan
from dci.framework.package_catalog import PackageCatalog as OldCatalog

def test_package_and_assembly_objects_are_compatibility_aliases(self) -> None:
    self.assertIs(OldPlan, NewPlan)
    self.assertIs(OldCatalog, NewCatalog)
```

Also assert every `src/dci/framework/*.py` compatibility module contains no class or function definitions.

- [ ] **Step 2: Run RED tests**

Run: `uv run python -m unittest tests.test_asterion_structure -v`

Expected: missing Asterion package/assembly modules.

- [ ] **Step 3: Move generic implementations and rewrite only internal imports**

Map modules exactly:

```text
package_protocol.py  -> asterion/packages/protocol.py
package_catalog.py   -> asterion/packages/catalog.py
packages.py          -> asterion/packages/composition.py
assembly.py          -> asterion/assembly/protocol.py
executor_protocol.py -> asterion/services/executor_protocol.py
```

Old paths become direct re-exports. Keep constants and wire strings unchanged.

- [ ] **Step 4: Run focused behavior and duplication gates**

Run:

```bash
uv run python -m unittest tests.test_asterion_structure tests.test_package_composition tests.test_package_catalog tests.test_application_assembly tests.test_executor_protocol -v
uv run python -m compileall -q src tests/test_asterion_structure.py
uv run ruff check src tests/test_asterion_structure.py
git diff --check
```

Expected: behavior unchanged, old/new public objects identical, compatibility files contain no definitions.

- [ ] **Step 5: Add AF-095-H-002 adapter dimensions and cycle**

Dimensions: `package_extraction`, `assembly_extraction`, `wire_stability`, `single_implementation`.

- [ ] **Step 6: Commit**

```bash
git add src/asterion src/dci/framework tests/test_asterion_structure.py tools/climb docs/status
git commit -m "refactor: extract Asterion composition contracts"
```

### Task 3: Separate capability and application assets

**Files:**
- Create: `capabilities/dci-research/src/asterion_dci_research/manifests/*.json`
- Create: `capabilities/controlled-code/manifests/*.json`
- Create: `applications/dci-agent-lite/assemblies/*.json`
- Modify: `src/asterion/packages/catalog.py` only if a named explicit-root helper is required
- Modify: TypeScript schema-copy/test paths under `packages/typescript/asterion-runtime/`
- Modify: architecture documentation
- Test: `tests/test_asterion_structure.py`
- Test: catalog, composition, assembly, and TypeScript suites

**Interfaces:**
- Consumes: Task 2 catalog and assembly APIs.
- Produces: declarative top-level ownership without changing `package_id`, version, protocol, or application identity.

- [ ] **Step 1: Write RED canonical-root tests**

```python
CAPABILITIES = ROOT / "capabilities"
APPLICATIONS = ROOT / "applications"

def test_declarative_assets_have_product_level_owners(self) -> None:
    self.assertEqual(
        {path.name for path in CAPABILITIES.iterdir()},
        {"controlled-code", "dci-research"},
    )
    self.assertTrue(
        (APPLICATIONS / "dci-agent-lite/assemblies/dci-local-research.json").is_file()
    )
```

Add equality tests comparing identities selected from new explicit roots with the pre-move expected eight package identities and two assembly identities.

- [ ] **Step 2: Run RED tests**

Run: `uv run python -m unittest tests.test_asterion_structure -v`

Expected: missing `capabilities/` and `applications/` roots.

- [ ] **Step 3: Move assets and update explicit callers**

Use `git mv` so history follows the files. Split the eight manifests by graph and place both assemblies under the DCI reference application. Update tests, examples, schema-copy scripts, and documentation to use explicit new roots; do not add fallback discovery or duplicate files.

- [ ] **Step 4: Rename cross-language working directories without changing package publication metadata**

Move `packages/typescript/asterion-runtime/` to `packages/typescript/asterion-runtime/` and `packages/rust/controlled-executor/` to `packages/rust/controlled-executor/`. Update Make targets and test paths. Keep current internal package names and protocol literals until a separate release decision.

- [ ] **Step 5: Run cross-language focused gates**

```bash
uv run python -m unittest tests.test_asterion_structure tests.test_package_composition tests.test_package_catalog tests.test_application_assembly -v
npm --prefix packages/typescript/asterion-runtime ci
npm --prefix packages/typescript/asterion-runtime test
make test-rust-executor
make check-rust-executor
git diff --check
```

Expected: eight exact package identities and two assembly identities validate from their new roots; all language suites pass.

- [ ] **Step 6: Add AF-095-H-003 dimensions and cycle**

Dimensions: `capability_roots`, `application_root`, `cross_language_paths`, `identity_stability`.

- [ ] **Step 7: Commit**

```bash
git add capabilities applications packages Makefile tests docs tools/climb
git commit -m "refactor: separate Asterion products and capabilities"
```

### Task 4: DCI compatibility and extraction closure

**Files:**
- Modify: `README.md`
- Modify: `.env.template` only for comments that describe ownership
- Modify: `docs/architecture/agent-framework.md`
- Create: `docs/architecture/asterion-framework-layout.md`
- Modify: `tests/test_asterion_structure.py`
- Modify: example/CLI tests
- Modify: status, decision, worklist, and climb adapter files

**Interfaces:**
- Consumes: Tasks 1–3 complete extracted layout.
- Produces: documented Asterion ownership, stable DCI product entry, and full AF-095 closure evidence.

- [ ] **Step 1: Add RED example and packaging contract tests**

```python
def test_verified_dci_examples_keep_the_product_cli(self) -> None:
    for name in ("dci_basic_example.sh", "dci_runtime_context_example.sh"):
        source = (ROOT / "scripts/examples" / name).read_text()
        self.assertIn("uv run dci-agent-lite", source)
        self.assertIn('source "$REPO_ROOT/.env"', source)

def test_distribution_preserves_every_existing_console_script(self) -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()
    for command in (
        "dci-agent-lite",
        "dci-run-pi-rpc",
        "dci-print-pi-system-prompt",
    ):
        self.assertIn(command, pyproject)
```

Add a model-free subprocess test that supplies harmless `DCI_PROVIDER` and
`DCI_MODEL`, replaces `uv` on `PATH` with a recording stub, invokes each example,
and asserts the resulting argv still targets `dci-agent-lite` without printing
the environment values.

- [ ] **Step 2: Run RED tests**

Run: `uv run python -m unittest tests.test_asterion_structure -v`

Expected: documentation/layout or model-free example contract failure before closure changes.

- [ ] **Step 3: Document the final ownership and compatibility window**

The guide must include the target directory tree, dependency rule
`asterion -> no dci imports`, DCI example commands, unchanged wire literals,
compatibility re-export policy, and explicit non-goals.

- [ ] **Step 4: Run provider-backed examples only when credentials are available**

```bash
if [ -n "${DCI_PROVIDER:-}" ] && [ -n "${DCI_MODEL:-}" ]; then
  bash scripts/examples/dci_basic_example.sh
  bash scripts/examples/dci_runtime_context_example.sh
fi
```

Never print the variables. Record executed/skipped status, not values.

- [ ] **Step 5: Add AF-095-H-004 full closure adapter and cycle**

Dimensions: `dci_cli_compatibility`, `example_compatibility`, `architecture_boundary`, `framework_closure`. The train gate runs full Python discovery, compile, Ruff, clean TypeScript install/tests, Rust tests/fmt/Clippy, shell syntax, AF-095 scope, and diff checks.

- [ ] **Step 6: Independently rerun full closure**

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q src tests tools
uv run ruff check src tests tools
npm --prefix packages/typescript/asterion-runtime ci
npm --prefix packages/typescript/asterion-runtime test
make test-rust-executor
make check-rust-executor
bash -n scripts/examples/dci_basic_example.sh scripts/examples/dci_runtime_context_example.sh tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
python3 tools/project_scope_check.py --climb-hypothesis AF-095-H-004
git diff --check
```

- [ ] **Step 7: Close AF-095 and reactivate AF-100**

Update `WORKLIST.md`, current state, decisions, journal, resume baton, and AF-100 spec paths. AF-100 becomes the sole `in_progress` package only after the scope audit passes with its seeded hypothesis.

- [ ] **Step 8: Commit**

```bash
git add README.md .env.template docs tests tools/climb
git commit -m "docs: close Asterion framework extraction"
```
