# AF-340 README Reproduction and Runtime-Parity Design

> Status: approved by the user on 2026-07-18.

## Goal

Make the repository's documented DCI product executable from its public
configuration contract through measured results. The original DCI README Quick
Start, Context Management Strategies, and Benchmark DCI-Agent-Lite paths must
run first as the comparison baseline. Asterion DCI must then run the same Pi
experiment contract and the paper's Claude Code runtime path through its own
independent implementation. Full-dataset results, result comparability, and
paper-reference comparison belong to this package rather than to bounded
functional acceptance.

AF-340 does not add Claude Agent SDK. It keeps the runtime contract open for a
future adapter while accepting only the currently implemented paper runtimes:
Pi and Claude Code.

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
runtime adapter and runtime-valid provider configuration.

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
  private evidence into a body-free record;
- `full`: runs the complete approved benchmark scopes and cross-product result
  comparison.

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
7. explicitly authorized full profiles and statistical comparison.

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
- Importing or launching original DCI from Asterion to manufacture parity.
- Allowing `.env`, a generic verify command, or cache presence to authorize a
  full-dataset run.
