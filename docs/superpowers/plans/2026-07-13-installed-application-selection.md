# Installed Application Selection Implementation Plan

> **For agentic workers:** Execute inline with test-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** List and run installed Asterion applications by exact `application_id@version` without exposing package-internal assembly paths.

**Architecture:** A pure selection module parses exact selectors and matches immutable provider applications. The CLI retains metadata-only global listing, loads only an explicitly selected provider for application listing/run, and keeps explicit assembly modes as compatibility paths.

**Tech Stack:** Python 3.10+, argparse, importlib metadata/resources, unittest, existing provider and runtime contracts.

## Global Constraints

- Plain `asterion list` must never load provider code.
- Exact application selection occurs only within one explicitly selected provider.
- No aliases, ranges, implicit latest version, global application scanning, or DCI-specific logic in generic modules.
- Runtime construction remains after provider, application, assembly, catalog, and binding preflight.
- Preserve `--assembly` and the AF-120 positional assembly spelling.

---

### Task 1: Exact application selector

**Files:**
- Create: `packages/python/asterion-core/src/asterion/applications/selection.py`
- Create: `tests/test_application_selection.py`

**Interfaces:**
- Produces frozen `ApplicationSelector(application_id: str, version: str)`.
- Produces `parse_application_selector(value: str) -> ApplicationSelector`.
- Produces `select_installed_application(provider, selector) -> InstalledApplication`.

- [ ] Write tests accepting `example.research@1.2.3` and rejecting whitespace, missing `@`, ranges, partial versions, invalid IDs, unknown matches, duplicate matches, and multiple assemblies.
- [ ] Run `uv run python -m unittest tests.test_application_selection -v` and confirm RED.
- [ ] Implement exact parsing/matching with fixed content-free `ApplicationProviderError` messages.
- [ ] Re-run focused tests, compile, Ruff, scope, and diff checks.
- [ ] Commit `feat: select installed applications exactly`.

### Task 2: Application-aware list and run CLI

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/cli.py`
- Modify: `tests/test_asterion_cli.py`
- Modify: `tests/test_builtin_dci_application.py`

**Interfaces:**
- `asterion list [--provider PROVIDER_ID]`.
- `asterion run --provider ID --runtime ID (--application ID@VERSION | --assembly PATH | LEGACY_PATH)`.

- [ ] Add failing tests for selected-provider application listing, exact application run, conflicting/missing modes before provider load, `--assembly`, legacy positional compatibility, deterministic output, and no DCI literal in generic modules.
- [ ] Run CLI tests and confirm RED for missing parser/selection behavior.
- [ ] Implement mode validation before provider load, selected application resolution, deterministic application JSON, and shared assembly execution.
- [ ] Re-run CLI/provider/discovery/selection suites plus compile, Ruff, scope, and diff checks.
- [ ] Commit `feat: run installed applications by identity`.

### Task 3: Installed product verification and AF-130 closure

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/asterion-framework-layout.md`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md` when checkpoint threshold is met.

**Interfaces:**
- Produces installed-wheel `list --provider dci-agent-lite` output and exact DCI application selection without `dci` import availability.

- [ ] Build/install the sole Asterion wheel in an isolated environment and verify global list, provider application list, resources, and exact selector preflight.
- [ ] Run  full Python, Node, Rust, compile, lint, shell, scope, and diff gates.
- [ ] Update user documentation, acceptance evidence, and governed successor state.
- [ ] Commit `docs: close installed application selection`.
