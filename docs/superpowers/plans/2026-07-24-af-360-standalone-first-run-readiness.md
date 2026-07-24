# AF-360 Standalone First-Run Readiness Implementation Plan

> **Execution note:** Run this plan inline in the current governed session with
> strict red-green-refactor cycles. Do not delegate to subagents unless the user
> explicitly authorizes delegation. Before each package boundary, run
> `python3 tools/project_scope_check.py`.

**Goal:** Make a clean copy of `asterion/` provision and verify its locked Pi
checkout and external DCI resources, expose one configuration contract, and
reach an actionable provider-free preflight boundary without parent-repository
dependencies.

**Architecture:** The standalone project keeps an ignored, source-pinned Pi
checkout as its runtime authority and explicitly selects a separate
user-managed Pi agent/auth directory. A package-owned resource tool uses named
`basic` and `benchmark` profiles; the existing packaged paper benchmark
inventory is the benchmark path source of truth. Existing capability
description and preflight types remain stable while their defaults, check IDs,
and safe repair summaries become precise.

**Technology:** Bash, Python 3.10+, `unittest`, `pathlib`, `subprocess`,
`huggingface_hub` as an optional setup dependency, existing Asterion exporters,
Make, uv, Ruff, local Git/resource fixtures.

**Cost and safety boundary:** All setup, check, doctor, and clean-copy tests
perform zero Agent requests, zero Judge requests, and no dataset execution.
Fixture tests never contact GitHub, Hugging Face, an Agent, or a Judge.

---

## Task 1: Ship locked Pi setup and read-only verification

**Files:**

- Create: `asterion/scripts/setup_pi.sh`
- Create: `asterion/tests/test_setup_pi.py`
- Modify: `asterion/Makefile`
- Modify: `asterion/tests/test_standalone_repository.py`

### Step 1: Write the failing local-Git fixture tests

Port the behavior-oriented fixture from `tests/test_setup_pi.py` into the
standalone suite and make the test invoke `asterion/scripts/setup_pi.sh`.
Construct a local bare remote with two commits and a fake `npm` executable that
records only the invoked working directory and arguments.

Cover these independent behaviors:

- an absent `DCI_PI_DIR` is cloned without selecting a moving branch and checked
  out at the full SHA in `pi-revision.txt`;
- a matching checkout with `packages/coding-agent/dist/cli.js` is idempotent and
  does not invoke npm;
- a clean mismatch switches to the locked commit;
- a dirty mismatch is rejected without changing HEAD or local files;
- `--check` never clones, fetches, switches, builds, or creates directories;
- a missing local locked revision fails in `--check` mode;
- a malformed default lock fails before cloning;
- a symlinked `DCI_PI_DIR` fails closed;
- the script never reads or copies `.pi/agent/auth.json`;
- Make exposes `setup-pi` and `check-pi`.

The public test helper must set only fixture values:

```python
environment.update(
    {
        "DCI_PI_DIR": str(self.pi_dir),
        "DCI_PI_REPO_URL": str(self.remote),
        "PATH": f"{self.fake_bin}{os.pathsep}{environment['PATH']}",
    }
)
```

### Step 2: Run the test and observe RED

Run:

```bash
uv run python -m unittest -v tests.test_setup_pi
```

Expected: failure because `scripts/setup_pi.sh` and the Make targets do not
exist. Confirm the failure is about the missing AF-360 surface, not fixture
construction.

### Step 3: Implement the minimal safe setup script

Move the proven logic from root `scripts/setup_pi.sh` into the standalone
project and add the missing first-run safety checks:

```bash
case "$PI_DIR" in
    /*) ;;
    *) PI_DIR="$PROJECT_ROOT/${PI_DIR#./}" ;;
esac

if [ -L "$PI_DIR" ]; then
    echo "ERROR: DCI_PI_DIR must not be a symlink: $PI_DIR" >&2
    exit 2
fi
```

The implementation must:

- resolve the project root from the script location;
- read exactly one full SHA from project-local `pi-revision.txt` unless
  `DCI_PI_REVISION` is explicitly set;
- use `git clone --no-checkout`, exact-SHA fetch, and detached checkout;
- refuse dirty revision changes;
- accept matching dirty source without discarding it;
- build `tui`, `ai`, `agent`, and `coding-agent` only when source changed or
  `dist/cli.js` is absent;
