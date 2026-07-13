# AF-220 Shared Configuration and Runnable Pi Application Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make Asterion DCI and source DCI use the same normal .env Pi/provider settings, then prove package CLI, benchmark, installed application, and two runnable examples produce equivalent native Pi requests.

**Architecture:** A frozen DciRuntimeOptions in asterion.dci resolves shared DCI_* values and explicit command values. It creates DciRunRequest values for package CLI, benchmark rows, and the provider-owned application executor. Generic asterion CLI and runner code remain unchanged and DCI-neutral.

**Tech Stack:** Python 3.11, dataclasses, python-dotenv, argparse, unittest, Pi JSONL RPC, Bash.

## Global Constraints

- Do not modify or import src/dci from Asterion runtime code.
- Do not edit the external pi checkout or persist credentials.
- Shared normal settings are DCI_PI_*, DCI_PROVIDER, DCI_MODEL, DCI_RPC_TIMEOUT_SECONDS, DCI_EVAL_JUDGE_*, and inherited Pi/provider environment variables.
- ASTERION_DCI_OUTPUT_ROOT is the normal Asterion-only setting. ASTERION_DCI_PI_* remains a backward-compatible alias only.
- Do not add DCI parsing or defaults to asterion.cli, runner, factory, or application-selection modules.
- Framework projection remains body-free; native evidence follows existing privacy boundaries.
- Run python3 tools/project_scope_check.py before Climb dispatch and package closure.
- Run unittest discovery, compileall, Ruff, Node, Rust, Bash syntax, and git diff --check before closure.

---

## File structure

| File | Responsibility |
|---|---|
| packages/python/asterion-core/src/asterion/dci/config.py | Shared paths and immutable runtime options. |
| packages/python/asterion-core/src/asterion/dci/run.py | Typed runtime controls in native requests/state/resume. |
| packages/python/asterion-core/src/asterion/dci/pi_rpc.py | Direct Pi argv and child environment. |
| packages/python/asterion-core/src/asterion/dci/cli.py | Package CLI option parsing and evaluation handoff. |
| packages/python/asterion-core/src/asterion/dci/benchmark.py | Runtime-option reuse for every batch row. |
| packages/python/asterion-core/src/asterion/dci/application_executor.py | Provider-owned installed-app mapping. |
| tests/test_asterion_dci_*.py | Focused shared-config, transport, CLI, batch, and application tests. |
| scripts/examples/asterion_dci_*.sh | Pi-default runnable product examples. |
| .env.template, README.md, Makefile | Shared configuration and operator entry points. |

### Task 1: Define shared configuration and option resolution

**Files:**
- Modify: packages/python/asterion-core/src/asterion/dci/config.py
- Modify: tests/test_asterion_dci_config.py
- Modify: .env.template

**Interfaces:**
- Produces DciRuntimeOptions(provider, model, tools, timeout_seconds, runtime_context_level, thinking_level, node_max_old_space_size_mb, keep_session, extra_args).
- Produces resolve_dci_runtime_options(overrides: Mapping[str, object] | None = None) -> DciRuntimeOptions.
- Updates resolve_dci_paths(repo_root: Path) -> DciPaths so non-empty DCI_PI_* wins over ASTERION_DCI_PI_* aliases.

- [ ] **Step 1: Write failing tests**

~~~python
def test_shared_paths_win_over_compatibility_aliases(self) -> None:
    with patch.dict(os.environ, {
        "DCI_PI_DIR": "shared/pi",
        "ASTERION_DCI_PI_DIR": "compat/pi",
    }, clear=True):
        paths = resolve_dci_paths(root)
    self.assertEqual(paths.pi.repo_dir, root / "shared/pi")

def test_runtime_options_merge_shared_env_and_explicit_values(self) -> None:
    with patch.dict(os.environ, {
        "DCI_PROVIDER": "openai",
        "DCI_MODEL": "gpt-test",
        "DCI_RPC_TIMEOUT_SECONDS": "45",
    }, clear=True):
        options = resolve_dci_runtime_options({"model": "explicit-model"})
    self.assertEqual(
        (options.provider, options.model, options.timeout_seconds),
        ("openai", "explicit-model", 45.0),
    )
~~~

- [ ] **Step 2: Run the focused test**

