# AF-340 README Reproduction and Runtime-Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the original DCI README paths and the independent Asterion Pi/Claude Code paths executable under one layered configuration contract, then produce bounded and explicitly authorized full-result comparison evidence.

**Architecture:** Original DCI and Asterion each own an independent runtime-first resolver and `dci.effective-config/v1` serializer. Existing runners, context profiles, batch engines, installed Asterion application, AF-320 dataset identities, and Judge clients remain the execution truth; AF-340 adds configuration provenance, immutable experiment profiles, authorization, normalized per-query evidence, and a root acceptance coordinator without introducing a production dependency between the products.

**Tech Stack:** Python 3.11+, `python-dotenv`, `argparse`, frozen dataclasses, JSON/JSONL schemas, `unittest`, Bash launchers, Asterion installed-application runtime factories, existing Pi JSONL RPC and Claude Code CLI adapters.

## Global Constraints

- Active work package is `AF-340`; run `python3 tools/project_scope_check.py` before implementation and before closure.
- Precedence is explicit CLI/application request > exported process environment > repository `.env` > selected-runtime or Judge default.
- Original DCI accepts only public runtime `pi`; Asterion accepts `pi` and `claude-code`, mapped to `pi.reference` and `claude-code.reference`.
- Pi defaults are provider `openai-codex` and model `gpt-5.6-luna`; Claude Code defaults to local subscription/native model selection and injects provider variables only for explicit compatible MiniMax Coding Plan selection.
- Judge defaults are `https://api.deepseek.com/v1`, `chat-completions`, `deepseek-v4-flash`, `DEEPSEEK_API_KEY`, disabled thinking, and JSON-object output.
- Agent and Judge credentials are independent and never appear in public configuration, result, error, or cache evidence.
- Original DCI and Asterion must not import or launch one another in production; only root acceptance tests/tools may compare or coordinate their public commands.
- `.env` cannot authorize a full dataset. Full execution requires `--authorize-full`, a declared immutable profile, a new empty private output root, and an explicit non-negative budget estimate.
- Do not edit the external `pi/` checkout. Preserve unrelated worktree changes.
- Every implementation task is test-first, ends with focused verification and an atomic commit, and is immediately journaled in `docs/status/JOURNAL.md`.

---

### Task 1: Original DCI Layered Runtime Contract and Safe Projection

**Files:**

- Create: `src/dci/effective_config.py`
- Create: `src/dci/effective-config.schema.json`
- Modify: `src/dci/config.py`
- Modify: `src/dci/benchmark/pi_rpc_runner.py:1520-1740`
- Modify: `scripts/bcplus_eval/run_bcplus_eval.py:65-235`
- Modify: `tests/test_config.py`
- Modify: `tests/test_pi_rpc_runner.py`
- Create: `tests/test_effective_config.py`

**Interfaces:**

- Produces `ConfigLayers.from_repo(repo_root, process_environment)`, which parses `.env` without overriding the supplied process snapshot and can materialize missing values into the process before external clients are built.
- Produces `resolve_original_runtime(invocation, layers) -> OriginalRuntimeConfig`; legal runtime is exactly `pi`.
- Produces `OriginalEffectiveConfig.to_public_dict() -> dict[str, object]` with schema literal `dci.effective-config/v1` and no credential/path/body fields.
- Existing `load_project_env(repo_root)` remains backward compatible and delegates to the new layer loader.

- [ ] **Step 1: Write RED precedence and runtime tests.** Add tests with this exact behavior:

```python
def test_original_runtime_precedence_and_sources(self) -> None:
    layers = ConfigLayers(
        process={"DCI_PROVIDER": "environment-provider"},
        dotenv={"DCI_PROVIDER": "dotenv-provider", "DCI_MODEL": "dotenv-model"},
    )
    resolved = resolve_original_runtime(
        {"provider": "invocation-provider", "model": None}, layers
    )
    self.assertEqual(resolved.runtime, "pi")
    self.assertEqual(resolved.provider, "invocation-provider")
    self.assertEqual(resolved.model, "dotenv-model")
    self.assertEqual(resolved.sources["agent.provider"], "invocation")
    self.assertEqual(resolved.sources["agent.model"], "environment")

def test_original_runtime_rejects_claude_code(self) -> None:
    with self.assertRaisesRegex(ValueError, "Original DCI runtime is unsupported"):
        resolve_original_runtime({"runtime": "claude-code"}, ConfigLayers({}, {}))
```

