# AF-350 Asterion Standalone Promotion Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `subagent-driven-development` when the user explicitly authorizes sub-agents;
> otherwise execute this plan inline task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** Make the contents of `asterion/` directly promotable to a GitHub
repository root whose provider-free build, tests, installed CLI acceptance,
documentation, TypeScript, Rust, Makefile, and clean-copy promotion gate run
without the parent DCI-Agent-Lite tree.

**Architecture:** Treat `asterion/` as the sole standalone project root in both
nested and promoted placements. Move installed acceptance into package-owned
Python/resource validation, keep the mixed-root 538-selector verifier as a
separately named integration gate, and prove independence by copying the subtree
to a temporary directory and rebuilding/installing/testing it there.

**Tech Stack:** Python 3.10+, Hatchling, uv, `unittest`, Ruff, GNU Make-compatible
Make, Bash, Node.js 20/npm, TypeScript, Rust/Cargo, GitHub Actions, Markdown.

## Global Constraints

- Active work package is `AF-350`; run `python3 tools/project_scope_check.py`
  before implementation and again before package closure.
- Follow D-056: standalone acceptance owns installed package/resource closure;
  `tools/verify_asterion_dci_product.py` owns mixed-root original DCI/Asterion
  integration parity and its 538 selectors.
- Do not run an Agent, Judge, provider-backed example, full dataset, paper
  reproduction, repository publication, remote push, or release.
- Do not edit, copy, commit, or clean the external `pi/` repository. Pi, corpora,
  benchmark datasets, credentials, and outputs remain external resources.
- Preserve Python import names, wheel/console-script names, provider IDs,
  application IDs, runtime IDs, wire schemas, and packaged resource identities.
- Never persist a credential or realistic-looking key. `.env.template` uses
  empty values and comments only; promotion and CI are provider-free.
- Write tests first, observe the intended RED, implement the smallest change,
  observe GREEN, and commit each cohesive task. Journal every nontrivial commit.
- Never commit a RED test or partial task. A task's tests and implementation land
  together only after its focused GREEN verification.
- Use `apply_patch` for hand-edited files. Generated lockfiles may be produced by
  their native formatter/generator.
- Keep root-level temporary planning files local and uncommitted. Durable truth
  belongs only in `docs/status/` through the project-state policy.

---

### Task 1: Add the standalone repository contract tests

**Files:**

- Create: `asterion/tests/test_standalone_repository.py`
- Modify: `asterion/tests/test_project_boundary.py`

**Interfaces:**

- Defines the required root assets, Make target names, safe-template rules,
  launcher path rules, and installed acceptance result expected by later tasks.
- Uses only the `asterion/` subtree and package APIs; it must not import root
  `tools` or root `tests`.

- [ ] **Step 1: Add failing repository-asset and safe-template tests**

Create `asterion/tests/test_standalone_repository.py` with these exact contract
constants and test responsibilities:

```python
from __future__ import annotations

import re
import shlex
import subprocess
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
REQUIRED_ASSETS = (
    ".env.template",
    ".gitignore",
    "LICENSE",
    "Makefile",
    "README.md",
    "pi-revision.txt",
    "uv.lock",
)
LIFECYCLE_TARGETS = (
    "help", "sync", "build", "test", "lint", "docs-check", "check",
    "promotion-check",
)
FRAMEWORK_TARGETS = (
    "asterion-list", "asterion-describe", "asterion-verify-preflight",
    "asterion-verify-basic", "asterion-verify-acceptance",
    "asterion-verify-complete", "asterion-run",
)
DCI_TARGETS = (
    "dci-system-prompt", "dci-run", "dci-terminal", "dci-resume",
    "dci-evaluate", "dci-benchmark", "dci-export", "dci-ablation",
    "dci-paper",
)
CROSS_LANGUAGE_TARGETS = ("test-typescript", "test-rust", "check-rust")


class StandaloneRepositoryTests(unittest.TestCase):
    def test_required_repository_assets_exist(self) -> None:
        missing = [name for name in REQUIRED_ASSETS if not (PROJECT / name).is_file()]
        self.assertEqual(missing, [])

    def test_environment_template_has_no_credentials_or_parent_defaults(self) -> None:
        text = (PROJECT / ".env.template").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?m)^[A-Z0-9_]*(?:KEY|TOKEN|SECRET)=.+$")
        self.assertNotIn("../", text)
        self.assertNotIn("pi-mono", text)

    def test_makefile_exposes_the_complete_explicit_command_surface(self) -> None:
        text = (PROJECT / "Makefile").read_text(encoding="utf-8")
        phony = {
            token
            for line in text.splitlines()
            if line.startswith(".PHONY:")
            for token in line.removeprefix(".PHONY:").split()
        }
        expected = set(
            LIFECYCLE_TARGETS + FRAMEWORK_TARGETS + DCI_TARGETS
            + CROSS_LANGUAGE_TARGETS
        )
        self.assertTrue(expected.issubset(phony), sorted(expected - phony))
        self.assertNotRegex(text, r"(?m)^asterion-verify:\s*$")
        self.assertNotIn("eval ", text)

    def test_make_help_labels_cost_boundaries(self) -> None:
        completed = subprocess.run(
            ["make", "help"], cwd=PROJECT, check=True,
            capture_output=True, text=True,
        )
        self.assertIn("provider-free", completed.stdout)
        self.assertIn("bounded provider-backed", completed.stdout)
        self.assertIn("full execution requires separate authorization", completed.stdout)

    def test_make_passthrough_arguments_are_not_shell_evaluated(self) -> None:
        completed = subprocess.run(
            ["make", "-n", "asterion-run", "ASTERION_ARGS=--help"],
            cwd=PROJECT, check=True, capture_output=True, text=True,
        )
        self.assertEqual(
            tuple(shlex.split(completed.stdout)),
            ("uv", "run", "asterion", "run", "--help"),
        )

if __name__ == "__main__":
    unittest.main()
```

