# Asterion DCI Durable Resume Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the independent Asterion DCI package with original-DCI-compatible durable run artifacts and safe resume behavior.

**Architecture:** Keep Pi transport in `asterion.dci.pi_rpc` and move durable state handling to an Asterion-owned recorder. A new run records raw events, full and processed conversations, latest model context, tool-result artifacts, final text, stderr, state, and a protocol attempt. A resume reopens only a failed/incomplete compatible output directory, validates all immutable inputs before Pi starts, creates a distinct protocol attempt, and projects the same body-free package result.

**Tech Stack:** Python 3.10+, dataclasses, JSON/JSONL, `pathlib`, `unittest`, Asterion runtime protocol.

## Global Constraints

- Work only under `packages/python/asterion-core/src/asterion/dci/`; never import, execute, inspect, or modify `src/dci` at runtime.
- Preserve the AF-180 `ASTERION_DCI_*` namespace, separate output root, direct Pi argv, safe public errors, and one-wheel boundary.
- Preserve original DCI artifact names and semantic fields: `events.jsonl`, `state.json`, `conversation_full.json`, `conversation.json`, `latest_model_context.json`, `final.txt`, `stderr.txt`, `tool_results/`, and per-attempt `protocol/` files.
- Resume never accepts a completed run or changed question, Pi paths, cwd, provider, model, tools, max turns, prompts, conversation features, or session mode.
- Fixture tests must not start Pi, Node, a judge, or Claude. Real Pi/judge/Claude requests remain separately authorized.
- The generic `asterion` CLI stays DCI-neutral. `asterion-dci resume` is the only AF-190 operator surface.

## File Structure

| File | Responsibility |
|---|---|
| `packages/python/asterion-core/src/asterion/dci/artifacts.py` | Durable recorder, artifact paths, state validation, conversations, tool-result handling, and protocol attempts. |
| `packages/python/asterion-core/src/asterion/dci/run.py` | Adds resume-aware request fields and delegates raw events/finalization to the recorder. |
| `packages/python/asterion-core/src/asterion/dci/cli.py` | Adds the product-local `resume` command and preserves AF-200 rejections. |
| `packages/python/asterion-core/src/asterion/dci/bridge.py` | Projects durable artifact references only after a completed normalized run. |
| `tests/test_asterion_dci_artifacts.py` | Fixture parity for artifacts, transcript processing, and resume validation. |
| `tests/test_asterion_dci_run.py` | Resume orchestration and attempt isolation fixtures. |
| `tests/test_asterion_dci_cli.py` | `asterion-dci resume` parsing, output, and safe rejection checks. |
| `tests/test_asterion_dci_bridge.py` | Durable artifact reference projection checks. |

## Task 1: Build the durable Asterion DCI recorder

**Files:**
- Create: `packages/python/asterion-core/src/asterion/dci/artifacts.py`
- Create: `tests/test_asterion_dci_artifacts.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class DciConversationFeatures:
    clear_tool_results: bool = False
    clear_tool_results_keep_last: int = 3
    externalize_tool_results: bool = False
    strip_thinking: bool = False
    strip_usage: bool = False

class DciRunRecorder:
    def __init__(self, *, output_dir: Path, request: DciRunRequest, paths: DciPaths): ...
    def record_event(self, event: dict[str, object]) -> None: ...
    def set_command(self, command: list[str]) -> None: ...
    def finalize(self, *, status: str, final_text: str = "", stderr_text: str = "") -> tuple[RunEvent, ...]: ...
```

- [ ] **Step 1: Write failing artifact tests**

```python
def test_recorder_writes_original_durable_artifact_set(tmp_path):
    recorder = DciRunRecorder(output_dir=tmp_path / "run", request=request(), paths=paths(tmp_path))
    recorder.record_event({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "answer"}})
    events = recorder.finalize(status="completed", final_text="answer")
    self.assertTrue((tmp_path / "run/conversation_full.json").is_file())
    self.assertTrue((tmp_path / "run/conversation.json").is_file())
    self.assertTrue((tmp_path / "run/latest_model_context.json").is_file())
    self.assertEqual((tmp_path / "run/final.txt").read_text(), "answer\n")
    validate_event_stream([event.to_mapping() for event in events])

def test_processed_conversation_can_externalize_and_clear_old_tool_results(tmp_path):
    recorder = DciRunRecorder(..., request=request(features=DciConversationFeatures(externalize_tool_results=True, clear_tool_results=True)))
    recorder.record_event(tool_result_event("call-1", "SECRET-TOOL-BODY"))
    recorder.finalize(status="failed")
    self.assertTrue((tmp_path / "run/tool_results/call-1.json").is_file())
    self.assertNotIn("SECRET-TOOL-BODY", json.loads((tmp_path / "run/conversation.json").read_text()))
```

