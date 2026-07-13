# Complete DCI Capability Execution Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Ship the first independent, Pi-backed Asterion DCI execution package and asterion-dci run command with original DCI single-run semantics, minimal native artifacts, and a framework-facing result projection.

**Architecture:** Add an Asterion-owned asterion.dci module inside the existing asterion wheel. It reads only ASTERION_DCI_* configuration, transplants the proven Pi JSONL-RPC lifecycle without importing src/dci, writes a separate Asterion DCI output root, and returns a typed native-run value. The generic asterion CLI remains unchanged; a package-local console command and pure package-result projection form the AF-180 bridge. Resume, judge/cache, batch evaluation, and provider-backed Claude semantic parity remain AF-190 through AF-210 work.

**Tech Stack:** Python 3.10+, argparse, threading/subprocess, python-dotenv, Asterion runtime protocol, unittest, Hatchling.

## Global Constraints

- Keep one first-party asterion wheel; do not add a second distribution or workspace member.
- Create new domain source only under packages/python/asterion-core/src/asterion/dci/. It must never import, execute, inspect, or modify src/dci.
- Read only ASTERION_DCI_* values for the new product. Do not accept old DCI_* values as aliases or share the old output root.
- Preserve direct Pi argv, JSONL acknowledgement and agent_settled idle checks, timeout/turn aborts, retry-final-text reset, tool-boundary output, and safe invalid-JSONL/nonzero-process handling.
- AF-180 writes question.txt, events.jsonl, state.json, final.txt, stderr.txt, and protocol/. Full transcripts and all resume behavior belong to AF-190.
- Do not add DCI parsing/imports to asterion.cli, generic runtime factories, catalog, composer, or runner.
- Unit tests never start Pi, Node, a judge, or Claude. A provider-backed run needs separate operator authorization.
- Use TDD for every task, run its focused test before and after implementation, and commit each passing task.

---

## File structure

| File | Responsibility |
|---|---|
| packages/python/asterion-core/src/asterion/dci/__init__.py | Small public exports for the Asterion-owned DCI package. |
| packages/python/asterion-core/src/asterion/dci/config.py | .env loading and ASTERION_DCI_* Pi/output path resolution. |
| packages/python/asterion-core/src/asterion/dci/pi_rpc.py | Transplanted Pi command builder and JSONL-RPC process lifecycle. |
| packages/python/asterion-core/src/asterion/dci/run.py | Immutable run values, minimal native recorder, and Pi orchestration. |
| packages/python/asterion-core/src/asterion/dci/system_prompt.py | Package-local Pi system prompt rendering. |
| packages/python/asterion-core/src/asterion/dci/cli.py | asterion-dci run and system-prompt parsing/exit handling. |
| packages/python/asterion-core/src/asterion/dci/bridge.py | Pure DciRunResult to PackageExecutionResult conversion. |
| packages/python/asterion-core/pyproject.toml | asterion-dci console script in the existing wheel. |
| packages/python/asterion-core/src/asterion/capabilities/dci_research/implementation.py | Explicit native-run projection seam; existing runtime-neutral execute remains unchanged. |
| tests/test_asterion_dci_config.py | Isolated configuration and output-root tests. |
| tests/test_asterion_dci_pi_rpc.py | Pi command/lifecycle parity fixtures. |
| tests/test_asterion_dci_run.py | Native artifact and protocol-projection tests. |
| tests/test_asterion_dci_cli.py | Package-local command tests with mocked run boundary. |
| tests/test_asterion_dci_bridge.py | Body-free declared package-output tests. |
| tests/test_dci_research_capability.py | Existing fixture behavior plus native projection seam. |
| tests/test_distribution_boundaries.py | One-wheel, console-script, and no-baseline-import assertions. |

## Task 1: Establish independent Asterion DCI configuration

**Files:**
- Create: packages/python/asterion-core/src/asterion/dci/__init__.py
- Create: packages/python/asterion-core/src/asterion/dci/config.py
- Test: tests/test_asterion_dci_config.py

