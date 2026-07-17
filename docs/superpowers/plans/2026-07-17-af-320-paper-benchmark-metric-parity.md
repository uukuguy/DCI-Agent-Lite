# AF-320 Paper Benchmark and Metric Parity Implementation Plan

> **Execution:** Implement this plan task-by-task in the active session. Steps use
> checkbox (`- [ ]`) syntax for tracking; repository policy currently forbids
> unsolicited sub-agent dispatch.

> Status: approved after independent review. Execute only after AF-320
> governance is active. Use TDD for every production change. Full datasets are
> forbidden.

**Goal:** Reproduce the paper-described DCI capabilities and evidence paths while separating functional acceptance from literal experiment configuration.

**Architecture:** Keep paper experiment identities as provenance, but execute bounded acceptance with the configured production Judge. Persist and independently revalidate the effective Judge configuration and prompt/request-shaping identity without requiring a specific provider or model.

**Tech Stack:** Python 3.10+, `unittest`, Asterion DCI native artifacts, JSON body-free evidence, external Pi JSONL runtime.

## Global Constraints

- Active package is AF-320; run `python3 tools/project_scope_check.py` before implementation and closure.
- No full dataset, matrix expansion, score-reproduction claim, credential persistence, or modification of the user-owned external `pi/` checkout.
- Provider mode performs exactly two Pi agent operations and one configured Judge operation.
- Effective Judge provider/model/API/endpoint/request-shaping identity must be truthful, body-free, cache-safe, and artifact-bound.
- Paper-model and published-score comparability remain AF-340 scope.

---

## Goal

Ship all thirteen paper benchmark profiles, paper-exact parameterized trajectory
coverage/localization and retained-evidence analysis, and deterministic bounded
ablation matrices through the existing Asterion DCI product.

## Task 1 — Governance, inventory contract, and Climb pool

Create a schema-closed packaged inventory containing exactly the thirteen
canonical dataset IDs and their family/mode/metric/resource contracts, source
split/count, versioned QA exclusion policy, paper-declared GPT-4.1 Judge provenance, and closed
execution class. Add a separate schema-closed experiment-scope registry for
paper selection mode/count, seed provenance/algorithm, and selected-ID identity.
Never invent a paper seed: published DCI-Bench selections with an unreported
seed package and hash the exact selected-ID manifest and verify it against the
full source ID population. BrowseComp sampled analysis IDs are not published,
so bind explicitly labeled Asterion-defined reproduction seeds/algorithms and
never call those manifests paper-published. Encode
BrowseComp all-830 main results, trajectory/tool/corpus `n=100`, context-ablation
random `n=100`, and Appendix A.1 random-50 as distinct scopes; also encode full
BRIGHT/Bamboogle versus applicable random-50 selection, including the ArguAna
1,406 and SciFact 300 source counts. Add cross-checks against batch profiles,
launchers, documentation, and wheel resources. Keep paper-full Bamboogle 125
explicitly unbound from its existing sample-50 profile/launcher. Activate a fresh AF-320 Climb
session with four hypotheses:

1. dataset inventory and BEIR adapters;
2. coverage/localization/retained metric equivalence;
3. conservative observation alignment and evidence safety;
4. deterministic ablation/product closure.

RED tests reject missing/extra/duplicate datasets, aliases, unsupported metrics,
selection-scope or manifest collisions, fabricated/missing seed provenance,
missing BrowseComp scopes, unversioned
exclusions, executable `paper-full` rows, wrong corpus/gold fields, and an
unparented Climb hypothesis. GREEN adds
only the contract/resource/governance surface. Run focused tests, compile, Ruff,
scope with H001, and diff checks; commit and journal.

## Task 2 — ArguAna and SciFact adapters/profiles

First repair NDCG@10 to first-occurrence retrieval deduplication, standard binary
DCG/IDCG, and finite `[0,1]` output. RED proves the existing duplicate relevant
retrieval can exceed one. Then add strict source-row adapters for both BEIR
datasets into the existing `BenchmarkRow` IR shape, canonical profiles, corpus
preflight, bounded fixtures, source/project launch commands, download allowlist
metadata (without downloading), and corrected NDCG@10 routing.

RED covers malformed qrels, duplicate query/document IDs, multiple relevance
grades, missing corpus documents, path/symlink escape, wrong mode/metric, and
provider construction before preflight. GREEN reuses the existing IR batch with
the corrected metric. Verify source/profile/launcher/wheel parity and zero
provider operations, then close H001 and journal.

## Task 3 — Resolution metric primitives

Implement pure immutable types/functions for gold sets, surfaced sets,
`coverage_any`, `coverage_mean`, `coverage_all`, segment normalization,
localization candidate score, per-document maximum, query coverage aggregation,
and flattened surfaced-gold dataset localization aggregation.
Require explicit positive `segment_characters` and closed unavailable reasons.

