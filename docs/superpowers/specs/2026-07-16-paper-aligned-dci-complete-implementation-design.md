# Paper-Aligned DCI Complete Implementation Design

> Status: approved in conversation and reviewed as a written specification on
> 2026-07-16.
> Proposed package sequence: AF-310 → AF-320 → AF-330 → AF-340.

## Purpose

The converged `asterion/` project already contains an independent implementation
of the current repository DCI product surface. AF-180 through AF-250 proved that
surface with executable source-parity inventories, bounded Pi and Judge runs,
and isolated-wheel verification. That closure does not prove that Asterion
implements every capability and experiment described by the DCI paper.

The next milestone will close that distinction. Its target is paper-aligned DCI:

- exact live runtime context-management policies rather than post-run artifact
  processing or an `unsupported` diagnostic;
- every paper benchmark family, including BEIR ArguAna and SciFact;
- the paper's trajectory coverage and localization metrics and controlled
  ablation surfaces;
- complete capability/application exposure for research, evaluation,
  benchmarking, analysis, and export;
- bounded semantic verification across Pi and Claude Code; and
- a separately authorized final phase for full-dataset and score reproduction.

The implementation remains Asterion-owned. The mixed-repository `src/dci`
product stays an independent comparison baseline, and the external `pi/`
checkout stays an external dependency.

## Evidence Baseline

The design starts from these verified facts:

- `asterion-dci` exposes `run`, `terminal`, `resume`, `system-prompt`,
  `evaluate`, `benchmark`, and `export`.
- Provider-free product verification passes 8/8 product rows, 533/533 delegated
  selectors, 12/12 launcher pairs, 6/6 batch extras, and 7/7 retained bounded
  cases without a provider request.
- BrowseComp-Plus, six knowledge-intensive QA datasets, and four BRIGHT domains
  have Asterion profiles and launchers.
- The installed generic application executes one DCI research capability, but
  evaluation, benchmarking, analysis, and export remain product-CLI operations
  rather than complete application composition units.
- `runtime_context_level` is accepted and preserved in native state, but the
  current Asterion path records the requested control as unsupported and does
  not select a paper-defined live context policy.
- Conversation artifact controls clear, externalize, or strip saved evidence
  after execution. They do not change the context seen by the model.
- The current external Pi exposes official extension hooks and an explicit
  `--extension` loader, so Asterion can own the DCI policy without modifying Pi.
- Current acceptance deliberately excludes full-dataset execution and does not
  reproduce the paper's published scores.

## Completeness Definition

Paper-aligned DCI is complete only when all four evidence layers are stated
separately:

1. **Implemented** — Asterion owns the production behavior.
2. **Model-free verified** — deterministic fixtures and tests prove its exact
   semantics without a provider request.
3. **Bounded provider verified** — a small real run proves that the selected
   runtime actually executes the behavior.
4. **Experiment reproduced** — the full paper workload and result have been run
   under a recorded configuration and budget.

Completion of layers 1–3 does not imply layer 4. Documentation and product
metadata must preserve this distinction.

## Options Considered

### One monolithic package

One AF-310 package could combine live context management, benchmark additions,
metrics, application composition, Claude semantic verification, and full paper
experiments. This was rejected because unrelated runtime, evaluation, product,
and cost risks would share one acceptance boundary.

### Staged paper-aligned packages

The selected approach uses four dependency-ordered packages:

- AF-310 — exact live runtime context management;
- AF-320 — paper benchmark and metric parity;
- AF-330 — complete application and dual-runtime exposure; and
- AF-340 — separately authorized paper experiment reproduction.

Each package produces a useful, independently verifiable product increment and
can close without weakening a later package's evidence standard.

### Documentation-only compatibility

Another option was to rely on Pi's default compaction and merely document the
mapping. This was rejected because generic Pi compaction is not evidence that
the paper's L0–L4 thresholds, turn retention, summarization, and failure
semantics executed.

## Architecture

### Context profile contract

A closed `dci.context-profile/v1` contract will define the supported paper
profiles and their observable settings. The contract contains no prompt,
credential, tool-result body, or mutable runtime path.

