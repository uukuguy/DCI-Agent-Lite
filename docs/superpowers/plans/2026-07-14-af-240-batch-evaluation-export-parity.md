# AF-240 Complete Batch, Evaluation, and Export Parity Plan

> **Required execution method:** Use subagent-driven development task by task, with TDD and an independent specification review after every task. Do not start a later task while the prior review has blocking findings.

**Goal:** Transplant the remaining source DCI concurrent BCPlus/QA/BRIGHT batch, Judge, IR metric, aggregate analysis, corpus export, and launcher behavior into independently owned Asterion DCI code.

**Architecture:** Extend the existing Asterion-native run, recorder, evaluator, and Judge boundaries; never import or launch `src/dci`. One in-process bounded batch coordinator owns deterministic row selection and aggregate publication while each query continues to use the private native run directory and single-writer recorder. Dataset adapters, metrics, analysis, and exporters are pure or separately bounded modules. All output paths preserve no-follow semantics, aggregate files publish atomically, credentials never enter configuration/results, and reusable Judge results require the complete request fingerprint.

**Tech stack:** Python 3.10+, asyncio, existing Asterion DCI modules, matplotlib/pyarrow/tqdm for the same installed export/report surface as the source product, unittest, Ruff, Bash launchers.

**Work package:** AF-240 only. AF-250 owns the final cross-product acceptance matrix and any full-parity conclusion.

## Non-negotiable boundaries

- Pi remains the default runtime. Batch code calls `run_pi_research()` and `evaluate_run_directory()` directly; it never shells into `src/dci` or an Asterion CLI.
- `src/dci` and existing source launchers remain an unchanged comparison baseline.
- The repository-root `.env` and normal `DCI_*` names remain shared configuration. No credential value is written to batch configuration, query results, summaries, logs, or reports.
- Dataset, corpus, prompt, and export-source paths are canonicalized as input resources. Output roots and per-query destinations remain lexical absolute paths and reject every symlink component before mutation.
- Each query persists its input/configuration and terminal result before it can appear in aggregate files. Aggregate JSON/JSONL/Markdown/figure publication is atomic and deterministic by dataset order.
- `--max-concurrency` bounds both Pi trajectories and Judge work. A query failure is represented as a safe per-query result and does not corrupt successful siblings.
- Existing completed runs and exact Judge-cache hits are reusable. Failed/incomplete compatible runs use the AF-230 resume boundary; incompatible or malformed evidence fails closed.
- Full external datasets are never started automatically. Provider-backed closure is bounded to the separately authorized small sample.

## Task 0: Freeze AF-240 behavior inventory and executable hypotheses

**Files:**
- Create: `assets/dci/batch-parity.json`
- Modify: `docs/status/climb/hypotheses.yaml`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/eval-local.sh`
- Modify: `tests/test_climb_tools.py`
- Modify: `docs/status/JOURNAL.md`

**Interfaces:**
- The inventory maps source functions, CLI flags, launcher profiles, durable files, cache rules, metrics, analysis artifacts, the BCPlus QA extractor, and both corpus exporters to an Asterion owner and verification command.
- Register AF-240-H-001 through H-004: dataset/prompt/IR parity; concurrent durable batch/reuse; evaluation/aggregate/analysis parity; export/launcher/installed-boundary parity.

**Steps:**
1. Add RED schema/inventory and Climb adapter tests that reject missing mappings and placeholder/unsupported rows.
2. Populate the inventory from `scripts/bcplus_eval/run_bcplus_eval.py`, `scripts/bcplus_eval/extract_bcplus_qa.py`, `scripts/{bcplus_eval,qa,bright}`, and both `src/dci/benchmark/export_*` modules. Enumerate every source flag and durable output rather than using an “all controls” placeholder.
3. Add literal AF-240 train/eval cases whose evidence is tied to focused test names, not unconditional exit-zero stubs.
4. Run `tests.test_climb_tools`, scope, JSON parsing, and diff checks. Commit inventory/adapter changes and journal the verified mapping.

## Task 1: Add strict dataset adapters, prompts, and IR metrics

**Files:**
- Create: `packages/python/asterion-core/src/asterion/dci/datasets.py`
- Create: `packages/python/asterion-core/src/asterion/dci/metrics.py`
- Create: `tests/test_asterion_dci_datasets.py`
- Create: `tests/test_asterion_dci_metrics.py`
- Modify: `assets/dci/batch-parity.json`

**Interfaces:**
- `load_benchmark_rows(path) -> tuple[BenchmarkRow, ...]` preserves dataset order and the source QA/BCPlus/BRIGHT fields while enforcing unique safe query IDs and exact field types.
- `build_qa_prompt(...)` and `build_ir_prompt(...)` reproduce source semantics without embedding credentials or escaping the selected corpus.
- `parse_retrieved_documents(...)`, `normalize_retrieved_path(...)`, and `ndcg_at_k(...)` reproduce BRIGHT ranking semantics, including query-document exclusion and `gold_docs`/`gold_ids` aliases.

**Steps:**
1. Write table-driven RED tests from representative BCPlus, six QA, and four BRIGHT rows, including blank lines, duplicates, traversal IDs, invalid UTF-8/JSON/types, absent optional fields, and stable order.
2. Add exact prompt snapshots and adversarial retrieval parsing/NDCG tests for Windows/POSIX paths, escaped newlines, duplicates, query self-document, empty gold, and k boundaries.
3. Implement immutable row types and pure prompt/metric functions with no provider or filesystem writes.
4. Run both new test modules, compile, Ruff, scope, and diff. Commit and journal.

## Task 2: Complete Judge retry, cache, and safe evaluation semantics

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/judge.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/evaluation.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/artifacts.py`
- Modify: `tests/test_asterion_dci_judge.py`
- Modify: `tests/test_asterion_dci_evaluation.py`
- Modify: `assets/dci/batch-parity.json`

