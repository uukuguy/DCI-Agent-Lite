# Asterion Capability Discovery and Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generic `asterion describe/verify` commands, prove them with DCI preflight/basic/acceptance/complete profiles, and publish a beginner-oriented usage guide.

**Architecture:** A new immutable generic product-description/verification contract is optionally attached to one explicitly selected installed provider. The generic CLI validates and renders that contract but owns no DCI behavior. The DCI provider supplies package-local descriptions and a verifier that composes existing configuration, native run, Judge, and product-acceptance boundaries without shell strings or full-dataset execution.

**Tech Stack:** Python 3.14, frozen dataclasses, `argparse`, `unittest`, existing Asterion provider discovery, existing Asterion DCI run/evaluation code, Markdown, Git.

## Global Constraints

- Work package is AF-270; run `python3 tools/project_scope_check.py` before implementation and closure.
- Original `src/dci` and its two example scripts remain unchanged.
- Generic Asterion modules must not import `asterion.dci` or name DCI-specific configuration.
- Exact provider selection loads no adjacent provider.
- Verification never evaluates shell command strings and never prints secret values, questions, answers, conversations, provider bodies, or private absolute paths.
- `preflight` and `acceptance` make zero provider requests.
- `basic` runs exactly the two documented bounded DCI cases.
- `complete` runs `preflight`, `basic`, and `acceptance` in order and never runs a full dataset.
- The repository-root `.env` is the default; `--env-file`, `--corpus-root`, and `--output-root` are explicit operator overrides.
- Preserve the existing `asterion list`, `asterion run`, and `asterion-dci` interfaces.
- Use TDD: every production behavior begins with a focused failing test and observed RED result.
- Preserve the user-owned untracked `.superpowers/sdd/task-0-review.md`.

---

### Task 1: Immutable capability-product description and verification contract

**Files:**
- Create: `packages/python/asterion-core/src/asterion/applications/product.py`
- Modify: `packages/python/asterion-core/src/asterion/applications/provider.py`
- Modify: `tests/test_installed_application_provider.py`
- Create: `tests/test_capability_product.py`

**Interfaces:**
- Produces: `ConfigurationRequirement`, `CapabilityFunction`, `VerificationProfile`, `CapabilityProductDescription`, `VerificationRequest`, `VerificationCheckResult`, `VerificationResult`, `InstalledCapabilityProduct`, `CapabilityVerifier`
- Changes: `InstalledApplicationProvider.product: InstalledCapabilityProduct | None = None`
- Consumes later: Tasks 2–5 load only the validated optional `product` field.

- [ ] **Step 1: Write failing value-contract tests**

Test frozen values, tuple-only collections, safe identifiers, sorted unique
function/profile IDs, allowed cost classes (`provider-free`,
`bounded-provider-backed`, `full-dataset`), closed statuses (`PASS`, `FAIL`,
`SKIP`, `NOT RUN`), safe relative artifact references, aggregate counts, and
recursive absence of secret/body/path fields. Include this intended API:

```python
description = CapabilityProductDescription(
    product_id="example-product",
    version="1.0.0",
    summary="Example capability product",
    functions=(
        CapabilityFunction(
            function_id="research",
            summary="Research a local corpus",
            argv=("example", "run"),
        ),
    ),
    configuration=(
        ConfigurationRequirement(
            name="EXAMPLE_API_KEY",
            purpose="provider credential",
            required_for=("basic",),
            secret=True,
            default=None,
            hint="set this in .env",
        ),
    ),
    profiles=(
        VerificationProfile(
            level="preflight",
            summary="Check local prerequisites",
            cost_class="provider-free",
            external_request_count=0,
            full_dataset=False,
        ),
    ),
)
```

- [ ] **Step 2: Run RED contract tests**

Run:

```bash
uv run python -m unittest tests.test_capability_product tests.test_installed_application_provider -v
```

Expected: import failure because `asterion.applications.product` and the
provider `product` field do not exist.

- [ ] **Step 3: Implement and validate the generic contract**

Create frozen dataclasses and `validate_capability_product()`. Define:

```python
@dataclass(frozen=True)
class VerificationRequest:
    level: str
    env_file: Path | None
    corpus_root: Path | None
    output_root: Path | None
    acceptance_root: Path | None

@dataclass(frozen=True)
class VerificationResult:
    product_id: str
    level: str
    status: str
    checks: tuple[VerificationCheckResult, ...]
    external_request_count: int
    full_dataset_ran: bool

class CapabilityVerifier(Protocol):
    def __call__(self, request: VerificationRequest) -> VerificationResult: ...

@dataclass(frozen=True)
class InstalledCapabilityProduct:
    description: CapabilityProductDescription
    verifier: CapabilityVerifier
```

