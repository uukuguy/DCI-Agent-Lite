# Application Runner Vertical Slice Design

> Status: approved direction; blocked on AF-095 Asterion extraction and written-spec revision.

## Goal

Execute one already-resolved `AssemblyPlan` through an explicitly supplied Agent
Runtime Protocol client and explicitly supplied host services. Prove that the
DCI reference application can cross the static-plan-to-runtime boundary without
introducing a general workflow engine, service locator, process manager, or
control plane.

## Chosen approach

Add a small Python application runner under `src/asterion/runner/` over
existing public contracts.

1. **Plan-driven runner — selected.** It consumes an `AssemblyPlan`, runtime
   client, application input, and an explicit host-service mapping. This is the
   smallest end-to-end framework slice after static assembly.
2. **Assembly inspection CLI.** Rejected as the primary next package because it
   improves operability but does not prove that an assembled application runs.
3. **Registry/distribution.** Rejected because no real remote source currently
   requires publishing, installation, or dependency solving.

## Scope

AF-100 executes only the DCI local-research reference application. It validates
the runner boundary with Pi and Claude Code fixture clients through the shared
Agent Runtime Protocol surface. Provider-backed Claude evidence remains deferred
until credentials are available and does not block model-free conformance.

The controlled-code assembly is used only to prove that missing
`executor.controlled` fails before runtime invocation. Running its workflow or
starting the Rust sidecar is outside AF-100.

## Public Python API

Add `src/asterion/runner/application.py` with an asynchronous boundary:

```python
@dataclass(frozen=True)
class ApplicationRunResult:
    application_id: str
    runtime_id: str
    run_id: str
    events: tuple[Mapping[str, object], ...]
    artifacts: tuple[Mapping[str, object], ...]

async def run_application(
    plan: AssemblyPlan,
    *,
    runtime: AgentRuntimeClient,
    run_id: str,
    input_text: str,
    host_services: Mapping[str, object],
    signal: object | None = None,
) -> ApplicationRunResult: ...
```

The concrete annotations may use existing protocol types, but the public API
must not import Pi-, Claude-, or Rust-private classes. The result is an immutable
projection of normalized events and artifacts, not raw provider output.

## Preconditions and ownership

- The caller resolves the assembly before calling the runner.
- `runtime.manifest.runtime_id` must equal `plan.runtime_id`.
- Every host capability declared by the source assembly must have an explicitly
  supplied service implementation. Because `AssemblyPlan` currently stores the
  composed graph rather than source ownership, AF-100 may add immutable
  `runtime_capabilities` and `host_capabilities` fields to the plan. It must not
  infer service ownership from names or merged capability sets.
- Runtime-native capabilities remain owned by the runtime manifest.
- The runner never discovers, imports, constructs, or starts a host service.

## Data flow

1. The caller supplies a validated immutable plan, matching runtime client,
   application input, run identity, and explicit services.
2. The runner checks runtime identity, required host-service presence, run ID,
   input shape, and cancellation state before invoking the runtime.
3. It derives one portable `RunRequest` from the application input and the
   plan's runtime-owned capability requirements.
4. It consumes the runtime's normalized event stream through the existing host
   contract and validates lifecycle ordering with the canonical protocol
   validator.
5. It projects `artifact.created` events into immutable result artifacts and
   returns the full normalized event tuple.

No package is dynamically invoked in AF-100. The package graph establishes the
application contract; the DCI runtime adapter remains the implementation of the
reference research capability for this vertical slice.

## Cancellation and errors

- A signal already cancelled before invocation fails without calling the
  runtime.
- Cancellation during a run is delegated through the existing runtime client's
  signal boundary; the runner accepts only the normalized terminal outcome.
- Runtime mismatch, missing host service, malformed request input, invalid event
  stream, runtime exception, and missing terminal event raise a public
  `ApplicationRunError`.
- Errors identify the structural failure class but do not echo input text,
  prompts, credentials, provider payloads, raw tool output, or service objects.
- Partial normalized events are not returned as a successful result.

## Security boundary

Host-service declarations are requirements, not authorization. Supplying an
object under `executor.controlled` does not authorize commands or make the
runtime a sandbox. AF-100 does not start subprocesses, read credentials, select
providers/models, load packages, execute workflow manifests, retry runs, persist
application data, or expose a remote API.

## Language boundary

Python Asterion owns the first runner because it owns orchestration and the
reference runtime adapters. DCI supplies the first capability integration and
existing `dci-agent-lite` execution baseline; the runner must not recreate DCI
research behavior. TypeScript retains schema/type validation and runtime-client
contracts but does not gain a second runner in AF-100. Rust remains an explicitly
provided controlled-execution service and is not started by the runner.

## Verification

Tests must prove:

- one DCI plan produces a valid request and immutable normalized result;
- Pi and Claude fixture clients produce protocol-equivalent application results;
- runtime mismatch and every missing declared host service fail before runtime
  invocation;
- pre-run and in-run cancellation preserve normalized lifecycle semantics;
- malformed or incomplete event streams and runtime exceptions fail safely;
- application input and provider/service contents never appear in public errors;
- controlled-code cannot run without `executor.controlled`, and the runner never
  starts the Rust service;
- no adapter-private imports, general scheduler, registry, or TypeScript runner
  enter the package;
- full Python, TypeScript, Rust, compile, lint, format, shell, scope, and diff
  gates pass.

## Acceptance

- A resolved DCI application runs once through the shared runtime-client
  boundary and yields immutable normalized events/artifacts.
- Equivalent Pi and Claude fixture runtimes satisfy the same runner contract.
- Runtime capability ownership and host-service injection remain explicit.
- Cancellation and all invalid inputs fail safely without accidental invocation.
- AF-100 adds no general workflow engine, registry, service discovery, process
  management, or remote control plane.

## Revalidation triggers

Propose workflow scheduling only when a second executable application requires
package-level sequencing that cannot be represented by one runtime invocation.
Propose automatic service startup only when a concrete operator workflow cannot
safely supply an already-authorized service. Propose registry/distribution only
when a real remote package source is required.