| Profile | Tool-result cap | Compaction | Summarization |
|---|---:|---|---|
| L0 | none | none | none |
| L1 | 50,000 characters | none | none |
| L2 | 20,000 characters | none | none |
| L3 | 20,000 characters | trigger above 240,000 accumulated tool-result characters; preserve the most recent 12 turns | none |
| L4 | L3 | L3 | summarize after compaction when estimated context remains above threshold; preserve the most recent 20,000 tokens; stop retrying after three consecutive failures |

Only `level0` through `level4` are valid paper profiles. `level5`, `legacy`,
empty aliases, and unknown values fail validation when paper-aligned execution
is requested.

The Python side owns configuration parsing, request validation, resume
compatibility, artifact projection, and operator errors. A canonical schema and
fixtures prevent the Python and TypeScript representations from drifting.

### Asterion-owned Pi extension

The live policy executes in an Asterion-owned TypeScript Pi extension. Its
authoritative source belongs below `asterion/packages/typescript/`; the Asterion
distribution carries a digest-bound runtime resource loaded with Pi's explicit
`--extension` option.

The extension may use documented Pi extension and compaction hooks, but it may
not patch Pi internals, write into the external checkout, install unreviewed
packages, or depend on user-global Pi state. Asterion resolves the packaged
resource before Pi startup, verifies its path and digest, and passes it as a
literal argv element.

The extension operates before each affected tool result re-enters live model
context. It emits structured telemetry without prompt or result bodies:

- selected profile and contract version;
- per-turn truncation counts and sizes;
- accumulated tool-result pressure;
- compaction trigger and preserved-turn counts;
- summarization attempts, successes, consecutive failures, and suppression;
- before/after context-size estimates; and
- extension version and digest.

The Asterion recorder stores full private evidence where needed and projects
only content-free counters and artifact references through the public
application boundary.

### Resume behavior

The selected profile, contract version, extension digest, and immutable
thresholds become part of native run identity. Resume reconstructs the original
policy and rejects a changed profile, changed extension, malformed policy state,
or incompatible Pi session before another provider request.

Each protocol attempt remains isolated. Existing attempt evidence is never
rewritten. A new attempt can continue the same compatible policy state without
claiming that post-run artifact processing changed prior model context.

### Benchmark and paper metrics

AF-320 extends the existing Asterion benchmark implementation rather than
creating a second runner. It adds:

- BEIR ArguAna and SciFact dataset adapters, profiles, corpus preflight, and IR
  launch commands;
- paper-compatible coverage aggregates;
- paper-compatible localization, including observation alignment for grep/rg,
  file reads, path-only surfacing, and unmatched local text;
- retained-evidence statistics used by context-policy analysis;
- context-policy, restricted-tool, and corpus-scale experiment matrices; and
- deterministic analysis artifacts that bind every value to source run
  evidence and configuration.

For path-only surfacing or text that cannot be reliably localized, the document
still contributes to coverage while localization conservatively uses full
document length. Ambiguous alignment may not be silently promoted to a narrow
snippet.

### Capability and application composition

AF-330 turns the complete DCI product workflow into explicit reusable units.
Research, evaluation, benchmarking, analysis, and export have distinct
implementation ownership and declared event/artifact edges. Applications bind
exact versions of those units to a selected runtime and authorized resources.

The dedicated `asterion-dci` CLI remains the ergonomic product interface, but
it calls the same Asterion domain implementations used by application
composition. The generic `asterion` product surface can discover, describe,
verify, and execute the supported application workflows without duplicating
DCI-specific behavior in framework core.

Pi and Claude Code assemblies share domain contracts. Runtime-specific policy
and security constraints stay in their adapters or application bindings rather
than leaking into generic capability implementations.

### Claude Code semantic boundary

Fixture conformance remains useful but no longer closes semantic parity. A
bounded real Claude Code acceptance must prove:

- terminal access to the selected local corpus;
- no web search or web fetch;
- no subagent delegation;
- no access to answer-bearing data outside the authorized corpus;
- the expected prompt, turn budget, cancellation, and artifact lifecycle; and
- body-free public projection with private retained evidence.

If the installed Claude runtime or current authorization cannot prove those
properties, AF-330 remains honestly incomplete. It may not substitute a fixture
for the bounded semantic result.

## Runtime Data Flow

1. CLI or application input resolves a closed context profile and immutable DCI
   runtime request.
2. Asterion preflights the corpus, provider, external Pi checkout, packaged
   extension resource, schema version, and operator-authorized configuration.
3. Asterion constructs direct Pi argv with the exact extension resource and no
   shell interpolation.
4. Pi loads the extension before the first model request.
5. The extension applies the selected policy to live context and emits
   content-free telemetry alongside the ordinary Pi event stream.
6. The native recorder atomically persists request, policy, events, attempts,
   conversation evidence, final answer, and provenance.
7. Capability implementations emit declared domain artifacts; application
   projection returns only safe references and counters.
8. Evaluation or benchmark consumers validate exact evidence identity before
   computing Judge, QA, IR, coverage, localization, analysis, or reuse results.

## Failure Semantics

### Context policy startup

If a requested paper profile cannot load an exact compatible extension, the run
fails before a model request. Missing files, symlinks, digest mismatch, unknown
schema versions, unavailable hooks, and unexpected extension output all fail
closed. There is no silent fallback to Pi defaults and no successful
`unsupported` status.

### Summarization

An individual L4 summarization failure retains the pre-summary context and
records a safe failure. After three consecutive failures in one session, the
extension suppresses additional summarization attempts while preserving the
rest of L4 behavior. It does not discard history merely to make the run appear
successful.

### Data and metrics

Missing datasets, corpora, gold documents, or incompatible schemas fail during
benchmark preflight. Partial execution remains explicitly partial. Missing or
unreliable observation alignment uses the documented conservative fallback or
marks the metric unavailable; it never fabricates a zero or a precise span.

### Runtime security

Pi or Claude Code runs fail before execution when required tool restrictions,
network restrictions, data isolation, extension integrity, or credential
preflight cannot be established. Public errors never include credentials,
prompts, answers, tool-result bodies, endpoint bodies, or private evidence
paths.

## Verification Strategy

### Model-free tests

- profile schema and cross-language fixture parity;
- exact character, turn, token, and retry thresholds;
- model-visible context before and after each policy transition;
- extension path, digest, argv, and external-checkout isolation;
- resume compatibility and attempt isolation;
- telemetry validation and content-free projection;
- ArguAna and SciFact dataset/profile behavior;
- coverage/localization formulas and every observation fallback;
- capability event/artifact edge validation;
- product CLI, generic application, and isolated-wheel behavior; and
- deterministic experiment-matrix and analysis generation.

Tests must inspect the context delivered to the model fixture. Testing only the
saved `conversation.json` is insufficient.

### Bounded provider acceptance

AF-310 requires bounded Pi evidence that forces and observes L3 compaction and
L4 summarization. AF-320 requires small QA and IR cases, including one BEIR
case, without a full dataset. AF-330 requires bounded Pi and Claude Code
application runs under the declared restrictions.

Provider operations, underlying API request ambiguity, cost, model, external Pi
revision, extension digest, and retained evidence identity are recorded without
credential values.

### Full experiment reproduction

AF-340 alone authorizes full datasets and paper-scale ablations. It runs with a
reviewed budget, fixed configuration, explicit corpus/dataset identities, and
immutable credential-clean result manifests. Reports distinguish successful
reproduction, statistical variation, model/runtime version drift, and external
dependency limitations.

Only AF-340 closure permits the project to claim that the paper experiments,
not merely the implementation, were reproduced.

## Work-Package Acceptance

### AF-310 — Paper-aligned runtime context management

- Asterion owns and ships the exact L0–L4 contract and Pi extension.
- Run, benchmark, resume, installed application, and isolated wheel select the
  same implementation.
