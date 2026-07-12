# Local Package Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Discover, validate, and exact-select portable package manifests from explicit local directories without installation, network access, or execution.

**Architecture:** A Python-only immutable catalog canonicalizes explicit roots, validates direct JSON children through `dci.package/v1`, rejects ambiguous identities, and returns fresh manifests for the existing composer. TypeScript retains canonical manifest validation and does not duplicate filesystem discovery.

**Tech Stack:** Python 3.14, pathlib, dataclasses, JSON, unittest, existing package protocol/composer, shell climb adapters.

## Global Constraints

- `AF-080` is the sole parent for every hypothesis in this plan.
- Roots are trusted operator configuration and never model/agent input.
- Scan direct `.json` children only; reject symlink roots/files and do not recurse.
- Support exact `package_id@version` only; no ranges, solving, upgrades, or lockfiles.
- Do not load modules, entry points, commands, prompts, credentials, environments, or executable hooks.
- Do not add a network registry, install/publish flow, watcher, database, execution, or TypeScript catalog.
- Preserve unrelated user changes and the independent dirty `pi/` checkout.

---

### Task 1: Deterministic validated discovery

**Files:**
- Create: `src/dci/framework/package_catalog.py`
- Create: `tests/test_package_catalog.py`
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`

**Interfaces:**
- Produces: `PackageCatalogError`, ordered frozen `PackageRef`, frozen `CatalogEntry`, frozen `PackageCatalog`, and `discover_packages(roots)`.
- Consumes: `validate_package_manifest(manifest)`.

- [ ] **Step 1: Write failing discovery tests**

Create temporary roots with valid copied manifests. Assert root permutation and file creation order produce equal refs and canonical sources; non-JSON files and nested JSON are ignored; every returned manifest validates.

- [ ] **Step 2: Run RED**

Run: `uv run python -m unittest tests.test_package_catalog.PackageDiscoveryTests -v`

Expected: import failure because `dci.framework.package_catalog` does not exist.

- [ ] **Step 3: Implement the minimal public types and discovery**

Use:

```python
@dataclass(frozen=True, order=True)
class PackageRef:
    package_id: str
    version: str

@dataclass(frozen=True)
class CatalogEntry:
    ref: PackageRef
    source: Path
    manifest: Mapping[str, object]

@dataclass(frozen=True)
class PackageCatalog:
    entries: tuple[CatalogEntry, ...]
```

Canonicalize roots with `resolve(strict=True)`, sort canonical paths, scan sorted direct `*.json` children, decode JSON, require an object, validate, and sort entries by `(ref, str(source))`.

- [ ] **Step 4: Run GREEN**

Run the discovery class; expect all tests pass.

- [ ] **Step 5: Add AF-080-H-001 adapter RED/GREEN and cycle**

Dimensions: `root_permutation`, `file_order`, `canonical_validation`, `non_recursive_filtering`. Add train/eval cases and run `bash tools/climb/cycle.sh AF-080-H-001`; expect `confirmed 4/4`.

- [ ] **Step 6: Run focused static/scope gates and commit**

Commit with `feat: discover local package manifests`.

### Task 2: Fail-closed filesystem and identity boundaries

**Files:**
- Modify: `src/dci/framework/package_catalog.py`
- Modify: `tests/test_package_catalog.py`
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`

**Interfaces:**
- Extends: `discover_packages` error behavior only; successful API remains unchanged.
- Produces: safe `PackageCatalogError` messages chained from local parser/protocol errors.

- [ ] **Step 1: Write failing boundary tests**

Cover missing root, file root, symlink root, duplicate canonical root, symlink JSON, malformed JSON containing sentinel text, non-object JSON, invalid manifest, unreadable JSON where supported, and duplicate exact identity across roots. Assert public error text excludes sentinel contents.

- [ ] **Step 2: Run RED**

Expected: raw filesystem/JSON/protocol exceptions or accepted ambiguous inputs.

