# Asterion Complete Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a truthful complete Asterion DCI reference, framework/capability integration guide, and standalone extraction design, with corrected context-management claims and durable navigation.

**Architecture:** Three focused documents own product operation, framework extension, and future repository extraction respectively. One documentation contract test validates required sections, evidence labels, canonical paths, cross-links, and the absence of the known false Pi context-level claim; README and `docs/README.md` provide the stable entry points.

**Tech Stack:** Markdown, Python `unittest`, `pathlib`, regular expressions, Asterion CLI metadata and checked-in JSON manifests.

## Global Constraints

- Use the exact evidence terms **Implemented**, **Verified**, **External-limited**, and **Not rerun**.
- Do not claim the current Pi CLI exposes a typed runtime context-management level.
- Do not claim the 533 model-free selectors reproduce full-dataset benchmark scores.
- Treat `packages/python/asterion-core/src/asterion/capabilities/` and `.../applications/` as canonical wheel-owned assets.
- Treat top-level `applications/*/python` as repository reference/compatibility hosts and top-level `capabilities/` as non-authoritative.
- Do not move directories, split repositories, alter packaging, change protocols, run full benchmark datasets, or modify external `pi/`.
- Preserve the user-owned untracked `.superpowers/sdd/task-0-review.md`.

---

### Task 1: Complete Asterion DCI product reference

**Files:**
- Create: `tests/test_asterion_documentation.py`
- Create: `docs/guides/asterion-dci-complete-reference.md`

**Interfaces:**
- Consumes: `asterion-dci --help`, `asterion describe`, `batch-profiles.json`, product parity/acceptance assets, and authoritative `asterion.dci` modules.
- Produces: one operator/developer reference covering the entire DCI product surface and evidence status.

- [ ] **Step 1: Write the failing product-reference contract test**

Create `tests/test_asterion_documentation.py` with `ROOT`, a `read(relative)` helper, and `AsterionDocumentationTests.test_complete_dci_reference_covers_product_and_evidence`. Require these headings and terms:

```python
required = (
    "# Asterion DCI 完整产品参考",
    "## 证据状态说明",
    "## 配置与依赖",
    "## 单次研究、终端与系统提示词",
    "## 原生产物、隐私与恢复",
    "## Context Management：两个不同层次",
    "## Judge、评测与精确缓存",
    "## Benchmark DCI-Agent-Lite",
    "## 数据集、Profile 与 Launcher",
    "## 指标、分析、图表与导出",
    "## 安装应用与能力包入口",
    "## 完整验证矩阵",
    "Implemented",
    "Verified",
    "External-limited",
    "Not rerun",
    "provider-backed operations",
    "533/533",
    "12/12",
)
```

Require all seven `asterion-dci` subcommands, both `make asterion-verify-*` provider-free/provider-backed categories, the five saved-conversation controls, `runtime_context_control`, all bundled benchmark profile IDs, all twelve `scripts/asterion/` launcher paths, and links to canonical `asterion/dci` modules. Reject language claiming that AF-290 reran full datasets or reproduced 62.9%.

- [ ] **Step 2: Run the product-reference test and verify RED**

Run:

```bash
uv run python -m unittest tests.test_asterion_documentation.AsterionDocumentationTests.test_complete_dci_reference_covers_product_and_evidence -v
```

Expected: FAIL because `docs/guides/asterion-dci-complete-reference.md` does not exist.

- [ ] **Step 3: Write the complete product reference from source evidence**

Create the required document with:

- a command table for `run`, `terminal`, `system-prompt`, `resume`, `evaluate`, `benchmark`, and `export`;
- shared `.env`, Pi/Node/corpus/dataset/Judge requirements and precedence;
- native artifact tree and resume invariants;
- a two-column Context Management section distinguishing Pi model-input behavior from saved-conversation processing;
- benchmark family/profile/launcher tables and output/metric/export descriptions;
- an evidence matrix using the four required labels and explicit limits;
- copyable source-checkout Make and installed CLI commands.

Every implementation claim links to a canonical source file or manifest. State that the current Pi CLI limitation is recorded as `unsupported`; explicit extra-argument forwarding does not prove runtime support. State that published scores are historical source-product results and were not rerun during Asterion migration.

- [ ] **Step 4: Run the product-reference test and verify GREEN**

