# Rust Controlled Executor Boundary Design

> Status: approved for autonomous AF-050 delivery.

## Goal

Add a small Rust sidecar that executes explicitly authorized local programs for agent tools while Python and TypeScript remain responsible for orchestration, runtime adapters, prompts, workflows, and model access.

## Honest security boundary

Version 1 is a policy-enforcing process executor, not an operating-system sandbox. It prevents shell interpretation, ambient child environment, unregistered executables, unbounded execution time, and unbounded captured output. It does not claim to prevent an allowed executable from opening absolute paths, using the network, spawning descendants, or invoking platform syscalls.

Stronger containment—containers, macOS sandbox profiles, Linux namespaces/seccomp/cgroups, Windows job objects, or a remote worker—must be a replaceable executor backend behind this contract. Documentation and event names must not call the v1 local backend a sandbox.

## Trust split

Trusted operator configuration is loaded once when the sidecar starts:

- canonical workspace root;
- map of stable `program_id` values to canonical absolute executable paths;
- maximum deadline, output bytes, and concurrent executions.

Agent-controlled requests cannot provide executable paths, environment variables, shell strings, policy changes, or workspace roots. A request names one registered program, an argument vector, a workspace-relative existing directory, a bounded deadline, and a bounded output limit.

The child is launched directly without a shell, with stdin closed and the environment cleared. The configured absolute executable path is used directly; `PATH` lookup is never part of authorization.

## Protocol

The sidecar uses newline-delimited JSON over stdin/stdout under a separate `dci.executor/v1` namespace. This is a tool-execution boundary beneath Agent Runtime Protocol, not another agent runtime.

### Execute request

- `protocol`, `request_id`, `type: "execute"`;
- `program_id` and `arguments`;
- `cwd` relative to the configured workspace;
- `deadline_ms` and `max_output_bytes`, each no greater than policy.

### Cancel request

- `protocol`, unique control `request_id`, `type: "cancel"`;
- `target_request_id` of an in-flight execution.

The input loop remains responsive while children run. Results are correlated by request ID and may be emitted out of order. A cancel request receives an acknowledgement, and the target eventually receives exactly one terminal execution result.

### Responses

Execution results use status `completed`, `failed`, `timed_out`, `cancelled`, or `denied`; optional exit code; bounded UTF-8-lossy stdout/stderr; and independent truncation flags. Cancel acknowledgements report whether the target was in flight. Protocol/parse failures produce safe error responses without echoing the full input line.

## Path, deadline, and output enforcement

- Canonicalize the requested working directory and require it to remain at or below the canonical workspace root.
- Reject missing directories and traversal before spawning.
- Reject duplicate in-flight request IDs and requests above policy limits.
- On deadline or accepted cancellation, kill and reap the child before emitting its terminal result.
- Drain stdout and stderr concurrently, retain at most the requested byte cap for each stream, and continue draining discarded bytes so a noisy child cannot deadlock on a full pipe.

## Relationship to Agent Runtime Protocol

Hosts translate an allowed execution to an adapter tool call and translate the terminal executor response to `tool.result`. Large or durable outputs can later become Agent Runtime Protocol artifacts; AF-050 keeps only bounded inline evidence. Executor policy and raw sidecar messages are not exposed as model/provider metadata.

## Acceptance

- Versioned JSON Schemas and positive/negative fixtures define execute, cancel, result, and acknowledgement envelopes.
- Rust tests prove policy denial, no shell, cleared environment, workspace containment, deadline kill/reap, output truncation, duplicate-ID handling, and explicit cancellation.
- JSONL stdout contains protocol responses only; diagnostics use stderr without echoing untrusted request bodies.
- Python orchestration and both agent adapters remain unchanged.
- `cargo fmt --check`, Clippy with warnings denied, Rust tests, Python/TypeScript regressions, scope audit, and repository checks pass.
