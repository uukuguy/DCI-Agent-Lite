# Complete Asterion DCI Capability Package Design

> Status: approved; AF-180 implementation plan written.
>
> Active package: AF-180.

## Goal

Make the Asterion DCI capability package the complete, independent successor
implementation of the existing DCI product.  Future DCI research changes land
in that Asterion-owned package.  The existing `src/dci` product remains intact
as an independent, source-only comparison baseline; neither product imports,
launches, nor discovers the other at runtime.

This is the first complete example of Asterion's intended capability-package
model: a package owns a full domain implementation internally, exposes only a
portable capability contract to the framework, and becomes a finished AI
application when an Asterion application assembly selects its runtime and host
boundaries.

## Chosen approach

Transplant the original DCI implementation by functional domain, preserving
its established behavior and on-disk formats before making targeted Asterion
boundary adaptations.  A rewrite is rejected because it would needlessly risk
the mature runner, Pi lifecycle, artifacts, resume, judge, cache, and benchmark
semantics.  Calling or importing `src/dci` is rejected because it would not
produce an independent product.

The repository continues to ship one `asterion` wheel.  The complete DCI
implementation is an independently owned module tree inside that wheel, not a
second first-party distribution.  That preserves D-030 while keeping the old
DCI product and the Asterion DCI capability package independent.

## Architecture and ownership

`asterion-core` remains domain-neutral.  It owns the Agent Runtime Protocol,
runtime factories, selected-provider/application resolution, composition,
application execution, and generic event/artifact abstractions.  It must not
import DCI domain code or contain DCI CLI behavior.

The Asterion wheel gains an Asterion-owned DCI domain module (target namespace
`asterion.dci`) with these internal domains:

1. run orchestration, Pi JSONL RPC control, system-prompt construction, corpus
   workspace/tool policy, and final-answer capture;
2. durable raw-event, transcript, final-answer, state, output-directory, and
   resume behavior;
3. judge configuration, safe request shaping, response validation, result
   fingerprint/cache handling, and evaluation artifacts;
4. dataset/batch benchmark orchestration and result/export behavior; and
5. a package-local CLI for run, resume, evaluate, and benchmark operations.

The existing `asterion.capabilities.dci_research` and
`asterion.applications.dci_agent_lite` remain the framework-facing contract and
application-composition layers.  Their implementation bridge turns an
`ApplicationExecutionContext` into an Asterion DCI request, executes the full
domain workflow, retains native DCI artifacts, and projects selected durable
outputs into the canonical Asterion event/artifact stream.  It must not replace
the actual final answer with a synthetic summary.

The normal researcher-facing command is a package-local `asterion-dci` command
family, such as `asterion-dci run`, `resume`, `evaluate`, and `benchmark`.
This prevents DCI-specific parsing from entering the generic `asterion` CLI.
The existing generic `asterion run` remains the framework application entry
point and can invoke the same capability implementation through its declared
application assembly.

## Contract and data flow

The capability contract exposes portable input, required runtime capability,
declared events, and artifact identities.  It does not expose Pi command-line
arguments, system-prompt details, judge credentials, or private directories.

At runtime, the application assembly selects the exact Pi or Claude runtime
and the capability implementation.  The DCI implementation then performs the
complete domain workflow and writes its own native run artifacts.  The bridge
creates Asterion artifacts for the final answer, raw-event transcript, run
state/resume metadata, and evaluation result where applicable.  Asterion
consumers use the normalized projection; researchers retain the native DCI
artifact directory for investigation.

The original DCI's Pi behavior is the mandatory full-parity baseline.  A
Claude runtime receives the same capability declaration only when the package
can express the same DCI contract.  The existing fixture-only Claude proof is
not evidence of full DCI semantic parity and cannot substitute for it.

## Configuration, persistence, and safety

The new package owns an `ASTERION_DCI_*` configuration namespace and a separate
default output root.  A narrow migration adapter maps that external
configuration into near-original internal DCI configuration objects, minimizing
changes to transplanted logic.  It may reuse safe values from a repository
`.env`, but it does not share an output root or rely on `DCI_*` settings owned
by the old product.

Credentials are environment-only.  Manifests, normalized events, cache
identity, logs, exports, and artifacts must not contain credentials, credential
derivatives, raw provider errors, unbounded protected stderr, or private input
echoes.  Public failures identify a safe structural class only.  Native
diagnostics remain subject to the existing protected-artifact policy.

## Migration work packages

The implementation is deliberately decomposed; each package has a behavioral
parity boundary rather than a code-volume target.

1. **AF-180 — execution and interactive-run parity.**  Establish the
   independently owned Asterion DCI domain module, transplant the original run
   path, and provide the new package-local CLI with Pi single-run parity.
2. **AF-190 — durable run and resume parity.**  Transplant output/state/
   transcript/final-answer artifacts and resume validation, then project them
   into Asterion artifacts/events without losing native evidence.
3. **AF-200 — evaluation and benchmark parity.**  Transplant judge, safe
   cache identity, dataset batch orchestration, exports, and their operator
   entry points so they reuse AF-180's execution implementation.
4. **AF-210 — complete application integration and runtime semantics.**
   Execute the same package through Asterion application assemblies, establish
   complete Pi parity, and evaluate Claude semantic parity only through
   authorized provider-backed evidence.

No batch evaluator, judge change, or Climb hypothesis may run until its active
package is planned and the scope audit passes.

## Verification and acceptance

Completion is determined by a functional-parity matrix.  Every public old DCI
behavior for running, artifacts, final answer, resume, judge, cache, batch
benchmark, and export has an Asterion DCI entry point and a focused comparison
test.  Stable fixture comparisons normalize volatile timestamps, run IDs, and
absolute paths, but compare the remaining artifact schema, final answer, and
cache-reuse verdict exactly.

Tests cover successful runs, safe failures, cancellation, resume, unavailable
judge, and cache invalidation.  Unit/fixture tests form the repeatable local
gate.  Real Pi or judge invocations remain explicitly credential-authorized
end-to-end checks.  A future provider-backed Claude claim requires its own
authorized semantic-parity evidence.

The final Asterion DCI package is complete only when all four migration
packages pass, `src/dci` is absent from the Asterion runtime dependency graph,
the generic framework remains DCI-neutral, and the full repository verification
gate passes.

## Non-goals

- Do not rewrite or modify the old DCI product as part of the migration.
- Do not make `src/dci` a compatibility shim, a subprocess dependency, or a
  hidden import of Asterion DCI.
- Do not add a second first-party wheel, registry, remote installation model,
  workflow scheduler, or generic DCI-specific framework behavior.
- Do not claim Claude parity from fixtures or send provider requests without
  explicit operator authorization.

## Revalidation triggers

Split `asterion.dci` into its own distribution only for a concrete independent
consumer/deployment requirement.  Change native artifact formats only with an
explicit migration and comparison policy.  Add a runtime-specific DCI behavior
only when its capability-contract difference is documented and tested.
