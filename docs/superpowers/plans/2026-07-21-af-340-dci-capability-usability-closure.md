# AF-340 DCI Capability-Usability Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close AF-340 by proving the complete Asterion DCI core-capability matrix with retained Pi r14 and Claude MiniMax r6 evidence, without requiring Claude subscription or strict paper reproduction.

**Architecture:** Keep bounded report validation strict and body-free, but split required dimensions from optional authentication evidence. The public inspector and AF-340 H-004 Climb path require Pi plus MiniMax, while accepting a valid subscription report only as an optional third report. Full/paper tooling remains implemented but leaves the AF-340 Climb and package-closure path; any future execution requires a new governed package.

**Tech Stack:** Python 3.12, `unittest`, Bash, YAML/JSON Climb state, Markdown documentation, existing Asterion Python/TypeScript/Rust verification targets.

## Global Constraints

- Active work package is `AF-340`; run `python3 tools/project_scope_check.py` before implementation and again before package closure.
- DCI core capability means research execution; L0-L4 context and conversation processing; artifacts/resume/cancellation/deadlines; Judge/cache/QA/IR evaluation; benchmark datasets/profiles/launchers/reuse; analysis/figures/exports; source/application/wheel delivery; Pi and Claude Code runtime integration; and configuration/privacy/body-free safety.
- Required retained reports are Pi r14 and Claude MiniMax r6, covering exactly `original-pi`, `asterion-pi`, and `asterion-claude-minimax`.
- `asterion-claude-subscription` is accepted only as optional additional evidence and is never required.
- MiniMax functional evidence must not be described as paper-model, published-score, statistical-parity, or full-result evidence.
- AF-340-H-005 and full/paper execution do not gate AF-340; future execution requires a new active work package, explicit invocation authorization, exact profiles, fresh private roots, and a finite budget.
- Preserve the external `pi/` checkout and unrelated user changes. Do not run a provider or full dataset while implementing the contract change.
- Write tests before implementation, observe RED, make the minimum production change, then observe GREEN.

---

### Task 1: Require Pi plus MiniMax and accept subscription optionally

**Files:**
- Modify: `tests/test_af340_reproduction_verifier.py`
- Modify: `tools/verify_af340_reproduction.py`

**Interfaces:**
- Consumes: `_validate_report(path, root, resource_root, corpus_cache) -> tuple[str, set[str]]` and the existing variant-specific native artifact revalidation.
- Produces: `REQUIRED_RETAINED_DIMENSIONS`, `OPTIONAL_RETAINED_DIMENSIONS`, and `_run_inspect(...)` behavior that accepts two required reports or those two plus one valid subscription report.

- [ ] **Step 1: Replace the old four-dimension test with required/optional acceptance tests**

Use the existing `_retained_report_fixture` helper and add explicit cases equivalent to:

```python
def test_inspect_requires_pi_and_minimax_three_dimensions(self) -> None:
    module = load_verifier()
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        root = Path(temporary)
        resource_root = root / "resources"
        (root / "pi").mkdir()
        (root / "claude-minimax").mkdir()
        pi_report, _ = self._retained_report_fixture(
            module, root / "pi", "pi", resource_root=resource_root
        )
        minimax_report, _ = self._retained_report_fixture(
            module,
            root / "claude-minimax",
            "claude-minimax",
            provider="minimax",
            model="MiniMax-M3",
            resource_root=resource_root,
        )
        args = [
            "inspect", "--resource-root", str(resource_root),
            "--report", str(pi_report),
            "--report", str(minimax_report),
        ]
        stdout = io.StringIO()
        self.assertEqual(
            module.verify_af340_reproduction_main(args, repo_root=ROOT, stdout=stdout),
            0,
        )
        self.assertIn("Required retained evidence dimensions: 3/3", stdout.getvalue())

def test_inspect_accepts_subscription_as_optional_third_report(self) -> None:
    module = load_verifier()
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        root = Path(temporary)
        resource_root = root / "resources"
        reports = []
        for variant, provider, model in (
            ("pi", None, None),
            ("claude-minimax", "minimax", "MiniMax-M3"),
            ("claude-subscription", None, None),
        ):
            variant_root = root / variant
            variant_root.mkdir()
            report, _ = self._retained_report_fixture(
                module,
                variant_root,
                variant,
                provider=provider,
                model=model,
                resource_root=resource_root,
            )
            reports.append(report)
        args = ["inspect", "--resource-root", str(resource_root)]
        for report in reports:
            args.extend(("--report", str(report)))
        stdout = io.StringIO()
        self.assertEqual(
            module.verify_af340_reproduction_main(args, repo_root=ROOT, stdout=stdout),
            0,
        )
        self.assertIn("Optional retained evidence dimensions: 1/1", stdout.getvalue())
        self.assertIn("Retained dimension: asterion-claude-subscription", stdout.getvalue())

def test_inspect_rejects_missing_minimax_or_duplicate_variant(self) -> None:
    module = load_verifier()
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        root = Path(temporary)
        resource_root = root / "resources"
        reports = {}
        for variant, provider, model in (
            ("pi", None, None),
            ("claude-minimax", "minimax", "MiniMax-M3"),
            ("claude-subscription", None, None),
        ):
            variant_root = root / variant
            variant_root.mkdir()
            reports[variant], _ = self._retained_report_fixture(
                module,
                variant_root,
                variant,
                provider=provider,
                model=model,
                resource_root=resource_root,
            )
        base = ["inspect", "--resource-root", str(resource_root)]
        missing_minimax = base + [
            "--report", str(reports["pi"]),
            "--report", str(reports["claude-subscription"]),
        ]
        duplicate_minimax = base + [
            "--report", str(reports["pi"]),
            "--report", str(reports["claude-minimax"]),
            "--report", str(reports["claude-minimax"]),
        ]
        self.assertEqual(
            module.verify_af340_reproduction_main(missing_minimax, repo_root=ROOT), 2
        )
        self.assertEqual(
            module.verify_af340_reproduction_main(duplicate_minimax, repo_root=ROOT), 2
        )
```

Keep the existing resource-manifest mutation, resource-content mutation, private artifact mutation, permission, signature, and genuine-native-reference assertions against the new Pi-plus-MiniMax argument set.

- [ ] **Step 2: Run the focused tests and observe RED**

Run:

```bash
uv run python -m unittest -v \
  tests.test_af340_reproduction_verifier.Af340ReproductionVerifierTests.test_inspect_requires_pi_and_minimax_three_dimensions \
  tests.test_af340_reproduction_verifier.Af340ReproductionVerifierTests.test_inspect_accepts_subscription_as_optional_third_report \
  tests.test_af340_reproduction_verifier.Af340ReproductionVerifierTests.test_inspect_rejects_missing_minimax_or_duplicate_variant
```

Expected: failures because `_run_inspect` still requires exactly three reports and all four dimensions.

- [ ] **Step 3: Implement required and optional dimension sets**

Replace the single four-dimension constant with:

```python
REQUIRED_RETAINED_DIMENSIONS = frozenset(
    {"original-pi", "asterion-pi", "asterion-claude-minimax"}
)
OPTIONAL_RETAINED_DIMENSIONS = frozenset({"asterion-claude-subscription"})
ACCEPTED_RETAINED_DIMENSIONS = (
    REQUIRED_RETAINED_DIMENSIONS | OPTIONAL_RETAINED_DIMENSIONS
)
```

Change `_run_inspect` so that it:

```python
if len(args.report) not in {2, 3}:
    raise ValueError("AF-340 retained evidence requires two reports plus optional subscription")
if not REQUIRED_RETAINED_DIMENSIONS.issubset(dimensions):
    raise ValueError("AF-340 retained evidence is incomplete")
if not dimensions.issubset(ACCEPTED_RETAINED_DIMENSIONS):
    raise ValueError("AF-340 retained evidence is invalid")
optional_count = len(dimensions & OPTIONAL_RETAINED_DIMENSIONS)
stdout.write(
    "PASS\nRequired retained evidence dimensions: 3/3\n"
    + f"Optional retained evidence dimensions: {optional_count}/1\n"
    + "".join(f"Retained dimension: {item}\n" for item in sorted(dimensions))
    + "Agent operations: 0\nJudge operations: 0\nFull dataset ran: no\n"
)
```

Keep the existing per-report validation loop, duplicate-variant rejection, and overlap rejection between the report-count check and the required-dimension check.

Do not weaken `_validate_report`, native tree rehashing, resource-manifest identity, report permissions, signature validation, or duplicate-dimension rejection.