- [ ] **Step 2: Run RED tests.** Run `uv run python -m unittest -v tests.test_config tests.test_effective_config tests.test_pi_rpc_runner`; expect import failures for `ConfigLayers`, `resolve_original_runtime`, and `OriginalEffectiveConfig`.

- [ ] **Step 3: Implement the focused layer and runtime values.** Use these public types and defaults:

```python
ValueSource = Literal["invocation", "environment", "runtime-default"]

@dataclass(frozen=True)
class ConfigLayers:
    process: Mapping[str, str]
    dotenv: Mapping[str, str]

    @classmethod
    def from_repo(
        cls, repo_root: Path, process_environment: Mapping[str, str] | None = None
    ) -> "ConfigLayers":
        process = dict(os.environ if process_environment is None else process_environment)
        loaded = dotenv_values(Path(repo_root) / ".env")
        dotenv = {key: value for key, value in loaded.items() if value is not None}
        return cls(process=MappingProxyType(process), dotenv=MappingProxyType(dotenv))

    def resolve(
        self, name: str, invocation: object, default: object
    ) -> tuple[object, ValueSource]:
        if invocation is not None:
            return invocation, "invocation"
        if name in self.process:
            return self.process[name], "environment"
        if name in self.dotenv:
            return self.dotenv[name], "environment"
        return default, "runtime-default"

    def materialize(self, target: MutableMapping[str, str]) -> None:
        for name, value in self.dotenv.items():
            target.setdefault(name, value)

@dataclass(frozen=True)
class OriginalRuntimeConfig:
    runtime: str
    provider: str
    model: str
    tools: str
    max_turns: int
    timeout_seconds: float | None
    thinking_level: str | None
    context_profile: str | None
    sources: Mapping[str, ValueSource]

PI_DEFAULT_PROVIDER = "openai-codex"
PI_DEFAULT_MODEL = "gpt-5.6-luna"
```

`ConfigLayers.from_repo()` must call `dotenv_values(repo_root / ".env")`, snapshot inherited values first, and use `os.environ.setdefault()` only when the caller asks to materialize the layers. Empty invocation values count as omitted; empty environment values remain explicit only for fields whose adapter allows omission.

- [ ] **Step 4: Add `--runtime` and remove parser-time provider/model defaults.** Both original entry points pass explicit arguments as an invocation mapping into `resolve_original_runtime()`. The batch driver retains its existing flags and `--limit`; it receives resolved values before Pi command construction and writes `effective-config.json` alongside existing private run artifacts.

- [ ] **Step 5: Implement safe serialization and schema validation.** The public mapping has exact top-level keys `schema`, `product`, `runtime`, `agent`, `context`, `judge`, `experiment`, `sources`, and `identity_sha256`. `schema` is `dci.effective-config/v1`, `product` is `original-dci`, and `identity_sha256` is the lowercase SHA-256 of canonical JSON for the other eight fields. The schema rejects unknown keys and the serializer rejects credential values, prompt/answer/tool bodies, and absolute/private paths.

- [ ] **Step 6: Run GREEN tests and static checks.** Run `uv run python -m unittest -v tests.test_config tests.test_effective_config tests.test_pi_rpc_runner`, `uv run python -m py_compile src/dci/config.py src/dci/effective_config.py src/dci/benchmark/pi_rpc_runner.py scripts/bcplus_eval/run_bcplus_eval.py`, and `uv run ruff check` on those four Python files; expect all pass.

- [ ] **Step 7: Commit and journal.** Commit only the files in this task with `git commit -m "feat(dci): add layered runtime configuration"`, then append the verified commit and test result to `docs/status/JOURNAL.md`.

### Task 2: Independent Asterion Resolver, Runtime Mapping, and Claude Authentication Modes

**Files:**

- Create: `asterion/src/asterion/dci/effective_config.py`
- Create: `asterion/src/asterion/dci/resources/effective-config.schema.json`
- Modify: `asterion/src/asterion/dci/config.py`
- Modify: `asterion/src/asterion/dci/cli.py:45-225`
- Modify: `asterion/src/asterion/cli.py:50-310`
- Modify: `asterion/src/asterion/runtime/factory.py`
- Modify: `asterion/src/asterion/runtime/defaults.py`
- Modify: `tests/test_asterion_dci_config.py`
- Modify: `tests/test_asterion_dci_cli.py`
- Modify: `asterion/tests/test_asterion_cli.py`
- Modify: `asterion/tests/test_default_runtime_factory.py`
- Modify: `asterion/tests/test_dci_complete_application.py`

