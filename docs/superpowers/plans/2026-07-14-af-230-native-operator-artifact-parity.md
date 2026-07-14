# AF-230 Native Operator and Artifact Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every remaining source-DCI single-run, terminal, native artifact, provenance, and resume behavior available through independently owned Asterion DCI code.

**Architecture:** `DciRunRecorder` becomes the sole production owner of native run-directory state while `run_pi_research` only orchestrates Pi and the recorder. Package-local CLI values are converted into immutable request and conversation-feature values; a private atomic run directory, one-writer lock, credential-safe Pi provenance, and isolated protocol attempts define the durability boundary. Terminal mode remains a direct Pi-owned TTY invocation and intentionally creates no RPC artifacts.

**Tech Stack:** Python 3.11, dataclasses, argparse, JSONL RPC, direct subprocess argv, unittest, Bash, Git.

## Global Constraints

- Do not modify or import `src/dci`; it remains the independent comparison baseline.
- Do not edit the external `pi/` checkout or persist credentials, environment mappings, unredacted Git URLs, arbitrary extra-argument values, provider bodies in framework projections, or raw commands.
- Keep DCI flags and defaults in package-local `asterion-dci` code; generic Asterion CLI, runner, factory, and selection modules remain DCI-neutral.
- `runtime_context_level` remains a recorded unsupported diagnostic until the selected Pi advertises a typed control; never fabricate a Pi flag.
- Native run directories are private, JSON state is atomically replaced, output/tool-result paths are contained, and concurrent writers are rejected before Pi construction.
- Resume of a completed run remains rejected. Artifact resume without `keep_session` is not claimed as Pi session continuity.
- AF-240 owns Judge/evaluation orchestration, batch concurrency, dataset adapters, metrics, summaries, and exports. AF-250 owns the final product matrix.
- Run `python3 tools/project_scope_check.py` before Climb dispatch and package closure.

---

## File structure

| File | Responsibility |
|---|---|
| `packages/python/asterion-core/src/asterion/dci/artifacts.py` | Private atomic run directory, unified recorder, conversations, tool/context evidence, protocol attempts, notes, stderr, and resume loading. |
| `packages/python/asterion-core/src/asterion/dci/provenance.py` | Credential-safe Pi Git revision and lock provenance. |
| `packages/python/asterion-core/src/asterion/dci/run.py` | Typed request/result orchestration and recorder-backed resume. |
| `packages/python/asterion-core/src/asterion/dci/pi_rpc.py` | Direct RPC/terminal Pi argv, inherited environment, Node selection, and child lifecycle. |
| `packages/python/asterion-core/src/asterion/dci/cli.py` | Package-local run/resume/terminal operator mapping and resource resolution. |
| `tests/test_asterion_dci_artifacts.py` | Recorder, privacy, atomicity, provenance, locking, and resume fixtures. |
| `tests/test_asterion_dci_run.py` | Real production-path artifact and resume integration fixtures. |
| `tests/test_asterion_dci_cli.py` | Operator input, unique destination, terminal, and safe-failure behavior. |
| `tests/test_asterion_dci_pi_rpc.py` | Literal RPC/terminal argv, Node, environment, and TTY-independent transport behavior. |

### Task 0: Register AF-230 Climb state before production changes

**Files:**
- Modify: `docs/status/climb/hypotheses.yaml`
- Modify: `docs/status/climb/session-state.json`
- Regenerate: `docs/status/climb/research-tree.md`
- Regenerate: `docs/status/climb/research-tree.json`
- Modify: `docs/status/JOURNAL.md`

**Interfaces:**
- Produces four active hypotheses: unified durable recorder; processed native evidence/privacy; provenance/resume single-writer safety; operator/terminal parity.

- [ ] **Step 1: Append AF-230 hypotheses**

Register `AF-230-H-001` through `AF-230-H-004` with `work_package_id: AF-230`, rankings `0.90`, `0.80`, `0.70`, `0.60`, status `pending`, and exact focused verification commands from Tasks 1–6. Do not reuse AF-220 cycles or edit historical results.

- [ ] **Step 2: Regenerate and preflight**

Run: `python3 tools/climb/regen-tree.py && python3 tools/project_scope_check.py --climb-hypothesis AF-230-H-001`

Expected: generated tree names AF-230-H-001 next and scope reports `ok: true`, `active_package: AF-230`.

- [ ] **Step 3: Commit registration**

```bash
git add docs/status/climb docs/status/JOURNAL.md
git commit -m "docs: register AF-230 Climb state"
```