**Interfaces:**
- Produces DciPiPaths(repo_dir, package_dir, agent_dir) and DciPaths(repo_root, pi, output_root), all absolute resolved Paths.
- Public functions are load_asterion_dci_env(repo_root: Path) -> Path and resolve_dci_paths(repo_root: Path) -> DciPaths.

- [ ] **Step 1: Write the failing tests**

~~~python
def test_asterion_dci_uses_only_its_own_namespace(tmp_path):
    with patch.dict(os.environ, {
        "ASTERION_DCI_PI_DIR": "vendor/pi",
        "ASTERION_DCI_PI_PACKAGE_DIR": "build/coding-agent",
        "ASTERION_DCI_PI_AGENT_DIR": "state/pi-agent",
        "ASTERION_DCI_OUTPUT_ROOT": "asterion-runs",
        "DCI_PI_DIR": "must-not-be-used",
    }, clear=True):
        paths = resolve_dci_paths(tmp_path)
    self.assertEqual(paths.pi.repo_dir, tmp_path / "vendor/pi")
    self.assertEqual(paths.pi.package_dir, tmp_path / "build/coding-agent")
    self.assertEqual(paths.pi.agent_dir, tmp_path / "state/pi-agent")
    self.assertEqual(paths.output_root, tmp_path / "asterion-runs")

def test_default_ignores_legacy_pi_mono_and_old_output_root(tmp_path):
    (tmp_path / "pi-mono").mkdir()
    with patch.dict(os.environ, {}, clear=True):
        paths = resolve_dci_paths(tmp_path)
    self.assertEqual(paths.pi.repo_dir, tmp_path / "pi")
    self.assertEqual(paths.output_root, tmp_path / "outputs/asterion-dci-runs")
~~~

- [ ] **Step 2: Run the test to verify failure**

Run: uv run python -m unittest -v tests.test_asterion_dci_config

Expected: FAIL with ModuleNotFoundError for asterion.dci.

- [ ] **Step 3: Implement exact configuration**

Create frozen dataclasses DciPiPaths and DciPaths. Load repo_root/.env with dotenv override=False. Resolve relative paths against repo_root and expand user paths. Use ASTERION_DCI_PI_DIR or repo_root/pi, ASTERION_DCI_PI_PACKAGE_DIR or pi/packages/coding-agent, ASTERION_DCI_PI_AGENT_DIR or pi/.pi/agent, and ASTERION_DCI_OUTPUT_ROOT or repo_root/outputs/asterion-dci-runs. Do not read any DCI_* value. Export exactly DciPaths, DciPiPaths, load_asterion_dci_env, and resolve_dci_paths.

- [ ] **Step 4: Run focused verification**

Run: uv run python -m unittest -v tests.test_asterion_dci_config tests.test_distribution_boundaries.SourceDistributionBoundaryTests

Expected: PASS; old DCI configuration has no effect and Asterion still imports no dci module.

- [ ] **Step 5: Commit**

~~~bash
git add packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_config.py
git commit -m "feat: add isolated Asterion DCI configuration"
~~~

## Task 2: Transplant Pi single-run transport and native artifacts

**Files:**
- Create: packages/python/asterion-core/src/asterion/dci/pi_rpc.py
- Create: packages/python/asterion-core/src/asterion/dci/run.py
- Test: tests/test_asterion_dci_pi_rpc.py
- Test: tests/test_asterion_dci_run.py

**Interfaces:**
- Consumes DciPaths, DciRunRequest, and fixture Pi JSONL events.
- Produces DciRunResult(output_dir, final_text, events, status), with native files under output_dir.

- [ ] **Step 1: Write failing transport and artifact tests**

Port these exact behaviors from tests/test_pi_rpc_runner.py, changing imports to asterion.dci.pi_rpc: acknowledgement before completion; agent_settled requires an idle get_state result; retry discards partial text; timeout sends abort; turn limit sends abort then waits; malformed JSONL fails; a nonzero child has protected diagnostics; and show-tools writes only stderr.