- [ ] **Step 4: Run the complete verifier suite and observe GREEN**

Run:

```bash
uv run python -m unittest -v tests.test_af340_reproduction_verifier
uv run python -m compileall -q tools/verify_af340_reproduction.py tests/test_af340_reproduction_verifier.py
uv run ruff check tools/verify_af340_reproduction.py tests/test_af340_reproduction_verifier.py
```

Expected: all verifier tests pass, compilation is quiet, and Ruff reports no errors.

- [ ] **Step 5: Commit the verifier contract**

```bash
git add tools/verify_af340_reproduction.py tests/test_af340_reproduction_verifier.py
git commit -m "fix(dci): close bounded evidence with Pi and MiniMax"
```

Journal the commit immediately with `project-state journal`.

---

### Task 2: Remove subscription and full-paper gates from AF-340 Climb execution

**Files:**
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`

**Interfaces:**
- Consumes: the Task 1 `inspect` CLI and retained report environment variables.
- Produces: H-004 Climb dimensions `bounded_original_pi`, `bounded_asterion_pi`, `bounded_claude_minimax`, and `retained_body_free_evidence`; AF-340-H-005 is no longer a runnable Climb branch.

- [ ] **Step 1: Write RED Climb contract assertions**

Update the AF-340 expectations so they require:

```python
"AF-340-H-004": (
    (
        "bounded_original_pi",
        "bounded_asterion_pi",
        "bounded_claude_minimax",
        "retained_body_free_evidence",
    ),
    (
        "bounded_original_pi",
        "bounded_asterion_pi",
        "bounded_claude_minimax",
        "retained_body_free_evidence",
    ),
),
```

In `test_af340_h004_eval_only_inspects_retained_evidence`, add these exact assertions while retaining the existing provider/full-run prohibitions:

```python
self.assertEqual(runner.group(1).count('--report "$AF340_'), 2)
self.assertIn("AF340_PI_REPORT", runner.group(1))
self.assertIn("AF340_CLAUDE_MINIMAX_REPORT", runner.group(1))
self.assertNotIn("AF340_CLAUDE_SUBSCRIPTION_REPORT", runner.group(1))
self.assertNotIn('elif [ "$1" = "AF-340-H-005" ]', train_script)
self.assertNotIn("AF-340-H-005)", eval_script)
```

- [ ] **Step 2: Run the focused Climb tests and observe RED**

```bash
uv run python -m unittest -v \
  tests.test_climb_tools.ClimbToolTests.test_af340_train_has_exact_closed_membership_and_paradigms \
  tests.test_climb_tools.ClimbToolTests.test_af340_eval_branches_have_exact_dimensions_and_selectors \
  tests.test_climb_tools.ClimbToolTests.test_af340_train_branches_use_exact_tracked_commands \
  tests.test_climb_tools.ClimbToolTests.test_af340_h004_eval_only_inspects_retained_evidence