Run:

```bash
uv run python -m unittest tests.test_asterion_documentation.AsterionDocumentationTests.test_complete_dci_reference_covers_product_and_evidence -v
```

Expected: PASS.

- [ ] **Step 5: Commit the product reference**

```bash
git add tests/test_asterion_documentation.py docs/guides/asterion-dci-complete-reference.md
git commit -m "docs: add complete Asterion DCI reference"
```

### Task 2: Framework and capability integration guide

**Files:**
- Modify: `tests/test_asterion_documentation.py`
- Create: `docs/architecture/asterion-framework-capability-integration.md`

**Interfaces:**
- Consumes: authoritative framework modules, DCI and controlled-code manifests, assemblies, providers, runner, and package metadata.
- Produces: one architectural map plus an end-to-end neutral capability/application integration recipe.

- [ ] **Step 1: Add the failing framework-guide contract test**

Add `test_framework_guide_explains_layers_and_complete_integration`. Require headings for repository map, dependency direction, runtime/adapters, package/capability, application/assembly/provider, services, CLI boundaries, worked integration, tests, and canonical-versus-top-level directories. Require exact canonical paths and the neutral identities `example.policy`, `example.research`, `example.observability`, and `example.research-app@1.0.0`.

Require the guide to name these integration steps in order: manifest → implementation binding → assembly → installed provider → Python entry point → `asterion list` → `asterion run` → isolated-wheel test. Require it to state `asterion` never imports `src/dci`, selected-only provider discovery loads no adjacent provider, and top-level `applications/`/`capabilities/` are not separately installable products.

- [ ] **Step 2: Run the framework-guide test and verify RED**

Run:

```bash
uv run python -m unittest tests.test_asterion_documentation.AsterionDocumentationTests.test_framework_guide_explains_layers_and_complete_integration -v
```

Expected: FAIL because the framework guide does not exist.

- [ ] **Step 3: Write the architecture and worked integration guide**

Create the document with a compact dependency diagram:

```text
CLI → selected provider → application assembly → resolved package plan
    → exact implementation bindings → runtime/host services → artifacts
```

Explain every canonical directory and generic/domain dependency. Include representative JSON for the four neutral manifests and one assembly, Python pseudocode using the real immutable provider/binding concepts, the `pyproject.toml` entry-point stanza, list/run commands, safe failure boundaries, packaging resource rules, and a test checklist. Mark illustrative code as an integration template rather than checked-in production identity.

- [ ] **Step 4: Run both documentation tests and verify GREEN**

Run:

```bash
uv run python -m unittest tests.test_asterion_documentation -v
```

Expected: product and framework tests PASS.

- [ ] **Step 5: Commit the framework guide**

```bash
git add tests/test_asterion_documentation.py docs/architecture/asterion-framework-capability-integration.md
git commit -m "docs: explain Asterion capability integration"
```

### Task 3: Standalone Asterion extraction design

**Files:**
- Modify: `tests/test_asterion_documentation.py`
- Create: `docs/architecture/asterion-standalone-extraction.md`

**Interfaces:**
- Consumes: current wheel metadata, cross-language packages, schemas, tests, external Pi/corpus/dataset boundaries, and Tasks 1–2 terminology.
- Produces: a phased, reversible standalone-repository proposal without filesystem mutation.

- [ ] **Step 1: Add the failing extraction-design contract test**

Add `test_standalone_design_inventory_tree_phases_and_gates`. Require headings for current self-contained inventory, external dependencies, proposed target tree, migration table, seven phases, DCI bundling decision gate, release gates, rollback, risks, and non-goals. Require exact inclusion of Python Asterion, TypeScript runtime host, Rust controlled executor, schemas, fixtures, tests, and docs; require exact exclusion of external Pi, corpora, benchmark datasets, credentials, outputs, `.worktrees`, and source-only `src/dci` from the standalone product.

Require the phrases `Phase 1` through `Phase 7`, `keep DCI bundled initially`, `separately versioned plugin decision gate`, and commands for isolated wheel install, provider listing, provider-free acceptance, bounded Pi examples, TypeScript tests, and Rust tests.

- [ ] **Step 2: Run the extraction-design test and verify RED**

Run:

```bash
uv run python -m unittest tests.test_asterion_documentation.AsterionDocumentationTests.test_standalone_design_inventory_tree_phases_and_gates -v
```