Provider validation must reject malformed optional products and retain
backward-compatible providers whose `product` is `None`.

- [ ] **Step 4: Run GREEN contract tests and generic boundary tests**

```bash
uv run python -m unittest \
  tests.test_capability_product \
  tests.test_installed_application_provider \
  tests.test_application_discovery -v
uv run ruff check packages/python/asterion-core/src/asterion/applications tests/test_capability_product.py tests/test_installed_application_provider.py
```

Expected: all pass; no provider is loaded during metadata-only global listing.

- [ ] **Step 5: Commit Task 1**

```bash
git add packages/python/asterion-core/src/asterion/applications/product.py \
  packages/python/asterion-core/src/asterion/applications/provider.py \
  tests/test_capability_product.py tests/test_installed_application_provider.py
git commit -m "feat: define capability product verification contract"
```

---

### Task 2: Generic `asterion describe` and `asterion verify` commands

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/cli.py`
- Modify: `tests/test_asterion_cli.py`
- Modify: `tests/test_application_discovery.py`

**Interfaces:**
- Consumes: validated `InstalledApplicationProvider.product` from Task 1
- Produces: `_description_payload()`, `_verification_payload()`, human renderers, CLI parsers for `describe` and `verify`
- CLI: `asterion describe --provider ID [--json]`
- CLI: `asterion verify --provider ID --level LEVEL [--env-file PATH] [--corpus-root PATH] [--output-root PATH] [--acceptance-root PATH] [--json]`

- [ ] **Step 1: Write failing CLI tests**

Use fake entry points for three cases: selected provider with product support,
selected provider without support, and an adjacent provider whose factory
raises if loaded. Assert:

```python
code = main(
    ["describe", "--provider", "example-app", "--json"],
    entry_points=(selected, adjacent),
    stdout=stdout,
    stderr=stderr,
)
self.assertEqual(code, 0)
self.assertEqual(selected.loads, 1)
self.assertEqual(adjacent.loads, 0)
self.assertEqual(json.loads(stdout.getvalue())["product_id"], "example-product")
```

Also test human output, stable JSON, invalid levels, verifier called exactly
once with absolute normalized option paths, nonzero exit for `FAIL`, and generic
redacted errors that do not echo injected secret/body/path values.

- [ ] **Step 2: Run RED CLI tests**

```bash
uv run python -m unittest tests.test_asterion_cli.AsterionCliTests -v
```

Expected: parser rejects `describe` and `verify` as unknown commands.

- [ ] **Step 3: Implement selected-provider command dispatch**

Handle `describe` and `verify` before the existing application-run selection.
`describe` loads exactly one provider, requires `product`, and renders its
validated description. `verify` checks the requested level is declared before
calling the verifier, creates `VerificationRequest`, validates the returned
result, renders it, and returns `0` only for overall `PASS`.

Human output must begin with product/level and end with:

```text
Overall: PASS
External requests: 0
Full dataset ran: no
```

Do not add DCI imports, environment-variable names, or provider-specific
branches to `asterion.cli`.

- [ ] **Step 4: Run GREEN CLI and compatibility tests**

```bash
uv run python -m unittest \
  tests.test_asterion_cli \
  tests.test_application_discovery \
  tests.test_application_selection -v
uv run asterion --help
uv run asterion describe --help
uv run asterion verify --help
```

Expected: new commands appear; existing list/run tests remain green.

- [ ] **Step 5: Commit Task 2**

```bash
git add packages/python/asterion-core/src/asterion/cli.py \
  tests/test_asterion_cli.py tests/test_application_discovery.py