**Interfaces:**

- Produces independent `resolve_asterion_runtime(overrides, layers) -> AsterionRuntimeConfig` and `AsterionEffectiveConfig.to_public_dict()`; no import from `src/dci`.
- Produces `resolve_public_runtime_id(value) -> str`, mapping `pi` to `pi.reference` and `claude-code` to `claude-code.reference`, while accepting exact installed IDs for backward compatibility.
- Extends `RuntimeFactoryContext.options` with already-resolved `provider`, `model`, `tools`, `timeout_seconds`, and `authentication_mode`; factories stop reloading `.env`.
- Produces `_claude_provider_environment(environment, provider, model) -> tuple[dict[str, str], str]`, where the second item is `subscription`, `minimax-coding-plan`, or `minimax-cn-coding-plan`.

- [ ] **Step 1: Write RED runtime-first tests.** Cover explicit CLI over process over `.env`, Pi defaults, `DCI_RUNTIME=claude-code`, exact installed-ID compatibility, unsupported pairs before factory construction, and equality of safe original/Asterion Pi projections after removing the `product` field.

- [ ] **Step 2: Write RED Claude mode tests.** Assert the exact cases:

```python
def test_claude_subscription_injects_no_provider_credentials(self) -> None:
    child, mode = _claude_provider_environment({}, provider=None, model=None)
    self.assertEqual(mode, "subscription")
    self.assertNotIn("ANTHROPIC_API_KEY", child)
    self.assertNotIn("ANTHROPIC_AUTH_TOKEN", child)
    self.assertNotIn("ANTHROPIC_BASE_URL", child)

def test_claude_rejects_pi_default_pair(self) -> None:
    with self.assertRaisesRegex(RuntimeFactoryError, "unsupported"):
        _claude_provider_environment(
            {}, provider="openai-codex", model="gpt-5.6-luna"
        )
```

Retain exact international/China MiniMax URL, key-name, ordinary-key, and `sk-cp-` Token Plan tests from AF-330.

- [ ] **Step 3: Run RED suites.** Run `uv run python -m unittest -v tests.test_asterion_dci_config tests.test_asterion_dci_cli asterion.tests.test_asterion_cli asterion.tests.test_default_runtime_factory asterion.tests.test_dci_complete_application`; expect failures for missing runtime mapping, source metadata, and subscription branch.

- [ ] **Step 4: Implement independent resolution.** Add `runtime: str = "pi"` to `DciRuntimeOptions`, resolve runtime before provider/model, apply Pi defaults only for Pi, and keep provider/model as `None` in Claude subscription mode. Pass the resolved immutable options through `RuntimeFactoryContext`; remove `load_dotenv(Path.cwd() / ".env")` from `default_runtime_factory_registry()`.

- [ ] **Step 5: Implement public-name mapping in generic Asterion CLI.** Make generic `asterion run --runtime` optional only when `DCI_RUNTIME` or the application default supplies it. Resolve to the exact ID before application validation and assembly selection. Explicit `--runtime pi` and `--runtime claude-code` must choose the same assemblies as their exact IDs.

- [ ] **Step 6: Implement Claude preflight.** Subscription mode keeps only operational variables and invokes the local `claude` login without derived provider settings. Explicit MiniMax mode requires its matching provider key and model, replaces conflicting Anthropic-native variables in the child-only mapping, and fails on mixed subscription/third-party signals, unsupported providers, or missing values before `ClaudeCodeRuntimeClient` construction.

- [ ] **Step 7: Generate the independent safe projection.** Match Task 1's schema and field/source names, set `product` to `asterion-dci`, map installed IDs back to public runtime names, and include the authentication mode but never its credential source value.

- [ ] **Step 8: Run GREEN suites and static checks.** Run the five RED suites, compile the touched Python modules, and run Ruff; expect all pass and no root-original import in `asterion/src`.

- [ ] **Step 9: Commit and journal.** Commit with `git commit -m "feat(asterion): resolve Pi and Claude runtime configuration"` and journal the focused evidence.

### Task 3: DeepSeek Judge Defaults and Complete Cache Identity

**Files:**

- Modify: `src/dci/benchmark/judge.py`
- Modify: `asterion/src/asterion/dci/judge.py`
- Modify: `src/dci/benchmark/pi_rpc_runner.py`
- Modify: `asterion/src/asterion/dci/cli.py`
- Modify: `.env.template`
- Modify: `tests/test_judge.py`
- Modify: `tests/test_asterion_dci_judge.py`
- Modify: `tests/test_check_judge.py`
- Modify: `tests/test_asterion_dci_product_parity.py`

