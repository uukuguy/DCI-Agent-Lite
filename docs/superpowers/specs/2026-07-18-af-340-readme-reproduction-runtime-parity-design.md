# AF-340 README Reproduction and Capability-Usability Design

> Status: approved by the user on 2026-07-18; functional-closure amendment approved on 2026-07-21.

## Goal

Make Asterion DCI a complete, installed, independently owned capability package
that proves the Asterion capability-package framework is usable. The
repository's documented original DCI Quick Start, Context Management
Strategies, and Benchmark DCI-Agent-Lite paths remain an executable comparison
baseline. Asterion DCI must reproduce those functional surfaces through Pi and
prove an independent Claude Code adapter path through an explicitly compatible
backend. Strict paper-model execution, published-score reproduction, and
full-dataset comparison are optional follow-on evidence rather than AF-340
closure gates.

AF-340 does not add Claude Agent SDK. It keeps the runtime contract open for a
future adapter while accepting the currently implemented DCI runtime families:
Pi and Claude Code.

## 2026-07-21 functional-closure amendment

AF-340 closes on complete DCI capability-package usability, not on access to
every supported authentication mode or strict reproduction of the DCI paper.
The required core-capability matrix is:

1. research execution over local corpora with multi-turn tool use, final
   answers, and inspectable system prompts;
2. `level0` through `level4` live context policies plus complete and processed
   conversation evidence;
3. private native artifacts, exact compatible resume, cancellation, deadlines,
   and truthful failed/partial states;
4. independent Judge execution, request/cache identity, QA accuracy, and IR
   NDCG@10;
5. QA/IR datasets and profiles, concurrent benchmark orchestration, all eleven
   launcher pairs, and exact reuse;
6. summaries, detailed analysis, figures, and BC+/BRIGHT/resolution exports;
7. one implementation across the source CLI, installed application, isolated
   wheel, Pi, and Claude Code MiniMax paths; and
8. layered configuration, credential separation, private-path safety, and
   body-free public evidence.

Model-free product gates verify the complete matrix. Retained Pi r14 covers
`original-pi` and `asterion-pi` across Quick Start, L3/L4, all eleven original
launchers, and all eleven Asterion launchers. Retained Claude MiniMax r6 covers
`asterion-claude-minimax` through installed and wheel-backed Claude Code paths.
These two reports cover the three required functional dimensions.

A compatible `claude-subscription` report may be inspected as additional
evidence when an account is available, but subscription login is not required
for bounded closure. Subscription support remains implemented and tested
locally; this amendment changes acceptance availability, not the public runtime
contract.

AF-340-H-005 no longer gates AF-340. Full datasets, paper-declared models,
published-score comparison, and statistical result reproduction require a new
active work package plus explicit invocation and finite-budget authorization.
Bounded MiniMax evidence proves functionality only and must never be relabeled
as paper-model or published-score evidence.

## One layered configuration contract

Repository `.env`, exported process environment, CLI options, and application
request fields are complementary layers of one contract. They are not separate
configuration systems and are not mutually exclusive. Effective values resolve
in this order:

1. explicit invocation values, including CLI and application request fields;
2. values already exported in the process environment;
3. values loaded from the repository `.env` only when the process environment
   did not already define the name;
4. defaults owned by the selected runtime or Judge role.

Runtime selection resolves before agent selection. `--runtime` overrides
`DCI_RUNTIME`, which overrides the application default. `--provider` and
`--model` override `DCI_PROVIDER` and `DCI_MODEL`, which override defaults for
the effective runtime. Judge CLI fields likewise override
`DCI_EVAL_JUDGE_*`, which override the Judge defaults.

`DCI_PROVIDER` and `DCI_MODEL` are shared public field names, but their meaning
is runtime-relative. They do not assert that every provider is valid for every
runtime. Each adapter owns an explicit compatibility table and translation.
Unsupported pairs fail before constructing or invoking an agent.