Add this native-artifact case:

~~~python
def test_completed_run_writes_native_artifacts_and_protocol_projection(tmp_path):
    result = run_with_fixture_events(
        tmp_path,
        [
            {"type": "response", "id": "py-1", "success": True},
            {"type": "message_update", "assistantMessageEvent": {
                "type": "text_delta", "delta": "answer"}},
            {"type": "agent_end"},
        ],
    )
    self.assertEqual(result.final_text, "answer")
    self.assertEqual((result.output_dir / "question.txt").read_text(), "question\n")
    self.assertTrue((result.output_dir / "events.jsonl").is_file())
    self.assertEqual((result.output_dir / "final.txt").read_text(), "answer\n")
    self.assertTrue((result.output_dir / "state.json").is_file())
    self.assertEqual(
        [event.type for event in result.events][-2:],
        ["artifact.created", "run.completed"],
    )
~~~

The helper must mock client readers/processes; it must not execute Node or Pi.

- [ ] **Step 2: Run tests to verify failure**

Run: uv run python -m unittest -v tests.test_asterion_dci_pi_rpc tests.test_asterion_dci_run

Expected: FAIL because the new modules are absent.

- [ ] **Step 3: Implement the exact transport and run boundary**

In pi_rpc.py transplant _node_bin, _node_env, ensure_built_pi_cli, build_pi_command, expand_extra_args, and PiRpcClient from src/dci/benchmark/pi_rpc_runner.py. Replace only baseline imports with asterion.adapters.pi.PiProtocolAdapter and asterion.runtime.protocol validation. Preserve direct argv order: node, dist/cli.js, --mode rpc, optional provider/model/tools/system-prompt flags, --no-session, expanded extra args. Preserve reader threads, reap sequence, prompt_and_wait, probe_protocol, timeout/turn aborts, retry reset, and agent_settled idle postcondition. Never invoke a shell.

In run.py define the following concrete values:

~~~python
@dataclass(frozen=True)
class DciRunRequest:
    run_id: str
    question: str
    cwd: Path
    provider: str | None = None
    model: str | None = None
    tools: str = "read,bash"
    max_turns: int | None = None
    timeout_seconds: float | None = 3600.0
    extra_args: tuple[str, ...] = ()
    show_tools: bool = False
    system_prompt_file: Path | None = None
    append_system_prompt_file: Path | None = None

@dataclass(frozen=True)
class DciRunResult:
    output_dir: Path
    final_text: str
    events: tuple[RunEvent, ...]
    status: str

class DciRunError(RuntimeError):
    pass

def run_pi_research(
    paths: DciPaths, request: DciRunRequest, *, output_dir: Path | None = None
) -> DciRunResult: ...
~~~

Reject an existing nonempty output directory. Write question.txt, raw Pi JSON objects to events.jsonl, bounded stderr.txt, and state.json with exactly run_id, status, question_path, final_path, events_path, stderr_path. Create protocol/attempt-0001.request.json and protocol/attempt-0001.events.jsonl from the normalized request/events. Build protocol events via PiProtocolAdapter. Success appends an artifact.created event with relative URI final.txt then run.completed. Failure appends safe run.failed and raises DciRunError("DCI Pi execution failed") without question, command, provider response, or stderr body.

- [ ] **Step 4: Run focused verification**

Run: uv run python -m unittest -v tests.test_asterion_dci_pi_rpc tests.test_asterion_dci_run

Expected: PASS; validate_event_stream succeeds over every returned RunEvent mapping.

- [ ] **Step 5: Commit**

~~~bash
git add packages/python/asterion-core/src/asterion/dci/pi_rpc.py packages/python/asterion-core/src/asterion/dci/run.py tests/test_asterion_dci_pi_rpc.py tests/test_asterion_dci_run.py
git commit -m "feat: add Asterion DCI Pi execution engine"
~~~

