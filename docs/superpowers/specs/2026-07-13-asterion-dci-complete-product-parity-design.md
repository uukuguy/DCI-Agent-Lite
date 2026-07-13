# Asterion DCI Complete Product Parity Design

## Goal

Make `asterion-dci` and the installed `asterion` DCI application a complete,
independently implemented DCI product whose default runtime is Pi.  The target
is behavioral coverage of the repository's source DCI product, not merely a
matching list of modules or a completed worklist entry.

`src/dci` remains the independent comparison baseline.  Asterion must neither
import it nor execute its Python modules at runtime.  The source product stays
available for controlled comparison, and future small source-product
adaptations are allowed only when they preserve its primary behavior and are
captured in the parity matrix.

## Configuration and ownership

The repository `.env` is one shared process configuration surface.  Both
products use the same Pi checkout, provider/model selection, Pi authentication
environment, RPC deadline, judge configuration, and pricing variables:

- `DCI_PI_DIR`, `DCI_PI_PACKAGE_DIR`, and `DCI_PI_AGENT_DIR` select Pi;
- `DCI_PROVIDER`, `DCI_MODEL`, and `DCI_RPC_TIMEOUT_SECONDS` supply normal
  agent defaults;
- `DCI_EVAL_JUDGE_*` supplies the evaluator; and
- normal Pi/provider environment variables remain inherited by the Pi child.

Explicit command-line values take precedence over inherited values, and an
already-exported process variable takes precedence over `.env`, matching the
existing product behavior.  `ASTERION_DCI_OUTPUT_ROOT` remains an
Asterion-only output-location override.  Existing `ASTERION_DCI_PI_*` path
variables remain backward-compatible aliases while documentation moves normal
operation to the shared `DCI_*` names; they must not create a second required
configuration surface.

The generic `asterion` CLI remains domain-neutral.  The first-party DCI
provider owns environment-to-request mapping for the installed application;
thus `asterion run --provider dci-agent-lite --runtime pi.reference` receives
the same effective Pi configuration as `asterion-dci run` without adding
DCI-specific flags to generic framework code.

## Functional surface

The migration is measured against this source-product matrix, with an
Asterion-owned entry point for every row.

| Source behavior | Asterion product entry point | Required parity |
|---|---|---|
| Interactive RPC run, stdin/question-file input, provider/model/tools, deadline, system prompt, extra Pi arguments, session controls, terminal mode | `asterion-dci run` / `asterion-dci terminal` | Same effective Pi argv and lifecycle semantics, subject to Asterion-owned code. |
| Context-management level, thinking level, Node heap, conversation processing controls | `asterion-dci run` and shared DCI runtime options | Use only controls advertised by the current Pi; record a requested but unavailable runtime-context level as an explicit native diagnostic, while thinking, heap, and conversation controls remain effective. |
| Native run directory, raw events, transcript, final answer, state, stderr, provenance, compatible resume | `asterion-dci run` / `resume` | Schema-level comparison after normalizing timestamps, paths, and IDs. |
| Explicit single-run judging and cache-safe reuse | `asterion-dci run --eval-*` / `evaluate` | Equivalent safe request shaping, cache identity, and result fields. |
| BCPlus/QA/BRIGHT batches: limits, concurrency, IR mode, corpus hints, metrics, summaries, exports | `asterion-dci benchmark` and Asterion launchers | Equivalent dataset handling, resumable per-query results, aggregate outputs, and supported IR metrics. |
| Corpus export helpers | `asterion-dci export bcplus|bright` | Same supported source-data-to-corpus transforms and safe failures. |
| Basic and runtime-context examples | `scripts/examples/asterion_dci_*.sh` | Executable Pi-default examples with the same questions/corpora and shared `.env`. |
| Installed application execution | `asterion run --provider dci-agent-lite --runtime pi.reference ...` | Same native request configuration and body-free framework projection as the package CLI. |

The package command may use clearer Asterion spelling where necessary, but
each source option must have a documented mapping or an explicit, tested
replacement.  No source behavior is considered migrated merely because an
unstructured `--extra-arg` can approximate it.

## Architecture

Add one immutable package-local `DciRuntimeOptions` value that resolves shared
configuration and explicit overrides.  Both package CLI requests, batch rows,
and the provider-owned application executor construct this value; native Pi
transport receives it without generic Asterion modules understanding DCI.

Retain the current direct Pi JSONL transport and native artifact boundary, but
complete the artifact recorder where it is presently only partial.  Batch work
must reuse the same native run and evaluator paths, run bounded concurrent
workers, and persist per-query state before aggregate reports.  Output bodies
remain in the native run directory only; framework-facing events and artifacts
continue to expose references rather than bodies.

Keep the original shell launchers unchanged.  Add Asterion-named launchers and
document their one-to-one correspondence.  This provides a repeatable product
acceptance path without making Asterion depend on the baseline scripts.

## Governed delivery

This is a dependent delivery chain, not a one-commit claim of completion:

1. **AF-220 — Shared configuration and runnable Pi application parity.**
   Establish the common `.env` configuration contract, map it into package,
   batch, and installed-application requests, and add the two Asterion Pi
   example scripts.
2. **AF-230 — Complete native operator and artifact parity.**
   Close remaining single-run, terminal, context/resource, artifact,
   provenance, and resume controls.
3. **AF-240 — Complete batch, evaluation, and export parity.**
   Transplant concurrent BCPlus/QA/BRIGHT behavior, IR metrics, exports,
   summaries, and result analysis into Asterion-owned code.
4. **AF-250 — Product acceptance matrix.**
   Make every matrix row executable and record reproducible local, Pi, and
   Pi-plus-Judge evidence.  The final conclusion is allowed only if the matrix
   has no unsupported source behavior.

Only one package is active at a time.  Each package carries its own approved
plan and Climb hypotheses; later packages do not redefine this contract.

## Verification and completion evidence

Automated verification must include a checked-in parity matrix that exercises
all parser/configuration mappings, artifact schemas, resume/cache behavior,
batch result formats, export transforms, and installed-wheel boundaries using
fixtures or fake Pi/Judge transports.  Tests compare stable semantics, not
model prose or volatile timings.

Provider-backed acceptance is authorized for bounded real checks:

1. run each Asterion example once through real Pi;
2. run the installed Asterion DCI application once through real Pi;
3. run one-row Asterion benchmark through real Pi plus the configured Judge;
4. retain safe native artifacts and record commands, effective non-secret
   configuration names, exit status, and verdict in the journal.

Full external datasets are not started automatically because they can be
costly.  Instead, each Asterion batch launcher must be runnable, receive a
small-sample real check where its dataset/corpus is available, and expose an
operator command for a deliberate full evaluation.  Completion requires all
local matrix rows and the authorized bounded real checks; a failed or
unavailable provider check is recorded as a failed acceptance item rather than
silently replaced by fixture evidence.

## Boundaries

- Do not modify or import `src/dci` as part of Asterion implementation.
- Do not edit the external `pi/` checkout.
- Do not add DCI parsing or defaults to generic framework CLI/runner modules.
- Do not persist credentials, provider response bodies, or hidden request
  payloads in framework projections or evaluation caches.
- Do not claim output-text equality across separate real model runs; validate
  lifecycle, artifacts, evaluator verdicts, and documented configuration
  mapping instead.
