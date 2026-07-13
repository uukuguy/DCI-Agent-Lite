# Asterion DCI Evaluation and Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent Asterion DCI judge, cache-safe evaluation, and dataset-batch benchmark surface that reuses the Asterion DCI run implementation.

**Architecture:** Transplant the original DCI judge configuration, request shaping, response parsing, usage/cost accounting, and request fingerprinting into focused Asterion-owned modules. Evaluation operates on an Asterion native run directory and persists an `eval_result.json` only after a validated judge response; the cache identity contains the complete public judge configuration plus shaped request. A deterministic batch module reads explicit JSONL input, calls only `asterion.dci.run.run_pi_research` and the new evaluator, and emits result and aggregate artifacts. The generic `asterion` CLI remains domain-neutral; `asterion-dci evaluate` and `asterion-dci benchmark` are product-local.

**Tech Stack:** Python 3.10+, `argparse`, `urllib.request`, dataclasses, JSON/JSONL, Asterion DCI artifacts, `unittest`, Ruff.

## Global Constraints

- Create or modify DCI product code only under `packages/python/asterion-core/src/asterion/dci/`; never import, execute, inspect, or modify `src/dci` at runtime.
- Preserve separate `ASTERION_DCI_*` configuration and output roots; never accept legacy `DCI_*` as aliases for product operation.
- Credentials remain environment-only. Do not persist API keys, raw provider responses/errors, unbounded stderr, or question/answer bodies in normalized package results, cache identities, logs, or exports.
- Judge HTTP requests, Pi execution, and benchmark runs require separate operator authorization. Unit tests must mock transports and native execution.
- The generic `asterion` command stays DCI-neutral. `asterion-dci` owns evaluation and benchmark arguments.
- Cache reuse requires exact request fingerprint equality, a boolean verdict, and matching public judge configuration. Changed question, gold answer, prediction, model, endpoint, API shape, strict-schema mode, thinking mode, token limit, or pricing/configuration must not reuse a result.
- Preserve `eval_result.json` and state summary field names where they are safe; use safe public failures (`DCI evaluation failed` or `DCI benchmark failed`) rather than provider detail.
- Use TDD for every task. Run focused tests before/after each implementation and commit each passing deliverable.

---

## File structure

| File | Responsibility |
|---|---|
| `packages/python/asterion-core/src/asterion/dci/judge.py` | Validated judge configuration, safe public configuration, request construction, fingerprinting, response parsing, HTTP transport, usage and cost normalization. |
| `packages/python/asterion-core/src/asterion/dci/evaluation.py` | Run-directory evaluator, exact cache reuse, `eval_result.json` persistence, and safe state summary update. |
| `packages/python/asterion-core/src/asterion/dci/benchmark.py` | Explicit JSONL dataset loading, deterministic per-row output directories, Asterion-run reuse, evaluator invocation, and aggregate export. |
| `packages/python/asterion-core/src/asterion/dci/cli.py` | Product-local `evaluate` and `benchmark` parsers and content-free terminal summaries. |
| `tests/test_asterion_dci_judge.py` | Mocked judge request/configuration/fingerprint/response and redaction contracts. |
| `tests/test_asterion_dci_evaluation.py` | Cache identity, persistence, and safe failure contracts with mocked judge transport. |
| `tests/test_asterion_dci_benchmark.py` | Dataset, deterministic output, reused native execution, aggregate export, and no-network batch contracts. |
| `tests/test_asterion_dci_cli.py` | Product-local evaluate/benchmark mapping, safe failure, and generic-CLI neutrality. |
| `README.md` and `docs/architecture/capability-execution.md` | Operator behavior, authorization, protected data, cache, and batch boundaries. |

## Task 1: Transplant the safe judge contract

**Files:**
- Create: `packages/python/asterion-core/src/asterion/dci/judge.py`
- Create: `tests/test_asterion_dci_judge.py`

**Interfaces:**
- Produces `JudgeConfig`, `build_judge_request`, `judge_request_fingerprint`, and `judge_answer_sync`.
- `JudgeConfig.public_dict() -> dict[str, object]` excludes `api_key`; `judge_answer_sync` returns only public configuration, fingerprint, validated verdict, normalized usage, and cost estimate.

- [ ] **Step 1: Write failing configuration and cache-identity tests**

```python
def test_fingerprint_changes_with_every_request_shaping_field(self) -> None:
    config = JudgeConfig(api="responses", model="fixture", api_key="secret")
    baseline = judge_request_fingerprint(
        config=config, question="q", gold_answer="g", predicted_answer="p"
    )
    changed = judge_request_fingerprint(
        config=replace(config, strict_json_schema=True),
        question="q", gold_answer="g", predicted_answer="p",
    )
    self.assertNotEqual(baseline, changed)
    self.assertNotIn("secret", repr(config.public_dict()))
```