The original DCI runner has one legal runtime, Pi. An omitted runtime resolves
to Pi; an explicit non-Pi runtime fails before provider construction. Asterion
maps the public runtime names `pi` and `claude-code` to its exact installed
runtime identities without changing the public configuration layers.

## Runtime defaults and authentication

The Pi default is `openai-codex` with `gpt-5.6-luna`. Pi retains its broader
provider registry, model selection, and saved-auth support. Explicit provider,
model, thinking, tools, timeout, turn, and context settings continue to override
the defaults through the same layered contract.

Claude Code defaults to its existing local subscription login and native model
selection. In that mode Asterion does not inject a third-party provider key or
silently replace the authenticated account. Explicit `minimax` and
`minimax-cn` selections use only the already tested Claude-Code-compatible
Coding Plan translations. The adapter derives its private Anthropic-compatible
URL, model aliases, and credential variables inside the restricted child
environment. No Pi-only provider is guessed to be Claude-compatible.

Missing credentials, unsupported runtime/provider pairs, ambiguous competing
authentication modes, or an unavailable local Claude login fail during
preflight. Provider credentials and derived native variables never enter public
artifacts.

## Independent Judge role

The Judge is a separate LLM role, not an agent runtime feature. Its default is
DeepSeek V4 Flash over the OpenAI-compatible Chat Completions API:

- base URL `https://api.deepseek.com/v1`;
- API `chat-completions`;
- model `deepseek-v4-flash`;
- key source `DEEPSEEK_API_KEY`;
- thinking disabled;
- JSON-object output enabled.

Both original DCI and Asterion DCI implement the same safe Judge contract
independently. Responses and other compatible endpoints remain overridable.
The complete safe endpoint, API, model, output-shaping, thinking, prompt, and
pricing identity participates in cache identity. Credentials, prompts, answers,
and response bodies do not enter public configuration evidence.

## Effective configuration evidence

Each product emits an independent `dci.effective-config/v1` safe projection
covering:

- public runtime identity;
- agent provider, model, reasoning, tools, maximum turns, and timeout;
- context-profile identity and implementation digest;
- Judge endpoint, API, model, request-shape identity, and prompt digest;
- dataset, selection, corpus, metric, and execution-class identities;
- the source of each effective value: invocation, environment, or runtime
  default.

The projection contains no credential value, private path, prompt body, answer,
or tool body. Original DCI and Asterion do not import or launch one another;
root parity tests compare their independently generated projections and exact
experiment inputs.

## Original DCI README acceptance

The current root README is the user contract. AF-340 binds acceptance to its
three named paths rather than to substitute demos.

### Quick Start

The documented terminal command starts the real Pi TUI over the local Wikipedia
corpus. The documented programmatic command answers the same task and produces
`question.txt`, `final.txt`, `conversation_full.json`, protocol evidence, and
safe effective-configuration evidence. The primary example consumes `.env` and
runtime defaults; a neighboring example demonstrates CLI provider/model
override without implying that CLI and `.env` conflict.

### Context Management Strategies

Level0 through level4 select the closed live context contract before provider
requests. Model-free verification covers truncation, compaction, summarization,
failure suppression, telemetry, resume, and installed resources. Bounded live
verification forces one L3 compaction and one L4 summary with private retained
evidence. The README command itself must work through the normal original DCI
entry point rather than through an Asterion-only verifier.

### Benchmark DCI-Agent-Lite

The documented BrowseComp-Plus launcher, six QA launchers, and four BRIGHT
launchers all resolve configuration through the same product resolver. Every
launcher supports a bounded `--limit 1` acceptance without changing the full
command. The unmodified full commands remain the explicit full-dataset surface.
Dataset selection, corpus identity, maximum turns, thinking, context profile,
Judge contract, metric, aggregation, and outputs are recorded for comparison.

## Asterion DCI parity acceptance

Asterion supplies a one-to-one operator path for each original DCI surface:

| Original DCI | Asterion DCI |
|---|---|
| Pi terminal runner | `asterion-dci terminal` |
| programmatic Pi runner | `asterion-dci run` |
| level0-level4 live context | the same profile identity and behavior |
| root benchmark launchers | `asterion/scripts/...` launchers |
| source batch/evaluation | product CLI, installed application, and wheel |

With Pi selected, original DCI and Asterion must resolve identical experiment
inputs and safe effective configuration while retaining separate code and
artifact roots. With Claude Code selected, Asterion uses the same dataset,
prompt, context, Judge, metric, and result contracts and changes only the
runtime adapter and runtime-valid provider configuration. The retained MiniMax
path is sufficient for functional closure; subscription mode is an optional
compatible path.

The installed Asterion CLI, selected application, and isolated wheel must bind
the same implementation and experiment identity as the source-tree Asterion
command. Passing a fixture-only path cannot close a provider-backed or
full-dataset acceptance row.

## Verification levels

One verifier coordinates the public paths without hiding their literal
commands:

- `local`: zero provider operations; validates configuration precedence,
  fixtures, launchers, context profiles, schemas, privacy, and product parity;
- `bounded`: runs at least one real sample for every user-facing path and binds
  private evidence into a body-free record; AF-340 closure requires Pi r14 and
  Claude MiniMax r6 to cover the three functional dimensions named above;
- `full`: optionally runs complete approved benchmark scopes and cross-product
  result comparison under a future separately authorized work package.

Retained bounded validation treats conventional `python`, `python3`, and
versioned Python names inside one environment `bin/` directory as equivalent
only when `samefile()` proves they resolve to the exact same interpreter inode.
The inspector may select the one complete plan identity that matches such an
alias; it must still reject a different interpreter, directory, operation,
argument, resource manifest, artifact digest, signature, or permission mode.
This normalization makes a retained report portable across `uv run python` and
`uv run python3` without weakening executable identity.

`.env` may provide every normal runtime and Judge value. It cannot by itself
authorize a full dataset. Full execution requires an explicit invocation-level
authorization, fresh output identity, declared experiment profile, and
estimated budget. Reuse is permitted only for exact compatible evidence.

## Versioned experiment profiles

AF-340 defines two immutable profiles.

The `current-default` family contains three immutable runtime variants:

- `current-default/pi`: `openai-codex`, `gpt-5.6-luna`, and DeepSeek V4 Flash;
- `current-default/claude-subscription`: local Claude Code subscription/native
  model selection and DeepSeek V4 Flash;
- `current-default/claude-minimax`: the exact configured compatible MiniMax
  Coding Plan model/key identity and DeepSeek V4 Flash.

The `paper-reference` family contains two immutable variants:

- `paper-reference/pi`: GPT-5.4 nano DCI-Agent-Lite, high reasoning, and the
  paper GPT-4.1 Judge;
- `paper-reference/claude-code`: Claude Sonnet 4.6 DCI-Agent-CC, medium
  reasoning, and the paper GPT-4.1 Judge.

Both paper variants bind 300-turn budgets, exact datasets, L3 main context where
applicable, published selections when available, and explicit paper-unreported
provenance where they are unavailable.

Both profiles record all material identities. A `current-default` result is not
silently relabeled as `paper-reference`, and neither profile may fabricate a
missing paper seed, FineWeb selection, or Bamboogle source.

Profile availability does not imply that every profile is required for package
acceptance. `current-default/claude-subscription` remains a supported optional
profile; `current-default/claude-minimax` is the required retained Claude Code
functional path for AF-340.

## Result comparison

Comparison operates on immutable per-query evidence rather than answer text
alone. It reports Judge verdicts, accuracy, NDCG@10, completion and failure
rates, operation counts, tokens, cost, runtime identity, and effective
configuration identity.

The initial versioned non-inferiority margins are:

- Asterion Pi QA and agentic-search accuracy no more than 5 percentage points
  below the matched original DCI Pi result;
- Asterion Pi mean IR NDCG@10 no more than 0.02 below the matched original DCI
  Pi result;
