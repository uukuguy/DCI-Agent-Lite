# Installed DCI Claude Compatibility Design

> Status: approved direction; awaiting written-spec review before implementation.
>
> Active package: AF-170.

## Goal

Allow the installed `dci-agent-lite` provider to run
`dci.research-capability@1.0.0` with either exact runtime identity,
`pi.reference` or `claude-code.reference`, while preserving the existing Pi
path and requiring no Claude authorization or provider request during
verification.

## Product contract

The DCI application has one application identity, one catalog, one package
implementation binding, and two explicit runtime-compatible assembly
declarations. The declarations have the same package, host-capability, event,
and artifact composition; their only semantic difference is the exact
`runtime_id`.

- The existing `dci-research-capability.json` remains the Pi declaration.
- A second checked-in Claude declaration uses the same immutable composition
  and `runtime_id: "claude-code.reference"`.
- The DCI provider declares both sorted runtime IDs. The controlled-code
  provider remains Pi-only.
- Runtime compatibility remains a provider-owned declaration. It is never
  inferred from credentials, an executable, a model, an environment variable,
  or a request payload.

## Generic assembly selection

Installed application selection stays exact. For `asterion run --application`,
the generic CLI selects the one assembly belonging to the selected application
whose declared runtime ID equals `--runtime`.

The CLI fails before runtime-factory construction when there are zero or more
than one matching assemblies. Its public failure stays the existing
content-free `asterion: command failed` form. An explicit `--assembly` path is
still an advanced compatibility route, but it must belong to the selected
provider application and its own declared runtime ID must equal `--runtime`
before catalog discovery, runtime construction, input consumption, or
execution.

This selection behavior belongs in generic Asterion code; neither the CLI nor
the provider protocol gains a DCI-specific branch.

## Fixture-only verification

AF-170 verifies the installed generic CLI by injecting a deterministic
`claude-code.reference` fixture runtime factory. The test executes the selected
DCI application through its declared Claude assembly and asserts normalized
research events/artifacts plus the absence of credentials, prompts, raw
provider output, and temporary paths in public output.

The verification also proves that:

- Pi continues to select and run its existing assembly unchanged.
- Provider metadata lists the two exact DCI runtime IDs in deterministic order.
- A mismatched runtime/assembly pair, unknown runtime, or duplicated matching
  assembly fails before factory construction.
- The wheel includes both DCI assembly resources while still excluding the
  source-only `dci` baseline.

No test invokes Claude, runs `claude auth`, accesses a network, or creates a
credential configuration surface. A future real invocation requires an
operator-supplied authorized Claude login or compatible gateway and is outside
AF-170.

## Non-goals

- No new DCI application identity, provider, wheel, assembly protocol version,
  runtime factory, daemon, executor service, retry mechanism, or dynamic
  runtime policy.
- No change to `src/dci/benchmark/` or source-baseline packaging.
- No claim that Pi and Claude have identical native semantics or that the
  fixture proves provider-backed behavior.

## Acceptance boundary

AF-170 closes only after an implementation plan, focused fixture tests, and
the repository closure gates demonstrate the contract above. The provider-backed
Claude DCI run remains a separately deferred operational acceptance.

## Revalidation triggers

Revisit this design if an application needs multiple assemblies for the same
runtime, runtime compatibility becomes versioned rather than exact-identity
based, or an operator authorizes a real Claude DCI run.