git commit -m "feat: add generic capability describe and verify commands"
```

---

### Task 3: DCI self-description and provider-free preflight

**Files:**
- Create: `packages/python/asterion-core/src/asterion/dci/verification.py`
- Modify: `packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/config.py`
- Create: `tests/test_asterion_dci_verification.py`
- Modify: `tests/test_builtin_dci_application.py`

**Interfaces:**
- Produces: `DCI_PRODUCT_DESCRIPTION`, `DciVerificationBackend`, `DciProductVerifier`, `create_dci_product()`
- Extends: `load_asterion_dci_env(repo_root: Path, *, env_file: Path | None = None) -> Path | None`
- DCI levels: `preflight`, `basic`, `acceptance`, `complete`

- [ ] **Step 1: Write failing DCI description and preflight tests**

Assert `describe` exposes the plain-language functions `research`, `terminal`,
`resume`, `evaluate`, `benchmark`, `export`, and `installed-application`, with
literal argv examples. Require configuration descriptions for `DCI_PROVIDER`,
`DCI_MODEL`, `DCI_PI_DIR`, provider credential, corpus root, output root, and
Judge settings without values.

Preflight fixture tests must cover:

- default repository `.env` and explicit `--env-file` precedence;
- provider/model and provider-specific credential selection;
- Pi checkout/package/agent paths;
- Node >=20;
- `wiki_corpus` and `bc_plus_docs` beneath an absolute corpus root;
- Judge requirements for `basic`/`complete`;
- missing/invalid inputs returning named `FAIL` checks before backend calls;
- no secret value or private absolute path in human/JSON output.

- [ ] **Step 2: Run RED DCI verification tests**

```bash
uv run python -m unittest tests.test_asterion_dci_verification tests.test_builtin_dci_application -v
```

Expected: import failure because `asterion.dci.verification` does not exist.

- [ ] **Step 3: Implement the DCI descriptor and preflight**

`create_dci_product()` returns `InstalledCapabilityProduct` with one
`DciProductVerifier`. Preflight uses existing configuration resolvers, performs
read-only path/version checks, and reports configuration sources and presence
only. It accepts `--corpus-root` directly and never requires users to set
`ASTERION_DCI_CORPUS_ROOT` for the unified command.

The DCI provider attaches this product while preserving native-executor
injection used by existing application tests.

- [ ] **Step 4: Run GREEN DCI preflight and provider tests**

```bash
uv run python -m unittest \
  tests.test_asterion_dci_verification \
  tests.test_builtin_dci_application \
  tests.test_asterion_dci_config -v
uv run ruff check packages/python/asterion-core/src/asterion/dci/verification.py \
  packages/python/asterion-core/src/asterion/dci/config.py \
  packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py \
  tests/test_asterion_dci_verification.py
```

Expected: preflight sends zero requests and every error is body-free.

- [ ] **Step 5: Commit Task 3**

```bash
git add packages/python/asterion-core/src/asterion/dci/verification.py \
  packages/python/asterion-core/src/asterion/dci/config.py \
  packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py \
  tests/test_asterion_dci_verification.py tests/test_builtin_dci_application.py
git commit -m "feat: describe and preflight the DCI capability product"
```

---

### Task 4: Two-case DCI `basic` verification

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/verification.py`
- Modify: `tests/test_asterion_dci_verification.py`
- Modify: `tests/test_asterion_dci_product_parity.py`

**Interfaces:**
- Consumes: `DciProductVerifier`, resolved paths/options, `run_pi_research()`, `evaluate_run_directory()`
- Produces: `BASIC_CASES`, backend methods `run_research_case()` and `evaluate_case()`, aggregate `basic` result

- [ ] **Step 1: Write failing two-case orchestration tests**

Define the exact cases:

```python
BASIC_CASES = (
    BasicVerificationCase(
        case_id="basic-corpus-research",
        corpus_subdir="wiki_corpus",
        expected_answer=None,
        max_turns=None,
        thinking_level="high",
    ),
    BasicVerificationCase(
        case_id="runtime-context-and-judge",
        corpus_subdir="bc_plus_docs",
        expected_answer="Adaku",
        max_turns=6,
        thinking_level="high",
    ),
)
```

Tests must assert exact two-case order, two native runs, exactly one Judge
evaluation, unique private output directories, shared resolved provider/model,
first failure stops later work, overall counts, and no answer/provider body in
the public result. Compare request semantics with the two existing Asterion
example scripts and their original DCI counterparts.

- [ ] **Step 2: Run RED basic tests**

```bash
uv run python -m unittest \
  tests.test_asterion_dci_verification.DciBasicVerificationTests \
  tests.test_asterion_dci_product_parity -v
```

Expected: `basic` is declared but returns unsupported/not-run.

- [ ] **Step 3: Implement bounded native runs and Judge evaluation**

Use the injected backend in tests and existing package-local run/evaluation
functions in production. The public check result contains only case ID, status,
relative artifact roles, verdict boolean, and safe counts. Invocation of
`--level basic` is explicit authorization for exactly two Pi generations and
one Judge evaluation; print that bound before work begins.

- [ ] **Step 4: Run GREEN basic/parity tests**

```bash
uv run python -m unittest \
  tests.test_asterion_dci_verification \
  tests.test_asterion_dci_product_parity \
  tests.test_asterion_dci_run \
  tests.test_asterion_dci_evaluation -v
```