Run: uv run python -m unittest -v tests.test_asterion_dci_config

Expected: FAIL because current Asterion paths ignore DCI_PI_DIR and no runtime-options resolver exists.

- [ ] **Step 3: Implement the minimal resolver**

~~~python
@dataclass(frozen=True)
class DciRuntimeOptions:
    provider: str | None
    model: str | None
    tools: str = "read,bash"
    timeout_seconds: float | None = 3600.0
    runtime_context_level: str | None = None
    thinking_level: str | None = None
    node_max_old_space_size_mb: int | None = None
    keep_session: bool = False
    extra_args: tuple[str, ...] = ()

def resolve_dci_runtime_options(
    overrides: Mapping[str, object] | None = None,
) -> DciRuntimeOptions:
    values = {} if overrides is None else dict(overrides)
    return DciRuntimeOptions(
        provider=_override_or_env(values, "provider", "DCI_PROVIDER"),
        model=_override_or_env(values, "model", "DCI_MODEL"),
        tools=str(_override_or_env(values, "tools", "DCI_TOOLS", "read,bash")),
        timeout_seconds=_timeout_value(
            _override_or_env(values, "timeout_seconds", "DCI_RPC_TIMEOUT_SECONDS", "3600")
        ),
        runtime_context_level=_override_or_env(
            values, "runtime_context_level", "DCI_RUNTIME_CONTEXT_LEVEL"
        ),
        thinking_level=_override_or_env(
            values, "thinking_level", "DCI_PI_THINKING_LEVEL"
        ),
        node_max_old_space_size_mb=_optional_positive_int(
            _override_or_env(
                values, "node_max_old_space_size_mb", "DCI_NODE_MAX_OLD_SPACE_SIZE_MB"
            )
        ),
        keep_session=bool(values.get("keep_session", False)),
        extra_args=tuple(values.get("extra_args", ())),
    )
~~~

Implement _configured_path_shared(shared_name, alias_name, default, root) so shared values win, aliases are fallback, and root/pi stays the default.

- [ ] **Step 4: Document the contract**

Replace the isolated Asterion-path paragraph in .env.template. Document DCI_PI_*, DCI_PROVIDER, DCI_MODEL, DCI_RPC_TIMEOUT_SECONDS, and DCI_EVAL_JUDGE_* as shared; document only ASTERION_DCI_OUTPUT_ROOT as Asterion-specific and label ASTERION_DCI_PI_* as aliases.

- [ ] **Step 5: Verify and commit**

Run: uv run python -m unittest -v tests.test_asterion_dci_config

Expected: PASS, including invalid timeout and invalid heap rejection.

~~~bash
git add packages/python/asterion-core/src/asterion/dci/config.py tests/test_asterion_dci_config.py .env.template
git commit -m "feat: share DCI runtime configuration"
~~~

### Task 2: Carry context, session, and resource controls to native Pi

**Files:**
- Modify: packages/python/asterion-core/src/asterion/dci/run.py
- Modify: packages/python/asterion-core/src/asterion/dci/pi_rpc.py
- Modify: tests/test_asterion_dci_run.py
- Modify: tests/test_asterion_dci_pi_rpc.py

**Interfaces:**
- Extends DciRunRequest with runtime_context_level, thinking_level, node_max_old_space_size_mb, and keep_session.
- Produces request_from_runtime_options(options: DciRuntimeOptions, *, run_id: str, question: str, cwd: Path) -> DciRunRequest in run.py, avoiding a config.py-to-run.py import cycle.
- PiRpcClient accepts keep_session and node_max_old_space_size_mb.

- [ ] **Step 1: Write failing transport tests**

~~~python
def test_client_maps_context_thinking_and_session_to_pi(self) -> None:
    command = build_pi_command(
        package_dir=Path("/pi/packages/coding-agent"),
        mode="rpc", provider="p", model="m", tools="read,bash",
        no_session=False, system_prompt_file=None,
        append_system_prompt_file=None,
        extra_args=["--context-management-level", "level3", "--thinking", "high"],
    )
    self.assertNotIn("--no-session", command)
    self.assertEqual(
        command[-4:],
        ["--context-management-level", "level3", "--thinking", "high"],
    )