Extend `test_project_boundary.py` with a recursive text scan over project-owned
source, tests, tools, scripts, docs, README, Makefile, and CI. Permit explicit
documentation phrases such as “mixed repository” but reject operational parent
dependencies: `--project asterion`, `../src/dci`, `../tools`, the developer's
absolute workspace path, and launcher `../../..` root traversal. Limit this
first scan to repository metadata and Python production/test files; launcher and
documentation scans are added with their own RED/GREEN tasks.

- [ ] **Step 2: Run the new tests and observe RED**

```bash
(cd asterion && uv run python -m unittest -v \
  tests.test_standalone_repository \
  tests.test_project_boundary)
```

Expected: missing repository assets and incomplete Make surface. Do not broaden
the test to acceptance, launchers, docs, or CI before their corresponding task.

- [ ] **Step 3: Keep RED changes uncommitted and continue directly to Task 2**

Do not checkpoint or commit the failing tests. Task 2 implements their contract,
runs them GREEN, and commits the tests and implementation atomically.

---

### Task 2: Add the repository skeleton and complete Make command surface

**Files:**

- Create: `asterion/README.md`
- Create: `asterion/LICENSE`
- Create: `asterion/.gitignore`
- Create: `asterion/.env.template`
- Create: `asterion/Makefile`
- Create: `asterion/pi-revision.txt`
- Create: `asterion/uv.lock` (generated)
- Create: `asterion/tools/__init__.py`
- Modify: `asterion/pyproject.toml`
- Modify: `asterion/tests/test_standalone_repository.py`

**Interfaces:**

- `make help` is the discoverable command index.
- `ASTERION_ARGS` and `DCI_ARGS` are literal Make argument lists; recipes never
  call shell `eval`.
- `uv sync --frozen` must succeed after copying `asterion/` to a clean directory.

- [ ] **Step 1: Add exact Make dry-run expectations before implementation**

Extend `test_standalone_repository.py` so `make -n` asserts these command stems:

```text
asterion-list              -> uv run asterion list
asterion-describe          -> uv run asterion describe --provider dci-agent-lite
asterion-verify-preflight  -> uv run asterion verify --provider dci-agent-lite --level preflight $(ASTERION_ARGS)
asterion-verify-basic      -> uv run asterion verify --provider dci-agent-lite --level basic $(ASTERION_ARGS)
asterion-verify-acceptance -> uv run asterion verify --provider dci-agent-lite --level acceptance $(ASTERION_ARGS)
asterion-verify-complete   -> uv run asterion verify --provider dci-agent-lite --level complete $(ASTERION_ARGS)
asterion-run               -> uv run asterion run $(ASTERION_ARGS)
dci-system-prompt          -> uv run asterion-dci system-prompt $(DCI_ARGS)
dci-run                    -> uv run asterion-dci run $(DCI_ARGS)
dci-terminal               -> uv run asterion-dci terminal $(DCI_ARGS)
dci-resume                 -> uv run asterion-dci resume $(DCI_ARGS)
dci-evaluate               -> uv run asterion-dci evaluate $(DCI_ARGS)
dci-benchmark              -> uv run asterion-dci benchmark $(DCI_ARGS)
dci-export                 -> uv run asterion-dci export $(DCI_ARGS)
dci-ablation               -> uv run asterion-dci ablation $(DCI_ARGS)
dci-paper                  -> uv run asterion-dci paper $(DCI_ARGS)
```

Assert lifecycle and cross-language recipes render the exact native tools named
in the design, including `python -m unittest discover -s tests -v`, `compileall`,
`ruff`, `uv build`, npm runtime then extension tests, and Cargo test/fmt/Clippy.

- [ ] **Step 2: Create repository-owned root assets**

Copy the root MIT license terms while preserving the existing copyright. Copy
the exact pinned Pi revision from root `pi-revision.txt`. Build `.gitignore`
around these categories: `.env` and secret variants, `.venv`, Python caches,
coverage/build artifacts, `node_modules`, Cargo `target`, editor caches, `pi/`,
`pi-mono/`, corpora, datasets, outputs, and temporary promotion directories.