Expected: fixture basic reports two PASS checks, request count `3`, and
`full_dataset_ran=false`.

- [ ] **Step 5: Commit Task 4**

```bash
git add packages/python/asterion-core/src/asterion/dci/verification.py \
  tests/test_asterion_dci_verification.py tests/test_asterion_dci_product_parity.py
git commit -m "feat: run two bounded DCI verification cases"
```

---

### Task 5: DCI `acceptance` and aggregate `complete` verification

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/verification.py`
- Modify: `tools/verify_asterion_dci_product.py`
- Modify: `tests/test_asterion_dci_verification.py`
- Modify: `tests/test_asterion_dci_product_acceptance.py`

**Interfaces:**
- Produces: importable body-free `ProductAcceptanceSummary`, `verify_product_acceptance(root, *, acceptance_root=None)`, ordered `acceptance` and `complete` results
- Consumes: existing allowlisted public product verifier; optional private acceptance root

- [ ] **Step 1: Write failing acceptance/complete tests**

Require an importable verifier result instead of parsing subprocess prose:

```python
summary = verify_product_acceptance(ROOT)
self.assertEqual(summary.product_rows, (8, 8))
self.assertEqual(summary.delegated_inventory, (533, 533))
self.assertEqual(summary.launcher_pairs, (12, 12))
self.assertEqual(summary.batch_extras, (6, 6))
self.assertEqual(summary.bounded_acceptance, (7, 7))
self.assertEqual(summary.provider_backed_executed, 0)
```

DCI `acceptance` must map these to plain feature checks and make zero backend
requests. `complete` must call `preflight`, then two-case `basic`, then
`acceptance`, stop on failure, report exactly three external requests when all
pass, and reject any backend/profile attempt to mark `full_dataset_ran=true`.
Private validation remains optional and requires every referenced credential.

- [ ] **Step 2: Run RED acceptance tests**

```bash
uv run python -m unittest \
  tests.test_asterion_dci_verification.DciAcceptanceVerificationTests \
  tests.test_asterion_dci_product_acceptance -v
```

Expected: no importable summary API and no complete orchestration.

- [ ] **Step 3: Refactor the verifier and implement levels**

Keep the existing script output and exit behavior as a thin wrapper over the
new immutable summary. DCI verification may import the tool only in a source
checkout; outside a checkout, `acceptance` returns a clear `NOT RUN` checkout
requirement while installed `describe` and `preflight` remain functional.
Never invoke a launcher without `--limit`, and do not execute any launcher in
`acceptance` or `complete`.

- [ ] **Step 4: Run GREEN product verification**

```bash
uv run python -m unittest \
  tests.test_asterion_dci_verification \
  tests.test_asterion_dci_product_acceptance \
  tests.test_asterion_dci_product_parity -v
uv run python tools/verify_asterion_dci_product.py
```

Expected: public product rows 8/8, delegated 533/533, launchers 12/12,
extras 6/6, bounded acceptance 7/7, provider-backed executed 0.

- [ ] **Step 5: Commit Task 5**

```bash
git add packages/python/asterion-core/src/asterion/dci/verification.py \
  tools/verify_asterion_dci_product.py \
  tests/test_asterion_dci_verification.py \
  tests/test_asterion_dci_product_acceptance.py
git commit -m "feat: aggregate complete DCI product verification"
```

---

### Task 6: Beginner usage guide and concise product entry points

**Files:**
- Create: `docs/guides/asterion-capability-usage.md`
- Modify: `README.md`
- Modify: `docs/verification/asterion-dci-validation-guide.md`
- Modify: `.env.template`
- Modify: `tests/test_distribution_boundaries.py`

**Interfaces:**
- Consumes: final CLI and DCI levels from Tasks 2–5
- Produces: one beginner guide linked before the advanced acceptance guide

- [ ] **Step 1: Write failing documentation-contract tests**

Require the beginner guide to contain, in this order:

1. five-minute quickstart;
2. minimal `.env` with `DCI_PROVIDER`, `DCI_MODEL`, provider credential, Pi,
   and Judge examples using placeholders only;
3. `asterion describe`;
4. `preflight`, `basic`, `acceptance`, and `complete` commands;
5. a plain-language table of original DCI functions and Asterion commands;
6. expected PASS output, request counts, artifacts, costs, and troubleshooting;
7. a link to the advanced validation guide.

Assert README links the beginner guide before the audit guide and no guide
contains a credential assignment with a real-looking value or a private path.

- [ ] **Step 2: Run RED documentation tests**

```bash
uv run python -m unittest \
  tests.test_distribution_boundaries.SourceDistributionBoundaryTests.test_asterion_capability_beginner_guide_is_complete -v