**Interfaces:**

- Both independent `JudgeConfig` implementations use identical zero-argument defaults and preserve every existing CLI/env override.
- `judge_request_fingerprint()` includes endpoint, API, model, JSON mode, strict schema mode, Responses store flag, effective thinking, max output tokens, prices, and canonical prompt/request-shape digest.
- Effective configuration consumes `JudgeConfig.public_dict()` plus the request-shape and prompt-contract digests; no key value is serialized.

- [ ] **Step 1: Write RED default and fingerprint tests.** Assert the default endpoint is `https://api.deepseek.com/v1/chat/completions`, API `chat-completions`, model `deepseek-v4-flash`, key env `DEEPSEEK_API_KEY`, effective thinking `disabled`, JSON mode true, and zero default prices. Mutating any request-shaping field must change the fingerprint; mutating only the credential value must not.

- [ ] **Step 2: Run RED suites.** Run `uv run python -m unittest -v tests.test_judge tests.test_asterion_dci_judge tests.test_check_judge tests.test_asterion_dci_product_parity`; expect failures showing the OpenAI Responses fallback.

- [ ] **Step 3: Replace built-in defaults independently.** Use these constants in both products:

```python
DEFAULT_JUDGE_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_JUDGE_API = "chat-completions"
DEFAULT_JUDGE_MODEL = "deepseek-v4-flash"
DEFAULT_JUDGE_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEFAULT_JUDGE_THINKING = "disabled"
```

Keep OpenAI Responses and GPT-4.1 available only through explicit overrides/profile application. Do not silently use DeepSeek pricing.

- [ ] **Step 4: Update `.env.template`.** Set `DCI_RUNTIME=pi`, `DCI_PROVIDER=openai-codex`, and `DCI_MODEL=gpt-5.6-luna`; document that omitting provider/model for `DCI_RUNTIME=claude-code` uses local subscription login, while explicit MiniMax examples require the compatible Coding Plan model and matching key. Retain the independent Judge block and explicitly state CLI precedence.

- [ ] **Step 5: Run GREEN suites, compile, Ruff, and secret scan.** Run the four focused suites, compile both Judge modules, Ruff them, and run `rg -n "api_key.*public|DEEPSEEK_API_KEY=" src asterion/src tests .env.template`; expect no serialized credential and only the documented placeholder assignment.

- [ ] **Step 6: Commit and journal.** Commit with `git commit -m "feat(dci): default independent judge to DeepSeek V4"` and journal tests plus cache-identity coverage.

### Task 4: Literal Original README Quick Start and Context Paths

**Files:**

- Modify: `README.md:447-555`
- Modify: `src/dci/benchmark/pi_rpc_runner.py`
- Create: `tools/verify_original_readme.py`
- Create: `tests/test_original_readme_acceptance.py`
- Modify: `tests/test_pi_rpc_runner.py`
- Modify: `tests/test_asterion_dci_context_profiles.py`

**Interfaces:**

- Produces `verify_original_readme_main(argv) -> int` with `--level local|bounded`, `--env-file`, and `--output-root`.
- `local` parses the literal fenced commands, validates L0-L4 installed context resources/behavior with zero providers, and checks required output contracts.
- `bounded` executes the documented programmatic Quick Start plus one forced L3 compaction and one forced L4 summary, retaining private evidence under a 0700 root; terminal TUI is preflighted locally because it is interactive.
- Original programmatic runs write `question.txt`, `final.txt`, `conversation_full.json`, protocol evidence, and `effective-config.json` with mode 0600.

- [ ] **Step 1: Write RED documentation-contract tests.** Parse the README headings and command fences; assert the primary examples omit explicit provider/model, a neighboring override example supplies both, the command uses the real `src/dci/benchmark/pi_rpc_runner.py`, and context commands cover exactly `level0` through `level4`.

- [ ] **Step 2: Write RED artifact and context tests.** Use fake Pi/RPC fixtures to prove the programmatic path creates all five required artifacts and that local verification rejects missing compaction, summary, failure suppression, telemetry, resume, or extension digest evidence.

- [ ] **Step 3: Run RED tests.** Run `uv run python -m unittest -v tests.test_original_readme_acceptance tests.test_pi_rpc_runner tests.test_asterion_dci_context_profiles`; expect README literal/artifact failures.