```

Expected: failures naming the subscription report, the old `bounded_claude_modes` dimension, three report arguments, or the H-005 branch.

- [ ] **Step 3: Implement the minimal H-004 shell change**

In both `train.sh` and `eval-local.sh`, require only:

```bash
: "${AF340_RESOURCE_ROOT:?set AF340_RESOURCE_ROOT to the exact bounded resource tree}"
: "${AF340_PI_REPORT:?set AF340_PI_REPORT to the retained Pi bounded report}"
: "${AF340_CLAUDE_MINIMAX_REPORT:?set AF340_CLAUDE_MINIMAX_REPORT to the retained Claude MiniMax report}"
```

Call `inspect` with only Pi and MiniMax. Rename the third H-004 dimension to `bounded_claude_minimax` and pass it only when the log contains `Retained dimension: asterion-claude-minimax`. Remove AF-340-H-005 from the train allowlist, paradigm selection, train branch, eval case, and AF-340 expected maps; do not delete `full`, `terminal`, `inspect-full`, or `inspect-closure` from the standalone verifier.

- [ ] **Step 4: Run GREEN Climb and shell checks**

```bash
uv run python -m unittest -v tests.test_climb_tools
bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
```

Expected: all Climb tests pass and Bash syntax checks are quiet.

- [ ] **Step 5: Commit the Climb contract**

```bash
git add tools/climb/train.sh tools/climb/eval-local.sh tests/test_climb_tools.py
git commit -m "fix(climb): align AF-340 with capability closure"
```

Journal the commit immediately.

---

### Task 3: Publish the functional evidence contract and supersede H-005

**Files:**
- Modify: `tests/test_asterion_documentation.py`
- Modify: `asterion/docs/guides/asterion-dci-complete-reference.md`
- Modify: `asterion/docs/verification/asterion-dci-validation-guide.md`
- Modify: `docs/status/climb/hypotheses.yaml`
- Modify: `docs/status/climb/session-state.json`
- Modify: `docs/status/climb/session-target.md`
- Regenerate: `docs/status/climb/research-tree.json`
- Regenerate: `docs/status/climb/research-tree.md`

**Interfaces:**
- Consumes: D-053 and the Task 1/2 command contract.
- Produces: user-facing Pi-plus-MiniMax inspection commands, optional subscription guidance, H-005 `superseded` state, and a Climb resume point that names only H-004.

- [ ] **Step 1: Write RED documentation assertions**

Add a focused test that reads both complete-reference and validation-guide text and asserts:

```python
def test_af340_functional_closure_uses_pi_and_minimax(self) -> None:
    complete_reference = (
        PROJECT / "docs/guides/asterion-dci-complete-reference.md"
    ).read_text(encoding="utf-8")
    validation_guide = (
        PROJECT / "docs/verification/asterion-dci-validation-guide.md"
    ).read_text(encoding="utf-8")
    for document in (complete_reference, validation_guide):
        self.assertIn("Pi r14", document)
        self.assertIn("Claude MiniMax r6", document)
        self.assertIn("subscription", document)
        self.assertIn("optional", document)
        self.assertIn("strict paper reproduction", document)
        self.assertIn("new active work package", document)
        inspect_block = document.split(
            "verify_af340_reproduction.py inspect ", 1
        )[1].split("```", 1)[0]
        self.assertEqual(inspect_block.count("--report"), 2)
```

- [ ] **Step 2: Run the documentation test and observe RED**

```bash
uv run python -m unittest -v \
  tests.test_asterion_documentation.AsterionDocumentationTests.test_af340_functional_closure_uses_pi_and_minimax
```

Expected: failure because both documents still require three reports and H-005 full closure.

- [ ] **Step 3: Update both operator documents**

Show Pi and MiniMax as the required bounded commands. Move the subscription command into an explicitly optional subsection. Make the primary `inspect` command contain exactly:

```bash
uv run python tools/verify_af340_reproduction.py inspect \
  --resource-root "$DCI_RESOURCE_ROOT" \
  --report outputs/verification/af340-bounded-pi/af340-bounded-report.json \
  --report outputs/verification/af340-bounded-claude-minimax/af340-bounded-report.json
```

State that a validated subscription report may be appended as a third report. Label full/paper commands as dormant optional tooling that cannot close AF-340 and may execute only after a new work package and explicit budget authorization.

- [ ] **Step 4: Supersede the old H-005 Climb route**

Change AF-340-H-004 description to Pi plus MiniMax core-capability coverage. Change AF-340-H-005 to:

```yaml
status: superseded
superseded_by: D-053
superseded_reason: Strict paper reproduction is optional future evidence outside AF-340 closure.
```

Keep its historical description and empty results for traceability. Update `session-target.md` to capability-package usability and `session-state.json` so H-004 is the only next hypothesis and its next action is to inspect Pi r14 plus MiniMax r6. Regenerate summaries:

```bash
python3 tools/climb/regen-tree.py
```

- [ ] **Step 5: Run GREEN documentation and state tests**

```bash
uv run python -m unittest -v tests.test_asterion_documentation tests.test_climb_tools
python3 tools/project_scope_check.py --climb-hypothesis AF-340-H-004
git diff --check
```

Expected: documentation and Climb tests pass; scope reports `ok: true`; H-005 is absent from active research-tree hypotheses.

- [ ] **Step 6: Commit documentation and tracked state**

```bash
git add \
  tests/test_asterion_documentation.py \
  asterion/docs/guides/asterion-dci-complete-reference.md \
  asterion/docs/verification/asterion-dci-validation-guide.md \
  docs/status/climb/hypotheses.yaml \
  docs/status/climb/session-state.json \
  docs/status/climb/session-target.md \
  docs/status/climb/research-tree.json \
  docs/status/climb/research-tree.md
