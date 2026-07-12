# Composable Capability Execution Design

> Status: approved, including the AF-110/AF-120 split discovered during plan review.
>
> Governance parent: AF-100 successor transition. Proposed successor: AF-110.

## Goal

Establish Asterion as a compositional agent-application framework in which a
capability package is a reusable executable function and an application is the
boundary that combines exact package versions, a runtime, host services, and
operator input into one executable product.

Prove the model with a real local-corpus research implementation supplied by
the DCI capability package. The existing `src/dci/benchmark/` implementation
and `dci-agent-lite` command remain an independent upstream baseline and are
not imported, wrapped, or modified by Asterion.

## Architectural position

Asterion has four distinct layers:

1. A **package manifest** declares portable capabilities, policies, events, and
   artifacts. It remains runtime-neutral and contains no executable values.
2. A **package implementation** supplies executable behavior for one exact
   `package_id@version` through an Asterion-owned contract.
3. An **application manifest** selects exact packages and binds their portable
   graph to one runtime identity and explicit host-service requirements.
4. The **application host and runner** resolve the application, inject runtime,
   implementation, service, and input dependencies, and execute the resolved
   graph.

A package may provide a useful function on its own or participate in a larger
composition. It is not itself the process-level application boundary. Policy,
evaluation, memory, workflow, and observability packages therefore remain
first-class compositional units rather than being forced into independent
application processes.

## Alternatives considered

### Capability package as application

Rejected. It makes simple capabilities easy to launch but forces policy,
evaluation, memory, and observability packages to pretend to be applications.
It also obscures where runtime configuration, input, services, and lifecycle
belong.

### Capability package as application-private plug-in

Rejected. Application code would own invocation order and adapter details,
leaving package manifests as descriptive metadata rather than enforceable,
reusable boundaries.

### Reusable executable package plus application composition

Selected. Package behavior stays reusable and application-independent while
the application remains the explicit executable and operational boundary.

## Scope

AF-110 will define the package-implementation contract and prove one real
vertical slice: execute the DCI `research.local-corpus` capability as part of an
Asterion application.

The slice includes:

- an Asterion-owned asynchronous package-implementation interface;
- exact `package_id@version` implementation registration;
- deterministic execution of the supported resolved package path;
- explicit injection of application input, runtime client, cancellation, and
  host services;
- normalized event and artifact validation at package boundaries;
- a DCI-owned local-corpus research implementation outside
  `src/dci/benchmark/`;
- provider-backed Pi integration and credential-free Claude fixture parity;
- an external baseline comparison that invokes, but never imports or wraps,
  the existing `dci-agent-lite` command.

The initial executable application may select only the subset of packages that
have real implementations. A package with no implementation must be rejected
as non-executable; it must not be represented by a no-op or fabricated result.

## Package implementation contract

Each executable implementation is bound to one exact package identity. The
public contract will be asynchronous and use only Asterion protocol types. Its
concrete Python shape will be finalized in the implementation plan, but it must
carry these semantic inputs:

- the exact package identity and resolved package declaration;
- immutable application input;
- immutable upstream normalized artifacts;
- the explicitly selected `AgentRuntimeClient`;
- explicit host-service objects authorized by the application host;
- an optional read-only cancellation signal.

It returns only normalized events and artifacts declared by the package
manifest. Provider-native responses, mutable service objects, prompts,
credentials, and adapter-private types cannot cross the public result boundary.

Implementations are registered explicitly by exact `package_id@version`.
Duplicate registrations and missing implementations fail before execution.
There is no import scanning, entry-point discovery, registry lookup, version
range solving, or implicit highest-version selection in AF-110.

## Execution model

The runner consumes an already validated `AssemblyPlan` and an explicit
implementation mapping. It uses the package composition's deterministic order
and performs these steps:

1. Validate runtime identity, implementation coverage, host-service coverage,
   package declarations, input shape, and cancellation state.
2. For each supported executable package in deterministic topological order,
   construct an immutable invocation from declared inputs and prior artifacts.
3. Await the implementation and validate every returned event and artifact
   against the package's declarations.
4. Make validated outputs available only to downstream packages that declare
   compatible consumption edges.
5. Stop on failure or cancellation; otherwise project the application-level
   normalized events and artifacts into an immutable result.

AF-110 supports only a deterministic sequential traversal. Parallel scheduling,
dynamic branches, retries, checkpoints, recovery, persistence, and distributed
execution are outside scope.

## DCI capability integration

The DCI research implementation belongs to the capability product area, not to
the original benchmark runner. It implements the portable
`research.local-corpus` behavior through the package contract and receives all
runtime and filesystem context explicitly.

The implementation must not import anything under `dci.benchmark`. A source
boundary test will enforce that neither Asterion nor its DCI capability
implementation depends on `src/dci/benchmark/`.

The same DCI research package must be reusable in at least two assembly
contexts: the checked-in DCI local-research application and a focused test
application with a different surrounding package set. This proves that the
implementation is attached to the capability package rather than hidden in one
application entry point.

