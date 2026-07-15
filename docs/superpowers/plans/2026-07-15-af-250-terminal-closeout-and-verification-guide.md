# AF-250 Terminal Closeout and Verification Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close AF-250 and the migration roadmap in an explicit terminal lifecycle while publishing one authoritative, runnable Asterion DCI functional-verification guide.

**Architecture:** The worklist owns one explicit repository lifecycle marker. The scope checker distinguishes an active lifecycle with exactly one package from a complete lifecycle with no active or incomplete packages. A standalone verification guide organizes existing commands by cost/authority and is linked from README; state and Climb files then transition atomically to terminal truth.

**Tech Stack:** Python 3.14, `unittest`, Markdown, Bash, JSON/YAML project state, Git.

## Global Constraints

- Do not run a full dataset.
- Do not modify or commit the external `pi/` checkout.
- Do not persist credential values, provider bodies, private corpus paths, or private acceptance-root paths.
- Preserve `src/dci` as an independent source-only baseline; Asterion must not import or launch it.
- `docs/status/JOURNAL.md` remains append-only.
- Terminal scope must be explicit; never infer completion merely because no package is active.

---

### Task 1: Explicit Terminal Governance Contract

**Files:**
- Modify: `tools/project_scope_check.py`
- Modify: `tests/test_project_scope_check.py`
- Modify: `docs/status/WORKLIST.md`

**Interfaces:**
- Consumes: worklist line `> Project lifecycle: active|complete`
- Produces: scope payload fields `lifecycle: str` and `active_package: str | null`

- [ ] **Step 1: Write failing lifecycle tests**

Add fixtures that rewrite the worklist lifecycle and package statuses, then assert:

```python
def test_terminal_lifecycle_accepts_zero_active_completed_packages(self) -> None:
    root = self.copy_repository_state()
    self.set_lifecycle(root, "complete")
    self.set_package_status(root, "AF-250", "completed")
    self.set_resume_package(root, "none")
    result = self.run_check(root)
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    self.assertEqual(json.loads(result.stdout)["lifecycle"], "complete")

def test_terminal_lifecycle_rejects_active_or_incomplete_packages(self) -> None:
    root = self.copy_repository_state()
    self.set_lifecycle(root, "complete")
    with self.assertRaisesScopeError(root, "complete lifecycle"):
        pass
```

Also cover missing/unknown lifecycle, `active` with zero or multiple active
packages, and `complete` with an active or non-completed package.

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run python -m unittest tests.test_project_scope_check -v
```

Expected: new terminal tests fail because the checker still requires exactly
one `in_progress` package and an AF package in RESUME.

- [ ] **Step 3: Implement lifecycle parsing and validation**

Add a strict marker and terminal-aware marker validation:

```python
LIFECYCLE_MARKER = re.compile(r"^> Project lifecycle: (?P<value>[a-z]+)$", re.MULTILINE)
VALID_LIFECYCLES = {"active", "complete"}
RESUME_MARKER = re.compile(
    r"^Active work package: (?P<id>[A-Z][A-Z0-9]*-\d+|none)\s*$",
    re.MULTILINE,
)
```

`active` requires exactly one `in_progress` package. `complete` requires zero
`in_progress` packages and every parsed package status to equal `completed`.
The JSON result always includes `lifecycle`; terminal success uses
`active_package: null` and requires `Active work package: none`.

- [ ] **Step 4: Run governance tests and pre-transition scope check**

```bash
uv run python -m unittest tests.test_project_scope_check -v
python3 tools/project_scope_check.py
```

Expected: tests pass; the current `active` AF-250 state still passes before the
terminal transition.

- [ ] **Step 5: Commit governance support**

```bash
git add tools/project_scope_check.py tests/test_project_scope_check.py docs/status/WORKLIST.md
git commit -m "feat: support explicit terminal project lifecycle"
```

---

### Task 2: Authoritative Asterion DCI Functional Verification Guide

**Files:**
- Create: `docs/verification/asterion-dci-validation-guide.md`
- Modify: `README.md`
- Modify: `tests/test_distribution_boundaries.py`

**Interfaces:**
- Consumes: existing source/Asterion examples, CLIs, profiles, launchers, product verifier, and repository gates
- Produces: one stable guide linked by README with provider-cost labels and body-free pass criteria

- [ ] **Step 1: Write failing documentation-contract tests**

Add a test that requires the guide and canonical verification surfaces:

```python
def test_complete_dci_validation_guide_covers_both_products_and_all_tiers(self) -> None:
    text = (ROOT / "docs/verification/asterion-dci-validation-guide.md").read_text()
    for required in (
        "scripts/examples/dci_basic_example.sh",
        "scripts/examples/dci_runtime_context_example.sh",
        "scripts/examples/asterion_dci_basic_example.sh",
        "scripts/examples/asterion_dci_runtime_context_example.sh",
        "asterion-dci resume",
        "asterion-dci terminal",
        "asterion-dci evaluate",
        "asterion-dci benchmark",
        "verify_asterion_dci_product.py",
        "--acceptance-root",
        "533/533",
        "7/7",
    ):
        self.assertIn(required, text)