- leave authentication entirely untouched;
- exit `4` for a read-only readiness miss and `2`/`3` for invalid input or a
  dirty switch refusal.

Add Make targets:

```make
setup-pi:
	bash scripts/setup_pi.sh

check-pi:
	bash scripts/setup_pi.sh --check
```

### Step 4: Run GREEN and shell/static checks

Run:

```bash
uv run python -m unittest -v tests.test_setup_pi tests.test_standalone_repository
bash -n asterion/scripts/setup_pi.sh
uv run ruff check asterion/tests/test_setup_pi.py
```

Expected: all tests pass, Bash syntax passes, and Ruff reports no errors.

### Step 5: Commit the Pi slice

```bash
git add asterion/scripts/setup_pi.sh asterion/tests/test_setup_pi.py \
  asterion/tests/test_standalone_repository.py asterion/Makefile
git commit -m "feat: add standalone pinned Pi setup"
```

Journal the commit and its fixture-backed result.

---

## Task 2: Add declarative basic resource setup and checks

**Files:**

- Create: `asterion/src/asterion/dci/resource_setup.py`
- Create: `asterion/tools/setup_resources.py`
- Create: `asterion/tests/test_resource_setup.py`
- Modify: `asterion/pyproject.toml`
- Modify: `asterion/uv.lock`
- Modify: `asterion/Makefile`

### Step 1: Define the failing basic-profile contract

Write tests against this public Python API:

```python
class ResourceSetupError(RuntimeError):
    pass

def prepare_resources(
    *,
    profile: str,
    resource_root: Path,
    source_root: Path | None = None,
    check_only: bool = False,
) -> ResourceSetupResult:
    ...
```

`ResourceSetupResult` is immutable and contains only safe aggregate facts:
`profile`, `status`, `prepared`, `present`, and `missing` logical resource IDs.

Use local fixture sources arranged as:

```text
fixture-source/
├── browsecomp_plus/*.parquet
└── wiki/*
```

Tests must prove:

- `basic` materializes `corpus/wiki_corpus` and
  `corpus/bc_plus_docs`;
- BC+ conversion calls the existing `asterion.dci.export.export_bcplus`;
- `--check` reports both missing logical resources and creates nothing;
- a second prepare is idempotent;
- an existing complete destination is not overwritten;
- a symlinked resource root or destination is rejected;
- every resolved destination remains below the explicit resource root;
- errors contain logical IDs and relative destinations, never document bodies;
- the CLI returns nonzero on missing resources and renders zero Agent/Judge
  operations.

Patch `export_bcplus` in the conversion-specific test; use real file copying
for containment and idempotency tests.

### Step 2: Run the basic tests and observe RED

Run:

```bash
uv run python -m unittest -v tests.test_resource_setup
```

Expected: import failure for `asterion.dci.resource_setup`.

### Step 3: Implement the basic manifest and fixture/network source adapter

Define immutable entries:

```python
BASIC_RESOURCES = (
    ResourceSpec(
        resource_id="corpus.wiki",
        source_repo="DCI-Agent/corpus",
        source_path="wiki",
        destination="corpus/wiki_corpus",
        conversion="copy",
    ),
    ResourceSpec(
        resource_id="corpus.bc-plus",
        source_repo="DCI-Agent/corpus",
        source_path="browsecomp_plus",
        destination="corpus/bc_plus_docs",
        conversion="bcplus",
    ),
)
```

When `source_root` is supplied, copy from that local fixture and never import
or call Hugging Face. Otherwise lazily import `snapshot_download` inside the
network adapter, download only declared source paths into a temporary directory,
and atomically promote completed outputs.

The tool CLI accepts:

```text
--profile {basic,benchmark}
--resource-root PATH
--source-root PATH
--check
--json
```

Declare the setup-only dependency:

```toml
[project.optional-dependencies]
setup = ["huggingface-hub>=0.30.0"]
```

Add Make targets using `ASTERION_DCI_RESOURCE_ROOT` with project-root fallback:

```make
setup-resources-basic:
	$(UV_BIN) run --extra setup python tools/setup_resources.py --profile basic

check-resources-basic:
	$(UV_BIN) run python tools/setup_resources.py --profile basic --check
```

### Step 4: Run GREEN, lock, and static checks