### Task 1: Establish the private atomic recorder and single-writer boundary

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/artifacts.py`
- Modify: `tests/test_asterion_dci_artifacts.py`

**Interfaces:**
- Produces `DciRunLock.acquire(output_dir: Path) -> DciRunLock`, `release()`, `atomic_write_json(path, payload)`, and a resume-aware `DciRunRecorder(..., resume: bool)`.
- The lock file stores only `pid`, `hostname`, `created_at`, and a random owner token. Same-host dead PID is the only automatically removable lock; a live local PID, foreign hostname, malformed lock, or symlink fails closed.

- [ ] **Step 1: Write failing boundary tests**

Add tests that assert: run directory mode is `0700`; JSON files are `0600` where POSIX modes apply; output directory and lock symlinks are rejected; two acquisitions allow exactly one owner; a same-host nonexistent PID is reclaimable; foreign/malformed locks are not; and a fault before `Path.replace` leaves the previous JSON parseable.

- [ ] **Step 2: Prove RED**

Run: `uv run python -m unittest -v tests.test_asterion_dci_artifacts`

Expected: FAIL because no lock/atomic/private boundary exists.

- [ ] **Step 3: Implement the minimal boundary**

Use `os.open(..., os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)` for lock acquisition and JSON temp files in the destination directory. Use `os.replace` only after flush/fsync, enforce containment with resolved parents, reject symlink run roots/targets, and remove a lock only when its owner token still matches.

- [ ] **Step 4: Verify and commit**

Run: `uv run python -m unittest -v tests.test_asterion_dci_artifacts && uv run ruff check packages/python/asterion-core/src/asterion/dci/artifacts.py tests/test_asterion_dci_artifacts.py`

Expected: PASS with concurrent acquisition constructing no Pi client.

```bash
git add packages/python/asterion-core/src/asterion/dci/artifacts.py tests/test_asterion_dci_artifacts.py
git commit -m "feat: protect native DCI run directories"
```

### Task 2: Complete transcript, tool, context, and processed-view semantics

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/artifacts.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/run.py`
- Modify: `tests/test_asterion_dci_artifacts.py`
- Modify: `tests/test_asterion_dci_run.py`

**Interfaces:**
- `DciConversationFeatures` validates `clear_tool_results_keep_last >= 0` and serializes through `to_mapping()` / `from_mapping()`.
- `DciRunRecorder.record_event(event)` atomically updates running state, full conversation, processed conversation, latest provider context, raw JSONL, and normalized protocol events.

- [ ] **Step 1: Add a production-path fixture sequence**

Feed `run_pi_research` a fake client emitting system prompt, message start, partial update, four tool results, paired tool start/end events, assistant thinking/usage, two provider-request contexts, message end, and settlement. Assert `state.json` is readable with `status=running` during the sequence.

- [ ] **Step 2: Add processed-view RED assertions**

Enable externalization, clear-results keep-last `2`, strip-thinking, and strip-usage. Assert full evidence retains all four bodies/thinking/usage; processed evidence externalizes all tool results, clears only the first two with stats and relative pointers, keeps the last two inline, and strips thinking/usage only there. A `toolCallId` containing `../` must produce a bounded contained filename and deterministic collision suffix.

- [ ] **Step 3: Implement message and context projections**

Track pending messages, ordered completed messages, text deltas, tool timestamps/durations, request count, latest model/payload/messages, runtime-context metadata, and system prompt sources. Rebuild pending/completed timing indexes on resume. Persist after every event with Task 1 atomic helpers.

- [ ] **Step 4: Verify and commit**

Run: `uv run python -m unittest -v tests.test_asterion_dci_artifacts tests.test_asterion_dci_run`

Expected: PASS and framework/application tests still expose URIs only.

```bash
git add packages/python/asterion-core/src/asterion/dci/artifacts.py packages/python/asterion-core/src/asterion/dci/run.py tests/test_asterion_dci_artifacts.py tests/test_asterion_dci_run.py
git commit -m "feat: complete native DCI conversation artifacts"
```

### Task 3: Record credential-safe Pi provenance and attempt diagnostics

**Files:**
- Create: `packages/python/asterion-core/src/asterion/dci/provenance.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/artifacts.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/run.py`
- Modify: `tests/test_asterion_dci_artifacts.py`
- Modify: `tests/test_asterion_dci_run.py`

**Interfaces:**
- Produces `collect_pi_provenance(package_dir: Path, lock_file: Path, revision_override: str | None) -> dict[str, object]` and `format_pi_revision_warning(provenance) -> str | None`.
- Provenance contains booleans/revisions and a sanitized origin host/path only; it never contains URL userinfo, query, fragment, Git status content, environment values, or arbitrary extra-argument values.

- [ ] **Step 1: Write provenance RED tests**

Create clean, dirty, mismatched, override, and non-Git fixture repositories. Configure an origin such as `https://sentinel-user:sentinel-pass@example.invalid/repo.git?token=secret#fragment`. Assert the sentinels are absent from provenance, notes, stderr/public output, and every artifact.

