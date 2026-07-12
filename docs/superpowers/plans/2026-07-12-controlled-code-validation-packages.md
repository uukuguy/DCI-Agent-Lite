# Controlled Code Validation Packages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove a second independently useful `dci.package/v1` graph for controlled local code validation without adding execution or adapter-private package semantics.

**Architecture:** Four closed manifests model controlled-code policy, code-quality workflow, execution audit, and evaluation. The existing Python composer resolves the graph against normalized runtime capabilities plus a shared controlled-executor host capability; TypeScript validates the same checked-in manifests without implementing a resolver.

**Tech Stack:** Python 3.14, unittest, JSON, Draft 2020-12 JSON Schema, TypeScript 6, Ajv 2020, Node test runner, shell climb adapters.

## Global Constraints

- `AF-070` is the only work-package parent for every hypothesis in this plan.
- Composition remains static: do not spawn the Rust executor, invoke a runtime, schedule steps, inspect source, or add automatic repair.
- `executor.controlled` is supplied by a shared host service, never claimed as a native Pi or Claude Code capability.
- Manifests contain no commands, executable paths, arguments, environment values, workspaces, prompts, credentials, providers, mutable state, or adapter-private types.
- Python remains the only graph composer; TypeScript validates canonical manifests only.
- Preserve unrelated user changes and the independent dirty `pi/` checkout.

---

### Task 1: Controlled-code package manifests

**Files:**
- Create: `packages/manifests/controlled-code-policy.json`
- Create: `packages/manifests/code-quality-workflow.json`
- Create: `packages/manifests/execution-audit-observability.json`
- Create: `packages/manifests/code-quality-evaluation.json`
- Modify: `tests/test_package_composition.py`
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`

**Interfaces:**
- Consumes: `validate_package_manifest(manifest)` and `compose_packages(...)` from the existing package boundary.
- Produces: `ControlledCodePackageTests.manifests()` and a four-package graph ordered as policy → workflow → evaluation → observability.

- [ ] **Step 1: Write the failing manifest tests**

Add a `ControlledCodePackageTests` class that loads exactly these four files and asserts each validates, includes no forbidden runtime fields, uses the `workflow` kind, and composes to:

```python
(
    "policy.controlled-code-check",
    "workflow.code-quality",
    "evaluation.code-quality",
    "observability.execution-audit",
)
```

The successful host inputs are:

```python
host_capabilities={"executor.controlled", "filesystem.read"},
host_events={"run.started", "tool.result"},
host_artifacts={"text/x-source"},
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `uv run python -m unittest tests.test_package_composition.ControlledCodePackageTests -v`

Expected: FAIL with `FileNotFoundError` for the first controlled-code manifest.

- [ ] **Step 3: Add the four closed manifests**

Use these exact portable edges:

```json
{
  "policy.controlled-code-check": {
    "kind": "policy"
  },
  "workflow.code-quality": {
    "kind": "workflow",
    "provides_capabilities": ["workflow.code-quality"],
    "requires_capabilities": ["executor.controlled", "filesystem.read"],
    "requires_policies": ["policy.controlled-code-check"],
    "emits_events": ["workflow.code-quality.completed"],
    "consumes_events": ["run.started", "tool.result"],
    "produces_artifacts": ["application/vnd.dci.code-quality+json"],
    "consumes_artifacts": ["text/x-source"]
  },
  "evaluation.code-quality": {
    "kind": "evaluation",
    "requires_capabilities": ["workflow.code-quality"],
    "requires_policies": ["policy.controlled-code-check"],
    "consumes_events": ["workflow.code-quality.completed"],
    "produces_artifacts": ["application/vnd.dci.code-quality-verdict+json"],
    "consumes_artifacts": ["application/vnd.dci.code-quality+json"]
  },
  "observability.execution-audit": {
    "kind": "observability",
    "requires_capabilities": ["workflow.code-quality"],
    "requires_policies": ["policy.controlled-code-check"],
    "emits_events": ["audit.execution-recorded"],
    "consumes_events": ["tool.result", "workflow.code-quality.completed"],
    "produces_artifacts": ["application/vnd.dci.execution-audit+json"],
    "consumes_artifacts": ["application/vnd.dci.code-quality+json"]
  }
}
```

