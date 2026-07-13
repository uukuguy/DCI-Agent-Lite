# Installed DCI Claude Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or inline execution task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the installed DCI research application select either exact Pi or Claude runtime through paired immutable assemblies, with fixture-only CLI proof.

**Architecture:** Keep DCI's application identity, capability binding, and composition unchanged. Add a Claude-specific canonical assembly and make the generic CLI choose one selected application's unique assembly matching `--runtime`; provider metadata declares both IDs. The CLI remains DCI-neutral and every verification injects a fixture runtime rather than invoking Claude.

**Tech Stack:** Python 3.10+, `unittest`, Asterion immutable application/assembly contracts, `uv build`.

## Global Constraints

- Never invoke Claude, run `claude auth`, automate login, persist credentials, or make a network/provider request.
- Do not modify `src/dci/benchmark/`, package `src/dci`, create another wheel, or add DCI names to generic CLI/provider modules.
- Treat runtime compatibility as exact identity; Pi remains supported and controlled-code remains Pi-only.
- Runtime/assembly mismatch, absence, or ambiguity must fail before factory construction, input reading, catalog discovery, or execution with the existing content-free CLI failure.
- Use test-first changes, focused commits, `uv run python -m unittest`, Python compilation, Ruff, shell syntax, scope audit, and `git diff --check`.

---

## File Structure

- `packages/python/asterion-core/src/asterion/cli.py` — generic exact runtime-to-assembly selection and explicit-path runtime preflight.
- `packages/python/asterion-core/src/asterion/applications/selection.py` — exact application identity selection, independent of its runtime-specific assembly count.
- `tests/test_asterion_cli.py` — fixture provider tests for selected, missing, and ambiguous runtime assemblies plus a real bundled-DCI fixture CLI run.
- `tests/test_application_selection.py` — regression test that application selection permits multiple assemblies for later runtime selection.
- `packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py` — DCI-only declaration of the two allowed runtime IDs and assembly resources.
- `packages/python/asterion-core/src/asterion/applications/dci_agent_lite/assemblies/dci-research-capability-claude.json` — Claude runtime variant with the same composition as the Pi declaration.
- `tests/test_builtin_dci_application.py` and `tests/test_application_assembly.py` — provider/resource and immutable-composition parity checks.
- `tests/test_distribution_boundaries.py` — wheel-resource count/name verification.
- `README.md` and `docs/architecture/asterion-framework-layout.md` — operator contract, deferred real UAT, and advanced assembly behavior.
- `docs/status/{WORKLIST,CURRENT-STATE,DECISIONS,JOURNAL,RESUME-NEXT-SESSION}.md` — package closure and recovery facts.

### Task 1: Make generic application assembly selection runtime-exact

**Files:**
- Modify: `tests/test_asterion_cli.py`
- Modify: `tests/test_application_selection.py`
- Modify: `packages/python/asterion-core/src/asterion/cli.py`
- Modify: `packages/python/asterion-core/src/asterion/applications/selection.py`

**Interfaces:**
- Produce: `_select_application_assembly(application: InstalledApplication, runtime_id: str) -> Path`.
- Preserve: `main()` selects a provider and application before any runtime factory is constructed.
- Preserve: `select_installed_application()` proves one exact application identity only; it must not preempt runtime-specific assembly uniqueness.

- [ ] **Step 0: Remove the obsolete AF-130 single-assembly precondition with a failing test.**

  In `tests/test_application_selection.py`, construct one otherwise-valid application with two assembly paths and assert exact application selection returns it:

  ```python
  selected = select_installed_application(
      multiple, ApplicationSelector("example.research", "1.0.0")
  )
  self.assertEqual(len(selected.assembly_paths), 2)
  ```

  Run:

  ```bash
  uv run python -m unittest tests.test_application_selection.ApplicationSelectorTests.test_selects_application_with_multiple_assemblies -v
  ```

  Expected: failure from the old `len(application.assembly_paths) != 1` check. Remove only that check and change the docstring to "unique application"; duplicate application identities and unknown selectors must remain rejected.

- [ ] **Step 1: Write failing selection tests.**

  Add a `write_assembly(..., runtime_id, filename)` fixture helper in `tests/test_asterion_cli.py`, then assert application selection chooses the Claude path and refuses duplicate Claude assembly matches without calling a factory:

  ```python
  self.assertEqual(factory_calls[0].assembly_path.name, "claude.json")
  self.assertEqual(code, 2)
  self.assertEqual(factory_calls, [])
  ```

  Construct the test application with:

  ```python
  assembly_paths=(pi_assembly, claude_assembly)
  runtime_ids=("claude-code.reference", "pi.reference")
  ```

- [ ] **Step 2: Run the focused test and confirm the current first-path behavior fails.**

  Run:

  ```bash
  uv run python -m unittest tests.test_asterion_cli.AsterionCliTests.test_run_selects_matching_runtime_assembly -v
  ```

  Expected: failure because `_run()` always uses `application.assembly_paths[0]`.