**Interfaces:**
- One Judge layer owns a total budget of at most three HTTP requests. Retryable invalid responses, network failures, 408/409/429/5xx, bounded `Retry-After`, and cancellation are distinguished from terminal configuration/other 4xx failures.
- A reusable result must match the complete request fingerprint and validated public Judge configuration; failures remain retryable and do not masquerade as verdicts.
- Evaluation acquires the same AF-230 run-directory writer authority used by the recorder. All evidence is validated and read/written descriptor-relative with no-follow semantics; the lock remains held across Judge cache reload, `eval_result.json`, and state publication.

**Steps:**
1. Add RED tests for transient invalid response retry, retryable/terminal HTTP classes, bounded/invalid `Retry-After`, cancellation, exact HTTP-call count never exceeding three, Responses/Chat shaping, pricing/usage, redirect rejection, and every request-shaping fingerprint field. Remove nested retry ownership rather than multiplying wrapper and transport attempts.
2. Add concurrent same-run evaluation tests proving the second evaluator waits, reloads under the shared lock, and reuses one Judge result; test atomic publication and fail-closed malformed/missing/symlink evidence.
3. Expose the minimal shared recorder lock/descriptor API, implement the single-budget async Judge path and locked atomic evaluation update, and define how cancellation closes blocking HTTP work before releasing the lock. Preserve the public body-free error boundary.
4. Run Judge/evaluation plus AF-230 recorder/resume regressions, Ruff/compile/scope/diff. Commit and journal.

## Task 3: Replace the minimal benchmark loop with a bounded durable coordinator

**Files:**
- Rewrite: `packages/python/asterion-core/src/asterion/dci/benchmark.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/run.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/pi_rpc.py`
- Create: `tests/test_asterion_dci_batch.py`
- Modify: `tests/test_asterion_dci_benchmark.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/cli.py`
- Modify: `assets/dci/batch-parity.json`

**Interfaces:**
- `BenchmarkRequest` gains mode/profile, corpus, max concurrency, max turns, prompt/context/thinking/conversation/session controls, resume policy, IR options, and analysis/figure controls while reusing `DciRuntimeOptions`.
- `run_benchmark_async(...)` schedules at most N query workers, uses native run/evaluate functions directly, and atomically persists `config.json`, per-query `item.json`/`input_question.txt`/`result.json`, `results.jsonl`, and `summary.json`.
- Re-entry deterministically classifies each query as reuse, judge-only, compatible resume, fresh run, or safe failed record. Duplicate batch writers are rejected.
- Schema-versioned batch and row fingerprints bind the allowlisted dataset identity, query/gold or gold documents, mode, exact prompt and corpus hint, canonical corpus identity, runtime/session/conversation controls, prompt-resource digests, raw-extra-argument fingerprint (never raw values), and Judge request fingerprint. A row change under the same ID fails before mutation/Pi/Judge.
- Query identities use one portable collision key that rejects Unicode normalization/casefold collisions, natural numeric-suffix collisions, Windows-reserved names, and aggregate-reserved names.
- Cancellation is cooperative end-to-end: a worker cancellation reaches `run_pi_research`, aborts/stops Pi, writes exactly one cancelled/failed terminal attempt, waits for blocking Judge work to close, and retains worker/batch locks until no child/provider work remains.