Run:

```bash
uv lock
uv run python -m unittest -v tests.test_resource_setup
uv run python -m compileall -q asterion/src/asterion/dci/resource_setup.py \
  asterion/tools/setup_resources.py asterion/tests/test_resource_setup.py
uv run ruff check asterion/src/asterion/dci/resource_setup.py \
  asterion/tools/setup_resources.py asterion/tests/test_resource_setup.py
```

Expected: all commands exit zero.

### Step 5: Commit the basic resource slice

```bash
git add asterion/src/asterion/dci/resource_setup.py \
  asterion/tools/setup_resources.py asterion/tests/test_resource_setup.py \
  asterion/pyproject.toml asterion/uv.lock asterion/Makefile
git commit -m "feat: provision standalone basic resources"
```

Journal the commit and provider-free result.

---

## Task 3: Account for all benchmark launcher resources

**Files:**

- Modify: `asterion/src/asterion/dci/resource_setup.py`
- Modify: `asterion/tests/test_resource_setup.py`
- Modify: `asterion/tests/test_standalone_launchers.py`
- Modify: `asterion/Makefile`

### Step 1: Write failing inventory-closure tests

Load
`asterion/src/asterion/dci/resources/paper-benchmarks.json` and assert that
every unique `dataset_path` and `corpus_path` is represented by the benchmark
profile. Independently parse all checked-in launchers and assert that every
literal `$RESOURCE_ROOT/...` dataset/corpus path resolves to the same packaged
inventory.

Add behavior tests proving:

- local-fixture benchmark setup prepares paths available from the fixture;
- `--check` returns exact missing logical IDs and relative paths for unavailable
  BEIR and gated resources;
- a missing upstream message names `DCI-Agent/dci-bench` or
  `DCI-Agent/corpus` and the authentication action;
- no fallback corpus or dataset is substituted;
- benchmark setup never invokes a launcher or backend.

### Step 2: Run the inventory tests and observe RED

Run:

```bash
uv run python -m unittest -v \
  tests.test_resource_setup tests.test_standalone_launchers
```

Expected: benchmark inventory assertions fail because only the basic manifest
exists.

### Step 3: Implement inventory-derived benchmark checks

Read the packaged JSON with `importlib.resources`. Derive benchmark requirements
from each record's `dataset_path` and `corpus_path`; merge them with the basic
resource specs by logical destination.

Fetching rules:

- `data/dci-bench/**` comes from `DCI-Agent/dci-bench`;
- `corpus/wiki_corpus`, BC+, and BRIGHT raw corpora come from
  `DCI-Agent/corpus`;
- `data/bcplus_qa.jsonl` is exported with `export_bcplus_qa`;
- BRIGHT document trees are exported with `export_bright`;
- BEIR paths without a declared downloadable source remain explicit
  `unavailable` requirements and fail with a safe acquisition explanation.

Add:

```make
setup-resources-benchmark:
	$(UV_BIN) run --extra setup python tools/setup_resources.py --profile benchmark

check-resources-benchmark:
	$(UV_BIN) run python tools/setup_resources.py --profile benchmark --check
```

### Step 4: Run GREEN and regression checks

Run:

```bash
uv run python -m unittest -v \
  tests.test_resource_setup tests.test_standalone_launchers
uv run ruff check asterion/src/asterion/dci/resource_setup.py \
  asterion/tests/test_resource_setup.py \
  asterion/tests/test_standalone_launchers.py
```

Expected: inventory and safety tests pass.

### Step 5: Commit the benchmark slice

```bash
git add asterion/src/asterion/dci/resource_setup.py \
  asterion/tests/test_resource_setup.py \
  asterion/tests/test_standalone_launchers.py asterion/Makefile
git commit -m "feat: validate standalone benchmark resources"
```

Journal the inventory count and commit.

---

## Task 4: Align template, description, doctor, and preflight

**Files:**

- Modify: `asterion/.env.template`
- Modify: `asterion/src/asterion/dci/verification.py`
- Modify: `asterion/tests/test_asterion_dci_verification.py`
- Modify: `asterion/tests/test_asterion_cli.py`
- Modify: `asterion/Makefile`

### Step 1: Write failing configuration-parity tests

Add standalone tests asserting:

- product description defaults are exactly `openai-codex`,
  `gpt-5.6-luna`, `./pi`, and `~/.pi/agent`;
- JSON `describe` reports those same values;
- `.env.template` contains active safe defaults for provider/model/Pi/resource
  roots and an empty credential surface;
- preflight returns sorted stable check IDs:

```python
(
    "agent-authentication",
    "agent-selection",
    "built-pi-cli",
    "environment",
    "judge",
    "node",
    "pi-checkout",
    "resources-basic",
)
```

- a checkout without `dist/cli.js` fails `built-pi-cli` and names
  `make setup-pi`;
- missing auth fails `agent-authentication` and names
  `DCI_PI_AGENT_DIR` without rendering an absolute path or secret;
- missing resources fail `resources-basic` and name
  `make setup-resources-basic`;
- missing `.env` names `cp .env.template .env`;
- empty provider/model values still resolve to the documented runtime defaults;
- a complete fixture with explicit user auth passes without backend Agent/Judge
  work;
- `make doctor` renders the provider-free preflight command.

### Step 2: Run the focused tests and observe RED

Run:

```bash
uv run python -m unittest -v \
  tests.test_asterion_dci_verification tests.test_asterion_cli \
  tests.test_standalone_repository
```

Expected: failures for null description defaults, old preflight IDs, absent
repair summaries, absent template auth selection, and absent doctor target.

### Step 3: Implement one effective contract

Import `PI_DEFAULT_PROVIDER` and `PI_DEFAULT_MODEL` into the description and
set:

```python
ConfigurationRequirement(
    "DCI_PI_AGENT_DIR",
    "User-managed Pi agent and authentication directory",
    ("basic", "complete", "preflight"),
    False,
    "~/.pi/agent",
    "Authenticate with Pi, then set this directory; setup never copies credentials",
)
```

Preflight must test source checkout and built CLI separately:

```python
pi_checkout_ready = (
    paths.pi.repo_dir.is_dir()
    and paths.pi.package_dir.is_dir()
    and (paths.pi.package_dir / "package.json").is_file()
)
built_cli_ready = (paths.pi.package_dir / "dist" / "cli.js").is_file()
```

Use safe, deterministic summaries that are also repair instructions. Preserve:

- sorted unique check IDs;
- `provider_backed_operation_count == 0`;
- `full_dataset_ran is False`;
- no absolute user path, credential value, or auth body in results.

Add:

```make
doctor:
	$(UV_BIN) run asterion verify --provider $(ASTERION_PROVIDER) \
	  --level preflight $(ASTERION_ARGS)
```

### Step 4: Run GREEN and configuration regressions

Run:

```bash
uv run python -m unittest -v \
  tests.test_asterion_dci_verification tests.test_asterion_cli \
  tests.test_standalone_repository
uv run python -m compileall -q asterion/src/asterion/dci/verification.py \
  asterion/tests/test_asterion_dci_verification.py
uv run ruff check asterion/src/asterion/dci/verification.py \
  asterion/tests/test_asterion_dci_verification.py \
  asterion/tests/test_asterion_cli.py
```

Expected: all focused checks pass.

### Step 5: Commit the configuration slice

```bash
git add asterion/.env.template asterion/src/asterion/dci/verification.py \
  asterion/tests/test_asterion_dci_verification.py \
  asterion/tests/test_asterion_cli.py \
  asterion/tests/test_standalone_repository.py asterion/Makefile
git commit -m "fix: align standalone first-run configuration"
```

Journal the stable check IDs and commit.

---

## Task 5: Prove the clean-copy first-run surface

**Files:**

- Modify: `asterion/tools/check_promotion.py`
- Modify: `asterion/tests/test_check_promotion.py`
- Modify: `asterion/tests/test_standalone_repository.py`
- Modify: `asterion/Makefile`
- Modify: `asterion/.github/workflows/ci.yml`

### Step 1: Write failing promotion-plan tests

Extend required assets with:

```python
"scripts/setup_pi.sh",
"tools/setup_resources.py",
```

Assert quick promotion runs these provider-free fixture test modules from the
copied repository before installed acceptance:

```text
tests.test_setup_pi
tests.test_resource_setup
tests.test_asterion_dci_verification
```

Assert the full rendered plan contains no real remote URL, provider credential,
basic/complete verification, launcher execution, or full authorization.