## Task 3: Add package-local CLI and system-prompt handling

**Files:**
- Create: packages/python/asterion-core/src/asterion/dci/system_prompt.py
- Create: packages/python/asterion-core/src/asterion/dci/cli.py
- Modify: packages/python/asterion-core/pyproject.toml
- Test: tests/test_asterion_dci_cli.py

**Interfaces:**
- Produces asterion-dci run and asterion-dci system-prompt. Generic asterion CLI parsing remains unchanged.

- [ ] **Step 1: Write failing CLI tests**

~~~python
def test_run_maps_original_single_run_options_to_domain_request(tmp_path):
    with patch("asterion.dci.cli.run_pi_research") as run:
        run.return_value = fixture_result(tmp_path / "run")
        code = main([
            "run", "--cwd", str(tmp_path), "--tools", "read,bash",
            "--max-turns", "6", "--show-tools",
            "--extra-arg", "--thinking high", "question",
        ])
    self.assertEqual(code, 0)
    request = run.call_args.args[1]
    self.assertEqual(request.tools, "read,bash")
    self.assertEqual(request.max_turns, 6)
    self.assertEqual(request.extra_args, ("--thinking high",))

def test_cli_rejects_future_features():
    self.assertEqual(main(["run", "--resume", "question"]), 2)
    self.assertEqual(main(["run", "--eval-answer", "gold", "question"]), 2)
~~~

Also prove asterion-dci --help names run and system-prompt while asterion.cli._parser() contains no DCI subcommand.

- [ ] **Step 2: Run test to verify failure**

Run: uv run python -m unittest -v tests.test_asterion_dci_cli

Expected: FAIL with ModuleNotFoundError for asterion.dci.cli.

- [ ] **Step 3: Implement command behavior**

Add asterion-dci = "asterion.dci.cli:main" beside the existing asterion script in pyproject.toml. Implement one argparse parser with required subcommands. run accepts positional question or --question-file/stdin, --provider, --model, --cwd, --tools, --max-turns, --rpc-timeout-seconds, --show-tools, repeatable --extra-arg, --system-prompt-file, --append-system-prompt-file, and --output-dir. It builds DciRunRequest and prints only output_dir, status, and final_answer_uri: "final.txt".

Reject --resume with "resume is not available until AF-190", --eval-answer or --eval-answer-file with "evaluation is not available until AF-200", and benchmark with "benchmark is not available until AF-200"; every rejection exits 2.

Transplant src/dci/benchmark/pi_system_prompt.py into system_prompt.py with paths from DciPaths and direct Node argv. Export render_pi_system_prompt(paths, cwd, tools, append_system_prompt_file) -> str. The CLI maps unexpected Node/provider detail to DciRunError("DCI system prompt generation failed") and keeps detailed stderr outside public structured output.

- [ ] **Step 4: Run focused verification**

Run: uv run python -m unittest -v tests.test_asterion_dci_cli tests.test_asterion_cli

Expected: PASS; no fixture starts Pi and generic application selection is unchanged.

- [ ] **Step 5: Commit**

~~~bash
git add packages/python/asterion-core/pyproject.toml packages/python/asterion-core/src/asterion/dci/cli.py packages/python/asterion-core/src/asterion/dci/system_prompt.py tests/test_asterion_dci_cli.py
git commit -m "feat: add Asterion DCI operator command"
~~~

## Task 4: Define capability result projection without generic ownership changes

**Files:**
- Create: packages/python/asterion-core/src/asterion/dci/bridge.py
- Modify: packages/python/asterion-core/src/asterion/dci/__init__.py
- Modify: packages/python/asterion-core/src/asterion/capabilities/dci_research/implementation.py
- Create: tests/test_asterion_dci_bridge.py
- Modify: tests/test_dci_research_capability.py

**Interfaces:**
- Consumes a completed DciRunResult.
- Produces a declared PackageExecutionResult without answer, question, command, or stderr bodies.