- [ ] **Step 4: Implement the verifier and artifact write.** The verifier must call the normal original entry point as a subprocess only in bounded mode, pass `--runtime pi`, `--runtime-context-level level3|level4`, bounded turn/timeout values, and never import Asterion. Public output reports command IDs, operation counts, effective-config digest, and private artifact hashes only.

- [ ] **Step 5: Rewrite the README sections.** Quick Start first copies `.env.template` to `.env`, uses runtime defaults for the main terminal/programmatic commands, and shows the adjacent explicit override `--provider openai-codex --model gpt-5.6-luna`. Context Management Strategies gives executable L0-L4 commands and the local/bounded verifier commands without presenting bounded evidence as full results.

- [ ] **Step 6: Run GREEN and no-provider local acceptance.** Run the RED suites and `uv run python tools/verify_original_readme.py --level local`; expect `PASS`, `Agent operations: 0`, `Judge operations: 0`, and `Full dataset ran: no`.

- [ ] **Step 7: Commit and journal.** Commit with `git commit -m "docs(dci): make Quick Start and context paths executable"` and journal the literal/local acceptance result.

### Task 5: Eleven Benchmark Launchers and Asterion One-to-One Parity

**Files:**

- Modify: `scripts/bcplus_eval/run_bcplus_eval_openai.sh`
- Modify: `scripts/qa/run_2wikimultihopqa_dev_sample50.sh`
- Modify: `scripts/qa/run_bamboogle_test_sample50.sh`
- Modify: `scripts/qa/run_hotpotqa_dev_sample50.sh`
- Modify: `scripts/qa/run_musique_dev_sample50.sh`
- Modify: `scripts/qa/run_nq_test_sample50.sh`
- Modify: `scripts/qa/run_triviaqa_test_sample50.sh`
- Modify: `scripts/bright/run_bio.sh`
- Modify: `scripts/bright/run_earth_science.sh`
- Modify: `scripts/bright/run_economics.sh`
- Modify: `scripts/bright/run_robotics.sh`
- Modify: the matching eleven files under `asterion/scripts/`
- Modify: `README.md:557-602`
- Modify: `asterion/docs/guides/asterion-dci-complete-reference.md`
- Modify: `asterion/docs/verification/asterion-dci-validation-guide.md`
- Modify: `tests/test_asterion_dci_batch_launchers.py`
- Modify: `tests/test_asterion_dci_product_parity.py`
- Modify: `tests/test_asterion_documentation.py`

**Interfaces:**

- Every wrapper forwards `"$@"` to its existing batch engine, accepts literal `--limit 1`, and does not source `.env` or inject provider/model.
- Python entry points load repository `.env` non-overriding, so an exported process value remains higher precedence.
- The eleven primary launcher identities are one BC+, six QA, and four BRIGHT; `run_L3.sh` remains a helper outside that count.

- [ ] **Step 1: Write RED launcher-contract tests.** For every exact pair, stub `uv` or `asterion-dci`, execute with exported `DCI_PROVIDER=exported`, repository `.env` containing a different value, and `--limit 1`; assert the captured argv contains the correct dataset/profile/corpus, contains `--limit 1` once, and contains no hard-coded `--provider`/`--model` or shell-sourced replacement.

- [ ] **Step 2: Run RED tests.** Run `uv run python -m unittest -v tests.test_asterion_dci_batch_launchers tests.test_asterion_dci_product_parity tests.test_asterion_documentation`; expect failures for shell sourcing, hard-coded source model flags, and documentation drift.

- [ ] **Step 3: Convert all wrappers to thin launchers.** Preserve each existing dataset, corpus, profile, output, mode, max-turn, concurrency, context, and thinking identity. Remove only shell `.env` loading and provider/model injection; keep positional BC+ level/thinking parsing and append remaining arguments exactly once.

- [ ] **Step 4: Update benchmark docs.** List all eleven original commands and their eleven Asterion counterparts, show `--limit 1` on representative BC+/QA/BRIGHT commands, explain that unmodified commands are full-dataset surfaces but not authorization, and link the explicit full verifier from Task 8.

- [ ] **Step 5: Run GREEN, syntax, and literal checks.** Run the RED suites, `bash -n` on all 22 primary launchers plus both `run_L3.sh` helpers, and `rg -n "source .*\.env|--provider (openai|anthropic)|--model gpt-5\.4-nano" scripts/{bcplus_eval,qa,bright} asterion/scripts/{bcplus_eval,qa,bright}`; expect no matches in primary launchers.