```

Also assert the README links the guide, all twelve launcher paths are named,
and the guide labels provider-free, bounded provider-backed, and full-dataset
commands separately.

- [ ] **Step 2: Run RED documentation tests**

```bash
uv run python -m unittest \
  tests.test_distribution_boundaries.SourceDistributionBoundaryTests.test_complete_dci_validation_guide_covers_both_products_and_all_tiers -v
```

Expected: FAIL because the guide does not exist.

- [ ] **Step 3: Write the verification guide**

Create the guide with these exact sections:

```markdown
# Asterion DCI Full Functional Verification Guide
## 1. Scope and definition of “complete”
## 2. Safety and prerequisites
## 3. Tier 1 — provider-free smoke verification
## 4. Tier 2 — original DCI examples
## 5. Tier 2 — Asterion DCI examples
## 6. Tier 3 — installed Pi-default application
## 7. Tier 3 — complete operator command surface
## 8. Tier 3 — batch profiles, exports, and twelve launchers
## 9. Tier 4 — public and private product acceptance
## 10. Tier 5 — full repository closure gates
## 11. Expected artifacts and pass criteria
## 12. Troubleshooting without weakening evidence
```

Use `$DCI_PI_DIR`, `$ASTERION_DCI_CORPUS_ROOT`,
`$ASTERION_DCI_OUTPUT_ROOT`, and `$AF250_ACCEPTANCE_ROOT` placeholders. Label
every code block `provider-free`, `bounded provider-backed`, or `full-dataset`.
Do not include concrete credentials or private paths.

- [ ] **Step 4: Link and verify the guide**

Add a README link under AF-250 acceptance, then run:

```bash
uv run python -m unittest tests.test_distribution_boundaries -v
bash -n scripts/examples/dci_basic_example.sh \
  scripts/examples/dci_runtime_context_example.sh \
  scripts/examples/asterion_dci_basic_example.sh \
  scripts/examples/asterion_dci_runtime_context_example.sh
git diff --check
```

Expected: all pass without a provider request.

- [ ] **Step 5: Commit the guide**

```bash
git add README.md docs/verification/asterion-dci-validation-guide.md tests/test_distribution_boundaries.py
git commit -m "docs: add complete Asterion DCI verification guide"
```

---

### Task 3: Transition AF-250 and Durable State to Terminal Complete

**Files:**
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`
- Append: `docs/status/JOURNAL.md`
- Modify: `docs/status/climb/session-state.json`
- Modify/regenerate: `docs/status/climb/research-tree.json`
- Modify/regenerate: `docs/status/climb/research-tree.md`
- Modify: `tests/test_climb_tools.py`

**Interfaces:**
- Consumes: accepted AF-250 evidence and lifecycle support from Task 1
- Produces: zero active packages, completed Climb session, terminal recovery state

- [ ] **Step 1: Write failing terminal-state assertions**

Update governance tests to require:

```python
self.assertEqual(worklist_lifecycle, "complete")
self.assertEqual(af250["Status"], "completed")
self.assertEqual(session["phase"], "completed")
self.assertIsNone(session["next_hypothesis"])
self.assertIsNone(session["in_flight"])
```

Require CURRENT to contain `Active work package: none` and RESUME to contain
`Active work package: none` with no implementation next action.

- [ ] **Step 2: Run RED terminal-state tests**

```bash
uv run python -m unittest \
  tests.test_climb_tools.ClimbToolTests.test_af250_governance_uses_the_exact_package_and_session \
  tests.test_project_scope_check -v
```

Expected: FAIL while AF-250 and the session remain active.

- [ ] **Step 3: Apply the terminal transition**

Set:

```text
> Project lifecycle: complete
AF-250 Status: completed
CURRENT Active work package: none
RESUME Active work package: none
Climb phase: completed
```

Rewrite RESUME as a terminal recovery baton with verification commands and the
rule that new work must explicitly reopen lifecycle governance. Append, never
rewrite, the JOURNAL completion events. Regenerate the research tree.

- [ ] **Step 4: Verify terminal governance**

```bash
python3 tools/project_scope_check.py
uv run python -m unittest \
  tests.test_project_scope_check \
  tests.test_climb_tools.ClimbToolTests.test_af250_governance_uses_the_exact_package_and_session -v
```

Expected scope payload:

```json
{"active_package": null, "errors": [], "lifecycle": "complete", "ok": true}
```

- [ ] **Step 5: Commit terminal state**

```bash
git add docs/status tests/test_climb_tools.py
git commit -m "docs: close AF-250 migration milestone"
```

---

### Task 4: Full Closure Verification and Independent Review

**Files:**
- Modify only if review finds a defect: files owned by Tasks 1–3
- Append: `docs/status/JOURNAL.md`

**Interfaces:**
- Consumes: terminal lifecycle, guide, and all prior migration evidence
- Produces: reviewed final commits and recoverable terminal state

- [ ] **Step 1: Run the public product verifier**

```bash
uv run python tools/verify_asterion_dci_product.py
```

Expected: 8/8 product rows, 533/533 delegated selectors, 12/12 launchers,
6/6 extras, bounded acceptance 7/7, and zero provider-backed execution.

- [ ] **Step 2: Revalidate retained private evidence**

With the shared root `.env` exported and the caller-owned root supplied:

```bash
uv run python tools/verify_asterion_dci_product.py \
  --acceptance-root "$AF250_ACCEPTANCE_ROOT" \
  --validate-only
```

Expected: `private-acceptance 7/7`; no provider request and no body output.

- [ ] **Step 3: Run all repository gates**

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q src tests tools packages/python/asterion-core/src
uv run ruff check src tests tools packages/python/asterion-core/src
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
cargo fmt --manifest-path packages/rust/controlled-executor/Cargo.toml --check
cargo clippy --manifest-path packages/rust/controlled-executor/Cargo.toml --all-targets -- -D warnings
bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
python3 tools/project_scope_check.py
git diff --check
```

Expected: every command exits zero.

- [ ] **Step 4: Request independent read-only review**

Review the complete closeout diff for lifecycle bypass, stale active-state
markers, unsafe provider commands, missing functional surfaces, secret/private
path leakage, and documentation that overclaims evidence. Fix every Critical
or Important issue and rerun affected gates.

- [ ] **Step 5: Commit review repairs and checkpoint**

Commit cohesive repairs, append one project-state journal line per commit, and
refresh RESUME only if the recovery boundary changed. Final status must have no
uncommitted implementation or documentation changes; an append-only
post-commit JOURNAL line may remain only when created by the repository hook.

## Plan Self-Review

- Spec coverage: terminal governance, guide tiers, privacy, testing, state
  transition, review, and terminal recovery all map to Tasks 1–4.
- Placeholder scan: no deferred implementation marker or unspecified command
  remains; environment placeholders are deliberate security boundaries.
- Interface consistency: lifecycle values are exactly `active|complete`;
  terminal RESUME uses exactly `Active work package: none`; the scope payload
  uses JSON `null` for no active package.
