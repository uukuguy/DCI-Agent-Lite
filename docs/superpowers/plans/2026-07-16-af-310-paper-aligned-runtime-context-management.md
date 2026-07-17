# AF-310 Paper-Aligned Runtime Context Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `climb` for the package's
> hypothesis/evidence loop and `test-driven-development` for every behavior
> change. Execute this plan task-by-task in the current repository. Do not edit
> the external `pi/` checkout.

**Goal:** Replace Asterion's recorded-but-unsupported runtime context setting
with an Asterion-owned, packaged, exact DCI paper L0–L4 policy that operates on
Pi's live model context and is selectable through run, benchmark, resume,
installed application, and isolated-wheel execution.

**Architecture:** Python owns the closed profile contract, packaged-resource
integrity, immutable run identity, Pi argv, telemetry ingestion, artifacts, and
operator errors. One dependency-free TypeScript Pi extension owns live
tool-result truncation, L3 context compaction, and L4 summarization/retry state
through documented Pi hooks. Its authoritative source is mirrored byte-for-byte
into the Python wheel by a deterministic sync script; the Python resolver
verifies the expected SHA-256 digest before starting Pi. Pi custom session
entries carry body-free telemetry, which the RPC client retrieves with
`get_entries` before finalization. Model-free fixtures inspect the exact
messages returned by the extension's `context` hook; bounded Pi acceptance must
force and observe both L3 and L4 transitions.

**Tech Stack:** Python 3.10+, frozen dataclasses, `importlib.resources`, Hatch,
TypeScript 6, Node 20 test runner, Pi extension/RPC APIs, JSON Schema,
`unittest`, Ruff, Climb.

## Global Constraints

- Parent every task and Climb hypothesis to active work package `AF-310`; run
  `python3 tools/project_scope_check.py` before implementation and closure.
- Treat `pi/` as a read-only external checkout. Do not add imports, patches,
  commits, generated files, or configuration under it.
- Support exactly `level0`, `level1`, `level2`, `level3`, and `level4`. Reject
  `level5`, `legacy`, empty strings, and unknown values before filesystem
  mutation or a provider request.
- Preserve existing behavior when no runtime context profile is requested; no
  extension is loaded and no paper-aligned claim is made.
- L0 loads the extension and records effective policy evidence even though it
  performs no truncation, compaction, or summary.
- Character caps are Unicode string length after Pi has normalized tool-result
  content to text: L1 50,000 and L2–L4 20,000 characters. Keep a deterministic
  suffix marker whose length is included in the cap.
- L3 triggers when accumulated original tool-result characters exceed 240,000,
  then retains the most recent 12 complete user/assistant turns. L4 adds a
  20,000-token recent-context target and suppresses summarization after three
  consecutive failures; successful summarization resets the failure count.
- No prompt, answer, tool-result body, credential, endpoint body, or private
  artifact path may appear in telemetry or public application projection.
- Resume must reject changed profile, contract version, thresholds, extension
  version/digest, missing policy state, or incompatible Pi session before a
  provider request.
- The packaged extension must not use runtime imports. Pi supplies the API
  object; the file contains its own structural TypeScript types and uses only
  JavaScript built-ins.
- No full dataset or AF-320/330/340 work is authorized by this plan.

---

## Task 0: Activate AF-310 governance and a fresh Climb session