The existing `dci-agent-lite` command remains unchanged and serves only as an
external behavioral baseline. Shared questions and corpora are allowed;
shared benchmark execution code is not.

## Explicit application host

AF-110 verifies execution through an explicit Python composition root owned by
the test/reference application host. The host constructs the package
implementation mapping directly and passes it to the Asterion runner. Asterion
core does not import DCI, and the package manifest does not name an executable
Python module.

This explicit host is an architectural seam, not the final distribution or
operator interface. It proves that an application can bind independently owned
capability implementations without making Asterion core depend on them.

## Deferred AF-120 application binding

The generic `asterion run <assembly>` command is deferred to AF-120 because a
generic process cannot obtain independently distributed implementation objects
without an explicit and security-reviewed binding mechanism. AF-120 will decide
how installed applications supply implementation registries, considering
installation-time entry points, explicit host modules, or signed bundles without
silently introducing arbitrary dynamic imports.

AF-110 therefore adds no CLI, automatic provider selection, implicit service
discovery, automatic service startup, package installation, remote registry,
dynamic import, or DCI-specific executable. Normal runtime configuration remains
on the repository `.env` surface or explicit test-host arguments, without
persisting or printing credentials.

## Cancellation and failures

Cancellation propagates from the application host through the runner and
package implementation to the runtime client. A pre-cancelled invocation starts
nothing. Cancellation during one package prevents all later packages from
starting.

Public failures identify only structural information such as application ID,
package ID, execution phase, and failure class. They must not echo application
input, corpus contents, prompts, credentials, provider payloads, raw tool
output, implementation objects, or service objects.

The system fails closed on at least:

- runtime identity mismatch;
- missing or duplicate exact implementation bindings;
- missing host service;
- undeclared or incompatible upstream artifact input;
- undeclared event or artifact output;
- malformed or incomplete runtime lifecycle;
- implementation exception;
- cancellation before or during execution.

Preflight failures occur before any implementation or runtime invocation.
Partial outputs are not returned as successful application results.

## Security boundary

Package declarations establish compatibility, not authorization. A declared
capability or supplied service does not authorize arbitrary commands,
environment access, filesystem roots, or network operations. Those permissions
remain owned by the runtime and host-service policy boundaries.

Package manifests and application manifests cannot contain prompts,
credentials, executable paths, commands, environment variables, provider
payloads, or mutable state. AF-110 does not treat the controlled executor as an
operating-system sandbox and does not accept executable policy from application
input or agent requests.

## Language ownership

Python owns the first implementation registry and executor because Python owns
the reference composer, assembly resolver, orchestration, and DCI research
integration. TypeScript continues to validate shared schemas and public host
types without gaining a second package executor. Rust remains an explicitly
provided controlled-execution service and is not started by the package runner.

The public package protocol literals remain stable in AF-110 even where they
currently use the `dci.*` prefix. Renaming wire protocols is a separate versioned
compatibility decision, not part of capability execution.

## Verification

Tests must prove:

- exact implementation binding is deterministic and fails closed on missing or
  duplicate identities;
- one DCI research package executes through the public package contract and
  returns only declared normalized events and artifacts;
- the same DCI implementation is reusable across two application compositions;
- provider-backed Pi and a credential-free Claude fixture satisfy the same
  implementation boundary without package-level adapter branching;
- application, package, runtime, service, event, artifact, and cancellation
  mismatches fail before unintended work;
- later packages do not start after failure or cancellation;
- errors redact application, corpus, provider, credential, tool, and service
  content;
- an explicit application-host composition root executes the selected
  application without Asterion importing or modifying the baseline runner;
- Asterion and capability implementation sources do not import
  `dci.benchmark`;
- the existing `dci-agent-lite` command and example scripts remain unchanged;
- an external comparison can run baseline and Asterion paths over the same
  corpus/question without shared execution code;
- all Python unit, compilation, Ruff, TypeScript, Rust, shell, scope, and diff
  gates pass.

The comparison does not require identical provider reasoning traces. It checks
protocol conformance, declared capability behavior, normalized artifacts, final
answer quality, and observable lifecycle boundaries.

## Acceptance

- Asterion has a public reusable package-implementation contract rather than an
  application-private DCI hook.
- An application deterministically composes and executes a real DCI research
  capability through that contract.
- The DCI implementation works through Pi and Claude fixture runtime clients
  without adapter-private package behavior.
- The same capability implementation is reusable across application contexts.
- The original DCI benchmark implementation and CLI remain unchanged and
  independent as the baseline.
- An explicit application-host composition root runs the reference application
  without workflow-engine, registry, dynamic-import, automatic service,
  persistence, or control-plane scope.
- Generic installed-application binding and `asterion run <assembly>` remain a
  separately governed AF-120 concern.

## Revalidation triggers

Add parallel scheduling only when two independently executable package branches
have a measured need for concurrency. Add persistence or recovery only when a
real application cannot safely restart a deterministic package traversal. Add
dynamic discovery or a registry only when an external package distribution
source exists. Version or rename the `dci.*` wire protocols only through a
separate public compatibility decision.