def test_heap_option_preserves_existing_node_options(self) -> None:
    client = make_client(node_max_old_space_size_mb=8192)
    with patch.dict(os.environ, {"NODE_OPTIONS": "--trace-warnings"}, clear=True):
        environment = client._child_environment()
    self.assertEqual(
        environment["NODE_OPTIONS"],
        "--trace-warnings --max-old-space-size=8192",
    )
~~~

- [ ] **Step 2: Run the focused tests**

Run: uv run python -m unittest -v tests.test_asterion_dci_pi_rpc tests.test_asterion_dci_run

Expected: FAIL because the current client always adds --no-session and has no heap environment path.

- [ ] **Step 3: Implement typed request mapping**

~~~python
@dataclass(frozen=True)
class DciRunRequest:
    # existing fields remain unchanged
    runtime_context_level: str | None = None
    thinking_level: str | None = None
    node_max_old_space_size_mb: int | None = None
    keep_session: bool = False

def _pi_extra_args(request: DciRunRequest) -> tuple[str, ...]:
    values = list(request.extra_args)
    if request.thinking_level:
        values.append(f"--thinking {request.thinking_level}")
    if request.runtime_context_level:
        values.append(
            f"--context-management-level {request.runtime_context_level}"
        )
    return tuple(values)

def request_from_runtime_options(
    options: DciRuntimeOptions, *, run_id: str, question: str, cwd: Path
) -> DciRunRequest:
    return DciRunRequest(
        run_id=run_id, question=question, cwd=cwd,
        provider=options.provider, model=options.model, tools=options.tools,
        timeout_seconds=options.timeout_seconds,
        runtime_context_level=options.runtime_context_level,
        thinking_level=options.thinking_level,
        node_max_old_space_size_mb=options.node_max_old_space_size_mb,
        keep_session=options.keep_session, extra_args=options.extra_args,
    )
~~~

Pass no_session=not request.keep_session, _pi_extra_args(request), and the heap setting to PiRpcClient. Implement _child_environment() by copying os.environ, setting PI_CODING_AGENT_DIR, and appending one --max-old-space-size=N token when N is present. Persist all four controls in state.json and include them in resume reconstruction and immutable mismatch validation.

- [ ] **Step 4: Verify and commit**

Run: uv run python -m unittest -v tests.test_asterion_dci_pi_rpc tests.test_asterion_dci_run

Expected: PASS; a changed context/session/heap value rejects resume before Pi construction.

~~~bash
git add packages/python/asterion-core/src/asterion/dci/run.py packages/python/asterion-core/src/asterion/dci/pi_rpc.py tests/test_asterion_dci_run.py tests/test_asterion_dci_pi_rpc.py
git commit -m "feat: carry DCI runtime controls to Pi"
~~~

### Task 3: Reuse options in product CLI and benchmark

**Files:**
- Modify: packages/python/asterion-core/src/asterion/dci/cli.py
- Modify: packages/python/asterion-core/src/asterion/dci/benchmark.py
- Modify: tests/test_asterion_dci_cli.py
- Modify: tests/test_asterion_dci_benchmark.py

**Interfaces:**
- BenchmarkRequest gains runtime_options: DciRuntimeOptions and limit: int | None.
- request_from_runtime_options(options: DciRuntimeOptions, *, run_id: str, question: str, cwd: Path) -> DciRunRequest is the only CLI/batch construction path.

- [ ] **Step 1: Write failing propagation tests**

~~~python
def test_run_uses_shared_defaults_and_explicit_context(self) -> None:
    with patch.dict(os.environ, {
        "DCI_PROVIDER": "openai", "DCI_MODEL": "gpt-test",
    }, clear=True):
        code = main([
            "run", "--runtime-context-level", "level3",
            "--thinking-level", "high", "question",
        ], repo_root=root, stdout=io.StringIO(), stderr=io.StringIO())
    request = run.call_args.args[1]
    self.assertEqual((request.provider, request.model), ("openai", "gpt-test"))
    self.assertEqual(
        (request.runtime_context_level, request.thinking_level),
        ("level3", "high"),
    )