**Steps:**
1. Add RED concurrency tests with controlled futures proving the cap in terms of live provider calls, dataset-order aggregates despite out-of-order completion, incremental persistence, sibling failure containment, SIGINT/task cancellation with zero orphan Pi/Judge work, and no subprocess/`src.dci` dependency.
2. Add re-entry tests covering every fingerprint field, changed row under the same ID, allowlisted persistence/no raw extra args, exact result reuse, stale Judge fingerprint, completed-run judge-only, failed compatible reconstruction with re-supplied raw args, IR rows requiring gold documents but no answer/Judge, QA rows requiring answers, malformed evidence, portable query collisions, output symlink components, and concurrent batch writers.
3. Implement a private batch-root lock, safe lexical destinations, portable collision validation, schema-versioned identities, atomic descriptor-relative aggregate writes, in-process worker orchestration, and the cooperative cancellation/stop bridge in `run.py`/`pi_rpc.py`.
4. Keep the synchronous `run_benchmark()` compatibility wrapper. Run batch/benchmark/run/evaluation/artifact tests and static gates. Commit and journal.

## Task 4: Reproduce query metrics, summaries, detailed analysis, and figures

**Files:**
- Create: `packages/python/asterion-core/src/asterion/dci/analysis.py`
- Create: `tests/test_asterion_dci_analysis.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/benchmark.py`
- Modify: `packages/python/asterion-core/pyproject.toml`
- Modify: `assets/dci/batch-parity.json`

**Interfaces:**
- Query metrics derive wall/tool/non-tool time, turns/events/requests, per-tool counts/errors/durations, agent/Judge tokens and costs, correctness or NDCG, runtime context, and bounded diagnostic tails from native artifacts.
- Aggregate output reproduces counts, accuracy, NDCG@10, totals, averages, timing reconstruction, percentiles, outcome slices, and per-tool analysis.
- `analysis.json`, `analysis.md`, enriched `analysis.jsonl`, and four reproducible PNG reports use stable ordering and headless rendering. Figure generation can be explicitly disabled but never silently omitted when requested.

**Steps:**
1. Build golden RED fixtures from source-shaped native states/results for metric extraction, aggregation, percentile interpolation, rerun timing preservation, and IR/non-IR summaries.
2. Add deterministic Markdown/JSONL snapshots and render every fixture figure twice, comparing decoded pixel arrays and dimensions (not volatile PNG metadata). Test missing metrics and failed runs without divide-by-zero or fabricated values.
3. Implement pure analysis functions and isolated rendering imports. Add installed Asterion dependencies required for the promised full batch/report surface.
4. Run analysis/batch/wheel dependency tests and static gates. Commit and journal.

## Task 5: Add safe BCPlus QA extraction and BCPlus/BRIGHT corpus exporters

**Files:**
- Create: `packages/python/asterion-core/src/asterion/dci/export.py`
- Create: `tests/test_asterion_dci_export.py`
- Modify: `packages/python/asterion-core/src/asterion/dci/cli.py`
- Modify: `packages/python/asterion-core/pyproject.toml`
- Modify: `assets/dci/batch-parity.json`

**Interfaces:**
- `asterion-dci export bcplus` preserves title/domain naming, stem limits, deterministic duplicate/docid suffixes, and idempotent identical-content reuse.
- `asterion-dci export bright` preserves safe relative IDs, selected/all subsets, content identity, and per-subset completion markers.
- `asterion-dci export bcplus-qa` preserves sorted shard order, case-insensitive column aliases, the built-in canary-derived XOR/base64 decryption, `--no-decrypt`, row order, and atomic JSONL publication while streaming parquet row groups without pandas concatenation.
- Export sources are validated parquet inputs. Source/output overlap is rejected; destinations use an exclusive writer lock, portable Unicode/casefold/natural-suffix/Windows-reserved collision keys, descriptor-relative no-follow private atomic writes, and terminal completion markers only after success. Unsafe IDs/ciphertext, decode/schema failures, missing shards, races, and collisions fail without lying markers.

**Steps:**
1. Add RED unit tests for QA column aliases/decryption/`--no-decrypt`/shard and row order/invalid base64 or UTF-8, naming/path functions, and tiny generated parquet fixtures covering row groups, duplicates, Unicode/casefold/natural suffix/Windows names, invalid schemas/IDs, traversal, symlinks, source-output overlap, simultaneous exporters, interrupted rerun, idempotency, and marker timing.
2. Implement streaming pyarrow row-group extraction/export with bounded memory, exclusive destination locks, collision ledgers, and descriptor-relative safe atomic writes. Do not import `src.dci`.
3. Add CLI parsing/body-free errors and installed-wheel import/resource tests.
4. Run exporter/CLI/wheel/static tests. Commit and journal.