- [ ] **Step 1: Write failing bridge tests**

~~~python
def test_projection_preserves_native_references_without_answer_body(tmp_path):
    result = fixture_result(tmp_path / "run", final_text="SECRET-ANSWER")
    projection = project_dci_run(result)
    self.assertEqual(projection.artifacts[0]["media_type"],
                     "application/vnd.dci.research+json")
    self.assertEqual(projection.artifacts[0]["value"], {
        "answer_artifact_uri": "final.txt",
        "events_artifact_uri": "events.jsonl",
        "state_artifact_uri": "state.json",
    })
    self.assertNotIn("SECRET-ANSWER", repr(projection))
~~~

Also assert that the existing runtime-neutral execute(PackageInvocation) fixture behavior stays unchanged, and projection rejects a result whose terminal normalized event is not run.completed.

- [ ] **Step 2: Run tests to verify failure**

Run: uv run python -m unittest -v tests.test_asterion_dci_bridge tests.test_dci_research_capability

Expected: FAIL because project_dci_run is absent.

- [ ] **Step 3: Implement explicit projection seam**

Define a DciRunExecutor Protocol with run(request: DciRunRequest) -> DciRunResult and project_dci_run(result: DciRunResult) -> PackageExecutionResult. Validate the complete result event stream, require the final artifact URI exactly final.txt, emit research.completed, and emit exactly one application/vnd.dci.research+json value with answer_artifact_uri, events_artifact_uri, and state_artifact_uri. Add execute_completed_native_run(result) to DciLocalResearchImplementation and have it return project_dci_run(result). Do not add implicit host-services discovery or change generic runner ownership; AF-210 owns that binding.

- [ ] **Step 4: Run focused verification**

Run: uv run python -m unittest -v tests.test_asterion_dci_bridge tests.test_dci_research_capability tests.test_distribution_boundaries.SourceDistributionBoundaryTests

Expected: PASS; projection is declared/body-free and no baseline import appears.

- [ ] **Step 5: Commit**

~~~bash
git add packages/python/asterion-core/src/asterion/dci/bridge.py packages/python/asterion-core/src/asterion/dci/__init__.py packages/python/asterion-core/src/asterion/capabilities/dci_research/implementation.py tests/test_asterion_dci_bridge.py tests/test_dci_research_capability.py
git commit -m "feat: project Asterion DCI native runs"
~~~

## Task 5: Document and prove the single-wheel product boundary

**Files:**
- Modify: .env.template
- Modify: README.md
- Modify: docs/architecture/capability-execution.md
- Modify: tests/test_distribution_boundaries.py

**Interfaces:**
- Produces documented ASTERION_DCI_* setup, asterion-dci commands, and an isolated-wheel proof that old DCI remains absent.

- [ ] **Step 1: Write failing wheel/documentation tests**

~~~python
def test_wheel_contains_asterion_dci_and_console_script_without_baseline_import():
    wheel = build_asterion_wheel()
    self.assertIn("asterion/dci/cli.py", wheel_names(wheel))
    self.assertIn("asterion/dci/run.py", wheel_names(wheel))
    self.assertNotIn("dci/benchmark/pi_rpc_runner.py", wheel_names(wheel))
    self.assertIn("asterion-dci = asterion.dci.cli:main", wheel_entry_points(wheel))
~~~

Assert .env.template names ASTERION_DCI_PI_DIR, ASTERION_DCI_PI_PACKAGE_DIR, ASTERION_DCI_PI_AGENT_DIR, and ASTERION_DCI_OUTPUT_ROOT. Assert README names the deferred AF-190/AF-200 functions.

- [ ] **Step 2: Run test to verify failure**

Run: uv run python -m unittest -v tests.test_distribution_boundaries

Expected: FAIL before the package and console script are installed in the wheel.

- [ ] **Step 3: Update exact operator documentation**

Add only the four ASTERION_DCI_* variables to .env.template with empty values. Add this README example:

