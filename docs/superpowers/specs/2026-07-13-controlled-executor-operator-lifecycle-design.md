# Controlled Executor Operator Lifecycle Design

> Status: approved direction; written specification pending review.
>
> Active package: AF-150.

## Goal

Let the installed `asterion run` command execute `code.quality@1.0.0` through an
operator-authorized controlled-executor sidecar while preserving host-owned
policy and deterministic process cleanup.

The operator explicitly supplies three independent inputs:

- controlled-executor binary path;
- Rust trusted-policy JSON path consumed by the sidecar at startup;
- Asterion trusted-validation JSON path containing `program_id`, fixed argument
  prefix, logical executor cwd, deadline, and output limit.

There is no binary, policy, socket, service, or configuration discovery.

## CLI contract

Add run-only options:

```text
--executor-binary PATH
--executor-policy PATH
--executor-validation-config PATH
```

The three options form one closed mode: either all are absent or all are
present. They are required when the selected application plan declares
`executor.controlled` and rejected when it does not. Environment-backed defaults
may use `ASTERION_EXECUTOR_BINARY`, `ASTERION_EXECUTOR_POLICY`, and
`ASTERION_EXECUTOR_VALIDATION_CONFIG`; CLI values take precedence. Values and
resolved paths are never printed.

Path validation rejects missing files, directories, symlinks, and invalid JSON
before process startup. The binary must be an existing canonical regular file;
AF-150 does not search `PATH`. Policy content is owned and validated by Rust;
Asterion only checks that it is a readable JSON object without persisting or
echoing it. Validation configuration uses the existing closed
`TrustedValidationConfig` fields and protocol limits.

## Lifecycle order

The command order is fixed:

1. Parse CLI and selection mode.
2. Load and validate only the selected provider.
3. Select application/assembly and validate runtime compatibility.
4. Resolve catalog/assembly and validate exact package bindings.
5. Determine required host services from the resolved plan.
6. Validate the complete operator executor configuration.
7. Construct the selected runtime.
8. Start the controlled-executor subprocess directly as
   `[binary, policy_path]`, with no shell.
9. Establish caller-owned stdin/stdout streams and verify readiness.
10. Inject one `ControlledExecutorJsonlClient` as `executor.controlled`.
11. Run the composed application.
12. Close stdin, wait briefly for clean EOF shutdown, then terminate/kill and
    reap if needed.

No sidecar starts before all portable/provider/binding/configuration preflight.
The generic runner remains process-agnostic; lifecycle ownership lives in the
CLI host layer and a focused managed-sidecar module.

## Readiness

The current Rust JSONL protocol has no health request. AF-150 therefore defines
readiness narrowly: subprocess creation succeeds, stdin/stdout pipes exist, and
the process remains alive through one event-loop checkpoint. This proves only
transport availability, not policy correctness. The first execute response is
the authoritative policy/protocol check.

AF-150 does not add an ad hoc health message to `dci.executor/v1`. A future
versioned protocol may add health/capabilities when multiple service backends
need negotiation.

## Cancellation and shutdown

Application cancellation is forwarded to the JSONL client. If an execution is
in flight, the client sends the existing correlated cancel request and waits for
the terminal execution result. Command cancellation or any exception then enters
the same shutdown path.

Shutdown is idempotent:

- close stdin;
- wait up to a fixed one-second grace period;
- terminate and wait up to one second;
- kill and reap if still alive;
- drain bounded stderr without exposing it.

The command returns only after the child is reaped. It never leaves a detached
service and never reuses a sidecar across CLI invocations.

## Security and privacy

The operator, not provider/application/agent input, authorizes executable and
policy paths. Provider values and portable manifests cannot set lifecycle
configuration. The subprocess is spawned with a direct argument vector and an
explicit minimal environment; credentials and the caller's general environment
are not forwarded.

Public failures distinguish configuration, startup, readiness, transport,
application, and shutdown classes without including:

- paths or file contents;
- binary/policy/config values;
- source target or application input;
- environment names/values or credentials;
- child stderr/stdout or protocol payloads;
- process reprs, tracebacks, or return payload bodies.

The Rust process remains policy enforcement, not OS sandboxing.

## Components

- `ManagedControlledExecutor` owns subprocess start/readiness/shutdown and
  yields a `ControlledExecutorJsonlClient`.
- `OperatorExecutorConfig` validates the three canonical files plus trusted
  validation fields.
- CLI application execution accepts explicit host services internally so the
  managed client is injected without changing provider contracts.
- Tests use fake subprocesses and the real Rust binary model-free operator test;
  no provider credentials are required.

## Verification

Tests must prove:

- incomplete, irrelevant, missing, symlinked, directory, malformed, or unsafe
  configuration fails before runtime/sidecar construction;
- direct argv is exactly binary plus policy path and never uses a shell;
- child environment is minimal and contains no credential sentinel;
- readiness rejects immediate exit and missing pipes;
- selected controlled-code run injects exactly one service after all preflight;
- DCI runs reject executor lifecycle flags and never start a sidecar;
- cancellation uses correlated protocol cancellation and every path reaps child;
- EOF, terminate, and kill fallback paths are deterministic and idempotent;
- stderr/protocol/config/input sentinels never enter public errors or output;
- isolated installed-wheel execution can run against a fixture sidecar and list
  both providers while `dci` remains unavailable;
- all Python, Node, Rust, compile, lint, shell, scope, and diff gates pass.

## Acceptance

- The generic installed CLI can run the controlled-code application with one
  explicit operator-authorized sidecar lifecycle.
- All service authority is validated before startup and no service is discovered
  or silently reused.
- The child is reaped on success, failure, cancellation, and malformed protocol.
- No new protocol message, scheduler, daemon, socket transport, remote worker,
  arbitrary wrapper command, or sandbox claim is introduced.

## Revalidation triggers

Add connect-only transport when an external supervisor is a concrete deployment
requirement. Add health/capability negotiation only through a versioned executor
protocol. Add persistent service reuse only with explicit tenancy, isolation,
correlation, recovery, and shutdown ownership.