def test_benchmark_uses_its_runtime_options_for_every_native_row(self) -> None:
    request = BenchmarkRequest(
        dataset=dataset, output_root=root / "out", cwd=root,
        judge_config=JudgeConfig(base_url="https://judge.example.test/v1"),
        runtime_options=DciRuntimeOptions(provider="openai", model="gpt-test"),
    )
    run_benchmark(request, paths=Mock())
    native_request = run.call_args.args[1]
    self.assertEqual((native_request.provider, native_request.model),
                     ("openai", "gpt-test"))
~~~

- [ ] **Step 2: Run the focused tests**

Run: uv run python -m unittest -v tests.test_asterion_dci_cli tests.test_asterion_dci_benchmark

Expected: FAIL because current CLI/benchmark omit shared options.

- [ ] **Step 3: Implement command mapping**

Add these run and benchmark flags: --provider, --model, --tools, --rpc-timeout-seconds, --runtime-context-level, --thinking-level, --node-max-old-space-size-mb, --keep-session, repeatable --extra-arg, and benchmark-only --limit. Validate --limit is at least one and slice the deterministic sorted rows before execution. Use None defaults for optional flags so environment defaults are distinguishable from an explicit CLI value.

~~~python
options = resolve_dci_runtime_options({
    "provider": args.provider,
    "model": args.model,
    "tools": args.tools,
    "timeout_seconds": args.rpc_timeout_seconds,
    "runtime_context_level": args.runtime_context_level,
    "thinking_level": args.thinking_level,
    "node_max_old_space_size_mb": args.node_max_old_space_size_mb,
    "keep_session": args.keep_session,
    "extra_args": tuple(args.extra_arg),
})
request = request_from_runtime_options(options,
    run_id=args.run_id, question=question, cwd=args.cwd
)
~~~

Replace the stale run --eval-answer rejection. When evaluation input is supplied, run the native request, call evaluate_run_directory with JudgeConfig.from_env(), and print only the output directory, boolean verdict, and eval_result.json URI.

- [ ] **Step 4: Verify and commit**

Run: uv run python -m unittest -v tests.test_asterion_dci_cli tests.test_asterion_dci_benchmark

Expected: PASS, including CLI-over-environment precedence, one options value reused by all rows, and public failure redaction.

~~~bash
git add packages/python/asterion-core/src/asterion/dci/cli.py packages/python/asterion-core/src/asterion/dci/benchmark.py tests/test_asterion_dci_cli.py tests/test_asterion_dci_benchmark.py
git commit -m "feat: reuse shared DCI options in product commands"
~~~

### Task 4: Configure installed Pi applications at the provider boundary

**Files:**
- Modify: packages/python/asterion-core/src/asterion/dci/application_executor.py
- Modify: packages/python/asterion-core/src/asterion/capabilities/dci_research/implementation.py
- Modify: tests/test_asterion_dci_application_executor.py
- Modify: tests/test_builtin_dci_application.py

**Interfaces:**
- EnvironmentDciRunExecutor.run(request) replaces only runtime defaults/cwd and preserves the invocation run_id and question.
- DciLocalResearchImplementation continues to create a minimal request; it does not parse environment variables.

- [ ] **Step 1: Write the failing installed-application test**

~~~python
def test_application_executor_applies_shared_options(self) -> None:
    with patch.dict(os.environ, {
        "DCI_PROVIDER": "openai", "DCI_MODEL": "gpt-test",
        "DCI_TOOLS": "read,bash",
        "DCI_RUNTIME_CONTEXT_LEVEL": "level3",
        "DCI_PI_THINKING_LEVEL": "high",
    }, clear=True):
        executor.run(
            DciRunRequest(
                run_id="application-run", question="question", cwd=Path("ignored")
            )
        )
    mapped = calls[0][1]
    self.assertEqual(
        (mapped.provider, mapped.model, mapped.tools),
        ("openai", "gpt-test", "read,bash"),
    )
    self.assertEqual(
        (mapped.runtime_context_level, mapped.thinking_level), ("level3", "high")
    )
~~~

- [ ] **Step 2: Run the focused test**

Run: uv run python -m unittest -v tests.test_asterion_dci_application_executor tests.test_builtin_dci_application

Expected: FAIL because the executor currently only maps cwd and Asterion path variables.

- [ ] **Step 3: Implement provider-owned mapping**