- [ ] **Step 3: Implement the smallest generic selector.**

  Add the helper to `asterion/cli.py`:

  ```python
  def _select_application_assembly(
      application: InstalledApplication, runtime_id: str
  ) -> Path:
      matches = []
      for path in application.assembly_paths:
          try:
              assembly = json.loads(path.read_text())
          except (OSError, TypeError, ValueError):
              raise ApplicationProviderError("application assembly selection is invalid") from None
          if assembly.get("runtime_id") == runtime_id:
              matches.append(path)
      if len(matches) != 1:
          raise ApplicationProviderError("application assembly selection is invalid")
      return matches[0]
  ```

  Use it for `--application`. For `--assembly`, retain ownership validation and additionally load the selected manifest, requiring `assembly.get("runtime_id") == args.runtime` before `registry.select()`, `discover_packages()`, runtime construction, or input reading.

- [ ] **Step 4: Run the focused tests and static checks.**

  Run:

  ```bash
  uv run python -m unittest tests.test_asterion_cli -v
  uv run python -m compileall -q packages/python/asterion-core/src tests
  uv run ruff check packages/python/asterion-core/src/asterion/cli.py tests/test_asterion_cli.py
  ```

  Expected: all pass; the duplicate-runtime ambiguity test has zero factory calls. The existing resolver remains the explicit-path runtime-match gate before factory construction.

- [ ] **Step 5: Commit the generic selection boundary.**

  ```bash
  git add packages/python/asterion-core/src/asterion/cli.py tests/test_asterion_cli.py
  git commit -m "feat: select application assemblies by runtime"
  ```

### Task 2: Declare paired DCI runtime assemblies

**Files:**
- Create: `packages/python/asterion-core/src/asterion/applications/dci_agent_lite/assemblies/dci-research-capability-claude.json`
- Modify: `packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py`
- Modify: `tests/test_builtin_dci_application.py`
- Modify: `tests/test_application_assembly.py`

**Interfaces:**
- Produce: one `dci.research-capability@1.0.0` provider declaration with exactly `("claude-code.reference", "pi.reference")` and one assembly per ID.
- Preserve: `DciLocalResearchImplementation` and all Pi assembly contents.

- [ ] **Step 1: Write failing provider/resource parity tests.**

  Assert the built-in DCI provider exposes both exact runtime IDs and these assembly file names:

  ```python
  self.assertEqual(application.runtime_ids, ("claude-code.reference", "pi.reference"))
  self.assertEqual(
      {path.name for path in application.assembly_paths},
      {"dci-research-capability.json", "dci-research-capability-claude.json"},
  )
  ```

  Parse the two JSON files and compare all fields after removing `runtime_id`; assert Pi/Claude values are exact and `validate_assembly_manifest()` accepts both.

- [ ] **Step 2: Run tests and confirm the Claude resource/declaration is absent.**

  Run:

  ```bash
  uv run python -m unittest tests.test_builtin_dci_application tests.test_application_assembly -v
  ```

  Expected: failure because the installed provider contains only Pi and the Claude assembly does not exist.

- [ ] **Step 3: Add the paired declaration.**

  Copy `dci-research-capability.json` to the new Claude file, changing only:

  ```json
  "runtime_id": "claude-code.reference"
  ```

  Update `create_provider()` to provide both paths and the sorted runtime tuple:

  ```python
  assembly_paths=(
      application_root / "assemblies/dci-research-capability-claude.json",
      application_root / "assemblies/dci-research-capability.json",
  ),
  runtime_ids=("claude-code.reference", "pi.reference"),
  ```

  Do not modify the controlled-code provider.

- [ ] **Step 4: Run focused verification.**

  Run:

  ```bash
  uv run python -m unittest tests.test_builtin_dci_application tests.test_application_assembly tests.test_dci_research_capability -v
  uv run ruff check packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py tests/test_builtin_dci_application.py tests/test_application_assembly.py
  ```

  Expected: the paired manifests resolve to equal compositions and existing Pi capability tests remain green.

- [ ] **Step 5: Commit the DCI declaration.**

  ```bash
  git add packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py \
    packages/python/asterion-core/src/asterion/applications/dci_agent_lite/assemblies/dci-research-capability-claude.json \
    tests/test_builtin_dci_application.py tests/test_application_assembly.py
  git commit -m "feat: declare DCI Claude compatibility"
  ```

### Task 3: Prove the installed generic CLI path with fixtures only

**Files:**
- Modify: `tests/test_asterion_cli.py`

**Interfaces:**
- Consume: Task 1's runtime-exact selector and Task 2's DCI provider resources.
- Produce: a direct `main()` test whose injected Claude fixture produces a valid DCI research result without subprocess, credentials, or network access.