Create `.env.template` with standalone-relative, non-secret examples only:

```dotenv
# Copy to .env and fill only the provider-backed settings you intend to use.
DCI_PI_DIR=./pi
DCI_OUTPUT_ROOT=./outputs
ASTERION_DCI_RESOURCE_ROOT=.
ASTERION_RUNTIME=pi
ASTERION_PROVIDER=
ASTERION_MODEL=
ASTERION_API_KEY=
ASTERION_DCI_JUDGE_MODEL=
ASTERION_DCI_JUDGE_API_KEY=
```

The README implemented in Task 5 will document the full configuration surface;
the template must not invent aliases absent from shared configuration. Adjust
variable names after checking `asterion/src/asterion/dci/config.py`, but retain
the empty-secret and standalone-relative invariant.

- [ ] **Step 3: Implement the Makefile**

Use explicit phony recipes and these variables:

```make
UV ?= uv
PYTHON := $(UV) run python
ASTERION_PROVIDER ?= dci-agent-lite
ASTERION_ARGS ?=
DCI_ARGS ?=

.PHONY: help sync build test lint docs-check check promotion-check \
	asterion-list asterion-describe asterion-verify-preflight \
	asterion-verify-basic asterion-verify-acceptance \
	asterion-verify-complete asterion-run dci-system-prompt dci-run \
	dci-terminal dci-resume dci-evaluate dci-benchmark dci-export \
	dci-ablation dci-paper test-typescript test-rust check-rust

sync:
	$(UV) sync --frozen

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m compileall -q src tests tools
	$(UV) run ruff check src tests tools

build:
	$(UV) build .

docs-check:
	$(PYTHON) tools/check_docs.py

asterion-list:
	$(UV) run asterion list $(ASTERION_ARGS)

asterion-describe:
	$(UV) run asterion describe --provider $(ASTERION_PROVIDER) $(ASTERION_ARGS)

asterion-verify-acceptance:
	$(UV) run asterion verify --provider $(ASTERION_PROVIDER) --level acceptance $(ASTERION_ARGS)

promotion-check:
	$(PYTHON) tools/check_promotion.py
```

Add the remaining approved commands as the direct equivalents above. `check`
depends only on provider-free source gates. Do not make `preflight`, `basic`,
`complete`, `run`, or any DCI execution target a dependency of `check`.

- [ ] **Step 4: Make package metadata self-describing and generate a lock**

Add `readme = "README.md"` and `license = { file = "LICENSE" }` to
`asterion/pyproject.toml`. Add a Ruff development dependency through a
`[dependency-groups] dev` table so `make lint` works after `uv sync --frozen`.
Do not remove runtime dependencies without a separate import/runtime audit.

Generate the standalone lock from a temporary copy so the parent uv workspace
cannot influence it:

```bash
promotion_tmp="$(mktemp -d)"
cp -R asterion/. "$promotion_tmp/"
(cd "$promotion_tmp" && uv lock)
cp "$promotion_tmp/uv.lock" asterion/uv.lock
```

Inspect the lock header and run `uv lock --check` inside another clean copy.

- [ ] **Step 5: Run focused tests and provider-free lifecycle gates**

```bash
(cd asterion && uv run python -m unittest -v \
  tests.test_standalone_repository \
  tests.test_project_boundary)
make -C asterion sync
make -C asterion test
make -C asterion lint
make -C asterion build
```

At this point `docs-check` and `promotion-check` may remain unavailable until
Tasks 5 and 6; all implemented targets must pass.

- [ ] **Step 6: Commit the standalone skeleton**

```bash
git add asterion/README.md asterion/LICENSE asterion/.gitignore \
  asterion/.env.template asterion/Makefile asterion/pi-revision.txt \
  asterion/uv.lock asterion/pyproject.toml asterion/tools/__init__.py \
  asterion/tests/test_standalone_repository.py \
  asterion/tests/test_project_boundary.py
git commit -m "build(asterion): add standalone repository skeleton"
```

Journal the commit and the clean-copy `uv lock --check` result.

---

### Task 3: Replace mixed-root dynamic acceptance with package-owned acceptance

**Files:**

- Create: `asterion/tests/test_asterion_dci_verification.py`
- Modify: `asterion/src/asterion/dci/verification.py`
- Modify: `asterion/tests/test_asterion_cli.py`
- Modify: `tests/test_asterion_dci_verification.py`

**Interfaces:**

- `DciProductVerifier.acceptance(Path | None) -> VerificationResult` validates
  immutable installed providers and packaged contracts only.
- It returns seven sorted checks, zero provider-backed operations, and
  `full_dataset_ran=False` from source or wheel and any current directory.
- The mixed-root verifier remains callable only through its root tool/test path.

- [ ] **Step 1: Move acceptance ownership expectations into package tests**

Create package tests for:

1. both built-in provider factories pass `validate_installed_provider`;
2. exact providers = 2, applications = 3, bound assemblies = 5;
3. packaged assembly JSON inventory = 6 and capability manifests = 11;
4. context profile count equals 5;
5. paper benchmark and paper scope identities load through their public
   resolvers and have nonempty canonical SHA-256 identities;