RED uses hand-computed golden values for one/multiple gold documents, segment
boundaries, `b=1`, full-document fallback, duplicate candidates, no surfaced
gold, invalid lengths, NaN/infinity, and empty gold. Property tests keep scores
within `[0,1]`, prove smaller snippets never score worse for a fixed document,
and distinguish arithmetic per-query coverage from matched-gold micro
localization. Queries with no surfaced gold do not enter the localization
denominator; a zero denominator is unavailable. GREEN stays independent of
filesystem and product code.

## Task 4 — Native observation alignment

Add a descriptor-safe analyzer that consumes one completed native attempt,
externalized tool results, corpus snapshot, and gold manifest. Implement closed
grep/rg line, read span, path-only, unmatched text, and ambiguous pipeline
rules. Persist private `dci.trajectory-resolution/v1` evidence atomically with
SHA-256 identities for the exact protocol event stream, every consumed
externalized tool-result blob, final model-visible context artifact, gold
manifest, and every opened corpus/gold file.

RED covers traversal, symlinks, inode/path replacement, malformed protocol
streams, unknown tools, body truncation, duplicate aliases, false substring
matches, multiple gold documents in one observation, conservative fallback,
and public body/path leakage. GREEN never reads public projections as evidence.
Close H002/H003 only after mutation tests and body-free artifact checks.

## Task 5 — Retained coverage and batch analysis

Align the final model-visible context artifact against the same gold manifest
and compute retained coverage or a closed unavailable reason. Extend batch
analysis/summary/JSONL/Markdown/figures and export with deterministic coverage,
localization, retained evidence, tool count, latency, cost, and query-status
fields. Rehash every Task 4 input plus analysis configuration before reuse and
export; any byte or identity change invalidates reuse.

RED proves processed saved views cannot substitute for final model context;
changed segment width, alignment rules, attempt, corpus, gold, or context policy
invalidate reuse; missing evidence stays unavailable rather than zero. GREEN
preserves existing outputs and exact float serialization.

## Task 6 — Deterministic ablation matrices

Add a closed matrix schema that separately represents paper-declared
100K/200K/400K BrowseComp/FineWeb rows and bounded analogues. Paper rows bind
the appropriate trajectory/tool/corpus or context-ablation BrowseComp `n=100`
query scope with seed/algorithm and selected-ID digest, plus FineWeb source and
target count. Because the paper does not publish the FineWeb seed, algorithm,
selected IDs, or manifest digest, paper corpus rows must mark those fields
`paper-unreported` and null rather than inventing an identity. They retain the
non-executable `paper-full` class. Bounded rows cover context levels 0–4, two
tool profiles (`read,grep` and `read,bash`), and tiny base/+1/+2 corpus
manifests. The restricted profile must use Pi's dedicated grep tool rather than
command-string filtering inside bash. Rows must be sorted, unique,
cost-classified, fixture-bound, and non-executable by default. Add validate/list/
render commands. Bounded execution requires an explicit row ID and ordinary
benchmark authorization; `paper-full` execution is rejected unconditionally in
AF-320 before provider/Judge construction, with no generic override.

RED rejects Cartesian expansion at execution time, full-dataset paths,
unbounded distractor manifests, hidden provider defaults, unknown tools,
duplicate rows, and cache collisions. GREEN produces deterministic JSON and
documented shell commands without provider/Judge operations.

## Task 7 — Product, installed, and isolated-wheel parity

Expose the inventory, BEIR profiles, analysis configuration, matrix listing,
and safe metric artifacts through `asterion-dci` benchmark/export/verification.
Update the complete reference, validation guide, root README, `.env.template`,
and launcher inventory. The generic `asterion` application does not gain new
workflow composition in AF-320.

RED installs a wheel outside the repository and proves it cannot load a CWD
lookalike inventory/schema. GREEN verifies source and installed outputs share
the same packaged digests and contain no original `src/dci` dependency.

## Task 8 — Bounded provider evidence

Create a cost-visible verifier whose default mode is model-free. Provider mode
preflights private configuration, clean locked external runtime, packaged
resources, two tiny fixture cases, output root, and exact operation count before
starting a process. It runs exactly three external operations: one QA agent
case, its configured production Judge request, and one BEIR/IR agent case. It never
expands a matrix or full dataset, and retains a 0600 body-free report plus
private artifact digests.

Bind final evidence into the terminal Climb result with artifact rehashing,
clean-runtime identity, no-follow/private-file checks, idempotence, and
conflict-no-mutation tests. Failed attempts remain diagnostic.

### D-048 correction — configured Judge functional acceptance