- [ ] **Step 2: Run the focused RED test**

Run: `uv run python -m unittest -v tests.test_asterion_dci_judge`

Expected: FAIL because `asterion.dci.judge` does not exist.

- [ ] **Step 3: Implement validated configuration and request construction**

```python
@dataclass(frozen=True)
class JudgeConfig:
    base_url: str = DEFAULT_JUDGE_BASE_URL
    api: str = "responses"
    model: str = DEFAULT_JUDGE_MODEL
    timeout_seconds: int = 120
    max_output_tokens: int = 1024
    strict_json_schema: bool = False
    responses_store: bool = False
    thinking: str = "auto"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = field(default="", repr=False)

    def public_dict(self) -> dict[str, object]: ...

def build_judge_request(
    config: JudgeConfig, *, question: str, gold_answer: str, predicted_answer: str
) -> dict[str, object]: ...

def judge_request_fingerprint(...) -> str: ...
```

Validate absolute HTTP(S) origins without credentials/query/fragment, normalize only `responses` and `chat-completions`, preserve strict schema and `store=False` behavior for the official Responses endpoint, and hash canonical public configuration plus endpoint and complete shaped request.

- [ ] **Step 4: Add mocked transport/response tests and implement the transport**

```python
with patch("asterion.dci.judge._open_judge_request", return_value=response):
    result = judge_answer_sync(config=config, question="q", gold_answer="g", predicted_answer="p")
self.assertTrue(result["is_correct"])
self.assertNotIn("secret", repr(result))
```

Make at most two parse attempts, reject redirects, normalize usage/cost, and map HTTP/URL/parse failures to bounded public `DciJudgeError` messages without response bodies.

- [ ] **Step 5: Run GREEN verification and commit**

Run: `uv run python -m unittest -v tests.test_asterion_dci_judge && uv run ruff check packages/python/asterion-core/src/asterion/dci/judge.py tests/test_asterion_dci_judge.py`

Expected: PASS; mocked tests make no HTTP request.

```bash
git add packages/python/asterion-core/src/asterion/dci/judge.py tests/test_asterion_dci_judge.py
git commit -m "feat: add Asterion DCI judge contract"
```

## Task 2: Add cache-safe run-directory evaluation

**Files:**
- Create: `packages/python/asterion-core/src/asterion/dci/evaluation.py`
- Create: `tests/test_asterion_dci_evaluation.py`

**Interfaces:**
- Consumes `JudgeConfig` and `judge_answer_sync` from `asterion.dci.judge`.
- Produces `evaluate_run_directory(output_dir: Path, *, gold_answer: str, predicted_answer: str | None, judge_config: JudgeConfig) -> dict[str, object]`.
- Reads native `state.json` question and `final.txt` when prediction is omitted; writes `eval_result.json` and a safe `state["evaluation"]` summary.

- [ ] **Step 1: Write failing cache and persistence tests**

```python
def test_reuses_only_an_exact_judge_request_fingerprint(self) -> None:
    write_native_run(run_dir, question="q", final_text="prediction")
    with patch("asterion.dci.evaluation.judge_answer_sync") as judge:
        first = evaluate_run_directory(run_dir, gold_answer="gold", judge_config=config)
        second = evaluate_run_directory(run_dir, gold_answer="gold", judge_config=config)
    self.assertEqual(judge.call_count, 1)
    self.assertEqual(first["judge_request_fingerprint"], second["judge_request_fingerprint"])
```

- [ ] **Step 2: Run the focused RED test**

Run: `uv run python -m unittest -v tests.test_asterion_dci_evaluation`

Expected: FAIL because the evaluator does not exist.

- [ ] **Step 3: Implement exact reuse and artifact persistence**

```python
def evaluate_run_directory(
    output_dir: Path,
    *,
    gold_answer: str,
    predicted_answer: str | None = None,
    judge_config: JudgeConfig,
) -> dict[str, object]:
    state = _load_completed_native_state(output_dir)
    prediction = predicted_answer if predicted_answer is not None else _read_final(output_dir)
    fingerprint = judge_request_fingerprint(...)
    reusable = _load_reusable_result(output_dir / "eval_result.json", fingerprint)
    if reusable is not None:
        _persist_state_summary(output_dir, reusable)
        return reusable
    result = judge_answer_sync(...)
    _write_json(output_dir / "eval_result.json", result)
    _persist_state_summary(output_dir, result)
    return result
```