Add repository tests that CI and Make expose a named `first-run-check` target.

### Step 2: Run promotion tests and observe RED

Run:

```bash
uv run python -m unittest -v \
  tests.test_check_promotion tests.test_standalone_repository
```

Expected: required-asset and command-plan assertions fail.

### Step 3: Implement the clean-copy gate

Add a Make target:

```make
first-run-check:
	$(UV_BIN) run python -m unittest -v \
	  tests.test_setup_pi tests.test_resource_setup \
	  tests.test_asterion_dci_verification
```

Add the same focused command to quick promotion and require both setup tools in
the copy audit. Add `make first-run-check` to the provider-free CI job before
promotion. The tests themselves inject only local fixture sources.

### Step 4: Run GREEN and quick promotion

Run:

```bash
uv run python -m unittest -v \
  tests.test_check_promotion tests.test_standalone_repository
uv run python tools/check_promotion.py --quick
```

Expected: the copied repository runs the fixture-backed first-run suite and
installed provider-free acceptance successfully.

### Step 5: Commit the clean-copy slice

```bash
git add asterion/tools/check_promotion.py asterion/tests/test_check_promotion.py \
  asterion/tests/test_standalone_repository.py asterion/Makefile \
  asterion/.github/workflows/ci.yml
git commit -m "test: verify standalone first-run promotion"
```

Journal the clean-copy command count and zero-operation result.

---

## Task 6: Publish the complete operator workflow and close AF-360

**Files:**

- Modify: `asterion/README.md`
- Modify: `asterion/docs/guides/asterion-capability-usage.md`
- Modify: `asterion/docs/guides/asterion-dci-complete-reference.md`
- Modify: `asterion/docs/verification/asterion-dci-validation-guide.md`
- Modify: `asterion/docs/architecture/agent-framework.md`
- Modify: `asterion/tests/test_standalone_repository.py`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/DECISIONS.md` only if implementation changes D-057
- Modify: `docs/status/INDEX.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

### Step 1: Write failing documentation-contract assertions

Extend repository tests to require one canonical fresh-clone sequence in the
README and links from both operator guides:

```bash
uv sync --frozen
make setup-pi
make setup-resources-basic
cp .env.template .env
make doctor
```

Require the docs to state:

- global `pi` is not the runtime source;
- `DCI_PI_AGENT_DIR` selects user-managed auth;
- setup uses network/disk but performs zero Agent/Judge operations;
- `basic` and `benchmark` resource profiles have distinct size/availability
  boundaries;
- unavailable BEIR/gated resources are reported and never substituted;
- provider-backed verification is a later, explicit operation.

### Step 2: Run docs tests and observe RED

Run:

```bash
uv run python -m unittest -v tests.test_standalone_repository
uv run python tools/check_docs.py
```

Expected: documentation contract fails until the canonical workflow is added.

### Step 3: Update documentation and help text

Make README the concise entrypoint and keep detailed setup, recovery, and
configuration precedence in the guides. Ensure every command runs from the
standalone root and no parent-relative path is introduced.

Update Make help with these exact categories:

- setup/check: provider-free, explicit network/disk;
- doctor/preflight: provider-free, zero operations;
- basic/complete/run: provider-backed;
- benchmark/full: separately authorized.

### Step 4: Run the complete fresh verification matrix

Run fresh, in this order:

```bash
python3 tools/project_scope_check.py
uv run python -m unittest discover -s asterion/tests -v
uv run python -m compileall -q asterion/src asterion/tests asterion/tools
uv run ruff check asterion/src asterion/tests asterion/tools
bash -n asterion/scripts/setup_pi.sh
find asterion/scripts -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
uv run python asterion/tools/check_docs.py
uv run python asterion/tools/check_promotion.py --quick
uv build asterion
uv run python -m unittest -v \
  tests.test_asterion_dci_verification \
  tests.test_asterion_standalone_integration \
  tests.test_project_scope_check
git diff --check
```

If valid credentials are available and the user separately authorizes the
bounded provider operation, run `make runtime-example`; otherwise record it as
not run by design. Never run a benchmark or full dataset for AF-360.

Review the implementation diff for:

- credential leakage or auth copying;
- destructive Pi or resource behavior;
- parent-repository imports or paths;
- duplicated resource inventory;
- setup that accidentally constructs a provider/Judge;
- missing check-only non-mutation coverage.

