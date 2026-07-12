# Controlled Code Validation Packages Design

> Status: approved design for the next package-first framework increment after AF-060.

## Goal

Prove that `dci.package/v1` can express a second independently useful package
graph: controlled local code validation. The graph combines an execution policy,
a code-quality workflow, execution audit observability, and compliance evaluation
without adding workflow execution or adapter-private package variants.

## Why this graph is next

AF-060 proved a policy → research → evaluation → observability graph for DCI.
The next increment should challenge the same static contract with a materially
different dependency shape and the previously unused `workflow` kind before any
execution engine is considered.

Three approaches were considered:

1. **Portable manifests plus static composition — selected.** Reuse the existing
   schema, Python composer, TypeScript validator, and normalized host edges. This
   tests the package abstraction directly at the smallest scope.
2. **Connect the composer to the Rust executor.** This would conflate graph
   validation with execution semantics before the package contract has failed to
   express a second graph.
3. **Build a package registry/catalog.** Discovery and distribution are useful
   later, but a registry would add infrastructure without increasing confidence
   in the composition semantics.

## Package graph

The reference graph contains four runtime-neutral manifests:

- `policy.controlled-code-check` (`policy`) provides the policy edge authorizing
  controlled code checks.
- `workflow.code-quality` (`workflow`) requires `filesystem.read`,
  `executor.controlled`, and `policy.controlled-code-check`; it consumes source
  input, emits `workflow.code-quality.completed`, and produces a code-quality
  report.
- `observability.execution-audit` (`observability`) consumes the workflow
  completion event plus portable executor/tool lifecycle events and produces an
  execution-audit artifact.
- `evaluation.code-quality` (`evaluation`) consumes the code-quality report and
  produces a compliance verdict.

All IDs, event names, and artifact media types are portable contract values. The
manifests contain no program path, command, argument vector, environment value,
workspace path, provider setting, prompt, credential, or adapter-private type.

## Static composition boundary

The Python reference composer receives the four manifests plus host-provided
capability, event, and artifact edges. It validates and deterministically orders
the graph, then returns the existing immutable `PackageComposition` summary.

Composition does not spawn the Rust sidecar, authorize a concrete execute
request, invoke a runtime, schedule workflow steps, or inspect a source tree. The
Rust executor remains the implementation boundary behind the portable
`executor.controlled` capability. The host combines each runtime adapter's
normalized capabilities with the same controlled-executor service capability;
neither Pi nor Claude Code claims that capability natively or receives a
package-specific variant.

The TypeScript host validates the canonical schema and every checked-in manifest.
It does not implement a second graph resolver.

## Data flow

1. A host combines a runtime adapter that advertises `filesystem.read` with a
   controlled-executor service that advertises `executor.controlled`, plus the
   portable executor/tool lifecycle events required by the audit package.
2. The composer validates each closed manifest against `dci.package/v1`.
3. Capability, policy, event, and artifact providers are indexed using the
   existing ambiguity rules.
4. The composer resolves the policy before the workflow and resolves report and
   workflow-completion-event consumers after it in a deterministic DAG.
5. The caller receives only package IDs and normalized provided/emitted/produced
   edges. A future execution layer may consume that summary without changing its
   identities or policy semantics.

## Failure behavior

Composition must reject:

- a host missing `filesystem.read` or `executor.controlled`;
- a missing controlled-code-check policy provider;
- a missing executor/tool event required by execution audit;
- a missing code-quality report required by evaluation;
- duplicate package IDs or ambiguous providers;
- dependency cycles; and
- any non-portable or unknown manifest field through the existing closed schema.

Permuting manifest input must not change the composition result. Error messages
remain safe structural diagnostics and must not include source content,
credentials, commands, environment values, or provider payloads.

## Verification strategy

Python tests will prove:

- all four new manifests satisfy the shared closed contract;
- the controlled-code graph composes in one stable order under input
  permutations;
- Pi and Claude Code normalized runtime edges, each combined with the same
  controlled-executor host service edges, produce the same result;
- the graph exposes the expected report, verdict, and audit artifacts; and
- every missing capability, policy, event, or artifact boundary is rejected.

TypeScript tests will load and validate every checked-in reference manifest with
the canonical copied schema. Existing composer rejection tests remain the
regression suite for ambiguity and cycles. Closure requires fresh full Python,
TypeScript, and Rust tests plus Python compilation, Ruff, Rust formatting,
Clippy, shell syntax, scope audit, and `git diff --check`.

## Non-goals

- No real command execution or automatic code repair.
- No workflow scheduler, step runner, prompt DSL, or retry engine.
- No new executor wire fields or claim of operating-system sandboxing.
- No persistent memory, remote worker, registry service, package installation,
  authentication, tenancy, or enterprise control plane.
- No provider-backed model call and no claim of identical native runtime
  behavior.

## Acceptance

- A second independent graph uses `policy`, `workflow`, `observability`, and
  `evaluation` packages through declared portable edges.
- The graph composes deterministically for equivalent Pi and Claude Code
  capability sets and rejects every missing boundary.
- Python and TypeScript validate the same canonical manifests without a second
  composer.
- Documentation states that the graph is static composition, not execution.
- Every repository closure gate passes with fresh evidence.

Successful acceptance revalidates D-022 in favor of static composition: because
the second graph is expressible, it does not trigger a workflow execution engine.
