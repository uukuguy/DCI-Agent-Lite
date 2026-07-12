# Judge Request Fingerprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute inline with test-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make evaluation-result reuse safe across every effective judge request shape without exposing credentials or duplicating prompts.

**Architecture:** A canonical identity combines `JudgeConfig.public_dict()`, `JudgeConfig.endpoint`, and the request dict returned by `build_judge_request`. Canonical JSON serialization and SHA-256 produce one safe digest. Fresh judge results persist that digest, and reuse requires it plus a boolean verdict; a missing digest invalidates legacy artifacts once.

**Tech Stack:** Python 3.10+, standard-library `hashlib` and `json`, `unittest`, Bash climb adapters.

## Global Constraints

- Do not include API keys, key hashes, raw prompts, or provider response bodies in safe output or artifacts.
- Preserve current judge request shapes and environment precedence.
- Keep all H-010 artifacts under `runs/climb/` and tracked state under `docs/status/climb/`.
- Run focused unit tests before full verification; do not change defaults merely to satisfy the experiment.

---

### Task 1: Derive and persist a request fingerprint

**Files:**

- Modify: `src/dci/benchmark/judge.py`
- Test: `tests/test_judge.py`

**Interfaces:**

- Produces: `judge_request_fingerprint(*, config: JudgeConfig, question: str, gold_answer: str, predicted_answer: str) -> str`
- Consumes: `build_judge_request()` and `JudgeConfig.endpoint`

- [ ] **Step 1: Write failing unit tests**

```python
fingerprint = judge_request_fingerprint(
    config=config,
    question="Question",
    gold_answer="Gold",
    predicted_answer="Prediction",
)
self.assertEqual(len(fingerprint), 64)
self.assertEqual(fingerprint, repeated_fingerprint)
self.assertNotEqual(fingerprint, changed_endpoint_fingerprint)
```

Also mock one successful judge response and assert `judge_answer_sync()` returns the same `judge_request_fingerprint`.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run python -m unittest tests.test_judge -v`

Expected: FAIL because `judge_request_fingerprint` is not exported and successful results have no fingerprint field.

- [ ] **Step 3: Implement the minimal safe identity**

```python
canonical = json.dumps(
    {"endpoint": config.endpoint, "request": request_payload},
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
)
return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

Use the exact request payload already built by `judge_answer_sync()` when persisting its result.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `uv run python -m unittest tests.test_judge -v`

Expected: PASS, including deterministic fingerprints and safe persistence.

- [ ] **Step 5: Commit the implementation and test**

```bash
git add src/dci/benchmark/judge.py tests/test_judge.py
git commit -m "feat: fingerprint judge evaluation requests"
```

### Task 2: Replace manual reuse matching and advance H-010

**Files:**

- Modify: `src/dci/benchmark/pi_rpc_runner.py`
- Modify: `tests/test_judge.py`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`
- Modify: `tests/test_climb_tools.py`
- Modify: `docs/status/climb/hypotheses.yaml`
- Generated: `docs/status/climb/{research-tree.md,research-tree.json}`
- Append: `docs/status/JOURNAL.md`

**Interfaces:**

- Consumes: `judge_request_fingerprint()` from `dci.benchmark.judge`
- Produces: cache reuse only when `existing["judge_request_fingerprint"]` equals the freshly computed digest

- [ ] **Step 1: Write failing cache and adapter tests**

```python
existing = {"judge_request_fingerprint": fingerprint, "is_correct": True}
self.assertEqual(reuse_same_request, existing)
self.assertIsNone(reuse_changed_request)
self.assertIsNone(reuse_legacy_result)
```

Add an H-010 adapter-contract test that selects the new four test dimensions.

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `uv run python -m unittest tests.test_judge tests.test_climb_tools -v`

Expected: FAIL because reuse still reads the manual key list and H-010 is not selectable.

- [ ] **Step 3: Implement the minimal reuse and climb changes**

Replace the manual configuration/input comparisons with one fingerprint comparison; add H-010 to the hypothesis pool and adapter `case` statements. Keep legacy artifacts non-reusable.

- [ ] **Step 4: Run acceptance and full verification**

Run:

```bash
bash tools/climb/cycle.sh H-010
uv run python -m unittest discover -v
uv run python -m compileall -q src tests scripts tools/climb
uv run ruff check src/dci/benchmark/judge.py src/dci/benchmark/pi_rpc_runner.py tests/test_judge.py tests/test_climb_tools.py
bash -n tools/climb/train.sh tools/climb/eval-local.sh tools/climb/cycle.sh
git diff --check
```

Expected: H-010 records `confirmed 4/4`, generated research-tree state is synchronized, and all verification commands pass.

- [ ] **Step 5: Document durable state and commit**

Append the verified H-010 result to `JOURNAL.md`, update `DECISIONS.md` and `CURRENT-STATE.md` only for the durable cache-identity change, regenerate the research tree, then commit the cohesive cycle.