- README and paper targets assessed with reported point estimates plus 95%
  confidence intervals, with the estimator and sample identity stored in the
  result manifest.

There is no original source Claude Code product to pair against. Asterion Claude
Code variants are assessed against their exact versioned profile and, for
`paper-reference/claude-code`, the published DCI-Agent-CC targets. They are not
misreported as source-product parity.

The paper target is a separate immutable `dci.reproduction-target/v1` resource
rather than an in-place mutation of `dci.experiment-profile/v1`. It binds
arXiv:2605.05242v1 and the paper's DCI-Agent-CC main-result rows: BrowseComp-Plus
accuracy `0.800`; QA accuracy NQ `0.78`, TriviaQA `0.96`, Bamboogle `0.80`,
HotpotQA `0.88`, 2WikiMultiHopQA `0.82`, MuSiQue `0.74`, aggregate `0.830`; and
IR NDCG@10 Biology `0.771`, Earth Science `0.690`, Economics `0.468`, Robotics
`0.568`, ArguAna `0.853`, SciFact `0.757`, aggregate `0.685`. A current-default
Claude profile has no published numeric target and must report that fact instead
of inheriting the paper-reference values.

The verifier preserves query-level pairs and exclusions so a summary cannot
hide divergent samples, systematic failures, or selection drift. Failed,
cancelled, timed-out, or missing rows remain failures unless the versioned
metric contract explicitly says otherwise.

## Failure, privacy, and cost boundaries

All configuration and corpus validation completes before provider construction.
Agent and Judge roles have independent credentials and request counters. A
runtime failure cannot be converted into a successful Judge row, and a Judge
failure cannot erase the completed native agent evidence. Resume and reuse
preserve exact attempt and cache identity.

Private run roots remain mode 0700 with sensitive artifacts mode 0600. Public
records contain only schemas, safe configuration, hashes, counts, metrics, and
body-free failure classes. Redirects, credential-bearing URLs, symlinked input
roots, outside-corpus access, web, subagents, and unauthorized commands retain
their existing fail-closed boundaries.

Full verification prints its planned dataset counts, agent/Judge operation
limits, selected profiles, and budget estimate before the first request. It
never starts from a generic `verify`, README render, import, or `.env` value.

## Implementation and test boundary

Implementation proceeds test-first in these slices:

1. layered runtime/agent/Judge resolution and safe projections;
2. runtime defaults, subscription login, MiniMax translation, and fail-closed
   compatibility;
3. original README Quick Start and context paths;
4. original benchmark launchers and result identities;
5. Asterion source, application, installed-wheel, and launcher parity;
6. local and bounded verification orchestration;
7. optional, separately scoped full profiles and statistical comparison.

Focused tests cover both independent configuration implementations, exact
precedence, environment loading, CLI overrides, credential shadowing, cache
identity, adapter translation, all launchers, context semantics, artifact
schemas, privacy, cancellation, reuse, installed resources, and result
comparison. Closure also requires full Python discovery, compilation, Ruff,
shell syntax, TypeScript and Rust gates, isolated wheel verification, scope
preflight, diff checks, and independent review.

## Rejected shortcuts

- Runtime-specific public variable families that bypass the shared layered
  contract.
- Treating `.env` and CLI as mutually exclusive configuration modes.
- Applying Pi's provider defaults or compatibility set to Claude Code.
- Treating a configured DeepSeek Judge as the agent backend or vice versa.
- Replacing README commands with internal fixture-only commands.
- Claiming full or comparable results from `--limit 1` evidence.
- Requiring an unavailable subscription account when an explicit compatible
  MiniMax backend already proves the Claude Code functional path.
- Blocking capability-package or framework usability on optional paper-model,
  full-dataset, or published-score reproduction.
- Importing or launching original DCI from Asterion to manufacture parity.
- Allowing `.env`, a generic verify command, or cache presence to authorize a
  full-dataset run.
