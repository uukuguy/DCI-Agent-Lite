# Static Application Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve a closed portable assembly manifest, exact local packages, and one runtime manifest into an immutable composition plan without execution.

**Architecture:** Draft 2020-12 schema and shared fixtures define `dci.assembly/v1`. Python validates and resolves through the existing catalog/composer; TypeScript validates and exports types but does not resolve.

**Tech Stack:** Python 3.14, JSON Schema, unittest, TypeScript/Ajv 2020, Node test runner, climb shell adapters.

## Global Constraints

- `AF-090` parents every cycle.
- Runtime capabilities come from the supplied runtime manifest; host services remain separate assembly edges.
- Package refs and edge arrays are sorted/unique exact values.
- No execution, prompts, credentials, provider/model choice, registry, installation, version ranges, transport, or mutable state.

---

### Task 1: Assembly schema and Python validation

**Files:** create `schemas/assembly/v1/assembly.schema.json`, positive/negative fixtures under `tests/fixtures/assembly/v1/`, `src/dci/framework/assembly.py`, `tests/test_application_assembly.py`; modify climb adapters/tests.

- [ ] Write failing tests for a valid fixture, closed fields, identifiers, exact refs, all required arrays, and sorted/unique refs/edges.
- [ ] Run `uv run python -m unittest tests.test_application_assembly.AssemblyManifestTests -v`; expect missing module/schema failure.
- [ ] Implement `AssemblyError`, `ASSEMBLY_PROTOCOL_VERSION`, schema-equivalent Python validation, and canonical ordering checks.
- [ ] Re-run GREEN; add AF-090-H-001 dimensions `valid_manifest`, `closed_contract`, `canonical_refs`, `canonical_edges`; cycle, focused gates, commit `feat: define static application assemblies`.

### Task 2: Pure assembly resolver

**Files:** modify `src/dci/framework/assembly.py`, `tests/test_application_assembly.py`, climb adapters/tests.

- [ ] Write RED tests for `AssemblyPlan` and `resolve_assembly`: runtime validation/match, exact catalog selection, runtime+host capability union, deterministic result, and no input mutation.
- [ ] Implement the frozen plan and pure resolver by calling `PackageCatalog.select` and `compose_packages`; wrap catalog/composition/protocol failures with safe `AssemblyError` messages.
- [ ] Prove runtime mismatch, unknown package, invalid runtime, and missing composition edges fail safely without manifest content.
- [ ] Add AF-090-H-002 dimensions `runtime_binding`, `catalog_binding`, `capability_separation`, `safe_resolution`; cycle, gates, commit `feat: resolve static application assemblies`.

### Task 3: Reference assemblies and parity

**Files:** create DCI and controlled-code manifests under `assemblies/`; modify assembly tests and climb adapters/tests.

- [ ] Write RED tests loading checked-in assemblies and stable Pi/Claude/runtime fixtures.
- [ ] Add canonical DCI and controlled-code assemblies; resolve DCI for equivalent Pi/Claude capabilities and controlled-code with separate `executor.controlled` host service.
- [ ] Assert stable package orders, portable outputs, host-service separation, and no execution fields.
- [ ] Add AF-090-H-003 dimensions `dci_plan`, `runtime_parity`, `controlled_plan`, `service_separation`; cycle, gates, commit `feat: add reference application assemblies`.

### Task 4: TypeScript parity, documentation, and closure

**Files:** modify TypeScript types/validator/schema copy/tests; create `docs/architecture/static-application-assembly.md`; modify Python docs tests, status, climb adapters/tests.

- [ ] Add Node RED tests for valid/invalid assembly fixtures and both checked-in assemblies; export `AssemblyManifest` and `validateAssemblyManifest` without resolver code.
- [ ] Add documentation RED tests for static planning, runtime/host-service separation, exact refs, safe errors, and non-execution.
- [ ] Add AF-090-H-004 full closure with dimensions `typescript_parity`, `assembly_docs`, `non_execution`, `framework_closure`.
- [ ] Run cycle then independently run full Python discovery/compile/Ruff, clean TypeScript tests, Rust tests/fmt/Clippy, shell syntax, `python3 tools/project_scope_check.py --climb-hypothesis AF-090-H-004`, and `git diff --check`.
- [ ] Close AF-090 only with fresh evidence and commit `docs: close static assembly acceptance` while keeping one next governed package active.