Require a completed native state and nonempty gold answer; use the exact fingerprint generated before calling the transport. The state summary may contain public judge metadata, verdict, normalized prediction, reason, timestamp, and cost estimate, but never a key, raw response, request body, or stderr.

- [ ] **Step 4: Add invalidation and safe-failure tests**

Test changed gold answer/configuration and malformed/failed native state; assert the judge is called again only for a changed valid request, and that public `DciEvaluationError` output does not echo native answer or provider detail.

- [ ] **Step 5: Run GREEN verification and commit**

Run: `uv run python -m unittest -v tests.test_asterion_dci_judge tests.test_asterion_dci_evaluation && uv run ruff check packages/python/asterion-core/src/asterion/dci/evaluation.py tests/test_asterion_dci_evaluation.py`

Expected: PASS; no test invokes Pi or a judge service.

```bash
git add packages/python/asterion-core/src/asterion/dci/evaluation.py tests/test_asterion_dci_evaluation.py
git commit -m "feat: add cache-safe Asterion DCI evaluation"
```

## Task 3: Add deterministic Asterion DCI batch orchestration

**Files:**
- Create: `packages/python/asterion-core/src/asterion/dci/benchmark.py`
- Create: `tests/test_asterion_dci_benchmark.py`

**Interfaces:**
- Consumes `DciRunRequest`, `run_pi_research`, `evaluate_run_directory`, and `JudgeConfig`.
- Produces `BenchmarkRequest`, `BenchmarkResult`, and `run_benchmark(request: BenchmarkRequest, *, paths: DciPaths) -> BenchmarkResult`.
- Dataset rows require `query_id`, `query`, and `answer`; result directories are `output_root / query_id` after rejecting empty, duplicate, absolute, or traversal IDs.

- [ ] **Step 1: Write failing deterministic batch tests**

```python
def test_batch_reuses_the_native_asterion_run_and_writes_aggregate(self) -> None:
    dataset.write_text('{"query_id":"q-1","query":"question","answer":"gold"}\n')
    with patch("asterion.dci.benchmark.run_pi_research", return_value=fixture_run(run_dir)) as run:
        with patch("asterion.dci.benchmark.evaluate_run_directory", return_value={"is_correct": True}):
            result = run_benchmark(request, paths=fixture_paths)
    self.assertEqual(run.call_count, 1)
    self.assertTrue((result.output_root / "summary.json").is_file())
```

- [ ] **Step 2: Run the focused RED test**

Run: `uv run python -m unittest -v tests.test_asterion_dci_benchmark`

Expected: FAIL because no batch module exists.

- [ ] **Step 3: Implement dataset validation, reuse, and aggregate export**

```python
@dataclass(frozen=True)
class BenchmarkRequest:
    dataset: Path
    output_root: Path
    cwd: Path
    run_template: DciRunRequest
    judge_config: JudgeConfig

def run_benchmark(request: BenchmarkRequest, *, paths: DciPaths) -> BenchmarkResult: ...
```

Sort valid rows by `query_id`, preserve an existing successful exact evaluation without rerunning Pi, reuse only Asterion native run directories, and write one content-bearing per-query `result.json` plus `summary.json` aggregate under the explicit output root. Keep normalized `BenchmarkResult` body-free: counts, output URI, and public cost/accuracy aggregates only.

- [ ] **Step 4: Add failure and resume tests**

Test duplicate/traversal IDs fail before execution, an existing successful exact result skips both mocks, a changed judge configuration re-evaluates but does not rerun Pi, and a failed native run is resumed only through the existing Asterion resume request path.

- [ ] **Step 5: Run GREEN verification and commit**

Run: `uv run python -m unittest -v tests.test_asterion_dci_benchmark tests.test_asterion_dci_evaluation tests.test_asterion_dci_run && uv run ruff check packages/python/asterion-core/src/asterion/dci/benchmark.py tests/test_asterion_dci_benchmark.py`

Expected: PASS; all batch execution and judge calls are mocks.

```bash
git add packages/python/asterion-core/src/asterion/dci/benchmark.py tests/test_asterion_dci_benchmark.py
git commit -m "feat: add Asterion DCI benchmark orchestration"
```

