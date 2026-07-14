# AF-250 Product Acceptance Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the complete original DCI product and the independent Pi-default Asterion DCI product through one checked-in executable matrix with no unsupported or unverified behavior.

**Architecture:** A strict product-level matrix composes the already executable 533-row AF-240 inventory with focused cross-product rows for configuration, run/terminal, native artifacts/resume, Judge/cache, examples, exports/batches, installed wheel, and installed application. A safe verifier executes only allowlisted argv arrays and never starts provider-backed cases; bounded real runs are recorded separately as body-free structural evidence. Stable differential tests normalize volatile paths, IDs, and timestamps while comparing lifecycle, configuration, artifact, cache, and verdict semantics.

**Tech Stack:** Python 3.12+, `unittest`, JSON/JSONL, Bash, `uv`, Pi JSONL RPC, Asterion wheel resources, existing TypeScript and Rust verification gates.

## Global Constraints

- Active work package is AF-250; run `python3 tools/project_scope_check.py` before implementation and closure.
- `src/dci` remains independently runnable and must never be imported or launched by Asterion production code.
- Root `.env` is shared; credentials remain environment-only and must never be printed or persisted.
- `pi/` is an external checkout and must not be edited.
- Full BCPlus/QA/BRIGHT datasets are never started automatically.
- Provider-backed work is bounded to the approved source examples, Asterion examples/application, and one-row Pi-plus-Judge evidence.
- A failed provider check remains failed evidence until a bounded recovery succeeds; fixtures cannot silently replace it.
- Every matrix row must name executable evidence; `unsupported`, `todo`, `tbd`, `placeholder`, empty owner, and unresolvable selectors are closure failures.

---

### Task 1: Register AF-250 governance and define the executable product matrix

**Files:**
- Create: `assets/dci/product-parity.json`
- Create: `tools/verify_asterion_dci_product.py`
- Create: `tests/test_asterion_dci_product_parity.py`
- Modify: `docs/status/climb/hypotheses.yaml`
- Modify: `docs/status/climb/session-state.json`
- Regenerate: `docs/status/climb/research-tree.md`
- Regenerate: `docs/status/climb/research-tree.json`
- Modify: `docs/status/JOURNAL.md`

**Interfaces:**
- Produces: `load_product_matrix(root: Path) -> dict[str, object]`.
- Produces: `validate_product_matrix(root: Path, document: object) -> tuple[dict[str, object], ...]`.
- Produces: `run_local_evidence(root: Path, rows: tuple[dict[str, object], ...]) -> dict[str, object]`.
- Produces: CLI `python3 tools/verify_asterion_dci_product.py [--validate-only]`.
- Matrix schema: `asterion.dci.product-parity/v1` with exactly eight required product rows and one exact AF-240 inventory reference.

- [ ] **Step 1: Run the mandatory package preflight**

Run:

```bash
python3 tools/project_scope_check.py
```

Expected: JSON reports `"active_package": "AF-250"` and `"ok": true`.

- [ ] **Step 2: Write RED matrix-schema and evidence-resolution tests**

Add tests requiring these exact row IDs:

```python
REQUIRED_PRODUCT_ROWS = {
    "configuration-and-pi-argv",
    "interactive-run-and-terminal",
    "native-artifacts-and-resume",
    "judge-and-exact-cache",
    "batch-ir-analysis-and-exports",
    "source-and-asterion-examples",
    "installed-wheel-boundary",
    "installed-pi-application",
}

def test_product_matrix_has_no_unsupported_or_unexecutable_row(self) -> None:
    document = load_product_matrix(ROOT)
    rows = validate_product_matrix(ROOT, document)
    self.assertEqual({row["id"] for row in rows}, REQUIRED_PRODUCT_ROWS)
    self.assertTrue(all(row["unsupported"] is False for row in rows))
    self.assertTrue(all(row["local_evidence"] for row in rows))
```

Also require the matrix to record `assets/dci/batch-parity.json`, its SHA-256, and `row_count: 533`; reject unknown fields, duplicate IDs, unsafe argv, missing paths, empty selectors, placeholder text, and provider-backed commands in `local_evidence`.

- [ ] **Step 3: Verify RED**

Run:

```bash
uv run python -m unittest tests.test_asterion_dci_product_parity -v
```