- Fixtures prove model-visible context semantics and every failure boundary.
- Bounded Pi runs prove real L3 compaction and L4 summarization.
- External `pi/` remains unmodified.
- Product documentation stops describing unsupported configuration as an
  implementation of live context management.

### AF-320 — Paper benchmark and metric parity

- All thirteen paper datasets have resolvable Asterion execution profiles.
- ArguAna and SciFact execute through the existing IR benchmark path with
  NDCG@10.
- Coverage, localization, retained evidence, and tool-output alignment match
  the paper definitions and conservative fallback.
- Context, tool-profile, and corpus-scale ablations have deterministic bounded
  commands and artifact schemas.
- Full datasets remain outside the closure requirement.

### AF-330 — Complete application and dual-runtime exposure

- Research, evaluation, benchmark, analysis, and export are discoverable
  capability/application units with exact bindings.
- Product CLI and generic applications share implementation and artifact
  identity.
- Pi and Claude Code execute the restricted local-corpus workflow through
  bounded real acceptance.
- Wheel, privacy, cancellation, resume, failure, and security boundaries pass.
- Fixture-only Claude evidence cannot close the package.

### AF-340 — Paper experiment reproduction

- A separately approved budget and configuration cover the paper datasets and
  ablations.
- Every result is traceable to immutable credential-clean native evidence.
- Published-score comparisons state configuration and version differences.
- Documentation distinguishes exact, statistically compatible, divergent, and
  externally blocked results.

## Climb Execution Model

Each package gets a fresh, package-parented Climb session. Existing completed
hypotheses remain historical evidence and are not reused as the new package's
active pool.

- AF-310 hypotheses cover profile schema, extension hooks, model-visible
  transformations, resume, packaging, and bounded runtime evidence.
- AF-320 hypotheses cover dataset additions, metric equivalence, conservative
  alignment, and experiment matrices.
- AF-330 hypotheses cover composition, product-surface parity, Pi restrictions,
  and Claude Code semantic acceptance.
- AF-340 hypotheses cover reproducibility, calibration, variance, and result
  interpretation under the authorized budget.

Every Climb cycle runs the repository scope preflight with its hypothesis ID,
uses isolated artifacts, appends verified or falsified results, regenerates the
research tree, journals the durable outcome, commits cohesive verified changes,
and immediately advances unless a Climb hard-pause condition applies.

Experimental values use explicit flags or environment settings. They do not
change baseline defaults until a verified result is promoted in a separate
commit with baseline revalidation.

## Security and Ownership Invariants

- No production import or process launch from `src/dci`.
- No modification or commit under external `pi/`.
- No untrusted extension discovery; Asterion passes one exact packaged resource.
- No prompt, answer, tool body, credential, or private path in public telemetry.
- No changed context profile during resume.
- No provider request before all configuration, resource, digest, and security
  preflight succeeds.
- No full-dataset execution without separate AF-340 budget authorization.
- No framework scheduler, registry, control plane, or automatic external
  service startup is introduced by this milestone.

## Documentation Requirements

The root README, complete DCI product reference, validation guide, capability
description, and application integration guide must use the four evidence
layers consistently. They must identify the exact paper-supported profiles and
datasets, explain which application executes each function, and keep historical
paper scores separate from newly reproduced results.

## Non-Goals

- Modifying or vendoring Pi.
- Making the original source DCI a compatibility dependency.
- Treating saved-conversation processing as live context management.
- Claiming paper scores from fixture, selector, or bounded-example success.
- Running paper-scale experiments during AF-310, AF-320, or AF-330.
- Generalizing the work into a workflow scheduler or experiment platform.
- Publishing packages or splitting first-party DCI into a second wheel.

## Package Transition Rules

AF-310 may close only after scope preflight, exact local closure, bounded Pi
evidence, independent review, and truthful documentation pass. AF-320 depends
on AF-310; AF-330 depends on AF-320; AF-340 depends on AF-330 and explicit
budget authorization. At each transition, the worklist, structural state,
decision record, journal, Climb state, and recovery checkpoint must name exactly
one active successor or an explicit terminal boundary.