Every omitted edge array in the sketch above must be present as `[]`; every manifest also includes `protocol`, `package_id`, and `version: "1.0.0"`.

- [ ] **Step 4: Re-run the focused tests to verify GREEN**

Run: `uv run python -m unittest tests.test_package_composition.ControlledCodePackageTests -v`

Expected: all initial controlled-code manifest/order tests pass.

- [ ] **Step 5: Add and verify the AF-070-H-001 climb contract**

Add adapter tests requiring `train.sh` to dispatch `ControlledCodePackageTests` and `eval-local.sh` to report these dimensions:

```text
portable_manifests
workflow_kind
stable_graph
forbidden_fields
```

Run the two adapter tests before and after adding `AF-070-H-001` cases, then run `bash tools/climb/cycle.sh AF-070-H-001`; expect `confirmed 4/4`.

- [ ] **Step 6: Run the focused gate and commit**

Run package, climb-tool, scope, compile, Ruff, shell-syntax, and diff checks. Commit all H-001 implementation and climb evidence with:

```bash
git commit -m "feat: add controlled code package graph"
```

### Task 2: Cross-host parity and rejection boundaries

**Files:**
- Modify: `tests/test_package_composition.py`
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`

**Interfaces:**
- Consumes: the four manifests and `map_pi_capabilities`, `map_claude_capabilities`.
- Produces: deterministic equality across normalized runtime edges plus the same `executor.controlled` host-service edge.

- [ ] **Step 1: Write failing parity and rejection tests**

Add tests that:

```python
pi_capabilities = set(map_pi_capabilities("read")) | {"executor.controlled"}
claude_capabilities = set(map_claude_capabilities(["Read"])) | {"executor.controlled"}
```

compose identically, permutations produce equal `PackageComposition`, and the result exposes:

```python
"workflow.code-quality"
"workflow.code-quality.completed"
"application/vnd.dci.code-quality+json"
"application/vnd.dci.code-quality-verdict+json"
"application/vnd.dci.execution-audit+json"
```

Add rejection subtests for each missing host capability, `tool.result`, `text/x-source`, the policy manifest, a workflow copy with no completion event, and a workflow copy with no report artifact.

- [ ] **Step 2: Run the new tests and verify meaningful failures**

Run only the new parity/rejection test names. Expected: at least the mutated event/artifact cases fail until the test helper replaces the target manifest by `package_id` without mutating shared fixtures.

- [ ] **Step 3: Add the minimal immutable test helper**

Implement a test-only helper:

```python
def replace_manifest(self, package_id: str, **changes: object) -> list[dict[str, object]]:
    return [
        {**manifest, **changes} if manifest["package_id"] == package_id else manifest
        for manifest in self.manifests()
    ]
```

Use it to remove only the provider edge under test; no production composer change is expected.

- [ ] **Step 4: Re-run the complete package suite**

Run: `uv run python -m unittest tests.test_package_composition -v`

Expected: all manifest, DCI graph, documentation, controlled-code parity, and rejection tests pass.

- [ ] **Step 5: Add and run AF-070-H-002**

The four local dimensions are:

```text
runtime_parity
permutation_stability
portable_outputs
missing_boundary_rejection
```

Add RED adapter tests, implement train/eval dispatch, run `bash tools/climb/cycle.sh AF-070-H-002`, and expect `confirmed 4/4`.

- [ ] **Step 6: Run focused verification and commit**

Run the same focused static/scope gate as Task 1 and commit:

```bash
git commit -m "test: prove controlled code graph boundaries"
```

### Task 3: TypeScript validates every reference manifest

**Files:**
- Modify: `packages/typescript/asterion-runtime/test/runtime.test.mjs`
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`

**Interfaces:**
- Consumes: public `validatePackageManifest(value: unknown): PackageManifest` and all JSON files in `packages/manifests/`.
- Produces: one Node test proving canonical TypeScript validation for both independent graphs.

- [ ] **Step 1: Write the failing Node manifest-directory test**

Load `packages/manifests/` using `readdir` and validate every sorted `.json` file:

```javascript
const names = (await readdir(referenceManifests))
  .filter((name) => name.endsWith(".json"))
  .sort();
assert.deepEqual(names, [
  "code-quality-evaluation.json",
  "code-quality-workflow.json",
  "controlled-code-policy.json",
  "dci-evaluation.json",
  "dci-research.json",
  "execution-audit-observability.json",
  "local-corpus-policy.json",
  "protocol-observability.json",
]);
for (const name of names) {
  const manifest = JSON.parse(await readFile(new URL(name, referenceManifests), "utf8"));
  assert.deepEqual(validatePackageManifest(manifest), manifest);
}
```

- [ ] **Step 2: Run Node tests to verify RED**

Run: `npm --prefix packages/typescript/asterion-runtime test`

Expected: FAIL because the manifest-directory helper/import or exact eight-file assertion is absent while the test is introduced.

- [ ] **Step 3: Complete the Node test without adding a composer**

Import `readdir` from `node:fs/promises`, define the repository-relative manifest URL, and retain the public validator as the only implementation dependency.

- [ ] **Step 4: Run a clean TypeScript gate**

Run:

```bash
npm --prefix packages/typescript/asterion-runtime ci
npm --prefix packages/typescript/asterion-runtime test
```

Expected: build/type contract and all Node tests pass; `src/` contains no graph-composition implementation.

- [ ] **Step 5: Add and run AF-070-H-003**

The four dimensions are `all_reference_manifests`, `canonical_schema`, `public_validator`, and `no_typescript_composer`. Add RED adapter tests, implement dispatch, run the cycle, then run the focused gate.

- [ ] **Step 6: Commit TypeScript parity**

```bash
git commit -m "test: validate all package graphs in TypeScript"
```

### Task 4: Architecture documentation and AF-070 closure

**Files:**
- Create: `docs/architecture/controlled-code-validation-packages.md`
- Modify: `tests/test_package_composition.py`
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- Consumes: both verified package graphs and all repository verification targets.
- Produces: a recoverable AF-070 closure proving that D-022 still favors static composition.

- [ ] **Step 1: Write failing documentation tests**

Require the guide to contain these exact concepts and examples:

```text
Second independent graph
Static composition, not code execution
executor.controlled
shared host service
does not make Pi or Claude Code a sandbox
does not trigger a workflow engine
```

Also require a manifest excerpt for `workflow.code-quality` and a Python `compose_packages(` example that unions the runtime mapping with `{"executor.controlled"}`.

- [ ] **Step 2: Run documentation tests to verify RED**

Run the new documentation test class. Expected: `FileNotFoundError` for `docs/architecture/controlled-code-validation-packages.md`.

- [ ] **Step 3: Write the operator/developer guide**

Document package roles, host-service capability injection, deterministic graph output, rejection examples, authoring boundaries, verification commands, and the explicit non-execution/non-sandbox conclusion. Do not document a command runner because this package adds none.

- [ ] **Step 4: Add and run AF-070-H-004 closure acceptance**

Add RED adapter tests, then implement a train case running full Python discovery, compilation, Ruff, clean TypeScript install/tests, Rust tests/fmt/Clippy, shell syntax, scope audit, and diff check. Local eval dimensions are `second_graph_docs`, `static_boundary`, `host_service_boundary`, and `framework_closure`. Run `bash tools/climb/cycle.sh AF-070-H-004`; expect `confirmed 4/4`.

- [ ] **Step 5: Run an independent fresh closure gate**

Run:

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q src tests tools
uv run ruff check src tests tools
npm --prefix packages/typescript/asterion-runtime ci
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
cargo fmt --manifest-path packages/rust/controlled-executor/Cargo.toml --check
cargo clippy --manifest-path packages/rust/controlled-executor/Cargo.toml --all-targets -- -D warnings
bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
python3 tools/project_scope_check.py --climb-hypothesis AF-070-H-004
git diff --check
```

Expected: zero failures and a passing AF-070 scope audit.

- [ ] **Step 6: Close state only after evidence**

Mark AF-070 complete only after the fresh gate. Update D-022 with evidence that the second graph is expressible and therefore does not trigger an execution engine. Refresh structural state, journal every commit/result, and leave the next active package governed before any new implementation.

- [ ] **Step 7: Commit closure**

```bash
git commit -m "docs: close controlled code package acceptance"
```