- [ ] **Step 6: Commit and journal.** Commit with `git commit -m "fix(dci): unify documented benchmark launchers"` and journal the 11/11 pair result.

### Task 6: Immutable Experiment Profiles and Explicit Full Authorization

**Files:**

- Create: `asterion/src/asterion/dci/resources/experiment-profile.schema.json`
- Create: `asterion/src/asterion/dci/resources/experiment-profiles.json`
- Create: `asterion/src/asterion/dci/experiment_profiles.py`
- Modify: `asterion/src/asterion/dci/paper_benchmarks.py`
- Modify: `asterion/src/asterion/dci/verification.py`
- Modify: `asterion/src/asterion/dci/cli.py`
- Modify: `asterion/pyproject.toml`
- Create: `tests/test_asterion_dci_experiment_profiles.py`
- Modify: `tests/test_asterion_dci_paper_benchmarks.py`
- Modify: `tests/test_asterion_dci_paper_product.py`

**Interfaces:**

- Produces `ExperimentProfile`, `resolve_experiment_profile(profile_id)`, and `experiment_profile_sha256(profile_id)`.
- Exact IDs are `current-default/pi`, `current-default/claude-subscription`, `current-default/claude-minimax`, `paper-reference/pi`, and `paper-reference/claude-code`.
- Produces frozen `FullExecutionAuthorization(profile_id, output_root, estimated_budget_usd, invocation_authorized)` and `authorize_full_execution(profile_id: str, output_root: Path, estimated_budget_usd: float, invocation_authorized: bool) -> FullExecutionAuthorization`.
- Replaces unconditional AF-320 rejection only for a valid AF-340 authorization object; `--provider-backed` remains bounded.

- [ ] **Step 1: Write RED profile tests.** Assert exact runtime/provider/model/reasoning/Judge/max-turn values from the approved spec, 300 turns for both paper profiles, exact AF-320 dataset/scope/selection digests, explicit `paper-unreported` provenance, immutable canonical SHA-256 identities, and wheel resource availability.

- [ ] **Step 2: Write RED authorization tests.** Reject authorization from any environment variable, missing `--authorize-full`, unknown profile, reused/non-empty/symlink output root, absent budget, negative/non-finite budget, dataset/profile mismatch, and cache-only evidence. Accept only a fresh 0700 root with explicit invocation boolean and complete preflight.

- [ ] **Step 3: Run RED tests.** Run `uv run python -m unittest -v tests.test_asterion_dci_experiment_profiles tests.test_asterion_dci_paper_benchmarks tests.test_asterion_dci_paper_product`; expect missing profile/authorization APIs.

- [ ] **Step 4: Add strict schema and resources.** Each profile binds runtime, provider/model or native selection, authentication mode, reasoning, tools, 300/default max turns, context identity, Judge identity, dataset scope IDs, selections, corpus, metric, aggregation, margins/targets, and provenance. `current-default/claude-minimax` records the configured model identity at invocation and cannot be resolved without it.

- [ ] **Step 5: Implement fail-closed authorization.** Add `asterion-dci paper reproduce --profile ID --output-root PATH --estimated-budget-usd N --authorize-full --dry-run`. `--dry-run` prints exact dataset counts, maximum agent/Judge operations, selected profile/digests, and budget before any provider construction. Omitting `--authorize-full` always stops after the plan, even if `.env` contains a similarly named value.

- [ ] **Step 6: Run GREEN and wheel checks.** Run the RED suites, build an isolated wheel, import `asterion.dci.experiment_profiles` from it, resolve all five profiles, and confirm `paper reproduce --dry-run` reports zero performed operations.

- [ ] **Step 7: Commit and journal.** Commit with `git commit -m "feat(asterion): add authorized reproduction profiles"` and journal profile digests plus the zero-operation authorization tests.

### Task 7: Normalized Per-Query Evidence and Versioned Statistical Comparison

**Files:**

- Create: `asterion/src/asterion/dci/reproduction.py`
- Create: `asterion/src/asterion/dci/resources/reproduction-result.schema.json`
- Modify: `asterion/src/asterion/dci/verification.py`
- Modify: `asterion/src/asterion/dci/cli.py`
- Create: `tests/test_asterion_dci_reproduction.py`
- Modify: `tests/test_asterion_dci_paper_resolution_analysis.py`
- Modify: `tests/test_asterion_dci_paper_product.py`