- [ ] **Step 2: Implement and attach provenance**

Run Git with literal argv/captured output. Record commit, dirty boolean, lock revision/match, expected revision/source/match, managed-checkout boolean, and sanitized origin. Attach the attempt snapshot to state, full conversation, and latest context; add a safe mismatch note before Pi starts.

- [ ] **Step 3: Complete protocol/stderr diagnostics**

Add SHA-256 to the final-answer protocol artifact. Store a safe command summary containing fixed option names/counts but not arbitrary values. Persist bounded success and failure stderr per attempt, append prior attempt tails on resume, and keep public errors body-free.

- [ ] **Step 4: Verify and commit**

Run: `uv run python -m unittest -v tests.test_asterion_dci_artifacts tests.test_asterion_dci_run`

Expected: PASS with exact digest and no sentinel leakage.

```bash
git add packages/python/asterion-core/src/asterion/dci/provenance.py packages/python/asterion-core/src/asterion/dci/artifacts.py packages/python/asterion-core/src/asterion/dci/run.py tests/test_asterion_dci_artifacts.py tests/test_asterion_dci_run.py
git commit -m "feat: record safe DCI Pi provenance"
```

### Task 4: Make the unified recorder the only production run and resume path

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/run.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/artifacts.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/application_executor.py`
- Modify: `tests/test_asterion_dci_run.py`
- Modify: `tests/test_asterion_dci_application_executor.py`

**Interfaces:**
- `DciRunRequest` persists/reconstructs every behavior-affecting value: question/cwd/provider/model/tools/max-turns/timeout/context diagnostic/thinking/heap/session/extra-arg fingerprint/show-tools/stream-text/prompts/conversation features and Pi package/agent paths.
- Timeout may change on resume, matching the source; all other listed execution semantics are immutable. Raw extra-argument values remain caller input but state stores only a fingerprint/count for validation and diagnostics.

- [ ] **Step 1: Write parameterized resume RED tests**

Mutate each immutable field/type independently and assert rejection before client construction. Assert timeout-only change is accepted; completed/malformed/missing state is rejected; a live running lock rejects; a provably stale local lock allows one resume; and two resume contenders construct at most one client.

- [ ] **Step 2: Integrate the recorder**

Remove duplicate state/protocol/JSONL persistence from `run.py`. Acquire the recorder lock before client construction, set safe command/provenance, route every raw event through the recorder, finalize exactly once, and release only the owned lock. Preserve evidence and create `attempt-0002` on compatible resume.

- [ ] **Step 3: Preserve application projection**

Verify the installed application uses the same recorder while `stream_text=False`, returns one body-free JSON object, and publishes only artifact URIs.

- [ ] **Step 4: Verify and commit**

Run: `uv run python -m unittest -v tests.test_asterion_dci_run tests.test_asterion_dci_artifacts tests.test_asterion_dci_application_executor tests.test_builtin_dci_application`

Expected: PASS with attempt 1/2 independently protocol-valid.

```bash
git add packages/python/asterion-core/src/asterion/dci/run.py packages/python/asterion-core/src/asterion/dci/artifacts.py packages/python/asterion-core/src/asterion/dci/application_executor.py tests/test_asterion_dci_run.py tests/test_asterion_dci_artifacts.py tests/test_asterion_dci_application_executor.py
git commit -m "feat: unify DCI production artifacts and resume"
```

### Task 5: Complete package-local run input and resource semantics

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/cli.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/config.py`
- Modify: `tests/test_asterion_dci_cli.py`
- Modify: `README.md`
- Modify: `assets/docs/artifacts.md`

**Interfaces:**
- Produces collision-resistant default run IDs when `--run-id` is omitted while preserving explicit stable IDs.
- Run accepts zero-or-more positional question tokens, question file, or non-TTY stdin; prompt resources are canonicalized against invocation cwd then repository root before child cwd changes.
- Adds the five `--conversation-*` controls only to `asterion-dci run`.

- [ ] **Step 1: Write CLI RED tests**

Assert two default runs create distinct destinations; explicit duplicate ID/destination fails before Pi; multiple question tokens join with spaces; question file/stdin precedence is deterministic; relative prompt paths resolve from invocation cwd before `--cwd`; missing/unreadable/symlink-unsafe resources fail before Pi.

- [ ] **Step 2: Implement request mapping**

Use `run_id=None` at parse time and generate a UTC timestamp plus random suffix only after validation. Canonicalize prompt and question files without changing process cwd. Convert all conversation flags to `DciConversationFeatures` and pass them through request construction/resume state.

- [ ] **Step 3: Document exact operator mappings**

Document full vs processed artifacts, protected bodies, session-resume distinction, unsupported runtime-context diagnostic, generated destinations, and each conversation control. Do not describe native directories as read-only when bash is enabled.