Expected: FAIL because the matrix and verifier do not exist.

- [ ] **Step 4: Implement the strict loader and allowlisted local executor**

The verifier must parse argv arrays without `shell=True` and accept only these prefixes:

```python
ALLOWED_PREFIXES = (
    ("uv", "run", "python", "-m", "unittest"),
    ("python3", "tools/verify_asterion_dci_product.py", "--validate-only"),
    ("bash", "-n"),
)
```

It must reject environment assignments, absolute executables, shell metacharacters, response bodies, and any evidence tier other than `local`, `model-free`, or `provider-backed`. The default CLI executes only `local` and `model-free`; it prints row IDs and exit status, never command output bodies or environment values.

- [ ] **Step 5: Add all eight product rows**

Each row must list concrete source and Asterion entry points, one or more focused `unittest` selectors, explicit stable semantics, and a `provider_evidence` case ID when applicable. The batch row delegates complete fine-grained coverage to the digest-bound 533-row inventory rather than duplicating it.

- [ ] **Step 6: Register four AF-250 Climb hypotheses**

Register:

```text
AF-250-H-001 source/Asterion runnable-surface completeness
AF-250-H-002 stable cross-product semantic comparison
AF-250-H-003 installed wheel/application independence
AF-250-H-004 bounded real evidence and final matrix closure
```

Use session `2026-07-15-af-250-product-acceptance-matrix`; all hypotheses start `pending`, are parented to AF-250, use distinct verification commands, and may become confirmed only through `tools/climb/cycle.sh`.

- [ ] **Step 7: Verify and commit**

Run:

```bash
uv run python -m unittest tests.test_asterion_dci_product_parity tests.test_climb_tools -v
uv run ruff check tools/verify_asterion_dci_product.py tests/test_asterion_dci_product_parity.py
python3 tools/project_scope_check.py
git diff --check
```

Commit:

```bash
git add assets/dci/product-parity.json tools/verify_asterion_dci_product.py tests/test_asterion_dci_product_parity.py docs/status/climb docs/status/JOURNAL.md
git commit -m "test: define executable DCI product parity matrix"
```

---

### Task 2: Make the original DCI verification surface independently executable

**Files:**
- Modify: `Makefile`
- Modify: `tests/test_check_judge.py`
- Modify: `tests/test_asterion_structure.py`
- Modify: `tests/test_asterion_dci_product_parity.py`
- Modify: `assets/dci/product-parity.json`
- Modify: `docs/status/JOURNAL.md`

**Interfaces:**
- Consumes: product row `configuration-and-pi-argv` and `source-and-asterion-examples`.
- Produces: working `make check-judge-config` and `make check-judge` source entry points using `PYTHONPATH=src`.
- Produces: model-free executable evidence for both original example scripts and their Asterion counterparts.

- [ ] **Step 1: Write RED tests for the source Make targets**

Add a subprocess test that runs:

```python
result = subprocess.run(
    ["make", "check-judge-config"],
    cwd=ROOT,
    env=synthetic_judge_environment(),
    text=True,
    capture_output=True,
)
self.assertEqual(result.returncode, 0, result.stderr)
```

Use a synthetic non-secret Judge configuration and verify output contains only public configuration/provenance fields.

- [ ] **Step 2: Verify RED reproduces the discovered defect**

Run:

```bash
uv run python -m unittest tests.test_check_judge -v
```

Expected: FAIL with `ModuleNotFoundError: dci` when the Make target does not set the source path itself.

- [ ] **Step 3: Repair only the source command boundary**

Change the two Make recipes to:

```make
check-judge:
	PYTHONPATH=src uv run python scripts/check_judge.py

check-judge-config:
	PYTHONPATH=src uv run python scripts/check_judge.py --config-only
```

Do not modify source DCI behavior, imports, or package ownership.

- [ ] **Step 4: Add model-free example execution tests**

Create a temporary `uv` shim that records literal argv and returns a minimal successful process. Run all four scripts with inherited synthetic `DCI_PROVIDER`, `DCI_MODEL`, and absolute corpus fixtures:

```text
scripts/examples/dci_basic_example.sh
scripts/examples/dci_runtime_context_example.sh
scripts/examples/asterion_dci_basic_example.sh
scripts/examples/asterion_dci_runtime_context_example.sh
```