```

Expected: FAIL because the beginner guide does not exist.

- [ ] **Step 3: Write the guide and simplify the advanced guide opening**

The first runnable path must be:

```bash
cp .env.template .env
# edit only the named placeholder values
uv sync
asterion describe --provider dci-agent-lite
asterion verify --provider dci-agent-lite --level preflight --corpus-root ./corpus
asterion verify --provider dci-agent-lite --level complete --corpus-root ./corpus
```

Explain that `basic` replaces manual execution of two Asterion scripts,
`acceptance` is model-free, and `complete` makes exactly two Pi generations
plus one Judge request. Put 533-selector and artifact-schema detail only in the
advanced guide.

- [ ] **Step 4: Run GREEN documentation and help tests**

```bash
uv run python -m unittest tests.test_distribution_boundaries tests.test_asterion_cli -v
uv run asterion describe --provider dci-agent-lite
uv run asterion verify --provider dci-agent-lite --level preflight --corpus-root "$PWD/corpus"
git diff --check
```

Expected: guide contract passes; describe is readable; preflight reports no
provider request and names any missing prerequisite safely.

- [ ] **Step 5: Commit Task 6**

```bash
git add docs/guides/asterion-capability-usage.md README.md \
  docs/verification/asterion-dci-validation-guide.md .env.template \
  tests/test_distribution_boundaries.py
git commit -m "docs: add Asterion capability usage guide"
```

---

### Task 7: Bounded real acceptance, independent review, and AF-270 closure

**Files:**
- Modify only for reviewed defects: files from Tasks 1–6
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`
- Append: `docs/status/JOURNAL.md`
- Modify: `docs/status/DECISIONS.md`

**Interfaces:**
- Consumes: complete generic/DCF implementation and shared repository `.env`
- Produces: reviewed `complete` evidence and explicit terminal lifecycle

- [ ] **Step 1: Run provider-free command acceptance**

```bash
uv run asterion describe --provider dci-agent-lite
uv run asterion describe --provider dci-agent-lite --json
uv run asterion verify --provider dci-agent-lite --level preflight --corpus-root "$PWD/corpus"
uv run asterion verify --provider dci-agent-lite --level acceptance --corpus-root "$PWD/corpus"
```

Expected: readable/JSON descriptions match; preflight and acceptance PASS;
external requests 0; full dataset no.

- [ ] **Step 2: Run one authorized bounded `complete` verification**

Using the shared root `.env` without printing it:

```bash
uv run asterion verify \
  --provider dci-agent-lite \
  --level complete \
  --env-file .env \
  --corpus-root "$PWD/corpus" \
  --output-root "$PWD/outputs/asterion-verification"
```

Expected: preflight PASS, two basic cases PASS, acceptance PASS, external
requests exactly 3 (two Pi generations plus one Judge), full dataset no.

- [ ] **Step 3: Run full repository gates**

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

Review for generic-layer DCI coupling, adjacent provider loading, arbitrary
command execution, secret/body/path leakage, provider-free levels sending
requests, complete running more than the documented bound, full-dataset launch,
installed-wheel breakage, misleading guide instructions, and stale governance.
Fix all Critical and Important findings and rerun affected gates.

- [ ] **Step 5: Close AF-270 and commit terminal state**

Set AF-270 `completed`, lifecycle `complete`, CURRENT/RESUME active package
`none`, and record exact fresh evidence plus review result. Then run:

```bash
python3 tools/project_scope_check.py
git diff --check
git add docs/status
git commit -m "docs: close unified capability verification"
```

Expected scope payload:

```json
{"active_package": null, "errors": [], "lifecycle": "complete", "ok": true}
```

## Plan Self-Review

- Spec coverage: generic discovery, optional provider contract, configuration
  UX, DCI function map, four levels, errors/results, beginner documentation,
  installed behavior, bounded real acceptance, review, and terminal governance
  map to Tasks 1–7.
- Placeholder scan: no deferred implementation marker remains; example values
  are deliberate safe placeholders for the guide.
- Type consistency: provider `product` contains one validated description and
  callable verifier; CLI and DCI tasks use the same `VerificationRequest` and
  `VerificationResult` signatures.
- Security consistency: only exact provider selection loads code; no shell
  strings, secret values, provider bodies, private paths, or full datasets
  enter verification execution/results.