6. acceptance uses no backend method and ignores `acceptance_root`/`cwd`;
7. mutating a copied resource makes the corresponding public validator fail,
   rather than acceptance silently counting filenames.

In `asterion/tests/test_asterion_cli.py`, add tests that invoke:

```python
code = main(
    ["verify", "--provider", "dci-agent-lite", "--level", "acceptance", "--json"],
    stdout=stdout,
    stderr=stderr,
)
payload = json.loads(stdout.getvalue())
self.assertEqual(code, 0, stderr.getvalue())
self.assertEqual(payload["status"], "PASS")
self.assertEqual(payload["provider_backed_operation_count"], 0)
self.assertFalse(payload["full_dataset_ran"])
self.assertEqual(
    [item["check_id"] for item in payload["checks"]],
    [
        "application-assemblies",
        "application-providers",
        "capability-manifests",
        "context-profiles",
        "paper-benchmarks",
        "paper-scopes",
        "provider-requests",
    ],
)
```

Add a second test that changes `cwd` to an empty temporary directory before the
same invocation and asserts the identical JSON payload. Add a third unit test
using a backend whose methods raise if called and assert acceptance never calls
the backend.

Delete root-test imports and cases for `_load_product_acceptance_runner`,
`ProductAcceptanceSummary`, `acceptance_runner`,
`acceptance_source_root`, and `_trusted_source_checkout_root`. Retain a root
integration test that directly calls `verify_product_acceptance(ROOT)` and
asserts `product_rows == (8, 8)`, `delegated_inventory == (538, 538)`, and zero
provider-backed executions.

- [ ] **Step 2: Run the acceptance tests and observe RED**

```bash
(cd asterion && uv run python -m unittest -v \
  tests.test_asterion_dci_verification \
  tests.test_asterion_cli)
uv run python -m unittest -v tests.test_asterion_dci_verification
```

Expected: package acceptance cannot run independently and the old root dynamic
loader fields/tests conflict with the new contract.

- [ ] **Step 3: Implement pure package acceptance**

Remove `importlib.util`, `sys`, `Callable`, `_run_product_acceptance`,
`_load_product_acceptance_runner`, `_trusted_source_checkout_root`, and the two
acceptance injection fields. Add package-owned helpers with this shape:

```python
def _acceptance_check(
    check_id: str, summary: str, *, actual: int, expected: int
) -> VerificationCheckResult:
    passed = actual == expected
    return VerificationCheckResult(
        check_id=check_id,
        summary=summary if passed else f"{summary} is incomplete",
        status="PASS" if passed else "FAIL",
        counts=(("actual", actual), ("expected", expected)),
    )


def _installed_acceptance_checks() -> tuple[VerificationCheckResult, ...]:
    from asterion.applications.controlled_code import create_provider as controlled
    from asterion.applications.dci_agent_lite import create_provider as dci
    from asterion.applications.provider import validate_installed_provider
    from asterion.packages.catalog import discover_packages

    providers = (
        validate_installed_provider(controlled(), selected_id="controlled-code"),
        validate_installed_provider(dci(), selected_id="dci-agent-lite"),
    )
    applications = tuple(app for provider in providers for app in provider.applications)
    bound_assemblies = tuple(path for app in applications for path in app.assembly_paths)
    catalog_roots = tuple(
        dict.fromkeys(root for app in applications for root in app.catalog_roots)
    )
    manifests = discover_packages(catalog_roots).entries
    package_root = Path(str(resources.files("asterion"))).resolve()
    packaged_assemblies = tuple(
        sorted((package_root / "applications").glob("*/assemblies/*.json"))
    )
    datasets = paper_benchmark_ids()
    scopes = paper_experiment_scope_ids()
    for dataset_id in datasets:
        resolve_paper_benchmark(dataset_id)
    for scope_id in scopes:
        resolve_paper_experiment_scope(scope_id)
    paper_benchmark_inventory_sha256()
    paper_experiment_scopes_sha256()
    return tuple(sorted((
        _acceptance_check("application-assemblies", "Application assembly closure is valid", actual=len(packaged_assemblies), expected=6),
        _acceptance_check("application-providers", "Installed provider closure is valid", actual=len(providers), expected=2),
        _acceptance_check("capability-manifests", "Capability manifest closure is valid", actual=len(manifests), expected=11),
        _acceptance_check("context-profiles", "Context profile closure is valid", actual=len(context_profile_names()), expected=5),
        _acceptance_check("paper-benchmarks", "Paper benchmark identity closure is valid", actual=len(datasets), expected=13),
        _acceptance_check("paper-scopes", "Paper scope identity closure is valid", actual=len(scopes), expected=16),
        _acceptance_check("provider-requests", "Installed acceptance made no provider requests", actual=0, expected=0),
    ), key=lambda item: item.check_id))
```

Before committing exact `13`/`16`, evaluate the public functions in the current
package and use their verified exact values; update tests and code together if
the source contract differs. Do not count raw JSON alone where a public loader
already validates identities and schemas.

