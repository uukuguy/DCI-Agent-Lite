# AF-300 Asterion Project-Root Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge every Asterion-owned product asset beneath a complete top-level `asterion/` project root while preserving the independent original DCI baseline and all installed behavior.

**Architecture:** The root remains a non-buildable mixed development workspace containing original DCI, parity evidence, and governance. `asterion/` becomes the sole buildable Asterion project with standard `src/asterion`, auxiliary TypeScript/Rust packages, schemas, examples, scripts, product docs, and project-local tests; root parity tests deliberately address both products.

**Tech Stack:** Python 3.10+, uv workspaces, Hatchling, `unittest`, Ruff, TypeScript 6/Node 20+, Rust 2024/Tokio, JSON Schema, Bash, Markdown.

## Global Constraints

- Active work package is AF-300; run `python3 tools/project_scope_check.py` before implementation and before closure.
- Preserve installed distribution name `asterion`, import root `asterion`, scripts `asterion`/`asterion-dci`, provider IDs, application/package IDs, protocol literals, configuration variables, and artifact formats.
- Keep `src/dci/` source-only and independent; neither production product may import or execute the other.
- Use `git mv` only for the exact mechanical path moves named below; use `apply_patch` for content edits.
- Do not add path compatibility stubs, symlinks, duplicate project files, or a second Python distribution.
- Do not move credentials, `.env`, corpora, datasets, outputs, caches, `.worktrees`, `node_modules`, Rust `target`, or external `pi/`.
- Preserve the user-owned untracked `.superpowers/sdd/task-0-review.md`.
- Every task uses a red/green test cycle and ends with a cohesive verified commit.
- All AF-300 verification is provider-free; do not run full datasets, publish a package, or claim 62.9% reproduction.

---

### Task 1: Move the primary Python project to the Asterion project root

**Files:**
- Create: `tests/test_asterion_project_root.py`
- Move: `packages/python/asterion-core/pyproject.toml` → `asterion/pyproject.toml`
- Move: `packages/python/asterion-core/src/asterion/` → `asterion/src/asterion/`
- Modify: `pyproject.toml`
- Modify: `tests/test_distribution_boundaries.py`
- Modify: `tests/test_asterion_structure.py`
- Modify: `assets/dci/product-parity.json`
- Modify: `tests/test_application_assembly.py`
- Modify: `tests/test_application_runner.py`
- Modify: `tests/test_asterion_dci_batch_launchers.py`
- Modify: `tests/test_asterion_dci_export.py`
- Modify: `tests/test_asterion_documentation.py`
- Modify: `tests/test_builtin_controlled_code_application.py`
- Modify: `tests/test_builtin_dci_application.py`
- Modify: `tests/test_composed_application_runner.py`
- Modify: `tests/test_controlled_code_application.py`
- Modify: `tests/test_dci_research_capability.py`
- Modify: `tests/test_package_catalog.py`
- Modify: `tests/test_package_composition.py`
- Modify: `tests/test_package_execution.py`

**Interfaces:**
- Consumes: approved D-043 target root and current `asterion` wheel metadata.
- Produces: buildable project at `asterion/pyproject.toml`, source root `asterion/src/asterion/`, and root workspace member `asterion`.

- [ ] **Step 1: Add the failing root-boundary contract**

Create `tests/test_asterion_project_root.py` with this initial content:

```python
from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "asterion"


class AsterionProjectRootTests(unittest.TestCase):
    def test_primary_python_project_has_the_converged_root(self) -> None:
        self.assertTrue((PROJECT / "pyproject.toml").is_file())
        self.assertTrue((PROJECT / "src/asterion/cli.py").is_file())
        self.assertFalse((ROOT / "packages/python/asterion-core").exists())

        workspace = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertEqual(workspace["tool"]["uv"]["workspace"]["members"], ["asterion"])
        self.assertEqual(
            workspace["tool"]["uv"]["sources"]["asterion"],
            {"workspace": True},
        )

        project = tomllib.loads((PROJECT / "pyproject.toml").read_text())
        self.assertEqual(project["project"]["name"], "asterion")
        self.assertEqual(project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"], ["src/asterion"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract and verify RED**

Run:

```bash
uv run python -m unittest tests.test_asterion_project_root -v
```

Expected: FAIL because `asterion/pyproject.toml` and `asterion/src/asterion/` do not exist.

- [ ] **Step 3: Perform the exact project move and workspace edit**

Run the mechanical moves:

```bash
mkdir -p asterion/src
git mv packages/python/asterion-core/pyproject.toml asterion/pyproject.toml
git mv packages/python/asterion-core/src/asterion asterion/src/asterion
rmdir packages/python/asterion-core/src packages/python/asterion-core packages/python 2>/dev/null || true
```

Patch root `pyproject.toml` to retain the existing source override and replace only the member:

```toml
[tool.uv.sources]
asterion = { workspace = true }

[tool.uv.workspace]
members = ["asterion"]
```

- [ ] **Step 4: Replace operational old-source paths**

List exact consumers:

```bash
rg -l 'packages/python/asterion-core' \
  Makefile pyproject.toml tools tests assets scripts \
  --glob '*.py' --glob '*.json' --glob '*.toml' --glob 'Makefile' --glob '*.sh'
```

The command must return only the files listed above plus `pyproject.toml` and the two boundary tests. For every returned operational file, use `apply_patch` to replace:

```text
packages/python/asterion-core/src/asterion  → asterion/src/asterion
packages/python/asterion-core/pyproject.toml → asterion/pyproject.toml
packages/python/asterion-core                → asterion
```

Do not edit historical `docs/superpowers/` or `docs/status/JOURNAL.md` occurrences. Product documentation moves in Task 5.

- [ ] **Step 5: Update distribution/source-boundary assertions**

In `tests/test_distribution_boundaries.py`, set the build project and source root to:

```python
ASTERION_PROJECT = ROOT / "asterion"
ASTERION_SOURCE = ASTERION_PROJECT / "src/asterion"
```

Update root-workspace assertions to expect `members == ["asterion"]`. In `tests/test_asterion_structure.py`, point every authoritative source, capability, application, and resource root beneath `ROOT / "asterion/src/asterion"`.

- [ ] **Step 6: Run focused Python/build tests and verify GREEN**

Run:

```bash
uv sync
uv run python -m unittest \
  tests.test_asterion_project_root \
  tests.test_asterion_structure \
  tests.test_distribution_boundaries -v
uv build asterion
uv run python -m compileall -q asterion/src/asterion tests/test_asterion_project_root.py
uv run ruff check asterion/src/asterion tests/test_asterion_project_root.py \
  tests/test_asterion_structure.py tests/test_distribution_boundaries.py
git diff --check
```

Expected: all tests/checks pass and `dist` output is created from `asterion/` only.

- [ ] **Step 7: Commit the primary project root**

```bash
git add asterion pyproject.toml tests tools assets scripts Makefile
git commit -m "refactor: establish Asterion project root"
```

Append a ≤20-word journal entry with the resulting hash before the next task.

### Task 2: Move schemas and auxiliary language packages

**Files:**
- Modify: `tests/test_asterion_project_root.py`
- Move: `schemas/` → `asterion/schemas/`
- Move: `packages/typescript/asterion-runtime/` → `asterion/packages/typescript/asterion-runtime/`
- Move: `packages/rust/controlled-executor/` → `asterion/packages/rust/controlled-executor/`
- Modify: `asterion/packages/typescript/asterion-runtime/scripts/copy-schemas.mjs`
- Modify: `asterion/packages/typescript/asterion-runtime/test/runtime.test.mjs`
- Modify: `Makefile`
- Modify: root tests with explicit schema, TypeScript, Rust, or fixture paths

**Interfaces:**
- Consumes: `asterion/` project root from Task 1 and existing protocol literals/fixtures.
- Produces: `asterion/schemas/` plus independently testable auxiliary packages under `asterion/packages/`.

- [ ] **Step 1: Extend the path contract and verify RED**

Add this method to `AsterionProjectRootTests`:

```python
    def test_cross_language_assets_live_inside_asterion(self) -> None:
        expected = (
            "schemas/agent-runtime/v1/event.schema.json",
            "schemas/assembly/v1/assembly.schema.json",
            "schemas/executor/v1/request.schema.json",
            "schemas/packages/v1/package-manifest.schema.json",
            "packages/typescript/asterion-runtime/package.json",
            "packages/rust/controlled-executor/Cargo.toml",
        )
        for relative in expected:
            self.assertTrue((PROJECT / relative).is_file(), relative)
        for obsolete in (ROOT / "schemas", ROOT / "packages/typescript", ROOT / "packages/rust"):
            self.assertFalse(obsolete.exists(), str(obsolete))