- [ ] **Step 4: Verify and commit**

Run: `uv run python -m unittest -v tests.test_asterion_dci_cli tests.test_asterion_dci_run tests.test_asterion_dci_artifacts`

Expected: PASS without a provider request.

```bash
git add packages/python/asterion-core/src/asterion/dci/cli.py packages/python/asterion-core/src/asterion/dci/config.py tests/test_asterion_dci_cli.py README.md assets/docs/artifacts.md
git commit -m "feat: complete DCI run operator controls"
```

### Task 6: Add independent Pi terminal mode and Node selection parity

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/pi_rpc.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/cli.py`
- Modify: `tests/test_asterion_dci_pi_rpc.py`
- Modify: `tests/test_asterion_dci_cli.py`
- Modify: `README.md`

**Interfaces:**
- Produces `run_pi_terminal(...) -> int`, using literal argv, inherited environment, configured heap, provider/model/tools/prompts/extra args, and optional initial question.
- Terminal requires stdin/stdout TTY, keeps Pi session, omits RPC mode and artifacts, and propagates the child's exit status.
- Node resolution selects a valid Node >=20 from PATH or nvm; otherwise it fails before Pi with a stable public error.

- [ ] **Step 1: Write terminal and Node RED tests**

Patch TTY and `subprocess.run` to assert exact argv/environment/cwd/message mapping, no `--mode rpc`, no `--no-session`, literal malicious values, heap preservation, and exit-code propagation. Non-TTY, invalid Node version, missing prompt, and runner-only option spellings must fail before Pi construction.

- [ ] **Step 2: Implement terminal command**

Add `asterion-dci terminal` with question tokens/file, provider/model/tools/cwd/prompts/thinking/heap/repeatable extra args. Build argv through the same literal builder and call `subprocess.run(..., check=False)` only after TTY/resource/Node validation. Do not create a run directory.

- [ ] **Step 3: Verify and commit**

Run: `uv run python -m unittest -v tests.test_asterion_dci_pi_rpc tests.test_asterion_dci_cli`

Expected: PASS; a model-free real `--help`/Node/Pi command-construction probe also exits zero, while no fake TTY/model call is attempted.

```bash
git add packages/python/asterion-core/src/asterion/dci/pi_rpc.py packages/python/asterion-core/src/asterion/dci/cli.py tests/test_asterion_dci_pi_rpc.py tests/test_asterion_dci_cli.py README.md
git commit -m "feat: add Asterion DCI terminal mode"
```

### Task 7: Execute Climb evidence, bounded real acceptance, and close AF-230

**Files:**
- Modify: `docs/status/climb/hypotheses.yaml`
- Modify: `docs/status/climb/session-state.json`
- Regenerate: `docs/status/climb/research-tree.md`
- Regenerate: `docs/status/climb/research-tree.json`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

- [ ] **Step 1: Run local closure**

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q packages/python/asterion-core/src/asterion
uv run ruff check packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_artifacts.py tests/test_asterion_dci_run.py tests/test_asterion_dci_pi_rpc.py tests/test_asterion_dci_cli.py tests/test_asterion_dci_application_executor.py
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
python3 tools/project_scope_check.py
git diff --check
```

Expected: every command exits zero. Run AF-230-H-001 through H-004 through the adapter, record 4/4 evidence, and regenerate the tree.

- [ ] **Step 2: Run bounded real acceptance**

With the already authorized process-local shared `.env`, external Pi path, corpus root, and worktree Python path, run one `asterion-dci run` only. Validate completed state, private/parseable complete artifact set, conversation separation, latest context, Pi provenance without secrets, protocol digest, and body-free application projection. Use fixtures for failed-run resume; do not spend a second provider request to manufacture failure. Limit terminal acceptance to Node/Pi command construction because no operator TTY is attached.

- [ ] **Step 3: Close only with evidence**

Mark AF-230 completed only when every mapped behavior and approved unsupported boundary is executable and all gates pass. Activate AF-240, regenerate state, rerun scope/diff, and commit:

```bash
git add docs/status
git commit -m "docs: record AF-230 native parity acceptance"
```

## Plan self-review

- **Spec coverage:** Tasks 1–6 cover the AF-230 rows for native run/terminal controls, context/resource behavior, complete artifacts/provenance, and compatible resume. AF-240 evaluation/batch/export work and AF-250 final matrix are excluded explicitly.
- **Placeholder scan:** Every task identifies concrete files, interfaces, failure-first tests, commands, expected outcomes, and commit boundaries; no TBD or deferred implementation step remains.
- **Type consistency:** Conversation features are defined once in `artifacts.py`, carried by `DciRunRequest`, persisted/reconstructed by the unified recorder, mapped by package CLI, and reused by the provider executor. The recorder lock is acquired before Pi construction and owned through finalization.