**Files:**
- Modify: `asterion/src/asterion/dci/verification.py`
- Modify: `asterion/src/asterion/dci/artifacts.py`
- Modify: `tests/test_asterion_dci_verification.py`
- Modify: `tests/test_asterion_dci_artifacts.py`
- Modify: `README.md`
- Modify: `asterion/docs/guides/asterion-dci-complete-reference.md`
- Modify: `asterion/docs/verification/asterion-dci-validation-guide.md`
- Modify: `.env.template`

**Interfaces:**
- Consumes: `JudgeConfig.public_dict()`, `build_judge_request()`, private `eval_result.json`, and the fixed `qa-agent`, `qa-judge`, `ir-agent` operation sequence.
- Produces: `paper_judge_identity(config: JudgeConfig) -> tuple[tuple[str, object], ...]`; the report's `judge` object containing effective public configuration plus `prompt_contract_sha256`; binder validation against the private evaluation artifact.

- [x] **Step 1: Write RED verifier tests for configured DeepSeek**

```python
judge = JudgeConfig(
    base_url="https://api.deepseek.com/v1",
    api="chat-completions",
    model="deepseek-v4-flash",
    api_key_env="DEEPSEEK_API_KEY",
    api_key="private-fixture-key",
)
identity = dict(paper_judge_identity(judge))
self.assertEqual(identity["judge_model"], "deepseek-v4-flash")
self.assertEqual(identity["judge_api"], "chat-completions")
self.assertRegex(identity["prompt_contract_sha256"], r"^[0-9a-f]{64}$")
```

- [x] **Step 2: Run RED and confirm the obsolete literal-model gate**

Run: `uv run --project asterion python -m unittest -v tests.test_asterion_dci_verification.PaperBenchmarkVerifierTests`

Expected: FAIL because `paper_judge_identity` is absent and `_paper_default_readiness` still requires official `gpt-4.1/responses`.

- [x] **Step 3: Implement the minimal dynamic Judge identity**

```python
def paper_judge_identity(config: JudgeConfig) -> tuple[tuple[str, object], ...]:
    public = config.public_dict()
    template = build_judge_request(
        config,
        question="[question]",
        gold_answer="[gold-answer]",
        predicted_answer="[predicted-answer]",
    )
    public["prompt_contract_sha256"] = canonical_json_sha256(template)
    return tuple(sorted(public.items()))
```

Remove provider/model/base/API literal comparisons from preflight. Continue requiring a valid `JudgeConfig`, a non-empty configured Judge credential, private configuration, packaged fixtures, an empty private output root, and a clean locked Pi runtime.

- [x] **Step 4: Write RED binder tests for truthful identity and mutation rejection**

```python
report["judge"] = dict(paper_judge_identity(deepseek_config))
evaluation["judge_model"] = "deepseek-v4-flash"
evaluation["judge_api"] = "chat-completions"
evaluation["judge_base_url"] = "https://api.deepseek.com/v1"
self.assertRegex(
    bind_paper_benchmark_evidence(report_path, state_dir=state_dir, pi_dir=pi_dir),
    r"^[0-9a-f]{64}$",
)
```

Mutate any report/evaluation Judge field or `prompt_contract_sha256`; expect rejection before Climb mutation.

- [x] **Step 5: Implement binder equality against private evaluation evidence**

The binder must require the report's exact `judge` keys, compare every `JudgeConfig.public_dict()` field persisted in `eval_result.json`, validate `judge_request_fingerprint`, and compare the current packaged prompt-contract digest. It must not contain a literal allowed-model list.

- [x] **Step 6: Turn focused tests GREEN**

Run: `uv run --project asterion python -m unittest -v tests.test_asterion_dci_verification.PaperBenchmarkVerifierTests tests.test_asterion_dci_artifacts.PaperBenchmarkEvidenceBinderTests`

Expected: all tests pass, including DeepSeek acceptance, identity mutation, symlink, mode, dirty-runtime, idempotence, and conflict-no-mutation cases.

- [x] **Step 7: Update operator documentation**

Document that any supported configured Judge can prove functional acceptance; effective identity is recorded; GPT-4.1 is paper experiment provenance and becomes mandatory only for an AF-340 paper-score comparison claim.

- [x] **Step 8: Verify and commit the correction**

Run Ruff and compilation for touched Python, the Task 7/8 selectors, model-free installed/wheel verification, `python3 tools/project_scope_check.py`, and `git diff --check`.

Commit: `fix(dci): accept configured judge evidence`

- [x] **Step 9: Run bounded DeepSeek evidence and bind H004**

Use a disposable clean checkout at `pi-revision.txt`, reuse only the existing private Pi auth directory, and invoke:

```bash
asterion-dci paper verify \
  --provider-backed \
  --env-file .env \
  --output-root PRIVATE_EMPTY_OUTPUT
```