```

Run `uv run python -m unittest tests.test_asterion_project_root -v`; expected: FAIL on the first new target.

- [ ] **Step 2: Move the three exact trees**

```bash
mkdir -p asterion/packages/typescript asterion/packages/rust
git mv schemas asterion/schemas
git mv packages/typescript/asterion-runtime asterion/packages/typescript/asterion-runtime
git mv packages/rust/controlled-executor asterion/packages/rust/controlled-executor
rmdir packages/typescript packages/rust packages 2>/dev/null || true
```

Generated ignored directories may move physically with their parent but must remain ignored and unstaged. Do not delete or commit them.

- [ ] **Step 3: Fix TypeScript source and temporary fixture paths**

Because schemas and the TypeScript package move together with the same relative depth, keep these `copy-schemas.mjs` URLs unchanged and add a test assertion for them:

```javascript
new URL("../../../../schemas/agent-runtime/v1", import.meta.url)
new URL("../../../../schemas/packages/v1/package-manifest.schema.json", import.meta.url)
new URL("../../../../schemas/assembly/v1/assembly.schema.json", import.meta.url)
```

In `test/runtime.test.mjs`, replace Python resource URLs with:

```javascript
new URL("../../../../src/asterion/capabilities/dci_research/manifests/", import.meta.url)
new URL("../../../../src/asterion/capabilities/controlled_code/manifests/", import.meta.url)
new URL("../../../../src/asterion/applications/dci_agent_lite/assemblies/", import.meta.url)
new URL("../../../../src/asterion/applications/controlled_code/assemblies/", import.meta.url)
```

Fixtures do not move until Task 5, so temporarily replace their root with five parents:

```javascript
new URL("../../../../../tests/fixtures/agent_runtime/v1/", import.meta.url)
new URL("../../../../../tests/fixtures/packages/v1/", import.meta.url)
new URL("../../../../../tests/fixtures/assembly/v1/", import.meta.url)
```

Task 5 removes this temporary mixed-root fixture dependency. Keep package name/version and protocol literals unchanged.

- [ ] **Step 4: Update Rust, Make, and root-test paths**

Use `apply_patch` for exact replacements returned by:

```bash
rg -l 'packages/(typescript/asterion-runtime|rust/controlled-executor)|ROOT / "schemas"|/schemas/' \
  Makefile tests tools assets asterion \
  --glob '*.py' --glob '*.mjs' --glob '*.ts' --glob '*.json' --glob '*.toml' --glob 'Makefile'
