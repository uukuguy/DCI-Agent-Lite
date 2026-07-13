# Controlled-Code Executable Application Vertical Slice Design

> Status: approved direction; written specification pending review.
>
> Active package: AF-140.

## Goal

Turn the existing `code.quality@1.0.0` controlled-code graph into Asterion's
second executable bundled application. Prove that the same installed-provider,
exact package-binding, composed-runner, event, and artifact contracts support a
non-DCI application without adding a workflow scheduler or allowing an agent to
choose executable commands.

## Execution model

The application retains its existing deterministic package order:

```text
policy.controlled-code-check
  → workflow.code-quality
      → evaluation.code-quality
      → observability.execution-audit
```

Each package has one exact Asterion implementation:

- policy implementation validates that the explicit controlled-executor service
  and trusted validation configuration are present, then produces no output;
- workflow implementation submits one host-owned validation request to that
  service and emits one normalized report artifact plus
  `workflow.code-quality.completed`;
- evaluation implementation converts the report into a deterministic verdict
  artifact without another process invocation;
- observability implementation converts the same report into a redacted audit
  artifact and emits `audit.execution-recorded`.

The composed runner remains a sequential package executor, not a general
workflow engine. Dependencies, events, and artifacts already determine the
order and routing.

## Controlled executor host service

Add a Python host contract for the existing `executor.controlled` capability.
The application receives it through the existing explicit `host_services`
mapping. The contract accepts a closed immutable request containing only the
source-relative validation target or logical input reference required by the
trusted host configuration. It returns an immutable normalized result with:

- terminal status;
- exit code when a process ran;
- bounded stdout/stderr metadata and truncation flags;
- duration and structural failure class.

The portable package manifest, application assembly, application input, and
runtime output never contain an executable path, argument vector, environment,
workspace root, or resource limit. The service implementation owns a trusted
startup policy that fixes those values and translates the logical request into
the existing `dci.executor/v1` sidecar request.

AF-140 first supplies an in-process fixture service for deterministic tests and
a JSONL sidecar client for the real Rust service. It does not automatically
start the sidecar. The caller must explicitly construct and inject a service;
the generic CLI fails preflight when the application requires
`executor.controlled` and no authorized service is supplied.

## Input and authority

The application input identifies or describes the source validation target; it
is not a shell command. The host-owned validation configuration determines the
allowed program, fixed arguments, canonical workspace, working directory,
deadline, and output limits before the application begins.

The agent runtime remains `pi.reference` because the assembly's portable
runtime capability is `filesystem.read`. The executor remains a separate host
service. Pi cannot claim, create, configure, or start `executor.controlled`.

No implementation invokes a shell. The Rust sidecar continues direct
argument-vector spawning under its trusted policy. AF-140 makes no operating-
system sandbox claim.

## Bundled ownership

Move the four controlled-code manifests into
`asterion.capabilities.controlled_code` and keep them canonical inside the sole
Asterion wheel. Add implementations under the same namespace. The existing
`code.quality@1.0.0` assembly moves from the DCI application resource directory
to `asterion.applications.controlled_code` with its own provider application
binding.

The single Asterion distribution may expose the application through the existing
`dci-agent-lite` built-in provider only if provider identity is understood as the
first-party application bundle. To avoid that misleading ownership, AF-140 adds
a second built-in provider ID, `controlled-code`, registered by the same
`asterion` distribution. Global list remains metadata-only and reports both
provider entries; selected listing loads only one.

## CLI boundary

The generic installed CLI can list the second provider and application:

```text
asterion list --provider controlled-code
```

Normal `asterion run --application code.quality@1.0.0` requires an explicitly
configured executor service. AF-140 does not invent service startup flags in the
generic CLI. A focused Python host example constructs the sidecar client,
runtime registry, and service mapping, then invokes the same generic run
function. A later package may add operator CLI service configuration only after
the lifecycle and authorization model is separately approved.

## Data and failure flow

1. Provider/application/runtime/package binding preflight completes.
2. Required `executor.controlled` service presence and type are validated.
3. Policy implementation confirms trusted configuration availability.
4. Workflow submits exactly one logical validation request.
5. The service returns a bounded normalized execution result.
6. Workflow emits the declared report artifact and completion event.
7. Evaluation and observability independently consume the report and emit only
   their declared outputs.
8. The composed runner returns one immutable normalized application result.

Missing service/configuration, rejected policy, malformed sidecar JSONL,
duplicate response, timeout, cancellation, nonzero exit, undeclared package
output, or malformed artifact fails closed. Later packages do not run after a
workflow failure. Public errors never echo source input, commands, paths,
environment values, stdout/stderr bodies, or sidecar payloads.

## Verification

Tests must prove:

- all four exact implementations bind and execute in the resolved package order;
- policy and workflow require one explicit `executor.controlled` service before
  any runtime or executor call;
- workflow submits one logical request and never accepts executable fields from
  application/runtime input;
- evaluation and audit consume the workflow report without another executor
  call;
- every emitted event/artifact matches the existing portable declarations;
- failure/cancellation stops later packages and redacts input, paths, command,
  environment, stdout/stderr, and sidecar payload sentinels;
- the JSONL sidecar client correlates one request, bounds lifecycle, validates
  the closed response, and never starts the Rust process itself;
- the `controlled-code` provider/application list and select by exact identity
  in an isolated Asterion wheel;
- generic core/provider/CLI modules contain no controlled-code special case;
- the source DCI baseline and `src/dci/benchmark/` remain untouched;
- all Python, Node, Rust, compile, lint, shell, scope, diff, and isolated-wheel
  gates pass.

## Acceptance

- A second independently identified bundled application executes through the
  same generic Asterion contracts as DCI.
- Executable policy remains host-owned and explicit; neither agent input nor
  portable metadata can choose commands or service startup.
- The existing Rust sidecar remains a policy-enforcement boundary, not a
  sandbox or runtime adapter.
- No scheduler, repair loop, automatic service process, registry, remote worker,
  or control plane is introduced.

## Revalidation triggers

Add generic CLI service configuration only when an operator lifecycle design
defines startup, authorization, failure recovery, and shutdown. Allow agent-
proposed validation actions only through a separately reviewed typed action
contract. Add scheduling only when a third executable graph cannot be expressed
by the existing deterministic dependency order.