Expected: FAIL because the extraction design does not exist.

- [ ] **Step 3: Write the standalone extraction design**

Create a proposed tree rooted at one independent repository with `packages/python/asterion-core`, `packages/typescript/asterion-runtime`, `packages/rust/controlled-executor`, `schemas`, `tests`, `docs`, and optional bundled examples. Include a current-to-target migration table, package/resource assumptions to remove, phase entry/exit criteria, rollback points before each destructive step, release/versioning choices, and the DCI plugin decision gate. Explicitly classify acceptance matrices and source-baseline parity assets as migration-time evidence rather than runtime wheel dependencies.

- [ ] **Step 4: Run all documentation tests and verify GREEN**

Run:

```bash
uv run python -m unittest tests.test_asterion_documentation -v
```

Expected: all three tests PASS.

- [ ] **Step 5: Commit the extraction design**

```bash
git add tests/test_asterion_documentation.py docs/architecture/asterion-standalone-extraction.md
git commit -m "docs: design standalone Asterion extraction"
```

### Task 4: Reconcile existing guidance and close AF-290

**Files:**
- Modify: `tests/test_asterion_documentation.py`
- Create: `docs/README.md`
- Modify: `README.md`
- Modify: `assets/docs/running.md`
- Modify: `docs/guides/asterion-capability-usage.md`
- Modify: `docs/verification/asterion-dci-validation-guide.md`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- Consumes: the three completed documents.
- Produces: one discoverable documentation hub, corrected legacy guidance, valid local links, and terminal AF-290 governance.

- [ ] **Step 1: Add the failing navigation and contradiction test**

Add `test_documentation_hub_links_set_and_reconciles_context_claims`. Require `docs/README.md` and README to link all three documents. Require the beginner and verification guides to link the complete DCI reference. Require `assets/docs/running.md` to state that current typed runtime context level is unsupported and reject the sentence `The configured Pi checkout supports runtime context-management profiles`.

Implement a local-link checker for the five touched navigation documents: extract Markdown link targets, ignore `http`, `https`, `mailto`, and pure anchors, strip fragments, resolve relative paths from each document, and assert every target exists.

- [ ] **Step 2: Run the navigation test and verify RED**

Run:

```bash
uv run python -m unittest tests.test_asterion_documentation.AsterionDocumentationTests.test_documentation_hub_links_set_and_reconciles_context_claims -v
```

Expected: FAIL because the hub and corrected links do not exist.

- [ ] **Step 3: Add navigation and correct stale guidance**

Create `docs/README.md` with operator, integrator, extraction, verification, and historical-design sections. Add concise links from root README and both existing guides. Rewrite `assets/docs/running.md` runtime-level section to describe the current unsupported typed flag, effective thinking control, saved-conversation processing, and the rule that explicit `--extra-arg` is operator-controlled compatibility only.

- [ ] **Step 4: Run evidence and documentation closure gates**

Run:

```bash
uv run python -m unittest tests.test_asterion_documentation tests.test_distribution_boundaries -v
uv run python -m compileall -q tests/test_asterion_documentation.py
uv run ruff check tests/test_asterion_documentation.py tests/test_distribution_boundaries.py
uv run asterion-dci --help
uv run asterion describe --provider dci-agent-lite
python3 tools/project_scope_check.py
git diff --check
```

Expected: tests, compile, Ruff, help/describe, active AF-290 scope, and diff checks pass without provider requests.

- [ ] **Step 5: Close AF-290 and verify terminal governance**

Set AF-290 to `completed`, project lifecycle to `complete`, and active package to none. Record exact evidence and the key conclusion that runtime context levels remain external-limited and full benchmark scores remain not rerun. Then run:

```bash
python3 tools/project_scope_check.py
uv run python -m unittest tests.test_project_scope_check tests.test_climb_tools.ClimbToolTests.test_resume_checkpoint_tracks_the_worklist_active_package -v
git diff --check
```

Expected: scope reports `active_package: null`, `lifecycle: complete`, no errors; tests pass.

- [ ] **Step 6: Commit closure**

```bash
git add README.md assets/docs/running.md docs tests/test_asterion_documentation.py
git commit -m "docs: complete Asterion product and framework documentation"
```