```

Use these target roots:

```text
asterion/packages/typescript/asterion-runtime
asterion/packages/rust/controlled-executor
asterion/schemas
```

Do not rename npm/crate identities or protocol constants.

- [ ] **Step 5: Run cross-language gates and verify GREEN**

```bash
uv run python -m unittest tests.test_asterion_project_root tests.test_asterion_structure -v
npm --prefix asterion/packages/typescript/asterion-runtime test
cargo fmt --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --check
cargo clippy --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml
git diff --check
```

Expected: Python, 11 TypeScript tests, Rust fmt/Clippy/tests, and diff checks pass.

- [ ] **Step 6: Commit schemas and language packages**

```bash
git add asterion Makefile tests tools assets
git commit -m "refactor: colocate Asterion language packages"
```

Journal the commit hash before Task 3.

### Task 3: Move Asterion examples and product scripts

**Files:**
- Modify: `tests/test_asterion_project_root.py`
- Move: `applications/dci-agent-lite/python/dci_research_host.py` → `asterion/examples/applications/dci_research.py`
- Move: `applications/controlled-code/python/controlled_code_host.py` → `asterion/examples/applications/controlled_code.py`
- Create: `asterion/examples/README.md`
- Move: `scripts/asterion/` → `asterion/scripts/`
- Modify: `tests/test_composed_application_runner.py`
- Modify: `tests/test_asterion_dci_batch_launchers.py`
- Modify: `assets/dci/product-parity.json`
- Modify: `assets/dci/batch-parity.json`
- Modify: `Makefile`

**Interfaces:**
- Consumes: authoritative package-local providers/capabilities under `asterion/src/asterion`.
- Produces: explicit non-installed Python examples and twelve Asterion-owned launcher paths under the project root.

- [ ] **Step 1: Add example/script path tests and verify RED**

Add:

```python
    def test_examples_and_launchers_are_project_owned(self) -> None:
        self.assertTrue((PROJECT / "examples/applications/dci_research.py").is_file())
        self.assertTrue((PROJECT / "examples/applications/controlled_code.py").is_file())
        launchers = sorted((PROJECT / "scripts").glob("**/run_*.sh"))
        self.assertEqual(len(launchers), 12)
        self.assertFalse((ROOT / "applications").exists())
        self.assertFalse((ROOT / "scripts/asterion").exists())
```

Run the project-root test; expected: FAIL.

- [ ] **Step 2: Move examples and launchers**

```bash
mkdir -p asterion/examples/applications
git mv applications/dci-agent-lite/python/dci_research_host.py asterion/examples/applications/dci_research.py
git mv applications/controlled-code/python/controlled_code_host.py asterion/examples/applications/controlled_code.py
git mv scripts/asterion asterion/scripts
find applications -type d -name __pycache__ -prune -exec rm -rf {} +
find applications -type d -empty -delete
```

Use `apply_patch` to create `asterion/examples/README.md` with these explicit points:

- `dci_research.py` demonstrates assembly/catalog/runtime/implementation binding;
- `controlled_code.py` demonstrates explicit host-service injection;
- neither file is installed or discovered as a provider;
- normal users run `asterion` or `asterion-dci`.

- [ ] **Step 3: Update executable consumers and parity metadata**

Patch exact old paths in the listed tests/assets/Makefile. In both parity JSON files, use project-root paths beginning with:

```text
asterion/examples/applications/
asterion/scripts/
asterion/src/asterion/
```

Recompute `assets/dci/batch-parity.json` SHA-256 after its launcher path changes and update only the `batch_inventory.sha256` field in `assets/dci/product-parity.json`:

```bash
shasum -a 256 assets/dci/batch-parity.json
```

Do not modify `assets/dci/product-acceptance.json` or its referenced digest.

- [ ] **Step 4: Preserve shell root/config behavior**

For each moved launcher, retain repository-root `.env`, corpus, dataset, and `uv run asterion-dci` semantics by computing the mixed workspace root from the script location. The shared prologue must resolve four parents from `asterion/scripts/<family>/<file>`:

```bash
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)
```

Keep explicit `ASTERION_DCI_CORPUS_ROOT` and other existing overrides unchanged.

- [ ] **Step 5: Run examples, launcher, parity, and shell gates**

```bash
uv run python -m unittest \
  tests.test_asterion_project_root \
  tests.test_composed_application_runner \
  tests.test_asterion_dci_batch_launchers \
  tests.test_asterion_dci_product_parity -v
