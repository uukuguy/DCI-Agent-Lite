# Installed Claude Runtime Interface Implementation Plan

> **For agentic workers:** Execute inline with test-driven development. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Expose claude-code.reference as an installed Asterion runtime factory and verify its fixture-only protocol boundary without a Claude account or provider request.

**Architecture:** A thin ClaudeCodeRuntimeClient adapts run_claude_code() to AgentRuntimeClient, uses a temporary per-request artifact directory, and yields only normalized events. The default registry selects it by exact ID and validates executable/cwd without starting Claude.

**Tech Stack:** Python asyncio, tempfile, unittest/mock, existing Claude JSONL fixtures, uv build.

## Global Constraints

- Never send a Claude prompt, provider/auth request, or network request during AF-160 verification.
- Preserve direct restricted command behavior: safe mode, no session persistence, explicit tools, and no permission bypass.
- Keep credentials, gateway values, raw stdout/stderr, and prompt text out of public outputs and persisted metadata.
- Do not change pi.reference, the DCI provider runtime list, src/dci, or src/dci/benchmark/.

---

### Task 1: Define the runtime-client contract

**Files:**

- Create: tests/test_asterion_claude_runtime.py
- Read: tests/fixtures/claude_code/valid-success.jsonl
- Modify later: packages/python/asterion-core/src/asterion/runtimes/claude_code.py

**Interfaces:**

~~~python
class ClaudeCodeRuntimeClient:
    def __init__(self, *, executable: str, cwd: Path,
                 environment: Mapping[str, str], run_process=subprocess.run) -> None: ...
    @property
    def manifest(self) -> RuntimeManifest: ...
    async def run(self, request: RunRequest, *,
                  signal: CancellationSignal | None = None) -> AsyncIterator[RunEvent]: ...
~~~

- [ ] Write an IsolatedAsyncioTestCase with a fake CompletedProcess containing valid-success.jsonl; consume runtime.run(RunRequest("run", "SECRET-PROMPT")).
- [ ] Assert manifest ID is claude-code.reference and capabilities are exactly ("filesystem.read", "shell"); validate mappings with validate_event_stream(); assert the fake sees ANTHROPIC_AUTH_TOKEN="SECRET" but repr(events) does not.
- [ ] Add red tests for pre-cancel before fake-process invocation, malformed fixture output producing content-free ProtocolError, and absence of retained temporary artifact paths.
- [ ] Run: uv run python -m unittest tests.test_asterion_claude_runtime -v. Expected: import failure because ClaudeCodeRuntimeClient does not exist.
- [ ] Commit:

~~~bash
git add tests/test_asterion_claude_runtime.py
git commit -m "test: define Claude runtime client contract"
~~~

### Task 2: Adapt the restricted Claude runner

**Files:**

- Modify: packages/python/asterion-core/src/asterion/runtimes/claude_code.py
- Test: tests/test_asterion_claude_runtime.py
- Preserve: tests/test_claude_code_runtime.py

**Interfaces:** ClaudeCodeRuntimeClient.run() calls existing run_claude_code() through asyncio.to_thread, reads that invocation's events.jsonl, then yields RunEvent.from_mapping().

- [ ] Implement TemporaryDirectory(prefix="asterion-claude-"), fixed Read/Bash tools, deadline-to-seconds conversion with a 30-second default, and RuntimeManifest("claude-code.reference", ("filesystem.read", "shell")).
- [ ] Call request.to_mapping(); reject pre-cancel before subprocess startup; convert filesystem, subprocess, malformed JSON, and protocol failures into fixed ProtocolError messages without exception text.
- [ ] Do not retain or return temporary paths, raw streams, prompt, environment, or completed-process objects.
- [ ] Run: uv run python -m unittest tests.test_asterion_claude_runtime tests.test_claude_code_runtime -v. Expected: all green and zero real Claude subprocesses.
- [ ] Run: uv run python -m compileall -q packages/python/asterion-core/src tests.
- [ ] Run: uv run ruff check packages/python/asterion-core/src/asterion/runtimes/claude_code.py tests/test_asterion_claude_runtime.py.
- [ ] Commit:

~~~bash
git add packages/python/asterion-core/src/asterion/runtimes/claude_code.py tests/test_asterion_claude_runtime.py
git commit -m "feat: adapt Claude runtime to Asterion host"
~~~

### Task 3: Register the exact installed factory

**Files:**

- Modify: packages/python/asterion-core/src/asterion/runtime/defaults.py
- Modify: tests/test_default_runtime_factory.py
- Test: tests/test_asterion_claude_runtime.py

**Interfaces:**

~~~python
def _create_claude_code_runtime(
    context: RuntimeFactoryContext,
) -> ClaudeCodeRuntimeClient: ...
~~~

- [ ] Write failing tests selecting claude-code.reference from default_runtime_factory_registry(), asserting exact capabilities, and constructing under patched shutil.which without calling run_process.
- [ ] Add a failing test that ASTERION_CLAUDE_EXECUTABLE="/SECRET/missing" yields only RuntimeFactoryError("Claude Code runtime is unavailable"); retain Pi tests unchanged.
- [ ] Run: uv run python -m unittest tests.test_default_runtime_factory -v. Expected: no Claude binding.
- [ ] Add the second RuntimeFactoryBinding. The private factory accepts only its exact ID, validates executable through explicit path or shutil.which, validates ASTERION_RUNTIME_CWD, copies caller environment for later use, and never runs Claude/auth/network code.
- [ ] Run: uv run python -m unittest tests.test_default_runtime_factory tests.test_asterion_claude_runtime -v. Expected: all green; mocked run-process count zero during construction.
- [ ] Commit:

~~~bash
git add packages/python/asterion-core/src/asterion/runtime/defaults.py tests/test_default_runtime_factory.py tests/test_asterion_claude_runtime.py
git commit -m "feat: register installed Claude runtime factory"
~~~

### Task 4: Verify the isolated product and close AF-160

**Files:**

- Modify: .env.template
- Modify: README.md
- Modify: docs/architecture/agent-framework.md
- Modify: docs/status/{WORKLIST,CURRENT-STATE,DECISIONS,JOURNAL,RESUME-NEXT-SESSION}.md

- [ ] Document ASTERION_CLAUDE_EXECUTABLE and existing ASTERION_RUNTIME_CWD as operator-owned configuration; state factory construction does not authenticate or prompt, and bundled DCI remains Pi-only.
- [ ] Build one wheel with uv build --out-dir /tmp/asterion-af160-wheel, install it into a fresh venv with uv pip install --python, and run a script that patches executable discovery, selects the exact Claude binding, checks its manifest, confirms importlib.util.find_spec("dci") is None, and never calls run().
- [ ] Run complete closure: uv run python -m unittest discover -q; Python compile and Ruff; npm test in packages/typescript/asterion-runtime; cargo test in packages/rust/controlled-executor; rg --files -g '*.sh' | xargs -n 1 bash -n; python3 tools/project_scope_check.py; git diff --check.
- [ ] Record verified results, continued real-provider deferral, and AF-160 closure in status files.
- [ ] Commit:

~~~bash
git add .env.template README.md docs packages/python/asterion-core/src tests
git commit -m "docs: close installed Claude runtime interface"
~~~

## Plan Self-Review

- Task 1 covers exact client/redaction behavior; Task 2 covers normalized events, pre-cancel, and temporary cleanup; Task 3 covers selection/safe construction; Task 4 covers docs, isolated wheel, and closure.
- Every introduced name, command, error type, and path is explicit. The scope contains no credential configuration, login automation, provider request, dynamic selection, or DCI runtime-list change.