Require exactly `Agent operations: 2`, `Judge operations: 1`, `External operations: 3`, and `Full dataset ran: no`; then run `tools/climb/bind-paper-benchmark-evidence.py` against the successful report and the same clean Pi checkout.

## Task 9 — Independent review and package closure

> Closure complete: final bounded DeepSeek evidence, independent acceptance
> review, Climb cycle 95, and all package gates passed on 2026-07-17.

Run:

- focused dataset/metric/alignment/matrix tests;
- full Python discovery under both test roots;
- TypeScript and Rust unchanged-boundary suites;
- compile, Ruff, shell syntax, wheel/install, product verifier, scope, and
  `git diff --check`;
- model-free verifier proving provider/Judge operations `0` and full dataset
  `no`;
- final bounded verifier proving exactly three declared operations: two agent
  calls and one Judge call.

Independent review must check formulas against arXiv:2605.05242v1, conservative
fallback, cache identity, private/public boundaries, thirteen-dataset closure,
and AF-330/340 exclusions. Reconcile WORKLIST, CURRENT-STATE, DECISIONS,
JOURNAL, Climb state, and RESUME only after all gates pass.

## Deterministic task map

| Task | Production/resource files | RED/GREEN selector and binding point |
| --- | --- | --- |
| 1 | `asterion/src/asterion/dci/paper_benchmarks.py`, `resources/paper-benchmarks.json`, `resources/paper-benchmark.schema.json`, `resources/paper-experiment-scopes.json`, governance/Climb state | `uv run python -m unittest -v tests.test_asterion_dci_paper_benchmarks.PaperBenchmarkInventoryTests tests.test_asterion_dci_paper_benchmarks.PaperExperimentScopeTests`; prove all-830, both n=100 scopes, and Appendix random-50 remain distinct; zero external calls |
| 2 | `metrics.py`, `datasets.py`, `resources/batch-profiles.json`, benchmark launchers | `uv run python -m unittest -v tests.test_asterion_dci_metrics.DciMetricsTests tests.test_asterion_dci_datasets.PaperBeirDatasetTests tests.test_asterion_dci_batch_launchers.PaperBeirLauncherTests`; close H001 only after duplicate-rank RED becomes bounded GREEN; zero external calls |
| 3 | `resolution_metrics.py` | `uv run python -m unittest -v tests.test_asterion_dci_resolution_metrics.ResolutionMetricTests`; zero external calls |
| 4 | `trajectory_resolution.py`, `artifacts.py`, `resources/trajectory-resolution.schema.json` | `uv run python -m unittest -v tests.test_asterion_dci_trajectory_resolution.TrajectoryResolutionTests tests.test_asterion_dci_artifacts.TrajectoryResolutionArtifactTests`; close H002/H003 only after exact evidence hashes, mutation, and body-free tests; zero external calls |
| 5 | `analysis.py`, `export.py`, `benchmark.py` | `uv run python -m unittest -v tests.test_asterion_dci_analysis.PaperResolutionAnalysisTests tests.test_asterion_dci_export.PaperResolutionExportTests tests.test_asterion_dci_batch.PaperResolutionBatchTests`; zero external calls |
| 6 | `ablation.py`, `resources/paper-ablation.schema.json`, `resources/paper-ablation-matrix.json` | `uv run python -m unittest -v tests.test_asterion_dci_ablation.PaperAblationMatrixTests`; prove paper rows list/validate/render but cannot execute and bounded analogues are deterministic; zero external calls |
| 7 | `cli.py`, complete reference, validation guide, root README, `.env.template`, wheel metadata | `uv run python -m unittest -v tests.test_asterion_dci_cli.PaperBenchmarkCliTests tests.test_asterion_dci_product_parity.PaperBenchmarkProductParityTests tests.test_asterion_dci_product_acceptance.PaperBenchmarkWheelTests`; zero external calls |
| 8 | `verification.py`, `artifacts.py`, verifier/binder tests | `uv run python -m unittest -v tests.test_asterion_dci_verification.PaperBenchmarkVerifierTests tests.test_asterion_dci_artifacts.PaperBenchmarkEvidenceBinderTests`; bounded evidence is exactly two Pi agent calls plus one Judge call; bind only after rehash, then close H004 |
| 9 | `docs/status/*`, Climb closure state | Run the full gate below, independent review, and scope closure; no additional external calls |

Every task also runs Python compilation and Ruff for touched Python, `bash -n`
for touched shell launchers, wheel resource parity when resources change,
`git diff --check`, and `python3 tools/project_scope_check.py`. The Task 8
evidence binding point is terminal: no H004 result exists before all source
artifacts have been rehashed and the immutable report is accepted.

## Commit discipline

Each task starts with failing tests, ends with focused verification, and lands
as one or more cohesive commits followed by a ≤20-word project-state journal
entry. After three commits or a structural boundary, evaluate a checkpoint.