find asterion/scripts scripts/examples -name '*.sh' -print0 | xargs -0 -n1 bash -n
uv run python tools/verify_asterion_dci_product.py --validate-only
git diff --check
```

Expected: both examples load, 12 launcher pairs resolve, 533 selectors resolve, no provider operation occurs, shell syntax passes.

- [ ] **Step 6: Commit project examples and scripts**

```bash
git add asterion applications scripts tests assets Makefile
git commit -m "refactor: move Asterion examples and launchers"
```

Journal the commit hash before Task 4.

### Task 4: Move Asterion product documentation

**Files:**
- Move: `docs/README.md` → `asterion/docs/README.md`
- Move: all 11 files under `docs/architecture/` → `asterion/docs/architecture/`
- Move: `docs/guides/asterion-capability-usage.md` → `asterion/docs/guides/asterion-capability-usage.md`
- Move: `docs/guides/asterion-dci-complete-reference.md` → `asterion/docs/guides/asterion-dci-complete-reference.md`
- Move: `docs/operator/rust-executor.md` → `asterion/docs/operator/rust-executor.md`
- Move: `docs/verification/asterion-dci-validation-guide.md` → `asterion/docs/verification/asterion-dci-validation-guide.md`
- Modify: `README.md`
- Modify: `assets/docs/running.md`
- Modify: root `docs/status/{INDEX,CURRENT-STATE,DECISIONS,RESUME-NEXT-SESSION,WORKLIST}.md`
- Modify: `AGENTS.md`
- Modify: `tools/project_scope_check.py`
- Modify: `tests/test_project_scope_check.py`
- Modify: `tests/test_asterion_documentation.py`
- Modify: documentation-path assertions in root tests

**Interfaces:**
- Consumes: converged source/package/schema/example/script paths.
- Produces: self-contained Asterion documentation hub under `asterion/docs/`, while root retains governance/migration history.

- [ ] **Step 1: Extend the path/link contract and verify RED**

Add to the project-root test:

```python
    def test_product_documentation_is_project_owned(self) -> None:
        required = (
            "docs/README.md",
            "docs/architecture/agent-framework.md",
            "docs/architecture/asterion-framework-capability-integration.md",
            "docs/architecture/asterion-standalone-extraction.md",
            "docs/guides/asterion-dci-complete-reference.md",
            "docs/verification/asterion-dci-validation-guide.md",
        )
        for relative in required:
            self.assertTrue((PROJECT / relative).is_file(), relative)