Replace `acceptance()` with exception-to-FAIL behavior over
`_installed_acceptance_checks()`. Do not return `NOT RUN` merely because a mixed
checkout is absent. `create_dci_product()` now constructs only
`DciProductVerifier(repo_root=root, backend=...)`.

- [ ] **Step 4: Verify source and isolated wheel acceptance**

```bash
(cd asterion && uv run python -m unittest -v \
  tests.test_asterion_dci_verification \
  tests.test_asterion_cli)
uv run --project asterion asterion verify \
  --provider dci-agent-lite --level acceptance --json
uv build asterion
wheel_tmp="$(mktemp -d)"
uv venv "$wheel_tmp/.venv"
uv pip install --python "$wheel_tmp/.venv/bin/python" \
  "$(find dist -maxdepth 1 -name 'asterion-*.whl' -print -quit)"
(cd "$wheel_tmp" && "$wheel_tmp/.venv/bin/asterion" verify \
  --provider dci-agent-lite --level acceptance --json)
uv run python -m unittest -v tests.test_asterion_dci_verification
```

Compare normalized source/wheel JSON exactly. Both must say PASS, zero provider
operations, and no full dataset.

- [ ] **Step 5: Commit acceptance ownership separation**

```bash
git add asterion/src/asterion/dci/verification.py \
  asterion/tests/test_asterion_dci_verification.py \
  asterion/tests/test_asterion_cli.py tests/test_asterion_dci_verification.py
git commit -m "refactor(asterion): own standalone acceptance in package"
```

Journal source/wheel parity and the retained 538-selector integration result.

---

### Task 4: Make all launchers resolve the standalone root

**Files:**

- Modify: all `asterion/scripts/{bcplus_eval,beir,bright,qa}/*.sh`
- Create: `asterion/tests/test_standalone_launchers.py`
- Modify: root launcher tests selected by `rg -l 'REPO_ROOT|--project.*asterion' tests`

**Interfaces:**

- Every launcher computes `PROJECT_ROOT` as `SCRIPT_DIR/../..`.
- Every launcher uses `uv run --project "$PROJECT_ROOT"`.
- Data/corpus defaults resolve from
  `ASTERION_DCI_RESOURCE_ROOT:-$PROJECT_ROOT`.

- [ ] **Step 1: Add failing static and sandbox launcher tests**

The new test enumerates every shell file under `scripts/`, runs `bash -n`, and
asserts:

```python
self.assertIn('PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"', text)
self.assertIn('RESOURCE_ROOT="${ASTERION_DCI_RESOURCE_ROOT:-$PROJECT_ROOT}"', text)
self.assertIn('uv run --project "$PROJECT_ROOT"', text)
self.assertNotIn("REPO_ROOT", text)
self.assertNotIn("../../..", text)
self.assertNotIn("$PROJECT_ROOT/asterion", text)
```

Add a temporary-copy dry-run fixture for one QA, one IR, one BRIGHT, and BC+
launcher. Use an injected fake `uv` executable that records argv and exits before
any provider construction. Assert the recorded `--project` path is the copied
root and resource arguments use the configured external root.

- [ ] **Step 2: Run tests and observe RED**

```bash
(cd asterion && uv run python -m unittest -v \
  tests.test_standalone_launchers)
```

- [ ] **Step 3: Patch every launcher mechanically**

For each script, replace the mixed-root prelude:

```bash
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
RESOURCE_ROOT="${ASTERION_DCI_RESOURCE_ROOT:-$REPO_ROOT}"
uv run --project "$REPO_ROOT/asterion" ...
```

with:

```bash
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESOURCE_ROOT="${ASTERION_DCI_RESOURCE_ROOT:-$PROJECT_ROOT}"
uv run --project "$PROJECT_ROOT" ...
```

Keep benchmark IDs, selection IDs, profile IDs, output paths, provider flags,
and all execution semantics unchanged.

- [ ] **Step 4: Verify shell syntax and launcher contracts**

```bash
find asterion/scripts -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
(cd asterion && uv run python -m unittest -v \
  tests.test_standalone_launchers)
uv run python -m unittest discover -v -s tests -p '*launcher*.py'
```

- [ ] **Step 5: Commit launcher root independence**

```bash
git add asterion/scripts asterion/tests/test_standalone_launchers.py tests
git commit -m "fix(asterion): resolve launchers from project root"
```

Stage only root tests actually changed; do not sweep unrelated `tests/` changes.
Journal the exact launcher count and syntax result.

---

### Task 5: Make standalone documentation complete and locally verifiable

**Files:**

- Modify: `asterion/README.md`
- Create: `asterion/tools/check_docs.py`
- Modify: `asterion/docs/README.md`
- Modify: `asterion/docs/architecture/agent-framework.md`
- Modify: `asterion/docs/architecture/asterion-standalone-extraction.md`
- Modify: `asterion/docs/guides/asterion-capability-usage.md`
- Modify: `asterion/docs/guides/asterion-dci-complete-reference.md`
- Modify: `asterion/docs/verification/asterion-dci-validation-guide.md`
- Modify: `asterion/tests/test_standalone_repository.py`
- Modify: `tests/test_asterion_documentation.py`