- [ ] **Step 3: Add one safe boundary wrapper**

Implement helpers that raise messages such as `catalog root is invalid`, `package document is invalid: <path>`, and `duplicate package identity: <id>@<version>` without including decoded content. Reject symlinks before canonicalization loses that evidence.

- [ ] **Step 4: Run the complete catalog suite**

Expected: every success and failure test passes without weakening package validation.

- [ ] **Step 5: Add AF-080-H-002 and run cycle**

Dimensions: `root_boundary`, `document_boundary`, `symlink_boundary`, `duplicate_identity`. Add adapter RED/GREEN, run the cycle, focused gates, and commit `feat: harden local package discovery`.

### Task 3: Exact selection and composer integration

**Files:**
- Modify: `src/dci/framework/package_catalog.py`
- Modify: `tests/test_package_catalog.py`
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`

**Interfaces:**
- Adds: `PackageCatalog.select(refs: Iterable[PackageRef]) -> tuple[Mapping[str, object], ...]`.
- Consumes: existing DCI and controlled-code manifests plus `compose_packages`.

- [ ] **Step 1: Write failing selection tests**

Discover `packages/manifests/`; assert all eight exact refs are present. Select each four-manifest graph in permuted request order, mutate one returned manifest, select again, and prove fresh data is returned. Compose both selections using their existing host edges. Reject duplicate requested refs and unknown exact versions.

- [ ] **Step 2: Run RED**

Expected: `PackageCatalog` has no `select` method.

- [ ] **Step 3: Implement exact immutable selection**

Index entries by `PackageRef`, reject duplicate requests, reject missing refs, sort refs, and return deep fresh JSON-compatible mappings (for example through `copy.deepcopy`). Never select a highest/latest version implicitly.

- [ ] **Step 4: Run GREEN and full catalog regression**

Expected: both existing graphs compose unchanged and selection mutation cannot alter catalog state.

- [ ] **Step 5: Add AF-080-H-003 and run cycle**

Dimensions: `exact_selection`, `fresh_manifests`, `graph_integration`, `selection_rejection`. Run adapter RED/GREEN, cycle, focused gates, and commit `feat: select exact catalog packages`.

### Task 4: Documentation and AF-080 closure

**Files:**
- Create: `docs/architecture/local-package-catalog.md`
- Modify: `tests/test_package_catalog.py`
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- Produces: tested operator/developer guidance and a recoverable AF-080 closure.

- [ ] **Step 1: Write failing documentation tests**

Require: `Explicit local roots`, `Direct JSON children only`, `Exact package_id@version selection`, `No network registry or installation`, `Symlinks are rejected`, `does not execute packages`, plus discovery/selection/composition examples.

- [ ] **Step 2: Run RED and write the guide**

Expected RED: missing guide. Then document APIs, root trust, examples, every error class, non-goals, and verification commands without implying plugin loading or execution.

- [ ] **Step 3: Add AF-080-H-004 full closure adapter**

Dimensions: `catalog_docs`, `filesystem_boundary`, `selection_boundary`, `framework_closure`. Train runs full Python discovery/compile/Ruff, clean TypeScript tests, Rust tests/fmt/Clippy, shell syntax, AF-080 scope, and diff check.

- [ ] **Step 4: Run cycle and an independent fresh closure gate**

Run `bash tools/climb/cycle.sh AF-080-H-004`, then independently repeat full Python discovery/compile/Ruff, clean TypeScript tests, Rust tests/fmt/Clippy, shell syntax, `python3 tools/project_scope_check.py --climb-hypothesis AF-080-H-004`, and `git diff --check`. Require zero failures before changing package status.

- [ ] **Step 5: Close state and commit**

Record catalog structure and safe boundaries, mark AF-080 complete only with fresh evidence, keep exactly one next governed package active, and commit `docs: close local package catalog acceptance`.