```

Run the test; expected: FAIL.

- [ ] **Step 2: Move the exact product documentation set**

```bash
mkdir -p asterion/docs/{architecture,guides,operator,verification}
git mv docs/README.md asterion/docs/README.md
git mv docs/architecture/*.md asterion/docs/architecture/
git mv docs/guides/asterion-capability-usage.md asterion/docs/guides/
git mv docs/guides/asterion-dci-complete-reference.md asterion/docs/guides/
git mv docs/operator/rust-executor.md asterion/docs/operator/
git mv docs/verification/asterion-dci-validation-guide.md asterion/docs/verification/
find docs -type d -empty -delete
```

Do not move `docs/status/` or `docs/superpowers/`.

- [ ] **Step 3: Rewrite product-local links and source paths**

Within `asterion/docs`, use `apply_patch` to make links resolve relative to the Asterion project root:

```text
packages/python/asterion-core/src/asterion → src/asterion
packages/typescript/asterion-runtime       → packages/typescript/asterion-runtime
packages/rust/controlled-executor          → packages/rust/controlled-executor
scripts/asterion                           → scripts
docs/<section>                             → <section> when linked from docs/README.md
```

Links to original DCI, `assets/dci`, or migration status must explicitly traverse `../../` or `../../../` and label the mixed-repository dependency.

- [ ] **Step 4: Update root navigation and durable pointers**

Change root README and `assets/docs/running.md` links to `asterion/docs/...`. Update `AGENTS.md`, `tools/project_scope_check.py`, its focused tests, and active status/index/decision/worklist/resume pointers so the north star is `asterion/docs/architecture/agent-framework.md`, while leaving historical journal text append-only. Update `tests/test_asterion_documentation.py` paths and its local-link roots.

- [ ] **Step 5: Run documentation contracts and link checks**

```bash
uv run python -m unittest \
  tests.test_asterion_project_root \
  tests.test_asterion_documentation \
  tests.test_distribution_boundaries -v
if rg -n 'packages/python/asterion-core|scripts/asterion|docs/(architecture|guides|operator|verification)' \
  asterion/docs README.md assets/docs/running.md; then
  exit 1
fi
python3 tools/project_scope_check.py
git diff --check
```

Expected: tests pass, no obsolete product paths remain in current user-facing docs, and historical design/state files are not rewritten wholesale.

- [ ] **Step 6: Commit product documentation**

```bash
git add asterion/docs README.md assets/docs docs/status tests
git commit -m "docs: colocate Asterion product documentation"
```

Journal the commit hash before Task 5.

### Task 5: Establish project-local tests and fixtures

**Files:**
- Create: `asterion/tests/__init__.py`
- Create: `asterion/tests/test_project_boundary.py`
- Move: `tests/fixtures/` → `asterion/tests/fixtures/`
- Move: the pure Asterion test modules listed below → `asterion/tests/`
- Modify: remaining root tests that intentionally consume canonical Asterion fixtures
- Modify: `tests/test_asterion_project_root.py`

**Interfaces:**
- Consumes: complete Asterion source, packages, schemas, examples, scripts, and docs subtree.
- Produces: provider-free project-local suite runnable from `asterion/` without importing `src/dci`; root keeps original-DCI, governance, and cross-product evidence tests.

- [ ] **Step 1: Add the failing project-test ownership contract**

Extend the root contract:

```python
    def test_project_local_tests_and_fixtures_exist(self) -> None:
        self.assertTrue((PROJECT / "tests/test_project_boundary.py").is_file())
        self.assertTrue((PROJECT / "tests/fixtures/agent_runtime/v1/valid-research.jsonl").is_file())
```

Run the root contract; expected: FAIL.

- [ ] **Step 2: Move canonical fixtures and selected pure tests**

Move the complete fixture tree and these exact modules, which neither serve root governance nor remain digest-bound parity selector owners:

```bash
mkdir -p asterion/tests
git mv tests/fixtures asterion/tests/fixtures
git mv tests/test_application_discovery.py asterion/tests/
git mv tests/test_application_selection.py asterion/tests/
git mv tests/test_asterion_claude_runtime.py asterion/tests/
git mv tests/test_asterion_cli.py asterion/tests/
git mv tests/test_asterion_dci_benchmark.py asterion/tests/
git mv tests/test_asterion_dci_bridge.py asterion/tests/
git mv tests/test_asterion_pi_runtime.py asterion/tests/
git mv tests/test_builtin_controlled_code_application.py asterion/tests/
git mv tests/test_capability_product.py asterion/tests/
git mv tests/test_controlled_code_application.py asterion/tests/
git mv tests/test_controlled_executor_jsonl.py asterion/tests/
git mv tests/test_controlled_executor_service.py asterion/tests/
git mv tests/test_dci_research_capability.py asterion/tests/
git mv tests/test_default_runtime_factory.py asterion/tests/
git mv tests/test_installed_application_provider.py asterion/tests/
git mv tests/test_managed_controlled_executor.py asterion/tests/
git mv tests/test_package_execution.py asterion/tests/
```

Keep `test_asterion_dci_product_acceptance.py`, `test_asterion_dci_product_parity.py`, every module named by `assets/dci/batch-parity.json`, original-DCI tests, Make/scope/climb/setup tests, and mixed framework compatibility tests at root.

- [ ] **Step 3: Create project package and independence test**

Create an empty `asterion/tests/__init__.py`. Create `asterion/tests/test_project_boundary.py`:

```python
from __future__ import annotations

import ast
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "src/asterion"


class AsterionProjectBoundaryTests(unittest.TestCase):
    def test_production_source_never_imports_original_dci_or_repository_tests(self) -> None:
        forbidden: list[tuple[Path, str]] = []
        for path in SOURCE.rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module is not None:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    if name == "dci" or name.startswith("dci.") or name == "tests" or name.startswith("tests."):
                        forbidden.append((path.relative_to(PROJECT), name))
        self.assertEqual(forbidden, [])

    def test_project_metadata_and_resources_are_internal(self) -> None:
        self.assertTrue((PROJECT / "pyproject.toml").is_file())
        self.assertTrue((PROJECT / "schemas/agent-runtime/v1/event.schema.json").is_file())
        self.assertTrue((SOURCE / "dci/resources/batch-profiles.json").is_file())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Rewrite moved-test roots and root fixture consumers**

In moved tests, set:

```python
PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "src/asterion"
FIXTURES = PROJECT / "tests/fixtures"
```

Replace old repository source/package/schema paths with project-local paths. In remaining root tests that use protocol fixtures, point to `ROOT / "asterion/tests/fixtures"`. Do not add the mixed root or `src/dci` to project-local test imports.

In `asterion/packages/typescript/asterion-runtime/test/runtime.test.mjs`, remove the temporary five-parent fixture paths from Task 2 and use:

```javascript
new URL("../../../../tests/fixtures/agent_runtime/v1/", import.meta.url)
new URL("../../../../tests/fixtures/packages/v1/", import.meta.url)
new URL("../../../../tests/fixtures/assembly/v1/", import.meta.url)
```

- [ ] **Step 5: Run project-local and remaining root tests**

```bash
(cd asterion && uv run python -m unittest discover -s tests -v)
uv run python -m unittest discover -s tests -v
npm --prefix asterion/packages/typescript/asterion-runtime test
uv run python -m compileall -q asterion/src/asterion asterion/tests tests
uv run ruff check asterion/src/asterion asterion/tests tests
git diff --check
```

Expected: both discovery suites pass independently; project-local suite imports no original DCI.

- [ ] **Step 6: Commit tests and fixtures**

```bash
git add asterion/tests tests
git commit -m "test: separate Asterion project verification"
```

Journal the commit hash before Task 6.

### Task 6: Reconcile parity, build an isolated wheel, and close AF-300

**Files:**
- Modify: `tools/verify_asterion_dci_product.py`
- Modify: `assets/dci/product-parity.json`
- Modify: `assets/dci/batch-parity.json`
- Modify: remaining root parity/distribution tests
- Modify: `Makefile`
- Modify: `.gitignore` only if relocated build outputs reveal a missing existing ignore rule
- Modify: `docs/status/{WORKLIST,CURRENT-STATE,JOURNAL,RESUME-NEXT-SESSION}.md`

**Interfaces:**
- Consumes: fully converged Asterion subtree and immutable provider-backed acceptance record.
- Produces: provider-free product evidence, isolated installation proof, terminal AF-300 governance, and an extraction-ready tree.

- [ ] **Step 1: Add final forbidden-root and inventory assertions**

Extend `tests/test_asterion_project_root.py`:

```python
    def test_no_obsolete_asterion_product_roots_remain(self) -> None:
        for relative in (
            "packages/python/asterion-core",
            "packages/typescript/asterion-runtime",
            "packages/rust/controlled-executor",
            "applications/dci-agent-lite",
            "applications/controlled-code",
            "scripts/asterion",
            "schemas",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_mixed_root_retains_baseline_and_migration_evidence(self) -> None:
        self.assertTrue((ROOT / "src/dci/benchmark/pi_rpc_runner.py").is_file())
        self.assertTrue((ROOT / "assets/dci/product-parity.json").is_file())
        self.assertTrue((ROOT / "assets/dci/product-acceptance.json").is_file())
        self.assertTrue((ROOT / "docs/status/WORKLIST.md").is_file())
```

Run the test. Expected: PASS if Tasks 1–5 are complete; any failure identifies an unclassified obsolete root.

- [ ] **Step 2: Make verifier roots explicit and revalidate digests**

In `tools/verify_asterion_dci_product.py`, define and use:

```python
ASTERION_ROOT = Path("asterion")
ASTERION_SOURCE = ASTERION_ROOT / "src/asterion"
ASTERION_SCRIPTS = ASTERION_ROOT / "scripts"
```

Keep root acceptance/inventory references under `assets/dci`. Update every matrix entry point and launcher pair to the converged path. Recompute only content-derived hashes for files actually changed; do not alter private artifact hashes or acceptance case count.

- [ ] **Step 3: Run the complete provider-free parity verifier**

```bash
uv run python tools/verify_asterion_dci_product.py
```

Expected summary includes:

```text
product-rows 8/8
delegated-inventory 533/533
launcher-pairs 12/12
batch-extra-selectors 6/6
provider-backed-executed 0
```

No provider or Judge request may occur.

- [ ] **Step 4: Build and test an isolated wheel**

Use a temporary directory outside the source tree:

```bash
rm -rf /tmp/af300-asterion-wheel
mkdir -p /tmp/af300-asterion-wheel
uv build asterion --out-dir /tmp/af300-asterion-wheel/dist
uv venv /tmp/af300-asterion-wheel/venv
uv pip install --python /tmp/af300-asterion-wheel/venv/bin/python \
  /tmp/af300-asterion-wheel/dist/*.whl
/tmp/af300-asterion-wheel/venv/bin/asterion list
/tmp/af300-asterion-wheel/venv/bin/asterion describe --provider dci-agent-lite
/tmp/af300-asterion-wheel/venv/bin/asterion-dci --help
```

Inspect the wheel archive with the existing distribution test and assert it contains `asterion/` plus the four capability/application resource groups, but no `dci/`, `examples/`, root tests, or repository paths.

- [ ] **Step 5: Run full language/static/governance closure**

```bash
(cd asterion && uv run python -m unittest discover -s tests -v)
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q asterion/src/asterion asterion/tests tests tools
uv run ruff check asterion/src/asterion asterion/tests tests tools
npm --prefix asterion/packages/typescript/asterion-runtime test
cargo fmt --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --check
cargo clippy --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml
find asterion/scripts scripts/examples -name '*.sh' -print0 | xargs -0 -n1 bash -n
python3 tools/project_scope_check.py
git diff --check
```

Expected: every command passes; scope still reports active AF-300 before closure.

- [ ] **Step 6: Close durable governance**

Use `apply_patch` to:

- set AF-300 `Status: completed` with exact closure counts and commit evidence;
- set worklist lifecycle to `complete`;
- set `CURRENT-STATE.md` active package to none and record the new project root;
- append Journal facts for every nontrivial commit and final gates;
- rewrite `RESUME-NEXT-SESSION.md` with `Active work package: none`, exact Git state, deferred full datasets/release work, and the first future framework-convergence action.

Run:

```bash
python3 tools/project_scope_check.py
uv run python -m unittest \
  tests.test_project_scope_check \
  tests.test_climb_tools.ClimbToolTests.test_resume_checkpoint_tracks_the_worklist_active_package -v
git diff --check
```

Expected: scope reports `active_package: null`, `lifecycle: complete`, no errors; governance tests pass.

- [ ] **Step 7: Commit AF-300 closure**

```bash
git add asterion Makefile pyproject.toml README.md assets docs scripts src tests tools .gitignore
git commit -m "refactor: complete Asterion project-root convergence"
```

Append a final journal line with the closure hash, checkpoint it, and verify `git status --short` shows only the preserved user-owned untracked file.