git commit -m "docs: publish AF-340 functional closure contract"
```

Journal the decision-aligned state migration and refresh the live checkpoint because the immediate next action changes.

---

### Task 4: Revalidate retained reports and confirm AF-340-H-004

**Files:**
- Modify before cycle: `tests/test_af340_reproduction_verifier.py`
- Modify before cycle: `tools/verify_af340_reproduction.py`
- Modify through `tools/climb/cycle.sh`: `docs/status/climb/hypotheses.yaml`, `docs/status/climb/runs.csv`, `docs/status/climb/session-state.json`, `docs/status/climb/research-tree.json`, `docs/status/climb/research-tree.md`, `docs/status/JOURNAL.md`
- Create ignored run evidence: `runs/climb/<generated-run-id>/`

**Interfaces:**
- Consumes: current main-repository resource tree, Pi r14, MiniMax r6, and the Task 1/2 H-004 inspector.
- Produces: one deterministic Climb cycle with H-004 `confirmed 4/4`; no provider request and no full dataset.

- [ ] **Step 1: Verify the exact retained files and scope before execution**

```bash
python3 tools/project_scope_check.py --climb-hypothesis AF-340-H-004
test -f outputs/verification/af340-bounded-pi-r14/af340-bounded-report.json
test -f .worktrees/af-340-implementation/outputs/verification/af340-bounded-claude-minimax-r6/af340-bounded-report.json
```

Expected: scope `ok: true` and both `test -f` commands succeed.

- [ ] **Step 2: TDD the strict same-file Python-alias repair**

Add a focused test that builds valid Pi retained evidence with a conventional
same-directory Python alias (`python3` when the current executable is
`python`) resolving by `samefile()` to the same interpreter. Require public
inspection under the current alias to accept that report. In the same test,
re-sign an otherwise structurally valid report whose original operations use
a different executable path and require rejection.

Run the focused selector first and observe RED from retained operation-plan
drift. Then minimally change retained validation so Pi plan candidates include
only the current executable plus conventional sibling aliases in the same
`bin/` directory that exist and pass `samefile()` against the current
executable. Select the single complete candidate plan matching the signed
`plan_sha256`, and use it for every existing per-operation/configuration hash
check. Do not weaken resource, artifact, native-tree, signature, permission,
duplicate, privacy, or body-free validation.

Run the focused selector, the complete verifier suite, compilation, and Ruff
GREEN, then commit:

```bash
git add tests/test_af340_reproduction_verifier.py tools/verify_af340_reproduction.py
git commit -m "fix(dci): normalize retained Python aliases"
```

- [ ] **Step 3: Run public retained-evidence inspection directly**

```bash
uv run python tools/verify_af340_reproduction.py inspect \
  --resource-root . \
  --report outputs/verification/af340-bounded-pi-r14/af340-bounded-report.json \
  --report .worktrees/af-340-implementation/outputs/verification/af340-bounded-claude-minimax-r6/af340-bounded-report.json
```

Expected: `PASS`, `Required retained evidence dimensions: 3/3`, all three required dimension lines, zero new Agent/Judge operations, and `Full dataset ran: no`.

- [ ] **Step 4: Run the governed H-004 Climb cycle**

```bash
AF340_RESOURCE_ROOT="$PWD" \
AF340_PI_REPORT="$PWD/outputs/verification/af340-bounded-pi-r14/af340-bounded-report.json" \
AF340_CLAUDE_MINIMAX_REPORT="$PWD/.worktrees/af-340-implementation/outputs/verification/af340-bounded-claude-minimax-r6/af340-bounded-report.json" \
bash tools/climb/cycle.sh AF-340-H-004
```

Expected: `AF-340-H-004 confirmed 4/4`, no provider request, H-005 remains superseded, and no next pending AF-340 hypothesis.

- [ ] **Step 5: Verify generated state and commit it**

```bash
python3 tools/climb/regen-tree.py
rg -n "AF-340-H-004|AF-340-H-005|Next hypothesis" \
  docs/status/climb/hypotheses.yaml docs/status/climb/research-tree.md