**Interfaces:**

- Produces `QueryEvidence`, `RunManifest`, `ComparisonReport`, `load_run_manifest(path)`, and `compare_reproduction_runs(baseline, candidate, profile) -> ComparisonReport`.
- QA/agentic accuracy uses matched query IDs and a paired bootstrap 95% confidence interval with a stored deterministic estimator seed; IR uses matched per-query NDCG@10 and the same paired estimator.
- Pi passes when candidate-minus-baseline accuracy lower confidence bound is at least `-0.05` and mean NDCG lower confidence bound is at least `-0.02`.
- Claude has no source baseline; it is labeled `target-comparison`, bound to exact profile/published target, and never labeled source parity.

- [ ] **Step 1: Write RED manifest validation tests.** Reject duplicate/missing query IDs, dataset/selection/profile/effective-config drift, absent failures/timeouts, excluded rows without versioned reason, answer/prompt bodies, credential-like fields, and aggregate values inconsistent with query rows.

- [ ] **Step 2: Write RED statistics tests.** Use fixed paired fixtures where accuracy delta is `-0.04` (pass), `-0.06` (fail), NDCG delta is `-0.019` (pass), and `-0.021` (fail). Assert deterministic 95% intervals, estimator name/seed/sample digest, completion/failure rates, operation/token/cost totals, and retained pair/exclusion IDs.

- [ ] **Step 3: Run RED tests.** Run `uv run python -m unittest -v tests.test_asterion_dci_reproduction tests.test_asterion_dci_paper_resolution_analysis tests.test_asterion_dci_paper_product`; expect missing reproduction types and comparator.

- [ ] **Step 4: Implement strict immutable values.** Use frozen dataclasses, canonical JSON hashing, finite-number checks, exact schema keys, stable query ordering, and explicit status values `completed`, `failed`, `cancelled`, `timed_out`, and `missing`. Non-completed rows contribute failure unless the selected profile's metric contract explicitly excludes them.

- [ ] **Step 5: Implement paired comparison.** Preserve every query-level verdict/NDCG/status and body-free digest. Compute point estimates and 10,000 deterministic paired bootstrap resamples for the 95% percentile interval; store estimator `paired-bootstrap-percentile/v1`, seed, resample count, query-set digest, and margins. Published target comparison stores the cited profile target identity without manufacturing pairs.

- [ ] **Step 6: Add CLI.** `asterion-dci paper compare --baseline MANIFEST --candidate MANIFEST --profile ID --output REPORT` writes a 0600 JSON report beneath a 0700 parent and exits nonzero on schema drift or failed acceptance.

- [ ] **Step 7: Run GREEN, compile, Ruff, and determinism checks.** Run the RED suites twice and byte-compare reports from identical inputs; expect all pass and identical output.

- [ ] **Step 8: Commit and journal.** Commit with `git commit -m "feat(asterion): compare versioned DCI reproduction results"` and journal the deterministic margin/CI evidence.

### Task 8: Unified Local, Bounded, and Full Acceptance Coordinator

**Files:**

- Create: `tools/verify_af340_reproduction.py`
- Create: `tests/test_af340_reproduction_verifier.py`
- Modify: `README.md`
- Modify: `asterion/docs/guides/asterion-dci-complete-reference.md`
- Modify: `asterion/docs/verification/asterion-dci-validation-guide.md`
- Modify: `tests/test_asterion_documentation.py`
- Modify: `docs/status/WORKLIST.md`
- Modify when structural truth changes: `docs/status/CURRENT-STATE.md`
- Append only: `docs/status/JOURNAL.md`
- Rewrite active checkpoint: `docs/status/RESUME-NEXT-SESSION.md`

**Interfaces:**

- `verify_af340_reproduction.py local` performs zero provider operations and coordinates literal source/Asterion commands through injected subprocess execution in tests.
- `bounded` requires `--env-file` and a fresh private output root; it runs original Quick Start programmatic, original L3/L4, all eleven original `--limit 1` launchers, Asterion Pi equivalents, Asterion installed/wheel Pi, and Asterion installed/wheel Claude subscription or explicit MiniMax, binding body-free private evidence.
- `full` delegates only after Task 6 authorization, executes selected complete scopes into distinct original/Asterion roots, normalizes per-query manifests, and calls Task 7 comparison.
- The coordinator is repository acceptance tooling; neither production product imports or launches the other.

