# Asterion Makefile Entry Points Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five explicit root Make targets for Asterion capability discovery and DCI verification, with safe defaults and approachable documentation.

**Architecture:** The Makefile remains a thin argument-forwarding layer over the accepted generic `uv run asterion` CLI. A focused unittest validates the static target surface and exact `make -n` argv, while README and the beginner guide present Make as a source-checkout convenience beside the canonical CLI.

**Tech Stack:** GNU/BSD Make, Python `unittest`, `subprocess`, `shlex`, Markdown documentation.

## Global Constraints

- Expose exactly `asterion-describe`, `asterion-verify-preflight`, `asterion-verify-basic`, `asterion-verify-acceptance`, and `asterion-verify-complete`.
- Do not add an ambiguous `asterion-verify` alias or parameterized `LEVEL=` target.
- Default provider to `dci-agent-lite`, environment file to `.env`, corpus root to `$(CURDIR)/corpus`, and output root to `$(CURDIR)/outputs/asterion-verification`.
- Never source or print `.env`, credentials, provider bodies, or private artifact paths in Make.
- Do not run a provider-backed target or full dataset during automated verification.
- Preserve the user-owned untracked `.superpowers/sdd/task-0-review.md`.

---

### Task 1: Exact Make target contract

**Files:**
- Create: `tests/test_makefile_entrypoints.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: the existing `uv run asterion describe/verify` CLI.
- Produces: five phony Make targets and four overridable Make variables.

- [ ] **Step 1: Write the failing Makefile contract test**

Create `tests/test_makefile_entrypoints.py` with a `MakefileEntryPointTests` class. Read `Makefile`, assert that the five exact targets occur in the `.PHONY` declaration, and use this helper to inspect recipes without executing them:

```python
def dry_run(target: str, *assignments: str) -> tuple[str, ...]:
    completed = subprocess.run(
        ["make", "-n", target, *assignments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(shlex.split(completed.stdout.replace("\\\n", " ")))
```

Assert the exact default argv for all five targets. Assert an override call with `ASTERION_PROVIDER=fixture-provider`, `ASTERION_ENV_FILE=fixture.env`, `ASTERION_CORPUS_ROOT=/tmp/fixture-corpus`, and `ASTERION_VERIFY_OUTPUT_ROOT=/tmp/fixture-output` produces those exact values. Assert the Makefile contains no target named exactly `asterion-verify:` and no `LEVEL` variable.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
uv run python -m unittest tests.test_makefile_entrypoints -v
```

Expected: FAIL because the five targets and variables do not exist.

- [ ] **Step 3: Add the minimal Makefile variables and recipes**

Add the four `?=` defaults before `.PHONY`, extend `.PHONY`, and add recipes equivalent to:

```make
asterion-describe:
	uv run asterion describe --provider "$(ASTERION_PROVIDER)"

asterion-verify-preflight:
	uv run asterion verify --provider "$(ASTERION_PROVIDER)" --level preflight --env-file "$(ASTERION_ENV_FILE)" --corpus-root "$(ASTERION_CORPUS_ROOT)"

asterion-verify-basic:
	uv run asterion verify --provider "$(ASTERION_PROVIDER)" --level basic --env-file "$(ASTERION_ENV_FILE)" --corpus-root "$(ASTERION_CORPUS_ROOT)" --output-root "$(ASTERION_VERIFY_OUTPUT_ROOT)"

asterion-verify-acceptance:
	uv run asterion verify --provider "$(ASTERION_PROVIDER)" --level acceptance

asterion-verify-complete:
	uv run asterion verify --provider "$(ASTERION_PROVIDER)" --level complete --env-file "$(ASTERION_ENV_FILE)" --corpus-root "$(ASTERION_CORPUS_ROOT)" --output-root "$(ASTERION_VERIFY_OUTPUT_ROOT)"
```

- [ ] **Step 4: Run focused and dry-run verification**

Run:

```bash
uv run python -m unittest tests.test_makefile_entrypoints -v
make -n asterion-describe
make -n asterion-verify-preflight
make -n asterion-verify-basic
make -n asterion-verify-acceptance
make -n asterion-verify-complete
```

Expected: all tests PASS; every dry run renders the matching fixed CLI level and none executes Asterion.

- [ ] **Step 5: Commit the Make target contract**

```bash
git add Makefile tests/test_makefile_entrypoints.py
git commit -m "feat: add Asterion Make verification targets"
```

### Task 2: User-facing Make workflow

**Files:**
- Modify: `README.md`
- Modify: `docs/guides/asterion-capability-usage.md`
- Modify: `tests/test_distribution_boundaries.py`

**Interfaces:**
- Consumes: the five Make targets from Task 1.
- Produces: discoverable quick-start documentation that keeps the full CLI canonical.

- [ ] **Step 1: Extend the documentation boundary test first**

In `SourceDistributionBoundaryTests.test_asterion_capability_beginner_guide_is_complete`, require all five `make asterion-*` commands in the guide. Also require `make asterion-describe` and `make asterion-verify-acceptance` in README, plus text distinguishing provider-free `preflight/acceptance` from provider-backed `basic/complete`.

- [ ] **Step 2: Run the documentation test and verify RED**

Run:

```bash
uv run python -m unittest tests.test_distribution_boundaries.SourceDistributionBoundaryTests.test_asterion_capability_beginner_guide_is_complete -v
```

Expected: FAIL because README and the guide do not name the new targets.

- [ ] **Step 3: Document the Make equivalents**

Add this source-checkout quick list near the guide's five-minute CLI flow and near README's existing Asterion example section:

```text
make asterion-describe
make asterion-verify-preflight
make asterion-verify-basic
make asterion-verify-acceptance
make asterion-verify-complete
```

State that `preflight` and `acceptance` are provider-free, while `basic` and `complete` run two bounded Pi operations and one Judge operation. Show one override example using `ASTERION_CORPUS_ROOT`; retain the full `uv run asterion` commands as the installed/canonical interface.

- [ ] **Step 4: Run focused documentation and Make tests**

Run:

```bash
uv run python -m unittest tests.test_makefile_entrypoints tests.test_distribution_boundaries.SourceDistributionBoundaryTests.test_asterion_capability_beginner_guide_is_complete -v
```

Expected: PASS.

- [ ] **Step 5: Commit the documented workflow**

```bash
git add README.md docs/guides/asterion-capability-usage.md tests/test_distribution_boundaries.py
git commit -m "docs: document Asterion Make workflow"
```

### Task 3: Safe smoke checks and AF-280 closure

**Files:**
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- Consumes: Tasks 1 and 2 plus the accepted AF-270 verifier.
- Produces: verified provider-free operator entry points and a terminal governed state.

- [ ] **Step 1: Run provider-free live smoke checks**

Run:

```bash
make asterion-describe
make asterion-verify-acceptance
```

Expected: description renders successfully; acceptance reports PASS with provider-backed operations `0` and full dataset `no`.

- [ ] **Step 2: Run bounded closure gates**

Run:

```bash
uv run python -m unittest tests.test_makefile_entrypoints tests.test_distribution_boundaries -v
uv run python -m compileall -q tests/test_makefile_entrypoints.py
uv run ruff check tests/test_makefile_entrypoints.py tests/test_distribution_boundaries.py
python3 tools/project_scope_check.py
git diff --check
```

Expected: all commands exit zero while AF-280 is active.

- [ ] **Step 3: Close AF-280 state**

Set AF-280 to `completed`, lifecycle to `complete`, active package to none, and record exact verification evidence. Rewrite the resume baton as an AF-280 completion checkpoint; do not alter previous journal lines.

- [ ] **Step 4: Verify terminal governance**

Run:

```bash
python3 tools/project_scope_check.py
uv run python -m unittest tests.test_project_scope_check tests.test_climb_tools.ClimbToolTests.test_resume_checkpoint_tracks_the_worklist_active_package -v
git diff --check
```

Expected: scope JSON reports `active_package: null`, `lifecycle: complete`, and no errors; tests pass.

- [ ] **Step 5: Commit closure**

```bash
git add docs/status
git commit -m "docs: close Asterion Make entry points"
```