**Interfaces:**

- `python tools/check_docs.py` checks README plus every Markdown file under
  `docs/`, resolves relative links inside the standalone root, and rejects
  machine-absolute or mixed-root operational references.
- Standalone commands use the promoted root form (`uv run ...`, `make ...`).
- Historical 90/1230 or 533/538 counts are either removed or explicitly labeled
  historical; no stale count is presented as current standalone acceptance.

- [ ] **Step 1: Write failing docs checker and content assertions**

Add tests that require README sections for installation, discovery, acceptance,
external Pi/resources, cost boundaries, development, promotion, and integration
parity. Require all local Markdown links to resolve after copying `asterion/` to
a temporary directory. Reject:

```text
uv run --project asterion
../../../docs/superpowers/
/Users/sujiangwen/
tools/verify_asterion_dci_product.py   (unless labeled mixed-repository only)
90 tests
1230 tests
```

At this point extend the required standalone asset list with
`tools/check_docs.py`; it was intentionally absent from the Task 1/2 skeleton
contract so those tasks could close GREEN before the real checker is added.

Update the root documentation test so it validates the standalone hub and
integration-only label without requiring links from `asterion/docs` into parent
governance documents.

- [ ] **Step 2: Run docs tests and observe RED**

```bash
(cd asterion && uv run python -m unittest -v \
  tests.test_standalone_repository)
uv run python -m unittest -v tests.test_asterion_documentation
```

- [ ] **Step 3: Implement the standalone link checker**

`tools/check_docs.py` must:

1. set `root = Path(__file__).resolve().parents[1]`;
2. enumerate `README.md` and `docs/**/*.md` deterministically;
3. extract inline Markdown links, skip `http`, `https`, `mailto`, and pure
   anchors;
4. URL-decode the path, drop the fragment, resolve it against the source file;
5. fail if the target escapes `root`, is absolute, or does not exist;
6. reject the operational forbidden strings above;
7. print only a concise checked-file/link count and return nonzero on failure.

Unit-test escaped links, anchors, URL encoding, missing links, and parent escapes.

- [ ] **Step 4: Rewrite the landing and verification path**

Make README the standalone quick start:

```bash
uv sync --frozen
uv run asterion list
uv run asterion describe --provider dci-agent-lite
uv run asterion verify --provider dci-agent-lite --level acceptance
make check
make promotion-check
```

Document `DCI_PI_DIR`, `ASTERION_DCI_RESOURCE_ROOT`, `.env`, external corpora and
datasets, and provider/ Judge credentials as optional cost-bearing setup. State
that `acceptance` is provider-free installed closure; `preflight`, `basic`, and
`complete` have different cost/resource boundaries. State that the 538-selector
matrix remains a DCI-Agent-Lite mixed-repository integration gate, not a
standalone live result.

Update the validation guide and complete reference to use command-based current
verification. Where historical test totals remain useful, label them with their
date/commit and never use them as current acceptance criteria.

- [ ] **Step 5: Verify all documentation locally and in a copied subtree**

```bash
make -C asterion docs-check
(cd asterion && uv run python -m unittest -v \
  tests.test_standalone_repository)
uv run python -m unittest -v tests.test_asterion_documentation
docs_tmp="$(mktemp -d)"
cp -R asterion/. "$docs_tmp/"
(cd "$docs_tmp" && uv run python tools/check_docs.py)
```

- [ ] **Step 6: Commit standalone documentation**

```bash
git add asterion/README.md asterion/tools/check_docs.py asterion/docs \
  asterion/tests/test_standalone_repository.py tests/test_asterion_documentation.py
git commit -m "docs(asterion): complete standalone usage and validation"
```

Journal the link/file totals and the removal/classification of stale counts.

---

### Task 6: Add the clean-copy promotion gate and provider-free CI

**Files:**

- Create: `asterion/tools/check_promotion.py`
- Create: `asterion/tests/test_check_promotion.py`
- Create: `asterion/.github/workflows/ci.yml`
- Modify: `asterion/Makefile`
- Modify: `asterion/tests/test_standalone_repository.py`

**Interfaces:**

- `python tools/check_promotion.py [--quick]` copies the project to a temporary
  root, audits the copy, and runs standalone gates without parent state.
- Default mode runs the full provider-free Python/docs/Node/Rust sequence.
- `--quick` runs deterministic copy/audit/Python CLI smoke suitable for unit
  tests, while CI and `make promotion-check` use default full mode.

- [ ] **Step 1: Write failing promotion-tool tests**

Tests must inject a subprocess runner and temporary source tree to assert:

- excluded directories/files: `.git`, `.venv`, `.env`, caches, `node_modules`,
  Cargo `target`, `dist`, `outputs`, corpora, datasets, `pi`, `pi-mono`;