~~~python
def run(self, request: DciRunRequest) -> DciRunResult:
    root = self._repo_root.resolve()
    load_asterion_dci_env(root)
    options = resolve_dci_runtime_options()
    cwd = Path(os.environ.get("ASTERION_RUNTIME_CWD", root)).resolve()
    mapped = request_from_runtime_options(options,
        run_id=request.run_id, question=request.question, cwd=cwd
    )
    return self._run_native(resolve_dci_paths(root), mapped)
~~~

Do not move this mapping into asterion.cli, runner, runtime factory, or selection code.

- [ ] **Step 4: Verify and commit**

Run: uv run python -m unittest -v tests.test_asterion_dci_application_executor tests.test_builtin_dci_application

Expected: PASS; existing generic-module source scans remain green.

~~~bash
git add packages/python/asterion-core/src/asterion/dci/application_executor.py packages/python/asterion-core/src/asterion/capabilities/dci_research/implementation.py tests/test_asterion_dci_application_executor.py tests/test_builtin_dci_application.py
git commit -m "feat: configure installed DCI Pi applications"
~~~

### Task 5: Add runnable Asterion examples and update operator docs

**Files:**
- Create: scripts/examples/asterion_dci_basic_example.sh
- Create: scripts/examples/asterion_dci_runtime_context_example.sh
- Modify: Makefile
- Modify: README.md
- Modify: tests/test_asterion_dci_cli.py

**Interfaces:**
- make asterion-example runs the basic Pi example.
- make asterion-runtime-example runs the runtime-context Pi/Judge example.

- [ ] **Step 1: Write the failing example test**

~~~python
def test_asterion_examples_use_shared_env_and_package_command(self) -> None:
    for path in (
        ROOT / "scripts/examples/asterion_dci_basic_example.sh",
        ROOT / "scripts/examples/asterion_dci_runtime_context_example.sh",
    ):
        source = path.read_text()
        self.assertIn("asterion-dci run", source)
        self.assertIn("DCI_PROVIDER", source)
        self.assertNotIn("python -m dci.", source)
~~~

- [ ] **Step 2: Run the focused test**

Run: uv run python -m unittest -v tests.test_asterion_dci_cli.AsterionDciCliTests.test_asterion_examples_use_shared_env_and_package_command

Expected: FAIL because the examples do not exist.

- [ ] **Step 3: Create examples and documentation**

Copy only repository-root/.env-loading boilerplate from the source examples. The basic launcher must require DCI_PROVIDER and DCI_MODEL, use set -euo pipefail, and execute:

~~~bash
asterion-dci run \
  --cwd "$REPO_ROOT/corpus/wiki_corpus" \
  --extra-arg="--thinking high" \
  "$QUESTION"
~~~

The context launcher must use the existing BCPlus question/corpus plus --tools read,bash, --max-turns 6, --runtime-context-level "$level", and --eval-answer "Adaku". Add Make targets asterion-example and asterion-runtime-example. Correct README so normal DCI_* configuration is shared by source DCI, asterion-dci, benchmark, and installed Pi application.

- [ ] **Step 4: Verify and commit**

Run: bash -n scripts/examples/asterion_dci_basic_example.sh scripts/examples/asterion_dci_runtime_context_example.sh && uv run python -m unittest -v tests.test_asterion_dci_cli

Expected: PASS without a provider request.

~~~bash
git add scripts/examples/asterion_dci_basic_example.sh scripts/examples/asterion_dci_runtime_context_example.sh Makefile README.md tests/test_asterion_dci_cli.py
git commit -m "docs: add runnable Asterion DCI Pi examples"
~~~

### Task 6: Register Climb evidence and complete local closure

**Files:**
- Modify: docs/status/climb/hypotheses.yaml
- Modify: docs/status/climb/session-state.json
- Regenerate: docs/status/climb/research-tree.md and docs/status/climb/research-tree.json
- Modify: docs/status/JOURNAL.md
- Modify: docs/status/WORKLIST.md
- Modify: docs/status/RESUME-NEXT-SESSION.md

**Interfaces:**
- Registers AF-220-H-001 shared configuration, AF-220-H-002 native Pi controls, AF-220-H-003 package/batch propagation, and AF-220-H-004 application/example equivalence.
- Each entry includes work_package_id: AF-220, pending state, and the exact Task 1-5 test command.

- [ ] **Step 1: Register hypotheses before implementation**