Assert source scripts execute `python -m dci.benchmark.pi_rpc_runner`, Asterion scripts execute `asterion-dci run`, both pairs preserve question/corpus/tools/thinking/max-turn/eval semantics, and no script calls the other product.

- [ ] **Step 5: Verify and commit**

Run:

```bash
uv run python -m unittest tests.test_check_judge tests.test_asterion_structure tests.test_asterion_dci_product_parity -v
bash -n scripts/examples/dci_basic_example.sh scripts/examples/dci_runtime_context_example.sh scripts/examples/asterion_dci_basic_example.sh scripts/examples/asterion_dci_runtime_context_example.sh
git diff --check
```

Commit:

```bash
git add Makefile tests/test_check_judge.py tests/test_asterion_structure.py tests/test_asterion_dci_product_parity.py assets/dci/product-parity.json docs/status/JOURNAL.md
git commit -m "fix: restore source DCI verification entry points"
```

---

### Task 3: Add stable cross-product semantic comparison tests

**Files:**
- Create: `tests/asterion_dci_parity_helpers.py`
- Modify: `tests/test_asterion_dci_product_parity.py`
- Modify: `assets/dci/product-parity.json`
- Modify: `docs/status/JOURNAL.md`

**Interfaces:**
- Produces: `canonical_run_semantics(root: Path) -> dict[str, object]`.
- Produces: `canonical_judge_semantics(result: Mapping[str, object]) -> dict[str, object]`.
- Produces: `canonical_batch_semantics(root: Path) -> dict[str, object]`.
- Normalizes only timestamps, absolute paths, generated run IDs, and provider prose; it must not normalize lifecycle state, configuration names, artifact presence, fingerprints, verdict types, counts, or reuse decisions.

- [ ] **Step 1: Write RED canonical-comparison tests**

Require stable views shaped like:

```python
{
    "status": "completed",
    "event_stream": "parseable-jsonl",
    "final_present": True,
    "state_present": True,
    "provider": "fixture-provider",
    "model": "fixture-model",
    "tools": "read,bash",
    "protocol_terminal": "completed",
}
```

