# Composable Framework Packages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven development task-by-task. This repository executes inline because the user authorized continuous autonomous climb and did not request agent delegation.

**Goal:** Deliver portable package manifests, deterministic policy-aware composition, and a DCI reference graph shared by Python and TypeScript hosts.

**Architecture:** JSON Schema and shared fixtures define `dci.package/v1`. A pure Python resolver validates package dependency/policy/event/artifact edges and emits deterministic order; TypeScript reuses the canonical fixtures without implementing a second resolver.

**Tech Stack:** Python dataclasses/JSON, Draft 2020-12 JSON Schema, TypeScript/Ajv 2020, unittest, Node test runner.

## Global Constraints

- Package manifests never contain credentials, prompts, executable paths, runtime commands, or adapter-private types.
- Composition is static validation, not workflow execution.
- Every implementation step starts with a failing focused test and ends with an atomic verified commit.
- `AF-060` is the only work-package parent for every climb hypothesis in this plan.

---

### Task 1: Package manifest contract

**Files:**
- Create: `schemas/packages/v1/package-manifest.schema.json`
- Create: `tests/fixtures/packages/v1/valid-*.json`
- Create: `tests/fixtures/packages/v1/invalid-*.json`
- Create: `tests/test_package_composition.py`

**Interfaces:** A manifest uses `protocol: "dci.package/v1"`, `package_id`, semantic `version`, `kind`, and sorted string arrays for capability/policy/event/artifact edges.

- [ ] Write tests loading every fixture and rejecting unknown fields, duplicate edge values, invalid IDs, and forbidden data-bearing fields.
- [ ] Run `uv run python -m unittest tests.test_package_composition -v`; expect missing-schema failure.
- [ ] Add the closed Draft 2020-12 schema and minimal fixtures.
- [ ] Re-run the focused test; expect all fixture cases to pass.
- [ ] Commit schema, fixtures, and focused tests.

### Task 2: Deterministic Python composer

**Files:**
- Create: `src/dci/framework/packages.py`
- Modify: `tests/test_package_composition.py`

**Interfaces:** `compose_packages(manifests, host_capabilities, host_policies) -> PackageComposition`; immutable output exposes `package_ids`, `provided_capabilities`, and normalized event/artifact edges.

- [ ] Write failing tests for duplicate IDs, missing capability/policy, dependency cycle, incompatible edges, and stable order under permuted input.
- [ ] Run the focused suite; expect import/API failure.
- [ ] Implement immutable manifest values, validation errors with safe static messages, and stable topological composition.
- [ ] Re-run focused tests and Ruff/compile for the module.
- [ ] Commit the resolver and tests.

### Task 3: DCI reference package graph

**Files:**
- Create: `packages/manifests/dci-research.json`
- Create: `packages/manifests/local-corpus-policy.json`
- Create: `packages/manifests/protocol-observability.json`
- Create: `packages/manifests/dci-evaluation.json`
- Modify: `tests/test_package_composition.py`

**Interfaces:** The graph requires only portable runtime capabilities already declared by Pi/Claude Code manifests and produces normalized research/evaluation artifacts.

- [ ] Write failing tests composing the same graph for Pi and Claude Code capability sets.
- [ ] Run the focused suite; expect missing manifests.
- [ ] Add minimal manifests without provider/runtime-private fields.
- [ ] Re-run focused tests; expect both graphs to compose identically.
- [ ] Commit the reference graph.

### Task 4: TypeScript shared-fixture parity

**Files:**
- Modify: `packages/typescript/agent-runtime/scripts/copy-schemas.mjs`
- Modify: `packages/typescript/agent-runtime/test/runtime.test.mjs`
- Modify: `packages/typescript/agent-runtime/src/index.ts`

**Interfaces:** `validatePackageManifest(value: unknown): PackageManifest` validates the same checked-in schema/fixtures; it does not compose graphs.

- [ ] Add failing Node tests for valid and invalid shared package fixtures.
- [ ] Run `npm --prefix packages/typescript/agent-runtime test`; expect missing validator failure.
- [ ] Add schema copying, public portable types, and Ajv validation.
- [ ] Re-run clean install, build, and Node tests.
- [ ] Commit TypeScript parity.

### Task 5: Documentation and closure

**Files:**
- Create: `docs/architecture/composable-packages.md`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/DECISIONS.md`

- [ ] Add documentation tests asserting the static-composition and extension boundaries.
- [ ] Write the operator/developer guide with manifest and resolver examples.
- [ ] Run full Python discovery, TypeScript clean build/tests, Rust gates, scope audit, and diff checks.
- [ ] Mark AF-060 complete only when every acceptance item has fresh evidence.
- [ ] Commit closure state and journal the result.