git diff --check
git add docs/status/climb docs/status/JOURNAL.md
git commit -m "docs: confirm AF-340 bounded capability evidence"
```

Journal the retained validation result if the cycle journal line does not already record it.

---

### Task 5: Run the complete DCI core-capability closure matrix

**Files:**
- No production files expected; retain command output only in ignored/local logs unless a verified count belongs in tracked closure state.

**Interfaces:**
- Consumes: committed Task 1-4 implementation and evidence.
- Produces: fresh terminal proof for the design's eight DCI core-capability groups, with no provider request or full dataset.

- [ ] **Step 1: Run focused functional and documentation suites**

```bash
uv run python -m unittest -v \
  tests.test_af340_reproduction_verifier \
  tests.test_original_readme_acceptance \
  tests.test_asterion_documentation \
  tests.test_asterion_dci_product_parity \
  tests.test_climb_tools
uv run python tools/verify_af340_reproduction.py local
```

Expected: all tests pass; local verifier prints `PASS`, zero Agent/Judge operations, and `Full dataset ran: no`.

- [ ] **Step 2: Run complete Python product suites**

```bash
uv run python -m unittest discover -v
(cd asterion && uv run python -m unittest discover -s tests -v)
```

Expected: both complete Python suites pass.

- [ ] **Step 3: Run static, shell, TypeScript, and Rust gates**

```bash
uv run python -m compileall -q src asterion/src/asterion asterion/tests tests tools
uv run ruff check src asterion/src/asterion asterion/tests tests tools
bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
npm --prefix asterion/packages/typescript/asterion-runtime test
make test-rust-executor
make check-rust-executor
python3 tools/project_scope_check.py
git diff --check
```

Expected: every command succeeds and scope reports `ok: true`.

- [ ] **Step 4: Review the complete diff before closure**

Inspect only the AF-340 change range and verify no credential, private body, external `pi/`, or full-run artifact is staged:

```bash
git status --short
git diff --stat ecc5400..HEAD
git diff --check ecc5400..HEAD
```

Expected: only planned verifier, tests, shell, documentation, and tracked state changes.

---

### Task 6: Close AF-340 under managed-package governance

**Files:**
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md`
- Rewrite as active checkpoint: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- Consumes: H-004 confirmed state and all Task 5 verification results.
- Produces: AF-340 `completed`, structural acceptance truth, a journaled terminal result, and a live recovery point. It does not authorize or create a successor paper-reproduction package.

- [ ] **Step 1: Run package-closure preflight**

```bash
python3 tools/project_scope_check.py
git status --short
```

Expected: AF-340 is the one active package, scope is healthy, and only planned state-closeout edits are pending.

- [ ] **Step 2: Record exact closure evidence**

Set AF-340 `Status: completed` and add closure evidence naming:

- the Task 5 fresh test counts and gates;
- H-001 through H-004 confirmed;
- Pi r14 plus MiniMax r6 and their three required dimensions;
- subscription optional and not executed;
- H-005 superseded by D-053;
- no provider request or full dataset during the contract migration; and
- strict paper reproduction still requiring a new work package and authority.

Update CURRENT-STATE structurally: AF-340 accepted, no active package unless a separately approved successor exists, and the framework objective remains DCI capability-package usability. Do not add session narration or next steps to CURRENT-STATE.

- [ ] **Step 3: Verify and commit structural closure**

```bash
python3 tools/project_scope_check.py
git diff --check
git add docs/status/WORKLIST.md docs/status/CURRENT-STATE.md
git commit -m "docs: close AF-340 capability usability"
```

Expected: closure preflight passes and the structural closure commit succeeds.

- [ ] **Step 4: Journal the exact closure commit and checkpoint recovery state**

Read the hash from `git rev-parse --short HEAD`, append one terminal JOURNAL line containing that hash plus the fresh Task 5 verification counts, and rewrite RESUME as `# Live Session Checkpoint` while the session remains active. Record that no paper/full successor is selected.

- [ ] **Step 5: Verify and commit the state checkpoint**

```bash
python3 tools/project_scope_check.py
git diff --check
git add docs/status/JOURNAL.md docs/status/RESUME-NEXT-SESSION.md
git commit -m "docs: checkpoint AF-340 capability closure"
git status --short --branch
```

Expected: completed-lifecycle scope is healthy, the checkpoint commit succeeds, and the main repository is clean. Do not push unless the user separately requests it.