Build source and Asterion artifacts through their own fake Pi transports. Compare canonical configuration precedence, effective Pi argv, successful/failing terminal lifecycle, raw events, final answer, state, provenance, and compatible resume semantics.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run python -m unittest tests.test_asterion_dci_product_parity -v
```

Expected: FAIL because the canonical helpers are absent.

- [ ] **Step 3: Implement narrow test-only normalizers**

Reject missing mandatory artifacts and malformed JSON/JSONL. Keep source and Asterion native schemas independent; project both into the design's stable semantic fields rather than forcing byte-identical files.

- [ ] **Step 4: Add Judge/cache and batch/export comparisons**

Use fake transports to compare:

```text
Judge request field semantics and boolean verdict
cache invalidation after answer/config changes
exact reuse without another fake transport call
QA result counts and failure classification
IR NDCG semantics
BCPlus and BRIGHT export transforms
```

Bind every comparison selector into the applicable matrix row.

- [ ] **Step 5: Verify and commit**

Run:

```bash
uv run python -m unittest tests.test_asterion_dci_product_parity tests.test_judge tests.test_asterion_dci_judge tests.test_asterion_dci_batch tests.test_asterion_dci_export -v
uv run python -m compileall -q tests/asterion_dci_parity_helpers.py tests/test_asterion_dci_product_parity.py
uv run ruff check tests/asterion_dci_parity_helpers.py tests/test_asterion_dci_product_parity.py
git diff --check
```

Commit:

```bash
git add tests/asterion_dci_parity_helpers.py tests/test_asterion_dci_product_parity.py assets/dci/product-parity.json docs/status/JOURNAL.md
git commit -m "test: compare stable DCI product semantics"
```

---

### Task 4: Prove batch inventory, launchers, wheel, and installed application as one product

**Files:**
- Modify: `tests/test_asterion_dci_product_parity.py`
- Modify: `tools/verify_asterion_dci_product.py`
- Modify: `assets/dci/product-parity.json`
- Modify: `docs/status/JOURNAL.md`

**Interfaces:**
- Consumes: the exact 533-row AF-240 inventory and its per-row executable selectors.
- Produces: isolated-wheel evidence with `asterion-dci`, 12 profiles, no `dci` package, and an executable Pi-default installed application.

- [ ] **Step 1: Write RED composition tests**

Require the product verifier to fail if the batch inventory digest/count changes, any of its 533 evidence selectors stops resolving, any of 12 source/Asterion launcher pairs disappears, or the wheel contains/imports `dci`.

- [ ] **Step 2: Add installed-wheel and installed-application fixture execution**

Build into a system temporary directory, install into a fresh venv, change cwd outside the repository, then assert:

```python
assert find_spec("dci") is None
assert len(load_installed_profiles()) == 12
assert run([venv / "bin/asterion-dci", "--help"]).returncode == 0
assert run([venv / "bin/asterion", "list"]).returncode == 0
```

Execute the installed DCI application through its fake Pi boundary and verify a real final-answer reference, native artifact reference, body-free framework projection, and shared runtime option mapping.

- [ ] **Step 3: Execute every local matrix row**

Run:

```bash
python3 tools/verify_asterion_dci_product.py
```

Expected: all eight rows `PASS`, delegated inventory `533/533`, and zero provider-backed commands executed.

- [ ] **Step 4: Verify and commit**

Run:

```bash
uv run python -m unittest tests.test_asterion_dci_product_parity tests.test_asterion_dci_batch_launchers tests.test_distribution_boundaries tests.test_builtin_dci_application -v
python3 tools/verify_asterion_dci_product.py
python3 tools/project_scope_check.py
git diff --check
```

Commit:

```bash
git add tests/test_asterion_dci_product_parity.py tools/verify_asterion_dci_product.py assets/dci/product-parity.json docs/status/JOURNAL.md
git commit -m "test: prove installed DCI product boundaries"
```

---

### Task 5: Record bounded real Pi and Judge acceptance without bodies

**Files:**
- Create: `assets/dci/product-acceptance.json`
- Create: `tests/test_asterion_dci_product_acceptance.py`
- Modify: `assets/dci/product-parity.json`
- Modify: `docs/status/JOURNAL.md`

**Interfaces:**
- Acceptance schema: `asterion.dci.product-acceptance/v1`.
- Required case IDs: `source-basic`, `source-runtime-context`, `asterion-basic`, `asterion-runtime-context`, `installed-pi-application`, `one-row-pi-judge`, and `one-row-exact-reuse`.
- Records only sanitized command templates, inherited configuration variable names, exit status, structural artifact names/modes/digests, boolean verdict/counts, attempt/generation counts, and timestamp.

- [ ] **Step 1: Write RED privacy/schema tests**

Reject missing cases, nonzero final status, absent structural checks, non-boolean Judge verdict, plaintext keys/tokens, provider bodies, absolute private paths, or a reuse record with more than one attempt/generation.

- [ ] **Step 2: Run both original DCI examples through real Pi**

Source the main repository `.env` into the process without printing it and resolve `DCI_PI_DIR` to the external main checkout. Direct source-run artifacts to explicit `/private/tmp` paths when invoking the runner; when exercising the unchanged example wrappers, identify their newly created ignored `outputs/runs` directory by before/after directory-set comparison and remove it only after structural evidence is recorded. Run exactly:

```bash
bash scripts/examples/dci_basic_example.sh
bash scripts/examples/dci_runtime_context_example.sh high
```

If the configured default provider rejects before usage, record that failed attempt and use one bounded existing non-default credential recovery; do not start a full dataset.

- [ ] **Step 3: Run both Asterion examples and the installed application through real Pi**

Run:

```bash
bash scripts/examples/asterion_dci_basic_example.sh
bash scripts/examples/asterion_dci_runtime_context_example.sh high
asterion run --provider dci-agent-lite --application dci.research-capability@1.0.0 --runtime pi.reference --run-id af250-installed-pi --input "Answer using only the authorized local corpus."
```

Use the same effective non-secret provider/model/tools/deadline configuration and tiny existing corpora. Validate completed native state, parseable events, nonempty final answer, safe Pi provenance, and body-free installed projection.

- [ ] **Step 4: Bind the AF-240 one-row Pi-plus-Judge and reuse evidence**

Revalidate the retained bounded acceptance root if present; otherwise run one new one-row temporary QA only after confirming no valid retained evidence exists. Require one completed/correct result, exact Judge fingerprint, 28-or-more credential-clean private files, unchanged event/Judge hashes and mtimes on reuse, one protocol attempt, and no second native generation.

- [ ] **Step 5: Write the body-free acceptance manifest and verify privacy**

The manifest must contain no question, final answer, conversation, event, stderr, credential value, or provider response. Scan every configured credential value against both the manifest and retained artifacts without printing the values.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run python -m unittest tests.test_asterion_dci_product_acceptance -v
python3 tools/verify_asterion_dci_product.py
git diff --check
```