**Files:**
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`
- Modify/Create through Climb tools: `docs/status/climb/**`

**Interfaces:**
- Consumes: the approved paper-aligned design and this plan.
- Produces: one active package and package-parented, resumable hypotheses.

- [ ] **Step 1: Record the package and architecture decision**

  Add AF-310 as the sole `in_progress` work package. Link the approved design
  and this plan, depend on AF-300, and copy the six AF-310 acceptance bullets
  from the design. Add D-044 recording the staged AF-310→AF-340 decision, the
  Asterion-owned extension boundary, and the four evidence layers. Supersede
  D-039 only for explicitly selected paper profiles; its no-fabricated-Pi-flag
  rule remains valid.

- [ ] **Step 2: Refresh structural and resume truth**

  Set lifecycle `active`, focus and active package to AF-310, name Task 1 as the
  next action, and state that prior 8/8 product parity is not paper parity.
  Append the activation fact to JOURNAL; do not rewrite old entries.

- [ ] **Step 3: Initialize the package Climb pool**

  Archive no historical evidence and do not reopen completed hypotheses. Create
  fresh AF-310 hypotheses for: H-001 contract parity, H-002 live transformation,
  H-003 packaging/transport/resume, H-004 artifact/application exposure, and
  H-005 bounded L3/L4 runtime evidence. Each hypothesis names `AF-310`, an
  isolated artifact root, a falsifiable expected result, and its test command.

- [ ] **Step 4: Run governance RED/GREEN preflight**

  Run before and after the edits:

  ```bash
  python3 tools/project_scope_check.py
  uv run python -m unittest tests.test_project_scope_check tests.test_climb_tools -v
  git diff --check
  ```

  The final scope JSON must report `AF-310`, lifecycle `active`, and no errors.

- [ ] **Step 5: Commit the governed start**

  ```bash
  git add docs/status
  git commit -m "docs: activate AF-310 runtime context management"
  ```

  Journal the commit hash in a follow-up state commit if the journal entry could
  not know it before commit.

---

## Task 1: Define the closed cross-language context-profile contract

**Files:**
- Create: `asterion/src/asterion/dci/context_profiles.py`
- Create: `asterion/src/asterion/dci/resources/context-profile.schema.json`
- Create: `asterion/src/asterion/dci/resources/context-profiles.json`
- Create: `tests/test_asterion_dci_context_profiles.py`
- Modify: `asterion/src/asterion/dci/config.py`
- Modify: `asterion/src/asterion/dci/run.py`
- Modify: `tests/test_asterion_dci_config.py`
- Modify: `tests/test_asterion_dci_run.py`

**Interfaces:**
- Produces `DciContextProfile`, `resolve_context_profile()`, and canonical
  `dci.context-profile/v1` JSON fixtures.
- Replaces free-form strings with one validated immutable profile or `None`.

- [ ] **Step 1: Write contract and invalid-input tests first**

  Assert exact settings for all five profiles, exact JSON round-trip, stable
  `identity_payload()`, and rejection of `level5`, `legacy`, whitespace aliases,
  booleans, and unknown keys. Assert invalid CLI/environment/application values
  fail before output directory creation. Replace the two tests that expect an
  `unsupported` diagnostic with tests that expect validated effective policy.

- [ ] **Step 2: Run focused tests and verify RED**

  ```bash
  uv run --project asterion python -m unittest \
    tests.test_asterion_dci_context_profiles \
    tests.test_asterion_dci_config \
    tests.test_asterion_dci_run -v
  ```

- [ ] **Step 3: Implement the frozen profile model**

  Use explicit fields and typed validation rather than accepting arbitrary
  mappings:

  ```python
  @dataclass(frozen=True)
  class DciContextProfile:
      name: Literal["level0", "level1", "level2", "level3", "level4"]
      contract_version: str
      tool_result_character_cap: int | None
      compaction_character_trigger: int | None
      retained_turns: int | None
      summary_recent_token_target: int | None
      summary_failure_limit: int | None

      def identity_payload(self) -> dict[str, object]:
          return {
              "profile": self.name,
              "contract_version": self.contract_version,
              "tool_result_character_cap": self.tool_result_character_cap,
              "compaction_character_trigger": self.compaction_character_trigger,
              "retained_turns": self.retained_turns,
              "summary_recent_token_target": self.summary_recent_token_target,
              "summary_failure_limit": self.summary_failure_limit,
          }
  ```

  Load the package resource once, validate the closed schema and exact expected
  names, and return canonical instances. `resolve_context_profile(None)` returns
  `None`; every non-`None` value must be an exact profile name.

- [ ] **Step 4: Thread the typed profile through request validation**

  Keep `runtime_context_level` at public parsing boundaries for compatibility,
  but resolve it into `context_profile: DciContextProfile | None` on the native
  request. Persist only the canonical name plus identity payload. Make
  `request_from_runtime_options()` and resume use the same resolver.

- [ ] **Step 5: Verify schema, compile, and lint**

  ```bash
  uv run --project asterion python -m unittest \
    tests.test_asterion_dci_context_profiles \
    tests.test_asterion_dci_config \
    tests.test_asterion_dci_run -v
  uv run --project asterion python -m compileall -q \
    src/asterion/dci/context_profiles.py src/asterion/dci/config.py src/asterion/dci/run.py
  uv run --project asterion ruff check \
    src/asterion/dci/context_profiles.py src/asterion/dci/config.py src/asterion/dci/run.py \
    tests/test_asterion_dci_context_profiles.py tests/test_asterion_dci_config.py \
    tests/test_asterion_dci_run.py
  ```

- [ ] **Step 6: Commit H-001**

  ```bash
  git add asterion/src/asterion/dci tests/test_asterion_dci_context_profiles.py \
    tests/test_asterion_dci_config.py tests/test_asterion_dci_run.py
  git commit -m "feat(dci): define paper context profiles"
  ```

  Record H-001 as verified or falsified with exact test counts and advance
  immediately.

---

## Task 2: Implement and test the live TypeScript policy engine

**Files:**
- Create: `asterion/packages/typescript/dci-context-extension/package.json`
- Create: `asterion/packages/typescript/dci-context-extension/tsconfig.json`
- Create: `asterion/packages/typescript/dci-context-extension/src/dci-context-extension.ts`
- Create: `asterion/packages/typescript/dci-context-extension/test/policy.test.mjs`
- Create: `asterion/packages/typescript/dci-context-extension/test/extension.test.mjs`

**Interfaces:**
- Exports pure `truncateToolResult`, `transformContext`, `planCompaction`,
  `recordSummaryResult`, and a default Pi extension initializer.
- Registers `--dci-context-profile` and `--dci-context-contract` extension flags.
- Emits `dci.context-telemetry/v2` custom entries with counters only; v2 represents
  an unobserved preserved-turn count as `null` rather than conflating it with zero.

- [ ] **Step 1: Build a fake Pi harness and RED policy matrix**

  The harness captures registered flags and handlers, invokes handlers with
  frozen fixtures, and records `appendEntry` calls. Tests must inspect the
  returned model-visible messages, not a saved conversation artifact. Cover:

  - L0 identity and effective-policy telemetry;
  - L1 exact 49,999/50,000/50,001 boundaries;
  - L2–L4 exact 19,999/20,000/20,001 boundaries;
  - marker-inclusive caps and non-string content blocks;
  - 240,000 versus 240,001 accumulated original characters;
  - retention of 12 complete turns without orphaned tool results;
  - L4 20,000-token target using the compaction preparation boundary, rejecting
    an incompatible Pi preparation rather than silently estimating a new one;
  - failures 1/2/3, suppression after failure 3, and reset after success;
  - handler reentrancy and two independent extension instances; and
  - telemetry key allowlist and absence of fixture secret substrings.

- [ ] **Step 2: Run Node tests and verify RED**

  ```bash
  npm --prefix asterion/packages/typescript/dci-context-extension test
  ```

- [ ] **Step 3: Implement deterministic pure transformations**

  Keep state serializable and body-free:

  ```typescript
  export interface PolicyState {
    accumulatedOriginalToolCharacters: number;
    compactionCount: number;
    summaryAttempts: number;
    summarySuccesses: number;
    consecutiveSummaryFailures: number;
    summarySuppressed: boolean;
  }

  export function truncateText(text: string, cap: number): string {
    const marker = "\n[DCI tool result truncated]";
    if (text.length <= cap) return text;
    return text.slice(0, Math.max(0, cap - marker.length)) + marker;
  }
  ```

  Never mutate input messages. Count the original model-visible tool-result
  text before truncation. Preserve tool call/result ordering and complete turn
  boundaries.

- [ ] **Step 4: Bind documented Pi hooks**

  Register `tool_result` for per-result truncation, `turn_end` to call
  `ctx.compact()` exactly once when the 240,000-character threshold is crossed,
  `context` for exact model-visible L3/L4 retention,
  `session_before_compact` and `session_compact` for custom compaction evidence,
  and `session_start` for state restoration. For L3, the before-compaction hook
  supplies an empty summary and the computed 12-turn `firstKeptEntryId`. For L4,
  it verifies the Pi preparation retains the required 20,000-token recent
  boundary and permits summarization; an incompatible preparation fails closed.
  Persist state with `appendEntry("dci-context-state", ...)`; persist telemetry
  with `appendEntry("dci-context-telemetry", ...)`. Reject missing/unknown flags
  during `session_start` by throwing before the first prompt.

  The extension must not call `sendMessage`, read environment credentials,
  traverse the filesystem, import a package at runtime, or expose message
  content in custom entries.

- [ ] **Step 5: Compile and run the exact hook matrix**

  ```bash
  npm --prefix asterion/packages/typescript/dci-context-extension test
  npm --prefix asterion/packages/typescript/dci-context-extension run build
  ```

  Inspect compiled output to ensure there are no runtime imports:

  ```bash
  rg -n '^import |require\(' \
    asterion/packages/typescript/dci-context-extension/dist/dci-context-extension.js
  ```

  Expected: `rg` exits 1 because no runtime imports exist.

- [ ] **Step 6: Commit the policy engine**

  ```bash
  git add asterion/packages/typescript/dci-context-extension
  git commit -m "feat(dci): implement live context policy extension"
  ```

  Update H-002 with boundary counts and fixture evidence.

---

## Task 3: Package and integrity-check the extension resource

**Files:**
- Create: `asterion/packages/typescript/dci-context-extension/scripts/sync-runtime-resource.mjs`
- Create: `asterion/src/asterion/dci/resources/pi/__init__.py`
- Create: `asterion/src/asterion/dci/resources/pi/dci-context-extension.ts`
- Create: `asterion/src/asterion/dci/resources/pi/context-extension-manifest.json`
- Create: `asterion/src/asterion/dci/context_extension.py`
- Create: `tests/test_asterion_dci_context_extension.py`
- Modify: `asterion/pyproject.toml`
- Modify: `asterion/packages/typescript/dci-context-extension/package.json`
- Modify: `tests/test_distribution_boundaries.py`

**Interfaces:**
- Produces `ResolvedContextExtension(path, version, sha256, contract_version)`
  from an exact package resource.
- The sync command copies bytes atomically and `--check` fails on drift.

- [ ] **Step 1: Write RED sync, resolver, and wheel tests**

  Assert source and mirror are byte-identical; missing files, directories,
  symlinks, world-writable files, unexpected digest, and malformed source fail
  closed. Build an isolated wheel, install it without the repository, resolve
  the extension, and assert the same digest and exact source bytes.

- [ ] **Step 2: Run focused tests and verify RED**

  ```bash
  uv run --project asterion python -m unittest \
    tests.test_asterion_dci_context_extension \
    tests.test_distribution_boundaries -v
  ```

- [ ] **Step 3: Add deterministic resource sync**

  Add package scripts:

  ```json
  {
    "scripts": {
      "build": "tsc -p tsconfig.json",
      "sync-resource": "node scripts/sync-runtime-resource.mjs",
      "check-resource": "node scripts/sync-runtime-resource.mjs --check",
      "test": "npm run build && node --test test/*.test.mjs && npm run check-resource"
    }
  }
  ```

  The script's source is `src/dci-context-extension.ts`; destination is
  `../../../src/asterion/dci/resources/pi/dci-context-extension.ts`. It also
  writes a closed manifest with extension version, contract version, byte
  length, and SHA-256. It must use same-directory temporary files plus rename
  and never follow a destination symlink.

- [ ] **Step 4: Implement the Python resolver**

  Use `importlib.resources.files("asterion.dci.resources.pi")`, open the
  resource without following symlinks where the platform permits, calculate
  SHA-256, compare it to the digest derived from the canonical distribution
  manifest, and return an `as_file()` context whose lifetime spans Pi. Do not
  accept an environment or CLI extension path override.

- [ ] **Step 5: Include and verify the resource in wheels**

  Add the `*.ts` package-resource include explicitly to Hatch configuration.
  Verify both editable/source and isolated-wheel paths:

  ```bash
  npm --prefix asterion/packages/typescript/dci-context-extension run sync-resource
  npm --prefix asterion/packages/typescript/dci-context-extension test
  uv run --project asterion python -m unittest \
    tests.test_asterion_dci_context_extension \
    tests.test_distribution_boundaries -v
  ```

- [ ] **Step 6: Commit H-003 packaging evidence**

  ```bash
  git add asterion/pyproject.toml \
    asterion/packages/typescript/dci-context-extension \
    asterion/src/asterion/dci/context_extension.py \
    asterion/src/asterion/dci/resources/pi \
    tests/test_asterion_dci_context_extension.py \
    tests/test_distribution_boundaries.py
  git commit -m "feat(dci): package context extension with integrity checks"
  ```

---

## Task 4: Load the extension through literal Pi argv and prove hook compatibility

**Files:**
- Modify: `asterion/src/asterion/dci/pi_rpc.py`
- Modify: `asterion/src/asterion/dci/run.py`
- Create: `tests/fixtures/pi-context-extension-harness.mjs`
- Modify: `tests/test_asterion_dci_pi_rpc.py`
- Modify: `tests/test_asterion_dci_run.py`

**Interfaces:**
- Adds typed `extension_path`, profile, and contract arguments to `PiRpcClient`.
- Adds `get_entries()` and returns only validated DCI custom entries.
- Uses Pi's public `--extension`, extension-registered
  `--dci-context-profile`, and `--dci-context-contract` flags.

- [ ] **Step 1: Write argv and read-only-checkout tests first**

  Assert exact argv ordering and literal path handling for spaces and shell
  metacharacters. Assert no context flags when no profile is selected. Assert
  extension resolution and all validation occur before `Popen`. Snapshot the
  external Pi worktree before/after a harness run and require no changes.

- [ ] **Step 2: Write RPC `get_entries` RED tests**

  Model interleaved RPC events, response IDs, invalid shapes, duplicate state
  entries, unknown schema versions, and content-bearing telemetry. Require safe
  `RuntimeError` messages without raw payloads.

- [ ] **Step 3: Implement typed transport**

  Construct literal arguments in `_pi_extra_args()`:

  ```python
  if context is not None:
      values.extend((
          "--extension", str(context.extension.path),
          "--dci-context-profile", context.profile.name,
          "--dci-context-contract", context.profile.contract_version,
      ))
  ```

  Do not put these values through `shlex.split`. Keep user `extra_args`
  separate and reject user attempts to supply `--extension` or reserved
  `--dci-context-*` flags when a paper profile is selected.

- [ ] **Step 4: Retrieve and validate extension entries before finalize**

  After `prompt_and_wait`, send `get_entries`, select exact custom types, validate
  schemas and monotonic counters, then pass them to the recorder. A missing
  startup/effective-policy entry makes a requested-profile run fail. Preserve
  raw validated entries only in private native evidence.

- [ ] **Step 5: Run the real Pi model-free harness**

  The harness loads the packaged extension through the external Pi loader but
  replaces provider execution with fixed messages. It must show the `context`
  hook's exact output for L0–L4 and verify the Pi checkout stays clean.

  ```bash
  uv run --project asterion python -m unittest \
    tests.test_asterion_dci_pi_rpc \
    tests.test_asterion_dci_run -v
  ```

- [ ] **Step 6: Commit typed Pi integration**

  ```bash
  git add asterion/src/asterion/dci/pi_rpc.py \
    asterion/src/asterion/dci/run.py \
    tests/test_asterion_dci_pi_rpc.py \
    tests/test_asterion_dci_run.py \
    tests/fixtures/pi-context-extension-harness.mjs
  git commit -m "feat(dci): execute context profiles through Pi extension"
  ```

---

## Task 5: Persist exact policy identity, telemetry, and immutable resume state

**Files:**
- Modify: `asterion/src/asterion/dci/artifacts.py`
- Modify: `asterion/src/asterion/dci/run.py`
- Modify: `asterion/src/asterion/dci/bridge.py`
- Modify: `tests/test_asterion_dci_artifacts.py`
- Modify: `tests/test_asterion_dci_run.py`
- Modify: `asterion/tests/test_asterion_dci_bridge.py`

**Interfaces:**
- Replaces `runtime_context_control.status == "unsupported"` with an effective
  `dci.context-policy-evidence/v2` record.
- Produces private `context-policy.json` and body-free public counters.

- [ ] **Step 1: Write RED artifact and resume compatibility tests**

  Require profile name, immutable thresholds, contract/extension versions,
  extension SHA-256, per-attempt telemetry references, and aggregate counters.
  Try changing each identity field on resume and assert failure before client
  construction. Test incomplete/failed attempt resume, malformed custom state,
  missing session entries, and independent attempt evidence.

- [ ] **Step 2: Implement one validated evidence model**

  Add a frozen evidence object with explicit parser and projection:

  ```python
  @dataclass(frozen=True)
  class DciContextPolicyEvidence:
      schema: Literal["dci.context-policy-evidence/v2"]
      profile: DciContextProfile
      extension_version: str
      extension_sha256: str
      telemetry: tuple[DciContextTelemetry, ...]

      def public_summary(self) -> dict[str, object]:
          return {
              "schema": self.schema,
              "profile": self.profile.name,
              "extension_sha256": self.extension_sha256,
              "truncated_results": sum(t.truncated_results for t in self.telemetry),
              "compactions": sum(t.compactions for t in self.telemetry),
              "summary_attempts": sum(t.summary_attempts for t in self.telemetry),
              "summary_successes": sum(t.summary_successes for t in self.telemetry),
              "summary_suppressed": any(t.summary_suppressed for t in self.telemetry),
          }
  ```

  Validate key allowlists, nonnegative integer types, profile match, monotonic
  event sequence, and digest format. Never persist an unvalidated entry.

- [ ] **Step 3: Make recorder writes atomic and attempt-scoped**

  Write `context-policy.json` with private permissions, include its digest and
  relative artifact name in state, and put attempt telemetry under the existing
  attempt boundary. Existing attempts are append-only. Public protocol events
  contain the safe summary only.

- [ ] **Step 4: Enforce resume identity before provider startup**

  `resume_request_from_output_dir()` reconstructs the canonical profile;
  `DciRunRecorder` compares exact identity payload and packaged extension
  digest; Pi session restoration must expose the last valid policy-state entry.
  Reject any mismatch with `DCI resume validation failed`.

- [ ] **Step 5: Run focused privacy and resume tests**

  ```bash
  uv run --project asterion python -m unittest \
    tests.test_asterion_dci_artifacts \
    tests.test_asterion_dci_run -v
  uv run --project asterion python -m unittest discover \
    -s asterion/tests -p 'test_asterion_dci_bridge.py' -v
  ```

- [ ] **Step 6: Commit immutable evidence and update H-003**

  ```bash
  git add asterion/src/asterion/dci/artifacts.py \
    asterion/src/asterion/dci/run.py \
    asterion/src/asterion/dci/bridge.py \
    tests/test_asterion_dci_artifacts.py \
    tests/test_asterion_dci_run.py \
    asterion/tests/test_asterion_dci_bridge.py
  git commit -m "feat(dci): persist immutable context policy evidence"
  ```

---

## Task 6: Expose one implementation through CLI, benchmark, and application

**Files:**
- Modify: `asterion/src/asterion/dci/cli.py`
- Modify: `asterion/src/asterion/dci/benchmark.py`
- Modify: `asterion/src/asterion/dci/application_executor.py`
- Modify: `asterion/src/asterion/applications/dci_agent_lite/provider.py`
- Modify: `asterion/src/asterion/capabilities/dci_research/implementation.py`
- Modify: `tests/test_asterion_dci_cli.py`
- Modify: `tests/test_asterion_dci_batch.py`
- Modify: `tests/test_asterion_dci_application_executor.py`
- Modify: `asterion/tests/test_dci_research_capability.py`
- Modify: `asterion/tests/test_asterion_dci_bridge.py`

**Interfaces:**
- All public entry points consume the same profile resolver and native runner.
- Application output adds body-free context-policy evidence and an artifact ref.

- [ ] **Step 1: Write RED surface-equivalence tests**

  For each L0–L4 profile, assert `asterion-dci run`, `benchmark`, runtime options,
  and installed application build the same canonical identity. Assert exact
  argparse choices/help and closed invalid values. Assert batch fingerprints
  include the full policy identity and extension digest, preventing cross-policy
  reuse.

- [ ] **Step 2: Implement shared surface mapping**

  Give CLI `choices=context_profile_names()`. Resolve profiles once at the
  boundary and pass the typed profile through run options. Do not duplicate
  threshold constants in CLI, benchmark, application, or capability code.

- [ ] **Step 3: Extend safe application projection**

  Add only profile, schema/version, extension digest, counters, and an opaque
  artifact reference. Tests inject prompt/answer/tool/credential canaries and
  assert none cross the public boundary.

- [ ] **Step 4: Verify batch reuse and application cancellation/failure**

  Cover new run, resume, reuse, cancellation, timeout, extension startup
  failure, malformed telemetry, and provider failure. Every preflight failure
  must result in zero provider operations.

- [ ] **Step 5: Run focused surface suite**

  ```bash
  uv run --project asterion python -m unittest \
    tests.test_asterion_dci_cli \
    tests.test_asterion_dci_batch \
    tests.test_asterion_dci_application_executor -v
  uv run --project asterion python -m unittest discover \
    -s asterion/tests -p 'test_dci_research_capability.py' -v
  uv run --project asterion python -m unittest discover \
    -s asterion/tests -p 'test_asterion_dci_bridge.py' -v
  ```

- [ ] **Step 6: Commit H-004**

  ```bash
  git add asterion/src/asterion/dci/cli.py \
    asterion/src/asterion/dci/benchmark.py \
    asterion/src/asterion/dci/application_executor.py \
    asterion/src/asterion/applications/dci_agent_lite/provider.py \
    asterion/src/asterion/capabilities/dci_research/implementation.py \
    tests/test_asterion_dci_cli.py tests/test_asterion_dci_batch.py \
    tests/test_asterion_dci_application_executor.py \
    asterion/tests/test_dci_research_capability.py \
    asterion/tests/test_asterion_dci_bridge.py
  git commit -m "feat(dci): expose live context profiles across product surfaces"
  ```

---

## Task 7: Update launchers, examples, and truthful product documentation

**Files:**
- Modify: `asterion/src/asterion/dci/resources/batch-profiles.json`
- Modify: `asterion/scripts/bcplus_eval/run_bcplus_eval_openai.sh`
- Modify: other `asterion/scripts/{qa,bright}/run_*.sh` only if generated
  profile/help expectations require it
- Modify: `.env.template`
- Modify: `README.md`
- Modify: `asterion/README.md`
- Modify: `asterion/docs/dci-complete-product-reference.md`
- Modify: `asterion/docs/guides/dci-application-integration.md`
- Modify: `asterion/docs/validation/dci-verification-guide.md`
- Modify: `tests/test_distribution_boundaries.py`
- Modify: `tests/test_asterion_dci_batch_launchers.py`

**Interfaces:**
- Replaces the old `unsupported` statement with exact implementation and
  evidence-layer language.
- Keeps all 12 current launchers mapped to the same shipped implementation.

- [ ] **Step 1: Write RED documentation and launcher contracts**

  Require the L0–L4 table, exact thresholds, live-versus-post-run distinction,
  extension ownership, resume behavior, four evidence layers, bounded commands,
  and the explicit statement that full paper reproduction remains AF-340. Reject
  stale phrases claiming the context setting is unsupported or that provider-
  free tests reproduce paper scores.

- [ ] **Step 2: Validate launcher profile input**

  Replace any free-form/legacy level acceptance with exact L0–L4 values and
  literal `asterion-dci benchmark --runtime-context-level`. Keep normal defaults
  in `.env.template`. Run `bash -n` for every touched script.

- [ ] **Step 3: Document exact operator workflows**

  Include provider-free contract tests, one bounded L3 command, one bounded L4
  command, artifact locations, credential precautions, cost warning, and how to
  distinguish implemented/model-free/bounded/reproduced evidence.

- [ ] **Step 4: Verify docs and launchers**

  ```bash
  uv run --project asterion python -m unittest \
    tests.test_distribution_boundaries \
    tests.test_asterion_dci_batch_launchers -v
  bash -n asterion/scripts/bcplus_eval/run_bcplus_eval_openai.sh
  ```

- [ ] **Step 5: Commit truthful documentation**

  ```bash
  git add .env.template README.md asterion/README.md asterion/docs \
    asterion/scripts asterion/src/asterion/dci/resources/batch-profiles.json \
    tests/test_distribution_boundaries.py \
    tests/test_asterion_dci_batch_launchers.py
  git commit -m "docs(dci): document live paper context profiles"
  ```

---

## Task 8: Run bounded L3/L4 Pi acceptance and retain credential-clean evidence

**Files:**
- Create: `tools/verify_dci_context_acceptance.py`
- Create under ignored output root at runtime: bounded private evidence
- Modify: `tests/test_asterion_dci_verification.py`
- Modify: `docs/status/JOURNAL.md`
- Modify through Climb tools: `docs/status/climb/**`

**Interfaces:**
- A model-free mode validates setup and artifact schemas with zero provider ops.
- An explicit `--provider-backed` mode performs exactly two bounded Pi runs:
  one forced L3 compaction and one forced L4 successful summary.

- [ ] **Step 1: Write RED verifier contract tests**

  Assert default invocation performs zero provider operations, prints planned
  operation count/cost ambiguity, and refuses provider-backed execution without
  credentials, corpus fixture, explicit output root, and external Pi revision.
  Assert retained report contains no credentials or content bodies.

- [ ] **Step 2: Implement the bounded verifier**

  Generate deterministic local corpus/tool-output pressure sufficient to cross
  240,000 original characters while keeping provider turns bounded. The L3 run
  must observe `compactions >= 1` and `preserved_turns == 12`; the L4 run must
  observe `summary_attempts >= 1`, `summary_successes >= 1`, and suppression
  false. Bind report to model/provider, Pi revision, contract version, extension
  digest, run artifact digests, actual provider operation count, and whether API
  request multiplicity is externally ambiguous.

- [ ] **Step 3: Run model-free verifier and focused tests**

  ```bash
  uv run --project asterion python -m unittest \
    tests.test_asterion_dci_verification -v
  uv run --project asterion python tools/verify_dci_context_acceptance.py
  ```

  Expected: PASS, provider operations `0`, full dataset `no`.

- [ ] **Step 4: Run the explicitly authorized bounded acceptance**

  Use repository `.env` without printing it:

  ```bash
  uv run --project asterion python tools/verify_dci_context_acceptance.py \
    --provider-backed \
    --env-file ../.env \
    --output-root ../outputs/asterion-dci-context-acceptance
  ```

  If credentials or an external provider are unavailable, record H-005 as
  externally blocked and do not close AF-310. A fixture cannot replace this
  gate. If a real run falsifies a threshold or hook assumption, preserve the
  evidence, update the hypothesis, repair through a new RED/GREEN cycle, and
  rerun both bounded cases.

- [ ] **Step 5: Verify and commit the verifier, not private bodies**

  ```bash
  uv run --project asterion python -m compileall -q \
    tools/verify_dci_context_acceptance.py
  uv run --project asterion ruff check \
    tools/verify_dci_context_acceptance.py \
    tests/test_asterion_dci_verification.py
  git diff --check
  git add tools/verify_dci_context_acceptance.py \
    tests/test_asterion_dci_verification.py docs/status
  git commit -m "test(dci): verify bounded live context policies"
  ```

  Never add output directories, credentials, prompts, answers, or tool bodies.

---

## Task 9: Full local closure, independent review, and AF-310 transition

**Files:**
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/DECISIONS.md` only if implementation changed an accepted
  boundary
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`
- Modify through Climb tools: `docs/status/climb/**`

**Interfaces:**
- Produces complete AF-310 closure evidence and either activates AF-320 or
  records an honest blocked boundary.

- [ ] **Step 1: Run the complete deterministic suite**

  ```bash
  npm --prefix asterion/packages/typescript/dci-context-extension test
  uv run --project asterion python -m unittest discover -v
  uv run --project asterion python -m compileall -q \
    asterion/src asterion/tests tests tools
  uv run --project asterion ruff check asterion/src asterion/tests tests tools
  uv run --project asterion python tools/verify_asterion_dci_product.py
  uv run --project asterion python tools/verify_dci_context_acceptance.py
  python3 tools/project_scope_check.py
  git diff --check
  ```

  Run `bash -n` on every touched shell script. The product verifier must remain
  8/8 with zero provider ops in provider-free mode.

- [ ] **Step 2: Re-run retained bounded acceptance**

  Re-run Task 8's two provider-backed cases against the final extension digest.
  Old evidence for a different digest cannot close the package.

- [ ] **Step 3: Request independent code and security review**

  Review exact changed files for hook correctness, untrusted argv, resource
  integrity, symlink/TOCTOU behavior, telemetry leakage, resume identity,
  cancellation, and public projection. Fix every Critical/High issue and rerun
  affected gates. Record accepted lower-severity issues explicitly.

- [ ] **Step 4: Audit AF-310 acceptance literally**

  Confirm all six acceptance bullets with direct artifact/test/commit evidence:
  owned/shipped L0–L4, same implementation on every surface, model-visible
  fixtures, real L3/L4 evidence, clean external Pi, and truthful docs. Confirm
  AF-320 benchmark/metric work and AF-340 full reproduction did not leak into
  scope.

- [ ] **Step 5: Close and transition atomically**

  Mark all AF-310 hypotheses terminal, regenerate the research tree, append
  exact closure results, and run the scope preflight again. If every gate passes,
  close AF-310 and activate AF-320 with its own approved plan prerequisite. If
  any bounded provider or security gate is unavailable, keep AF-310 active and
  write the exact next command instead of claiming completion.

- [ ] **Step 6: Commit closure state**

  ```bash
  git add docs/status
  git commit -m "docs: close AF-310 runtime context management"
  python3 tools/project_scope_check.py
  git status --short
  ```

  Final state must be clean apart from explicitly documented user-owned or
  private ignored evidence.

## Plan Self-Review Checklist

- [ ] Every production behavior has a preceding RED test and a focused GREEN
  command.
- [ ] Every public surface routes to one profile resolver and one native runner.
- [ ] Tests inspect model-visible messages, not only saved artifacts.
- [ ] The external Pi checkout remains unmodified and uncommitted.
- [ ] Extension source/resource byte parity and isolated-wheel execution pass.
- [ ] Resume binds every immutable policy and extension identity field.
- [ ] Public telemetry is content-free under canary tests.
- [ ] Real final-digest L3 and L4 runs exist before closure.
- [ ] Full datasets and paper score claims remain deferred to AF-340.
- [ ] Scope, Climb, journal, worklist, and recovery baton agree at transition.