~~~bash
asterion-dci run \
  --cwd "$PWD/corpus/wiki_corpus" \
  --tools read,bash \
  --extra-arg="--thinking high" \
  "Answer using only the local corpus."
~~~

Document AF-180 output files question.txt, events.jsonl, state.json, final.txt, stderr.txt, and protocol/. State that resume is AF-190 and judge/evaluation/benchmark are AF-200. In capability-execution.md document DciRunResult to project_dci_run and generic Asterion CLI neutrality.

- [ ] **Step 4: Run focused verification**

Run: uv run python -m unittest -v tests.test_distribution_boundaries tests.test_asterion_dci_cli

Expected: PASS; the isolated wheel has asterion.dci and asterion-dci but excludes old dci.

- [ ] **Step 5: Commit**

~~~bash
git add .env.template README.md docs/architecture/capability-execution.md tests/test_distribution_boundaries.py
git commit -m "docs: describe Asterion DCI execution package"
~~~

## Task 6: Execute AF-180 closure matrix and record evidence

**Files:**
- Modify: docs/status/WORKLIST.md
- Modify: docs/status/CURRENT-STATE.md
- Modify: docs/status/JOURNAL.md
- Modify: docs/status/RESUME-NEXT-SESSION.md

- [ ] **Step 1: Run focused parity matrix**

Run:

~~~bash
uv run python -m unittest -v \
  tests.test_asterion_dci_config \
  tests.test_asterion_dci_pi_rpc \
  tests.test_asterion_dci_run \
  tests.test_asterion_dci_cli \
  tests.test_asterion_dci_bridge \
  tests.test_dci_research_capability \
  tests.test_distribution_boundaries
~~~

Expected: PASS with no live Pi/judge/Claude request. If a behavior differs, stop and record the exact parity failure; do not weaken the assertion.

- [ ] **Step 2: Run repository gates**

Run:

~~~bash
uv run python -m unittest discover -v
uv run ruff check packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_config.py tests/test_asterion_dci_pi_rpc.py tests/test_asterion_dci_run.py tests/test_asterion_dci_cli.py tests/test_asterion_dci_bridge.py
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
bash -n scripts/examples/*.sh scripts/bcplus_eval/*.sh scripts/bright/*.sh
git diff --check
python3 tools/project_scope_check.py
~~~

Expected: every command exits 0.

- [ ] **Step 3: Perform only authorized end-to-end verification**

Run: asterion-dci run --help

Expected: exit 0 without starting Pi. Run a real Pi request only after explicit operator authorization; record only the output directory and parity observation. Never run judge, batch, or Claude provider commands in AF-180.

- [ ] **Step 4: Update durable state from evidence**

On complete success, replace AF-180 implementation evidence with exact test/build counts and activate AF-190 only in a separate reviewed governance commit. On any failure, retain AF-180 in_progress, append the exact failure to JOURNAL.md, and set RESUME-NEXT-SESSION.md to the first reproducer.

- [ ] **Step 5: Commit closure only after evidence exists**

~~~bash
git add docs/status/WORKLIST.md docs/status/CURRENT-STATE.md docs/status/JOURNAL.md docs/status/RESUME-NEXT-SESSION.md
git commit -m "docs: record AF-180 execution parity evidence"
~~~

## Plan self-review

- Spec coverage: Tasks 1-3 cover independent configuration, original Pi execution behavior, system prompt, native single-run artifacts, and package CLI. Task 4 adds the capability-contract result projection without prematurely altering generic application ownership. Task 5 proves one-wheel/operator boundaries. Task 6 provides parity gates, authorization limits, and state discipline. AF-190/200/210 remain excluded.
- Placeholder scan: no TBD/TODO or vague error-handling instruction remains; every deferred behavior has an owning AF package and exact CLI rejection.
- Type consistency: DciPaths flows into run_pi_research; it returns DciRunResult; project_dci_run returns PackageExecutionResult; execute_completed_native_run exposes the same result to the existing capability package without changing PackageInvocation.