- symlinks are rejected, not followed;
- required assets are checked in the copy;
- absolute machine paths and operational parent references fail the audit;
- command cwd is always the copied root;
- default commands include frozen sync, tests, compile, Ruff, build, isolated
  wheel install plus `list`/`describe`/`acceptance`, docs, npm, and Cargo;
- no command includes provider-backed/basic/complete/full/paper execution.

Extend `test_standalone_repository.py` at this point so the required asset list
also includes `.github/workflows/ci.yml` and `tools/check_promotion.py`, and add
the provider-free CI assertions that reject `API_KEY`, `provider-backed`,
`verify-basic`, and `verify-complete` while requiring `make promotion-check`.

- [ ] **Step 2: Run tests and observe RED**

```bash
(cd asterion && uv run python -m unittest -v \
  tests.test_check_promotion \
  tests.test_standalone_repository)
```

- [ ] **Step 3: Implement promotion copying and audit**

Use `tempfile.TemporaryDirectory`, `shutil.copytree`, and explicit ignore names.
Before copying, reject every symlink under the source root. After copying, assert
the required assets and recursively scan project-owned text suffixes for:

```python
FORBIDDEN = (
    "/Users/sujiangwen/",
    "--project asterion",
    "../src/dci",
    "../tools/verify_asterion_dci_product.py",
)
```

Do not reject explanatory prose merely containing “mixed repository”. The
default command plan, all with `cwd=copy_root`, is:

```text
uv sync --frozen
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests tools
uv run ruff check src tests tools
uv build .
uv venv <private wheel venv>
uv pip install --python <private python> <built wheel>
<private>/asterion list
<private>/asterion describe --provider dci-agent-lite --json
<private>/asterion verify --provider dci-agent-lite --level acceptance --json
uv run python tools/check_docs.py
npm ci --prefix packages/typescript/asterion-runtime
npm test --prefix packages/typescript/asterion-runtime
npm test --prefix packages/typescript/dci-context-extension
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
cargo fmt --manifest-path packages/rust/controlled-executor/Cargo.toml -- --check
cargo clippy --manifest-path packages/rust/controlled-executor/Cargo.toml -- -D warnings
```

If the extension needs the runtime build first, preserve the existing tested npm
ordering. Capture subprocess output and on failure report command plus a bounded
tail; never print environment values. Parse the installed acceptance JSON and
assert PASS, zero provider operations, and no full dataset.

- [ ] **Step 4: Add provider-free CI**

Create one Ubuntu workflow triggered by pull requests and pushes. Pin maintained
setup actions by major version, install Python 3.10 and uv, Node 20, and stable
Rust, then run `make promotion-check`. Do not declare secrets, API keys, network
providers, datasets, caches containing `.env`, or publishing permissions. Set
workflow permissions to `contents: read`.

- [ ] **Step 5: Verify promotion unit tests and one full promotion copy**

```bash
(cd asterion && uv run python -m unittest -v \
  tests.test_check_promotion \
  tests.test_standalone_repository)
make -C asterion promotion-check
```

Record exact Python/Node/Rust results. If a platform tool is genuinely absent,
do not weaken the gate; install/use the documented toolchain or report the
environmental blocker.

- [ ] **Step 6: Commit promotion automation**

```bash
git add asterion/tools/check_promotion.py \
  asterion/tests/test_check_promotion.py \
  asterion/.github/workflows/ci.yml asterion/Makefile \
  asterion/tests/test_standalone_repository.py
git commit -m "ci(asterion): verify clean standalone promotion"
```

Journal the full clean-copy result and confirm zero provider operations.

---

### Task 7: Delegate mixed-root commands and preserve integration parity

**Files:**

- Modify: `Makefile`
- Modify: `tests/test_makefile_entrypoints.py`
- Modify: `tests/test_asterion_distribution.py`
- Modify: `tests/test_asterion_documentation.py`
- Modify: `tests/test_asterion_dci_verification.py`

**Interfaces:**

- Shared root targets delegate to `$(MAKE) -C asterion <target>`.
- New root target `asterion-integration-acceptance` directly runs
  `tools/verify_asterion_dci_product.py` and remains provider-free.
- Root integration tests continue to assert 8/8 rows, 538/538 selectors, and
  zero provider-backed execution.

- [ ] **Step 1: Write failing root delegation tests**

Change Make dry-run expectations so the five existing discovery/verification
targets delegate to the nested project. Assert `asterion-integration-acceptance`
is phony, exact, and not a dependency of standalone `asterion-verify-acceptance`.
Add explicit assertions that provider-backed and full execution are not pulled
into any provider-free aggregate target.

- [ ] **Step 2: Run root contract tests and observe RED**

```bash
uv run python -m unittest -v \
  tests.test_makefile_entrypoints \
  tests.test_asterion_distribution \
  tests.test_asterion_documentation \
  tests.test_asterion_dci_verification
```

- [ ] **Step 3: Delegate root targets and name integration explicitly**

Use direct recursive Make recipes, forwarding only named variables:

```make
asterion-describe:
	$(MAKE) -C asterion asterion-describe \
		ASTERION_PROVIDER="$(ASTERION_PROVIDER)" ASTERION_ARGS="$(ASTERION_ARGS)"

asterion-verify-acceptance:
	$(MAKE) -C asterion asterion-verify-acceptance \
		ASTERION_PROVIDER="$(ASTERION_PROVIDER)" ASTERION_ARGS="$(ASTERION_ARGS)"

asterion-integration-acceptance:
	uv run python tools/verify_asterion_dci_product.py
```

Forward preflight/basic/complete arguments through `ASTERION_ARGS`; do not
recreate standalone command construction in the root Makefile. Preserve
backward-compatible root variable behavior where current tests/documentation
promise it by translating values once into `ASTERION_ARGS`.

- [ ] **Step 4: Run the mixed-root integration and governance regressions**

```bash
uv run python -m unittest -v \
  tests.test_makefile_entrypoints \
  tests.test_asterion_distribution \
  tests.test_asterion_documentation \
  tests.test_asterion_dci_verification
make asterion-integration-acceptance
python3 tools/project_scope_check.py
```

The integration verifier must report 8/8 product rows, 538/538 delegated
selectors, and zero provider-backed execution. Do not reinterpret those counts
as standalone acceptance.

- [ ] **Step 5: Commit mixed-root compatibility**

```bash
git add Makefile tests/test_makefile_entrypoints.py \
  tests/test_asterion_distribution.py tests/test_asterion_documentation.py \
  tests/test_asterion_dci_verification.py
git commit -m "build: delegate Asterion commands to standalone project"
```

Stage only files actually changed. Journal the integration counts and scope
preflight result.

---

### Task 8: Run closure verification and close AF-350 state

**Files:**

- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Append: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`
- Modify: `docs/status/INDEX.md` only if its active-file descriptions or pointers
  become inaccurate

**Interfaces:**

- AF-350 closes only with a full clean-copy promotion PASS, standalone source
  and wheel acceptance parity, mixed-root integration PASS, and clean Git state.
- State records evidence and next action without claiming publication or full
  paper execution.

- [ ] **Step 1: Run focused language and syntax gates**

```bash
uv run --project asterion python -m compileall -q \
  asterion/src asterion/tests asterion/tools
uv run --project asterion ruff check \
  asterion/src asterion/tests asterion/tools
find asterion/scripts -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
npm ci --prefix asterion/packages/typescript/asterion-runtime
npm test --prefix asterion/packages/typescript/asterion-runtime
npm test --prefix asterion/packages/typescript/dci-context-extension
cargo test --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml
cargo fmt --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml -- --check
cargo clippy --manifest-path asterion/packages/rust/controlled-executor/Cargo.toml -- -D warnings
```

- [ ] **Step 2: Run all standalone tests and build/install acceptance**

```bash
make -C asterion sync
make -C asterion test
make -C asterion lint
make -C asterion docs-check
make -C asterion build
make -C asterion asterion-list
make -C asterion asterion-describe
make -C asterion asterion-verify-acceptance
make -C asterion promotion-check
```

Save only body-free counts/status in the journal. Do not persist command
environments or provider configuration.

- [ ] **Step 3: Run mixed-root and repository gates**

```bash
uv run python -m unittest discover -s tests -v
make asterion-integration-acceptance
python3 tools/project_scope_check.py
git diff --check
git status --short --branch
```

Do not run `make runtime-example`; AF-350 has no provider authorization.

- [ ] **Step 4: Perform the required review pass**

Use `requesting-code-review` on the complete AF-350 diff. Address every confirmed
high/medium correctness, security, portability, documentation, or missing-test
finding through a new RED/GREEN loop. Re-run affected gates and then the full
promotion check. Do not spawn a reviewer agent unless the user explicitly
authorizes sub-agent work.

- [ ] **Step 5: Close package state only after all gates pass**

Update `WORKLIST.md` AF-350 to `completed` with the plan path and acceptance
evidence. Update `CURRENT-STATE.md` to say the subtree is promotion-ready, not
published. Append journal entries for the final verification and state commit.
Rewrite the live checkpoint so a new session knows:

- exact final commit and unpushed status;
- standalone source/wheel/promotion results;
- mixed integration 8/8 and 538/538 result;
- no provider/full/push/release occurred;
- the next operator-controlled action is to copy/promote the subtree or open a
  separate governed package for publication/release.

Run `python3 tools/project_scope_check.py` again after state edits.

- [ ] **Step 6: Commit closure and confirm cleanliness**

```bash
git add docs/status/WORKLIST.md docs/status/CURRENT-STATE.md \
  docs/status/JOURNAL.md docs/status/RESUME-NEXT-SESSION.md docs/status/INDEX.md
git commit -m "docs: close AF-350 standalone promotion readiness"
git diff --check HEAD~1 HEAD
git status --short --branch
```

Omit `docs/status/INDEX.md` from the commit if unchanged. The final report must
list the final commit, Git cleanliness, standalone promotion result, mixed
integration counts, state files updated, and the first safe next action.