### Step 5: Commit docs, close governance, and checkpoint

Only after every applicable gate passes:

1. commit the documentation slice;
2. append every material commit and verified result to `JOURNAL.md`;
3. rerun `python3 tools/project_scope_check.py`;
4. change AF-360 to `done` with exact closure evidence;
5. set lifecycle to `complete` if no package remains active;
6. refresh CURRENT, INDEX, and RESUME consistently;
7. commit the closure checkpoint.

Use cohesive commit messages:

```bash
git commit -m "docs: add standalone first-run workflow"
git commit -m "docs: close AF-360 first-run readiness"
```

Final completion evidence must name the final commit, Git cleanliness, exact
test counts, clean-copy result, and the fact that no Agent, Judge, full dataset,
external credential, publication, remote creation, or push occurred.

---

## Reopened correction — Task 7: Ship standalone runnable Asterion examples

**Active package:** `AF-360`

**Scope constraints:**

- Add only the two Asterion-native examples already proven at repository root.
- Do not change authentication, Pi setup, resource setup, corpus discovery,
  provider defaults, the root Makefile, or root example scripts.
- Do not add OpenAI-, Anthropic-, or vLLM-specific example variants.
- Keep `pi/` untouched and perform no Agent, Judge, benchmark, or full-dataset
  operation during implementation or verification.
- Every new path and command must work from a clean copy of `asterion/` without
  a parent repository.

**Files:**

- Create: `asterion/scripts/examples/asterion_dci_basic_example.sh`
- Create: `asterion/scripts/examples/asterion_dci_runtime_context_example.sh`
- Modify: `asterion/Makefile`
- Modify: `asterion/tests/test_standalone_repository.py`
- Modify: `asterion/tests/test_standalone_launchers.py`
- Modify: `asterion/tools/check_promotion.py`
- Modify: `asterion/tests/test_check_promotion.py`
- Modify: `asterion/README.md`
- Modify: `asterion/examples/README.md`
- Modify at closure: `docs/status/WORKLIST.md`
- Modify at closure: `docs/status/CURRENT-STATE.md`
- Modify at closure: `docs/status/INDEX.md`
- Append at implementation and closure: `docs/status/JOURNAL.md`
- Modify at closure: `docs/status/RESUME-NEXT-SESSION.md`

### Step 1: Write failing standalone example contracts

In `asterion/tests/test_standalone_repository.py`, add both scripts to
`REQUIRED_ASSETS`, add `example` and `runtime-example` to
`LIFECYCLE_TARGETS`, and assert the exact Make recipes:

```python
self.assertEqual(
    dry_run("example"),
    ("bash", "scripts/examples/asterion_dci_basic_example.sh"),
)
self.assertEqual(
    dry_run("runtime-example"),
    ("bash", "scripts/examples/asterion_dci_runtime_context_example.sh"),
)
```

Add a behavior test that creates a temporary corpus root containing
`wiki_corpus/` and `bc_plus_docs/`, puts a recording `uv` executable first on
`PATH`, and runs both scripts with:

```python
environment.update(
    {
        "ASTERION_DCI_CORPUS_ROOT": str(corpus_root),
        "DCI_PROVIDER": "fixture-provider",
        "DCI_MODEL": "fixture-model",
        "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
    }
)
```

The fake `uv` must record its working directory and arguments. Assert that:

- both processes return zero without contacting a provider;
- both working directories equal the standalone project root;
- both commands begin with `run asterion-dci run`;
- the basic command uses `wiki_corpus` and `--extra-arg=--thinking high`;
- the runtime command uses `bc_plus_docs`, `--tools read,bash`,
  `--max-turns 6`, `--thinking-level medium` when invoked with `medium`, and
  `--eval-answer Adaku`;
- both scripts derive the standalone root from their own `scripts/examples/`
  location and neither contains `python -m dci` or a parent-project path.

Keep `test_standalone_launchers.py`'s existing count and root-contract checks
scoped to the 14 dataset launchers while letting its Bash syntax check cover
all shell scripts, including the two new runnable examples.

In `asterion/tests/test_check_promotion.py`, add the two scripts to
`REQUIRED_FIXTURE_ASSETS` and assert that both exist inside the clean-copy
runner root.

