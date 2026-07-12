# Judge Structured-Output Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute inline with test-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit, credential-safe preflight that proves the configured judge returns the structured verdict used by evaluation.

**Architecture:** `scripts/check_judge.py` loads the normal `.env`, resolves one `JudgeConfig`, and delegates its single request to `judge_answer_sync`. It prints a safe projection of that result. `make check-judge`, docs, and the H-006 climb adapter expose and validate that exact path.

**Tech Stack:** Python 3.10+, `unittest`, `unittest.mock`, `uv`, Make, Bash.

## Global Constraints

- Reuse `JudgeConfig` and `judge_answer_sync`; do not add request shaping or another transport.
- Never print or persist API keys, raw judge prompts, or raw judge responses.
- Keep `check-judge` opt-in; no batch evaluator invokes it automatically.
- Leave the external `pi/` checkout untouched.

## File Map

- Create `scripts/check_judge.py` and `tests/test_check_judge.py`.
- Modify `Makefile`, `README.md`, `.env.template`.
- Modify `tools/climb/train.sh` and `tools/climb/eval-local.sh` for H-006.

---

### Task 1: Red/green preflight CLI

**Files:** Create `tests/test_check_judge.py`; create `scripts/check_judge.py`.

**Interfaces:** `run_preflight(config: JudgeConfig) -> dict[str, object]`; `main() -> int`.

- [ ] **Step 1: Write failing tests.**

```python
def test_preflight_uses_shared_transport(self) -> None:
    config = JudgeConfig(api="responses", api_key="test-key")
    with patch.object(check_judge, "judge_answer_sync", return_value={"is_correct": True}) as judge:
        payload = check_judge.run_preflight(config)
    judge.assert_called_once_with(config=config, question="What is 1 + 1?", gold_answer="2", predicted_answer="2")
    self.assertTrue(payload["is_correct"])

def test_preflight_rejects_missing_api_key_before_request(self) -> None:
    config = JudgeConfig(api_key_env="TEST_JUDGE_KEY", api_key="")
    with patch.object(check_judge, "judge_answer_sync") as judge:
        with self.assertRaisesRegex(ValueError, "TEST_JUDGE_KEY"):
            check_judge.run_preflight(config)
    judge.assert_not_called()

def test_main_outputs_only_safe_result_fields(self) -> None:
    config = JudgeConfig(api="chat-completions", api_key="secret-key")
    result = {**config.public_dict(), "is_correct": True, "usage": {}, "cost_estimate_usd": {}, "raw_response": {"secret": "no"}}
    with patch.object(check_judge, "load_project_env"), patch.object(check_judge.JudgeConfig, "from_env", return_value=config), patch.object(check_judge, "run_preflight", return_value=result), redirect_stdout(io.StringIO()) as stdout:
        self.assertEqual(check_judge.main(), 0)
    payload = json.loads(stdout.getvalue())
    self.assertTrue(payload["ok"])
    self.assertNotIn("api_key", payload)
    self.assertNotIn("raw_response", payload)
```

- [ ] **Step 2: Verify RED.** Run `uv run python -m unittest tests.test_check_judge -v`; it must fail because the preflight module is absent.

- [ ] **Step 3: Implement the minimal behavior.**

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_QUESTION = "What is 1 + 1?"
PREFLIGHT_ANSWER = "2"

def run_preflight(config: JudgeConfig) -> dict[str, object]:
    if not config.api_key:
        raise ValueError(f"Judge API key is missing; set {config.api_key_env}.")
    result = judge_answer_sync(config=config, question=PREFLIGHT_QUESTION, gold_answer=PREFLIGHT_ANSWER, predicted_answer=PREFLIGHT_ANSWER)
    if not isinstance(result.get("is_correct"), bool):
        raise ValueError('Judge preflight result field "is_correct" was not a boolean')
    return result
```

`main()` loads `.env`, resolves one config, returns `1` on `RuntimeError` or `ValueError`, and prints only `ok`, `config.public_dict()`, `is_correct`, `usage`, and `cost_estimate_usd`.

- [ ] **Step 4: Verify GREEN.** Run `uv run python -m unittest tests.test_check_judge -v`; all three behaviors pass.

- [ ] **Step 5: Commit.** Commit `scripts/check_judge.py` and `tests/test_check_judge.py` as `feat: add judge structured-output preflight`.

### Task 2: Add the target, documentation, and H-006 adapter

**Files:** Modify `Makefile`, `README.md`, `.env.template`, `tests/test_check_judge.py`, `tools/climb/train.sh`, and `tools/climb/eval-local.sh`.

- [ ] **Step 1: Add failing integration tests.**

```python
def test_make_target_runs_preflight(self) -> None:
    makefile = (REPO_ROOT / "Makefile").read_text()
    self.assertIn("check-judge:", makefile)
    self.assertIn("uv run python scripts/check_judge.py", makefile)

def test_h006_adapter_has_preflight_contract(self) -> None:
    self.assertIn("H-006", (REPO_ROOT / "tools/climb/eval-local.sh").read_text())
    train = (REPO_ROOT / "tools/climb/train.sh").read_text()
    self.assertIn("tests.test_check_judge", train)
    self.assertIn("make check-judge", train)
```

- [ ] **Step 2: Verify RED.** Run `uv run python -m unittest tests.test_check_judge -v`; target and adapter assertions fail.

- [ ] **Step 3: Implement integration.** Add this target and include `check-judge` in `.PHONY`:

```make
check-judge:
	uv run python scripts/check_judge.py
```

Document the command in `README.md` after judge configuration and in `.env.template` beside judge credentials. For H-006, `train.sh` runs the test module and `make check-judge`, declares `judge-contract-probe`, and `eval-local.sh` scores four named dimensions: shared transport, missing-key safety, safe output, and Make/adapter integration.

- [ ] **Step 4: Verify GREEN.** Run `uv run python -m unittest tests.test_check_judge -v` and confirm every preflight test passes.

- [ ] **Step 5: Commit.** Commit exposed command, docs, tests, and adapter as `feat: validate judge output before evaluation`.

### Task 3: Verify and record H-006

**Files:** Generated `docs/status/climb/*` state through the normal cycle only.

- [ ] **Step 1: Verify quality.** Run `uv run python -m unittest discover -v`, `uv run python -m compileall scripts/check_judge.py`, `uv run ruff check scripts/check_judge.py tests/test_check_judge.py`, `bash -n tools/climb/train.sh tools/climb/eval-local.sh`, `make check-pi-rpc`, and `git diff --check`.

- [ ] **Step 2: Produce live evidence.** Run `make check-judge` then `bash tools/climb/cycle.sh H-006`; expect safe JSON plus a regenerated `research-tree.md` with confirmed 4/4 and an advanced pool.

- [ ] **Step 3: Commit state.** Commit generated climb state, any applicable decision, the Journal entry, and the active checkpoint as `docs: record judge preflight climb evidence`.