- [ ] **Step 2: Run RED verification**

Run: `uv run python -m unittest -v tests.test_asterion_dci_artifacts`

Expected: import failure for `asterion.dci.artifacts`.

- [ ] **Step 3: Implement the recorder**

Port the durable, non-judge parts of original `RunRecorder` into `DciRunRecorder`: construct all artifact paths; initialize full state/conversation/context; write atomically; append raw JSONL; retain assistant text, messages, tool calls, notes, and provider request context; build a processed conversation with optional thinking/usage removal and tool-result externalization/clearing; bound persisted stderr; and create `protocol/attempt-0001.request.json` plus normalized event JSONL. Use `PiProtocolAdapter` and `validate_event_stream`; use only Asterion types.

- [ ] **Step 4: Run GREEN verification**

Run: `uv run python -m unittest -v tests.test_asterion_dci_artifacts tests.test_asterion_dci_run`

Expected: PASS; artifact schema, protocol terminal event, and protected processed conversation are fixture-verified.

- [ ] **Step 5: Commit**

```bash
git add packages/python/asterion-core/src/asterion/dci/artifacts.py tests/test_asterion_dci_artifacts.py
git commit -m "feat: add durable Asterion DCI run artifacts"
```

## Task 2: Add safe resume validation and execution orchestration

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/artifacts.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/run.py`
- Modify: `tests/test_asterion_dci_artifacts.py`
- Modify: `tests/test_asterion_dci_run.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class DciRunRequest:
    # existing AF-180 fields
    resume: bool = False
    keep_session: bool = False
    conversation_features: DciConversationFeatures = DciConversationFeatures()

def run_pi_research(paths: DciPaths, request: DciRunRequest, *, output_dir: Path | None = None) -> DciRunResult: ...
```

- [ ] **Step 1: Write failing resume tests**

```python
def test_resume_reuses_failed_directory_and_creates_a_second_protocol_attempt(tmp_path):
    first = recorder_for_failed_run(tmp_path / "run")
    result = run_with_fixture_client(paths(tmp_path), request(resume=True), output_dir=first)
    self.assertTrue((result.output_dir / "protocol/attempt-0002.request.json").is_file())
    self.assertEqual(json.loads((result.output_dir / "state.json").read_text())["resume_count"], 1)

def test_resume_rejects_completed_or_changed_immutable_inputs_before_client_start(tmp_path):
    completed = recorder_for_completed_run(tmp_path / "complete")
    with self.assertRaisesRegex(DciRunError, "resume validation failed"):
        run_pi_research(paths(tmp_path), request(resume=True), output_dir=completed)
    with self.assertRaisesRegex(DciRunError, "resume validation failed"):
        run_pi_research(paths(tmp_path), request(resume=True, model="different"), output_dir=failed)
```

- [ ] **Step 2: Run RED verification**

Run: `uv run python -m unittest -v tests.test_asterion_dci_artifacts tests.test_asterion_dci_run`

Expected: FAIL because AF-180 rejects every nonempty output directory and has no resume fields.

- [ ] **Step 3: Implement exact resume handling**

Allow a nonempty output directory only when `request.resume` is true. Load `state.json`, `conversation_full.json` (falling back to `conversation.json`), and `latest_model_context.json`; reject completed state and every immutable-input mismatch before constructing `PiRpcClient`; reset only running/terminal attempt fields; increment `resume_count`; preserve native evidence; append bounded stderr rather than overwrite it; and create `attempt-0002` (and later attempts) with a new normalized run ID. A resumed no-session run must record that it reuses artifacts only, not a Pi session.

- [ ] **Step 4: Run GREEN verification**

Run: `uv run python -m unittest -v tests.test_asterion_dci_artifacts tests.test_asterion_dci_run tests.test_asterion_dci_pi_rpc`

Expected: PASS; no fixture starts Pi/Node and no changed input reaches the client.

- [ ] **Step 5: Commit**

```bash
git add packages/python/asterion-core/src/asterion/dci/artifacts.py packages/python/asterion-core/src/asterion/dci/run.py tests/test_asterion_dci_artifacts.py tests/test_asterion_dci_run.py
git commit -m "feat: add Asterion DCI resume parity"
```

## Task 3: Expose the package-local resume command and durable projection

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/cli.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/bridge.py`
- Modify: `tests/test_asterion_dci_cli.py`
- Modify: `tests/test_asterion_dci_bridge.py`

- [ ] **Step 1: Write failing CLI and bridge tests**