## Task 6: Ship installed package-local batch profiles and one-to-one Asterion launchers

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/dci/cli.py`
- Create: `packages/python/asterion-core/src/asterion/dci/resources/batch-profiles.json`
- Create: `scripts/asterion/bcplus_eval/run_L3.sh`
- Create: `scripts/asterion/bcplus_eval/run_bcplus_eval_openai.sh`
- Create: six `scripts/asterion/qa/run_*.sh` launchers
- Create: four `scripts/asterion/bright/run_*.sh` launchers
- Modify: `README.md`
- Modify: `assets/docs/artifacts.md`
- Modify: `assets/docs/setup.md`
- Create: `tests/test_asterion_dci_batch_launchers.py`
- Modify: `tests/test_asterion_dci_cli.py`
- Modify: `assets/dci/batch-parity.json`

**Interfaces:**
- The package CLI explicitly exposes dataset, output root, corpus, provider/model/tools, max turns/concurrency/limit, context, both prompt resources, repeatable Pi extras, thinking, IR/corpus hint, all public Judge overrides, Node heap, reuse/resume, and analysis/figure controls with shared `.env` defaults and body-free validation.
- The importlib-loaded wheel resource defines exact BCPlus, QA, and BRIGHT dataset/corpus/output/runtime mappings and remains available when the repository is absent. Launchers are thin literal-argv wrappers over `asterion-dci benchmark`, accept an explicit `--limit` override, and preserve `run_bcplus_eval_openai.sh` positional context-level plus optional thinking behavior.
- Every Asterion launcher has exactly one source counterpart but never launches or imports it.

**Steps:**
1. Add RED parser/help/mapping tests for every enumerated batch flag and profile, dynamic level/thinking mapping, runner-only rejection, secrets, invalid concurrency/limit, resources, output symlinks, and exact CLI-to-request conversion.
2. Add shell contract tests asserting one-to-one names, shared `.env`, Pi-default Asterion command, literal quoting, corpus/dataset preflight, and no `src/dci`/source-script execution. Build/install a wheel in an isolated directory with the repository unavailable and load every profile through `importlib.resources`.
3. Implement profile selection/override rules and all launchers. Document full vs bounded operation, outputs, reuse/resume, IR/Judge modes, exports, and deliberate full-dataset commands.
4. Run CLI/launcher tests, `bash -n`, help, isolated wheel, no-baseline-import, scope, and diff. Commit and journal.

## Task 7: Run Climb evidence, bounded acceptance, and close AF-240

**Files:**
- Modify/regenerate: `docs/status/climb/{hypotheses.yaml,session-state.json,research-tree.md,research-tree.json,runs.csv}`
- Modify: `docs/status/{JOURNAL.md,WORKLIST.md,CURRENT-STATE.md,RESUME-NEXT-SESSION.md}`
- Modify: `assets/dci/batch-parity.json`

**Steps:**
1. Run full Python discovery, compile/Ruff, TypeScript, Rust, shell syntax, isolated-wheel/help/resource/import checks, scope, and diff.
2. Execute AF-240-H-001..H-004 through the Climb adapter and require 4/4 with regenerated research tree.
3. Run all BCPlus/QA/BRIGHT launchers in model-free `--help`/preflight or fixture mode. Do not start full datasets.
4. With the authorized shared `.env`, run at most one fresh one-row Asterion batch through real Pi plus Judge using the completed AF-240 coordinator. Verify per-query native evidence, exact Judge cache, incremental/final aggregates, analysis artifacts, privacy, and rerun reuse without a second provider/Judge request. Exercise BRIGHT IR and all other profiles with fixtures.
5. Close AF-240 only if the inventory has no missing/placeholder row and every behavior is executable. Activate AF-250, update durable state, rerun scope/diff, commit, and independently review closure evidence.

## Final verification commands

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q packages/python/asterion-core/src/asterion
uv run ruff check packages/python/asterion-core/src/asterion/dci tests
npm --prefix packages/typescript/asterion-runtime test
cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml
find scripts/asterion -name '*.sh' -print0 | xargs -0 -n1 bash -n
python3 tools/project_scope_check.py
git diff --check
```

## Plan self-review

- **Complete source surface:** BCPlus QA extraction/decryption, dataset/profile handling, QA and IR prompts, NDCG, Judge/retry/cache, bounded concurrency and cooperative cancellation, durable fingerprinted query/aggregate state, resume/reuse, metrics, summary, detailed analysis, reproducible figures, both corpus exporters, all source launcher counterparts including dynamic level/thinking, installed resources/dependencies, and bounded real acceptance are assigned exactly once.
- **Security:** credentials remain environment-only; input canonicalization and output no-follow semantics stay distinct; query/batch locks and atomic writes prevent multi-writer corruption; malformed cache/evidence never triggers unsafe reuse.
- **Cost:** no task launches a full dataset. Only Task 7 may use the already authorized one-row Pi-plus-Judge request.
- **Independence:** no production or launcher path imports, shells into, or edits `src/dci`; source files remain fixture/spec comparison inputs only.