Append four hypotheses with rankings 0.90, 0.80, 0.70, and 0.60. Set session-state phase to implementation, work_package_id to AF-220, last_cycle to the next unused integer, and next_hypothesis to AF-220-H-001. Regenerate the research tree.

- [ ] **Step 2: Run preflight**

Run: python3 tools/project_scope_check.py --climb-hypothesis AF-220-H-001

Expected: JSON reports ok true and active_package AF-220. Repair governance before code work if it fails.

- [ ] **Step 3: Run local closure**

~~~bash
uv run python -m unittest discover -v
uv run python -m compileall -q packages/python/asterion-core/src/asterion
uv run ruff check packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_config.py tests/test_asterion_dci_run.py tests/test_asterion_dci_pi_rpc.py tests/test_asterion_dci_cli.py tests/test_asterion_dci_benchmark.py tests/test_asterion_dci_application_executor.py
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
bash -n scripts/examples/asterion_dci_basic_example.sh scripts/examples/asterion_dci_runtime_context_example.sh
git diff --check
~~~

Expected: every command exits zero. Record totals and provider-independent evidence in JOURNAL.md.

- [ ] **Step 4: Confirm local hypotheses**

After each matching test passes, append its run record, mark it confirmed 4/4, regenerate the research tree, journal the result, and commit the implementation plus state. Do not close AF-220 before Task 7.

### Task 7: Run authorized bounded real acceptance and close AF-220

**Files:**
- Modify: docs/status/JOURNAL.md
- Modify: docs/status/WORKLIST.md
- Modify: docs/status/RESUME-NEXT-SESSION.md
- Modify: docs/status/CURRENT-STATE.md
- Regenerate: docs/status/climb/research-tree.md and docs/status/climb/research-tree.json

**Interfaces:**
- Uses only the shared .env. Neither command output nor status documents contain credential values.

- [ ] **Step 1: Verify prerequisites**

Run: make check-pi-rpc && make check-judge-config

Expected: both commands exit zero before model/Judge spending. If either fails, journal the safe failure and leave AF-220 in_progress.

- [ ] **Step 2: Run real example acceptance**

Run:

~~~bash
make asterion-example
make asterion-runtime-example
~~~

Expected: each exits zero and reports an Asterion-native output directory; the context run creates eval_result.json with boolean is_correct.

- [ ] **Step 3: Run installed application acceptance**

Run:

~~~bash
asterion run --provider dci-agent-lite --application dci.research-capability@1.0.0 --runtime pi.reference --run-id af220-application --input "Answer using only the local corpus."
~~~

Expected: zero exit, body-free JSON projection, and native state recording the shared provider/model/tools values.

- [ ] **Step 4: Run one-row Pi-plus-Judge benchmark**

Create the exact temporary dataset, then run:

~~~bash
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
printf '%s\n' '{"query_id":"great-fire","query":"Answer using only wiki_dump.jsonl in the current directory. In which street did the Great Fire of London originate?","answer":"Pudding Lane"}' > "$TMPDIR/one-row.jsonl"
asterion-dci benchmark --dataset "$TMPDIR/one-row.jsonl" --output-root "$TMPDIR/benchmark" --cwd "$PWD/corpus/wiki_corpus" --limit 1
~~~

Expected: zero exit, one native query directory, eval_result.json with boolean is_correct, result.json, and summary.json total 1.

- [ ] **Step 5: Close only with evidence**

Journal commands, output locations, exit status, and verdict without secrets. Mark AF-220 completed only after all four bounded real checks succeed; otherwise retain in_progress with the failed acceptance. Regenerate Climb state, select AF-230 only after closure, run python3 tools/project_scope_check.py and git diff --check, then commit:

~~~bash
git add docs/status
git commit -m "docs: record AF-220 parity acceptance"
~~~

## Plan self-review

- Spec coverage: Tasks 1 through 5 implement shared configuration, Pi controls, package/batch mapping, installed application mapping, and runnable examples. Tasks 6 and 7 supply local and authorized real evidence.
- Placeholder scan: each task names exact files, interfaces, test behavior, commands, and commit boundaries.
- Type consistency: DciRuntimeOptions is defined in Task 1, translated by request_from_runtime_options in Task 2, used by CLI/benchmark in Task 3, and used by the provider executor in Task 4.