- [ ] **Step 1: Write a failing bundled-DCI Claude CLI test.**

  Add a fixture runtime with exact Claude manifest and protocol-valid events:

  ```python
  class DciClaudeFixtureRuntime:
      manifest = RuntimeManifest(
          runtime_id="claude-code.reference",
          capabilities=("filesystem.read", "shell"),
      )

      async def run(self, request: RunRequest, *, signal: object | None = None):
          del signal
          yield RunEvent(request.run_id, 1, "run.started", {"capabilities": []})
          yield RunEvent(request.run_id, 2, "artifact.created", {"artifact": {
              "artifact_id": "answer", "kind": "answer",
              "media_type": "text/plain", "uri": "fixture-answer.txt",
          }})
          yield RunEvent(request.run_id, 3, "run.completed", {"status": "completed"})
  ```

  Invoke `main()` with `--provider dci-agent-lite`, `--application dci.research-capability@1.0.0`, and `--runtime claude-code.reference`; inject a registry binding whose factory appends its context and returns this fixture. Assert exit code zero, selected assembly ends in `dci-research-capability-claude.json`, output runtime is Claude, and a `SECRET-INPUT` sentinel is absent from output/error.

- [ ] **Step 2: Run it and confirm the pre-change provider rejects Claude.**

  Run:

  ```bash
  uv run python -m unittest tests.test_asterion_cli.AsterionCliTests.test_bundled_dci_runs_with_claude_fixture -v
  ```

  Expected: failure before fixture execution until Tasks 1 and 2 are complete.

- [ ] **Step 3: Keep the test fixture-only.**

  Do not add a subprocess mock, environment variable, Claude executable lookup, network fixture, or account probe. The injected `RuntimeFactoryRegistry` is the sole runtime authority for this test.

- [ ] **Step 4: Run the complete CLI and package-execution checks.**

  Run:

  ```bash
  uv run python -m unittest tests.test_asterion_cli tests.test_builtin_dci_application tests.test_dci_research_capability -v
  uv run ruff check tests/test_asterion_cli.py
  ```

  Expected: Pi and Claude fixture paths pass through the same DCI implementation; no test starts a real Claude process.

- [ ] **Step 5: Commit the fixture proof.**

  ```bash
  git add tests/test_asterion_cli.py
  git commit -m "test: prove DCI Claude CLI compatibility"
  ```

### Task 4: Verify distribution, document the boundary, and close AF-170

**Files:**
- Modify: `tests/test_distribution_boundaries.py`
- Modify: `README.md`
- Modify: `docs/architecture/asterion-framework-layout.md`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- Consume: both canonical DCI resources and the generic selector.
- Produce: an isolated-wheel assertion, accurate operator documentation, AF-170 closure evidence, and a recovery checkpoint.

- [ ] **Step 1: Write the failing wheel resource assertion.**

  In `test_asterion_is_the_only_buildable_wheel`, replace the bare assembly count with exact names:

  ```python
  self.assertEqual(
      {Path(name).name for name in assemblies},
      {
          "controlled-code-validation.json",
          "dci-local-research.json",
          "dci-research-capability.json",
          "dci-research-capability-claude.json",
      },
  )
  ```

- [ ] **Step 2: Run the wheel test and confirm it fails until the new resource is packaged.**

  Run:

  ```bash
  uv run python -m unittest tests.test_distribution_boundaries.BuiltDistributionBoundaryTests.test_asterion_is_the_only_buildable_wheel -v
  ```

  Expected: old wheel resource set is missing the Claude assembly.

- [ ] **Step 3: Document exact operator behavior.**

  Update README's installed command section to show the same DCI selector may use either listed exact runtime, while stating the Claude spelling is fixture-verified only until authorization. Update the layout guide to state that `--application` chooses the unique assembly matching `--runtime`, and that explicit `--assembly` must declare that same runtime.

- [ ] **Step 4: Run full repository closure.**

  Run:

  ```bash
  uv run python -m unittest discover -v
  uv run python -m compileall -q packages/python/asterion-core/src tests
  uv run ruff check packages/python/asterion-core/src/asterion/cli.py \
    packages/python/asterion-core/src/asterion/applications/dci_agent_lite/provider.py tests
  (cd packages/typescript/asterion-runtime && npm test)
  (cd packages/rust/controlled-executor && cargo test)
  rg --files -g '*.sh' | xargs -n 1 bash -n
  python3 tools/project_scope_check.py
  git diff --check
  ```

  Expected: all gates pass with no provider request and the wheel contains Asterion only, never `dci`.

- [ ] **Step 5: Record closure and commit.**

  Mark AF-170 completed only after the scope audit passes again. Journal the exact test totals, record the deferred real-provider UAT in CURRENT-STATE/RESUME, and commit:

  ```bash
  git add README.md docs tests packages/python/asterion-core/src
  git commit -m "docs: close DCI Claude compatibility"
  ```

## Plan Self-Review

- Product contract: Task 2 creates paired immutable declarations; Task 1 keeps their selection generic and exact.
- Security/failure boundary: Task 1 proves mismatch and ambiguity fail before factory construction; Task 3 injects the sole fixture authority and forbids real Claude access.
- Pi preservation and controlled-code isolation: Task 2 keeps Pi content intact and asserts controlled-code remains unchanged.
- Distribution and operator documentation: Task 4 verifies exact wheel contents and documents fixture-only versus future authorized UAT.
- No task adds a second wheel, dynamic runtime inference, credential configuration, or a source-baseline dependency.