Working directory: `asterion/`

Run:

```bash
uv run python -m unittest -v \
  tests.test_standalone_repository \
  tests.test_check_promotion
```

Expected RED: the required scripts and Make targets do not exist.

### Step 2: Add the two standalone scripts

Create `asterion/scripts/examples/asterion_dci_basic_example.sh` with this
complete content:

```bash
#!/usr/bin/env bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
fi

set -euo pipefail

: "${DCI_PROVIDER:?Set DCI_PROVIDER in .env}"
: "${DCI_MODEL:?Set DCI_MODEL in .env}"

QUESTION="Answer the following question using only wiki_dump.jsonl in the current directory. Do not use web search. Use rg instead of grep for fast searching. Question: In which street did the Great Fire of London originate?"
if [ -n "${ASTERION_DCI_CORPUS_ROOT:-}" ] && [ "${ASTERION_DCI_CORPUS_ROOT#/}" = "$ASTERION_DCI_CORPUS_ROOT" ]; then
  printf 'ASTERION_DCI_CORPUS_ROOT must be an absolute path\n' >&2
  exit 2
fi
CORPUS_ROOT="${ASTERION_DCI_CORPUS_ROOT:-$PROJECT_ROOT/corpus}"
CORPUS_DIR="$CORPUS_ROOT/wiki_corpus"
if [ ! -d "$CORPUS_DIR" ]; then
  printf 'Asterion DCI corpus directory does not exist: %s\n' "$CORPUS_DIR" >&2
  exit 2
fi

cd "$PROJECT_ROOT"
uv run asterion-dci run \
  --cwd "$CORPUS_DIR" \
  --extra-arg="--thinking high" \
  "$QUESTION"
```

Create `asterion/scripts/examples/asterion_dci_runtime_context_example.sh`
with this complete content:

```bash
#!/usr/bin/env bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env"
  set +a
fi

set -euo pipefail

: "${DCI_PROVIDER:?Set DCI_PROVIDER in .env}"
: "${DCI_MODEL:?Set DCI_MODEL in .env}"

level="${1:-high}"
QUESTION="Read the files in the current directory. Do not use web search. Use rg instead of grep when searching. Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name? Answer with just the first name and one supporting file path."
if [ -n "${ASTERION_DCI_CORPUS_ROOT:-}" ] && [ "${ASTERION_DCI_CORPUS_ROOT#/}" = "$ASTERION_DCI_CORPUS_ROOT" ]; then
  printf 'ASTERION_DCI_CORPUS_ROOT must be an absolute path\n' >&2
  exit 2
fi
CORPUS_ROOT="${ASTERION_DCI_CORPUS_ROOT:-$PROJECT_ROOT/corpus}"
CORPUS_DIR="$CORPUS_ROOT/bc_plus_docs"
if [ ! -d "$CORPUS_DIR" ]; then
  printf 'Asterion DCI corpus directory does not exist: %s\n' "$CORPUS_DIR" >&2
  exit 2
fi

cd "$PROJECT_ROOT"
uv run asterion-dci run \
  --cwd "$CORPUS_DIR" \
  --tools read,bash \
  --max-turns 6 \
  --thinking-level "$level" \
  --eval-answer "Adaku" \
  "$QUESTION"
```

These are literal standalone adaptations of the working root examples: the
only behavioral change is resolving `PROJECT_ROOT` from the script location
inside the independently copyable project.

### Step 3: Expose simple Make entrypoints

In `asterion/Makefile`, add:

```make
.PHONY: example runtime-example
```

and:

```make
example:
	bash scripts/examples/asterion_dci_basic_example.sh

runtime-example:
	bash scripts/examples/asterion_dci_runtime_context_example.sh
```

Add both names to the provider-backed help line. Do not change any existing
target recipe.

Working directory: `asterion/`

Run:

```bash
bash -n scripts/examples/asterion_dci_basic_example.sh
bash -n scripts/examples/asterion_dci_runtime_context_example.sh
uv run python -m unittest -v tests.test_standalone_repository
```

Expected GREEN: exact Make rendering, path portability, and fake-`uv`
invocation checks pass.

### Step 4: Make clean-copy promotion require the examples

Add these exact paths to `REQUIRED_ASSETS` in
`asterion/tools/check_promotion.py` and `REQUIRED_FIXTURE_ASSETS` in
`asterion/tests/test_check_promotion.py`:

```python
"scripts/examples/asterion_dci_basic_example.sh",
"scripts/examples/asterion_dci_runtime_context_example.sh",
```

The promotion checker must continue copying the existing source tree normally;
do not special-case or execute provider-backed scripts.

Working directory: `asterion/`

Run:

```bash
uv run python -m unittest -v tests.test_check_promotion
uv run python tools/check_promotion.py --quick
```

Expected GREEN: a clean copied project contains both scripts and passes the
existing provider-free quick gates.

### Step 5: Document the runnable examples

In `asterion/README.md`, add a concise “Runnable examples” section after the
first-run setup instructions:

```markdown
## Runnable examples

After configuring `.env` and installing the basic corpora, run:

```bash
make example
make runtime-example
```

Both commands are provider-backed and may incur model usage. The scripts are
available directly under `scripts/examples/`.
```

In `asterion/examples/README.md`, retain the existing Python composition
examples and add a short pointer stating that end-to-end executable DCI
examples live under `scripts/examples/` and are exposed as `make example` and
`make runtime-example`.

Working directory: `asterion/`

Run:

```bash
uv run python tools/check_docs.py
```

### Step 6: Run the bounded verification matrix

Run the scope check from the repository root:

```bash
python3 tools/project_scope_check.py
```

Run from `asterion/`:

```bash
uv run python -m unittest -v \
  tests.test_standalone_repository \
  tests.test_check_promotion
uv run python -m compileall -q tests tools
uv run ruff check tests tools
bash -n scripts/examples/asterion_dci_basic_example.sh
bash -n scripts/examples/asterion_dci_runtime_context_example.sh
uv run python tools/check_docs.py
uv run python tools/check_promotion.py --quick
```

Run from the repository root:

```bash
uv run python -m unittest -v \
  tests.test_asterion_dci_cli \
  tests.test_asterion_dci_verification \
  tests.test_asterion_documentation \
  tests.test_asterion_project_root \
  tests.test_asterion_structure \
  tests.test_project_scope_check
git diff --check
```

Do not run the new examples against a real provider. The fake-`uv` behavior
test proves standalone command construction without spending operations; the
user's successful execution of the four existing root Make examples is the
upstream behavioral evidence.

### Step 7: Commit, journal, and close the reopened package

1. Commit the implementation and documentation as one cohesive change:

   ```bash
   git commit -m "feat: add standalone Asterion examples"
   ```

2. Append the implementation commit and exact verified results to
   `docs/status/JOURNAL.md`.
3. Rerun `python3 tools/project_scope_check.py`.
4. Close AF-360 only if all Task 7 acceptance checks pass.
5. Refresh `WORKLIST.md`, `CURRENT-STATE.md`, `INDEX.md`, and
   `RESUME-NEXT-SESSION.md` consistently.
6. Commit the durable closure checkpoint:

   ```bash
   git commit -m "docs: close AF-360 standalone examples"
   ```

Final evidence must name both commits, Git cleanliness, exact focused test
counts, clean-copy promotion result, and confirm that no real Agent, Judge,
benchmark, full dataset, external Pi edit, remote creation, publication, or
push occurred.

---

## Reopened correction — Task 8: Consolidate the standalone example directory

The user rejected the duplicate `asterion/examples/` and
`asterion/scripts/examples/` layout. Keep one canonical example directory:
`asterion/examples/`.

1. Change standalone repository and promotion tests first to require
   `examples/asterion_dci_basic_example.sh` and
   `examples/asterion_dci_runtime_context_example.sh`, assert the Make recipes
   use those paths, execute copied scripts from that location, and reject the
   old `scripts/examples/` directory.
2. Run the focused tests and observe RED because production files and Make
   recipes still use `scripts/examples/`.
3. Move the two executable scripts to `asterion/examples/`, update Make,
   promotion assets, README text, and `examples/README.md`, then remove the
   now-empty duplicate hierarchy.
4. Restore `test_standalone_launchers.py` to its original 14-launcher
   `scripts/*/*.sh` contract because standalone examples no longer live there.
5. Run standalone tests, relevant mixed-root regressions, Bash syntax, Ruff,
   docs, quick clean-copy promotion, scope, and diff checks without a provider
   operation or full dataset.