```python
def test_resume_maps_existing_run_directory_to_a_resume_request(tmp_path):
    with patch("asterion.dci.cli.run_pi_research", return_value=fixture_result(tmp_path / "run")) as run:
        self.assertEqual(main(["resume", "--output-dir", str(tmp_path / "run")], repo_root=tmp_path), 0)
    self.assertTrue(run.call_args.args[1].resume)

def test_projection_lists_durable_references_without_bodies(tmp_path):
    projection = project_dci_run(fixture_result(tmp_path / "run"))
    self.assertEqual(dict(projection.artifacts[0]["value"])["conversation_artifact_uri"], "conversation.json")
    self.assertNotIn("SECRET-ANSWER", repr(projection))
```

- [ ] **Step 2: Run RED verification**

Run: `uv run python -m unittest -v tests.test_asterion_dci_cli tests.test_asterion_dci_bridge`

Expected: FAIL because `resume` is currently rejected and the AF-180 projection intentionally lists only minimal artifacts.

- [ ] **Step 3: Implement product-local resume and references**

Add an `asterion-dci resume` parser with `--output-dir` required and the immutable fields needed to compare the original run. It invokes `run_pi_research` with `resume=True`, prints only output directory/status/final URI, and maps detailed failures to `DCI Pi execution failed`. Extend the completed-run projection with `conversation_artifact_uri`, `latest_model_context_artifact_uri`, and `protocol_artifact_uri`, but never with final text, question, command, provider payload, or stderr body.

- [ ] **Step 4: Run GREEN verification**

Run: `uv run python -m unittest -v tests.test_asterion_dci_cli tests.test_asterion_dci_bridge tests.test_dci_research_capability`

Expected: PASS; generic `asterion` parser still contains no DCI subcommand.

- [ ] **Step 5: Commit**

```bash
git add packages/python/asterion-core/src/asterion/dci/cli.py packages/python/asterion-core/src/asterion/dci/bridge.py tests/test_asterion_dci_cli.py tests/test_asterion_dci_bridge.py
git commit -m "feat: expose Asterion DCI resume command"
```

## Task 4: Document durable behavior and close AF-190

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/capability-execution.md`
- Modify: `tests/test_distribution_boundaries.py`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

- [ ] **Step 1: Write failing documentation/boundary tests**

```python
def test_documentation_names_resume_artifacts_and_preserves_one_wheel_boundary(self):
    readme = (ROOT / "README.md").read_text()
    self.assertIn("asterion-dci resume", readme)
    self.assertIn("conversation_full.json", readme)
    self.assertIn("AF-200", readme)
```

- [ ] **Step 2: Run RED verification**

Run: `uv run python -m unittest -v tests.test_distribution_boundaries`

Expected: FAIL until the durable command and artifact behavior are documented.

- [ ] **Step 3: Update operator documentation and status**

Document the resume command, immutable-input constraint, native durable artifacts, and protected-artifact boundary. Keep judge/evaluation/benchmark deferred to AF-200. Only after all verification below passes, mark AF-190 completed, activate AF-200, update `CURRENT-STATE.md`, append exact closure evidence to `JOURNAL.md`, and create the recovery checkpoint.

- [ ] **Step 4: Run closure verification**

Run:

```bash
uv run python -m unittest -v tests.test_asterion_dci_artifacts tests.test_asterion_dci_run tests.test_asterion_dci_cli tests.test_asterion_dci_bridge tests.test_distribution_boundaries
uv run python -m unittest discover -v
uv run python -m compileall -q packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_artifacts.py tests/test_asterion_dci_run.py tests/test_asterion_dci_cli.py tests/test_asterion_dci_bridge.py
uv run ruff check packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_artifacts.py tests/test_asterion_dci_run.py tests/test_asterion_dci_cli.py tests/test_asterion_dci_bridge.py
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
bash -n scripts/examples/*.sh scripts/bcplus_eval/*.sh scripts/bright/*.sh
asterion-dci resume --help
python3 tools/project_scope_check.py
git diff --check
```

Expected: all commands exit 0 without a Pi, judge, or Claude provider request.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/architecture/capability-execution.md tests/test_distribution_boundaries.py docs/status
git commit -m "docs: close AF-190 durable resume parity"
```

## Plan Self-Review

- Covers AF-190 output/state/transcript/final-answer artifacts, immutable resume validation, native-evidence retention, product-local operator flow, body-free bridge projection, documentation, and closure gates.
- Keeps all original DCI reuse internal to new Asterion files and excludes judge/cache, benchmark, generic CLI behavior, and provider-backed requests.
- Uses consistent `DciConversationFeatures`, `DciRunRecorder`, `DciRunRequest.resume`, and `DciRunResult` names throughout.