- [ ] **Step 1: Write RED coordinator tests with a recording executor.** Assert exact operation matrix, command literals, zero local operations, bounded `--limit 1` on all 22 launcher invocations, installed-wheel commands, separate agent/Judge counters, stop-on-preflight failure, no full fallback, and no secret/body/path fields in the public report.

- [ ] **Step 2: Run RED tests.** Run `uv run python -m unittest -v tests.test_af340_reproduction_verifier tests.test_original_readme_acceptance tests.test_asterion_documentation`; expect missing coordinator/report failures.

- [ ] **Step 3: Implement the coordinator.** Define exact modes with `argparse` subcommands; validate all datasets/corpora/config/profiles/output roots before constructing a provider; write private evidence 0600 and the containing root 0700; preserve failed/cancelled/timed-out operations; print planned and actual operation counts.

- [ ] **Step 4: Implement literal local matrix.** Run schema/profile/launcher/context/artifact/privacy/cache/product/source-wheel checks and projection parity. Output must include `PASS`, `Agent operations: 0`, `Judge operations: 0`, and `Full dataset ran: no`.

- [ ] **Step 5: Implement bounded matrix.** Each user-facing path gets at least one real sample. Claude subscription and MiniMax are distinct selectable bounded variants; a run may select one per invocation, but AF-340 closure requires retained accepted evidence for both configured variants. Never count fixture-only execution as provider-backed.

- [ ] **Step 6: Implement full delegation.** Before the first request, print profile ID/digest, dataset and selected-query counts, agent/Judge operation maxima, fresh output identities, and budget estimate. Write normalized manifests after each scope and compare Asterion Pi against matched original Pi; compare Claude only against its exact profile/paper target.

- [ ] **Step 7: Update documentation.** Provide ready commands for local, bounded Pi, bounded Claude subscription, bounded Claude MiniMax, full dry-run, explicitly authorized full execution, and comparison. State that credentials live only in `.env`/exported environment and that full authorization is always a CLI action.

- [ ] **Step 8: Run local/focused GREEN gates.** Run `python3 tools/project_scope_check.py`, the RED suites, all configuration/Judge/launcher/profile/reproduction/product/documentation suites, `uv run python tools/verify_af340_reproduction.py local`, compilation, Ruff, shell syntax, and `git diff --check`; expect all pass with zero provider operations.

- [ ] **Step 9: Run bounded acceptance only with valid credentials.** Use a fresh private output root and execute bounded original Pi, original L3/L4, 11 source launchers, 11 Asterion Pi launchers, installed Pi, installed Claude subscription, and installed Claude MiniMax. Record actual agent/Judge operation counts and artifact/report digests; do not run full datasets in this step.

- [ ] **Step 10: Commit implementation and bounded evidence state.** Commit with `git commit -m "feat(dci): verify README and runtime reproduction parity"`, journal every verified/rejected bounded result, and refresh the active checkpoint. If either Claude authentication mode is externally unavailable, leave AF-340 `in_progress` with the exact failed preflight; do not substitute another backend.

- [ ] **Step 11: Stop at the full-cost authority gate when authorization is absent.** Produce the full dry-run budget/operation manifest and request explicit user authorization for the selected profiles and estimated budget. Do not mark AF-340 complete from local or bounded evidence.

- [ ] **Step 12: After explicit authorization, execute full profiles and close only on evidence.** Run each authorized profile into a fresh output root, compare matched original/Asterion Pi with the versioned 5pp/0.02 margins and 95% intervals, assess Claude against its exact target, run full Python discovery, TypeScript, Rust, isolated-wheel, compile, Ruff, shell, privacy, scope, and diff gates, obtain independent review, then update WORKLIST/CURRENT-STATE/JOURNAL/RESUME and commit package closure.

## Plan Self-Review Checklist

- [x] Every approved spec section maps to Tasks 1-8: layering/projection, runtime/authentication, Judge, README/context, launchers, profiles/authorization, comparison, and verification/closure.
- [x] Search this plan for forbidden placeholder language and replace any occurrence with exact code, command, type, or acceptance behavior.
- [x] Confirm `ConfigLayers`, runtime configs, effective-config fields, profile IDs, authorization fields, manifest types, comparison API, and verifier mode names are identical at every use.
- [x] Confirm no production Asterion file imports or invokes `src/dci`, and no production original file imports or invokes Asterion.
- [x] Confirm full execution remains a separately authorized Task 8 gate and cannot be triggered by `.env`, local/bounded verification, imports, documentation rendering, or cache presence.