## Task 4: Expose product-local operator commands and close AF-200

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/cli.py`
- Modify: `tests/test_asterion_dci_cli.py`
- Modify: `tests/test_asterion_dci_bridge.py`
- Modify: `README.md`
- Modify: `docs/architecture/capability-execution.md`
- Modify: `tests/test_distribution_boundaries.py`
- Modify: `docs/status/WORKLIST.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**
- `asterion-dci evaluate --output-dir RUN_DIR --gold-answer TEXT [--answer TEXT]` loads only native state and prints output directory, verdict, and `eval_result.json` URI.
- `asterion-dci benchmark --dataset FILE --output-root DIR --cwd DIR` maps explicit run/judge options into `BenchmarkRequest` and prints only public aggregate references/counts.
- `project_dci_run` adds an `evaluation_artifact_uri` only when a validated `eval_result.json` exists; it never projects evaluation bodies or secrets.

- [ ] **Step 1: Write failing CLI, projection, and documentation tests**

```python
def test_evaluate_is_product_local_and_redacts_failure(self) -> None:
    with patch("asterion.dci.cli.evaluate_run_directory", side_effect=DciEvaluationError("secret")):
        self.assertEqual(main(["evaluate", "--output-dir", "run", "--gold-answer", "gold"]), 2)
    self.assertNotIn("secret", stderr.getvalue())

def test_projection_adds_only_an_evaluation_artifact_reference(self) -> None:
    value = dict(project_dci_run(fixture_result(run_dir)).artifacts[0]["value"])
    self.assertEqual(value["evaluation_artifact_uri"], "eval_result.json")
```

- [ ] **Step 2: Run the focused RED test**

Run: `uv run python -m unittest -v tests.test_asterion_dci_cli tests.test_asterion_dci_bridge tests.test_distribution_boundaries`

Expected: FAIL because package-local evaluation/benchmark operators and evaluation artifact projection are absent.

- [ ] **Step 3: Implement parsers, mapping, safe output, and conditional projection**

Reject generic-CLI changes, malformed options, missing judge configuration, and invalid directories before creating a transport. Map all detailed judge/batch exceptions to `DCI evaluation failed` or `DCI benchmark failed`; terminal output must never include question, answer, provider response, or credential data. The bridge requires a valid completed result and an existing valid evaluation artifact before naming its URI.

- [ ] **Step 4: Document authorization and artifact boundaries**

Document the explicit judge authorization requirement, package-local evaluate/benchmark commands, exact cache invalidation, batch input contract, protected native bodies, and AF-210 deferral. Keep actual Pi/judge/Claude UAT out of this package.

- [ ] **Step 5: Run AF-200 closure verification**

Run:

```bash
uv run python -m unittest -v tests.test_asterion_dci_judge tests.test_asterion_dci_evaluation tests.test_asterion_dci_benchmark tests.test_asterion_dci_cli tests.test_asterion_dci_bridge tests.test_distribution_boundaries
uv run python -m unittest discover -v
uv run python -m compileall -q packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_judge.py tests/test_asterion_dci_evaluation.py tests/test_asterion_dci_benchmark.py tests/test_asterion_dci_cli.py tests/test_asterion_dci_bridge.py
uv run ruff check packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_judge.py tests/test_asterion_dci_evaluation.py tests/test_asterion_dci_benchmark.py tests/test_asterion_dci_cli.py tests/test_asterion_dci_bridge.py
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
bash -n scripts/examples/*.sh scripts/bcplus_eval/*.sh scripts/bright/*.sh
uv run asterion-dci evaluate --help
uv run asterion-dci benchmark --help
python3 tools/project_scope_check.py
git diff --check
```

Expected: PASS without Pi, judge, or Claude provider requests.

- [ ] **Step 6: Update durable status and commit**

After all four AF-200 Climb hypotheses are confirmed, mark AF-200 complete, activate AF-210, journal exact closure evidence, update durable state, and checkpoint recovery.

```bash
git add packages/python/asterion-core/src/asterion/dci tests/test_asterion_dci_*.py README.md docs/architecture/capability-execution.md tests/test_distribution_boundaries.py docs/status
git commit -m "docs: close AF-200 evaluation benchmark parity"
```

## Plan self-review

- Coverage: Tasks 1–4 cover original judge/request/response behavior, complete cache identity, run-directory persistence, deterministic dataset orchestration, exports, product-local command surfaces, bridge references, documentation, and AF-200 closure.
- Boundary: every execution path depends on Asterion-owned modules and explicit inputs; no task imports or invokes `src/dci`, uses generic CLI parsing, or authorizes a real Pi/judge/Claude request.
- Type consistency: `JudgeConfig` feeds evaluator and benchmark; `BenchmarkRequest` owns the run template/judge configuration; CLI maps only to those public types; bridge continues to expose references rather than bodies.
- Placeholder scan: no deferred implementation wording appears in task instructions; AF-210 is deliberately an out-of-scope follow-on rather than an unfinished AF-200 step.