Commit:

```bash
git add assets/dci/product-acceptance.json assets/dci/product-parity.json tests/test_asterion_dci_product_acceptance.py docs/status/JOURNAL.md
git commit -m "test: record bounded DCI product acceptance"
```

---

### Task 6: Confirm AF-250 Climb, run all gates, and make the final migration conclusion

**Files:**
- Modify/regenerate: `docs/status/climb/{hypotheses.yaml,session-state.json,research-tree.md,research-tree.json,runs.csv}`
- Modify: `docs/status/{JOURNAL.md,WORKLIST.md,CURRENT-STATE.md,RESUME-NEXT-SESSION.md}`
- Modify: `README.md`
- Modify: `assets/docs/artifacts.md`

**Interfaces:**
- Consumes: all eight executable product rows, 533 delegated batch rows, seven bounded acceptance cases, and four AF-250 hypotheses.
- Produces: final full-product conclusion only when every local and bounded row passes with no unsupported entry.

- [ ] **Step 1: Execute AF-250-H-001 through H-004**

Run:

```bash
for h in AF-250-H-001 AF-250-H-002 AF-250-H-003 AF-250-H-004; do
  bash tools/climb/cycle.sh "$h"
done
```

Expected: each records `confirmed 4/4` under the AF-250 session and the generated tree has no pending AF-250 hypothesis.

- [ ] **Step 2: Run the product verifier and full repository gates**

Run:

```bash
python3 tools/verify_asterion_dci_product.py
uv run python -m unittest discover -v
uv run python -m compileall -q packages/python/asterion-core/src/asterion src/dci tools tests
uv run ruff check packages/python/asterion-core/src/asterion/dci src/dci tools tests
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
find scripts -name '*.sh' -print0 | xargs -0 -n1 bash -n
python3 tools/project_scope_check.py
git diff --check
```

- [ ] **Step 3: Audit the final claim**

Programmatically assert:

```text
8/8 product rows executable and passing
533/533 delegated batch rows resolvable and passing
7/7 bounded acceptance cases structurally valid
4/4 AF-250 hypotheses confirmed 4/4
0 unsupported, missing, placeholder, unresolved, or unverified rows
0 Asterion runtime imports/launches of src/dci
```

Do not mark AF-250 complete if any assertion fails.

- [ ] **Step 4: Update operator documentation and durable state**

Document the exact local verifier, deliberate full-dataset launcher commands, bounded-real evidence policy, installed wheel/application commands, output artifacts, and the distinction between independent implementation and stable behavioral comparison. Mark AF-250 completed only now and state the migration conclusion with the exact evidence counts.

- [ ] **Step 5: Commit and request independent closure review**

Commit:

```bash
git add README.md assets/docs assets/dci docs/status tests tools Makefile
git commit -m "docs: complete Asterion DCI product acceptance"
```

Request a read-only independent review of the AF-250 range. Fix every Critical/Important issue, rerun affected gates, and record APPROVED before making a final completion claim.

## Plan self-review

- **Design coverage:** all eight rows from the approved complete-product design are explicit; batch detail is digest-bound to all 533 AF-240 rows rather than summarized away.
- **Source verification:** the two original example scripts, source Judge/config commands, and independent source modules are executable evidence, not worklist assertions.
- **Asterion verification:** package CLI, terminal/resume/evaluate/benchmark/export, examples, installed wheel, 12 launchers/profiles, and installed Pi application are all covered.
- **Stable comparison:** only volatile paths/IDs/timestamps/prose are normalized; lifecycle, configuration, artifacts, fingerprints, counts, and verdicts remain exact.
- **Cost and privacy:** no full dataset runs; real evidence is bounded and body-free; credential values are scanned but never printed.
- **No placeholders:** the plan contains no deferred implementation marker or unsupported product row.
