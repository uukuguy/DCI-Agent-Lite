# Installed Claude Runtime Interface Design

> Status: approved direction; written specification pending review.
>
> Active package: AF-160.

## Goal

Make the installed Asterion product expose the existing
`claude-code.reference` runtime through the same explicit runtime-factory
boundary as `pi.reference`, without requiring a Claude account, an API key, a
gateway, or a provider request.

The work proves the installed-product interface: exact runtime identity,
capability declaration, command shaping, caller-environment boundary, and
safe unauthenticated failure. A provider-backed run remains a separately
deferred operational acceptance.

## Factory contract

`default_runtime_factory_registry()` will contain one additional explicit
binding:

```text
runtime_id: claude-code.reference
capabilities: filesystem.read, shell
```

The factory is selected only when the CLI caller supplies
`--runtime claude-code.reference`. It is not inferred from provider,
application, environment variable, or installed executable. The existing
`pi.reference` factory remains unchanged.

The factory validates an operator-selected executable path (default `claude`)
and runtime working directory before returning a `ClaudeCodeRuntimeClient`. It
may accept an optional explicit `ASTERION_CLAUDE_EXECUTABLE` and
`ASTERION_RUNTIME_CWD`, but performs no `auth`, prompt, network, or model
operation during construction.

`ClaudeCodeRuntimeClient` is a thin `AgentRuntimeClient` adapter around the
existing `run_claude_code()` boundary. Its manifest has the exact factory ID
and capabilities. On `run()` it passes only the request input, configured
working directory, fixed `Read`/`Bash` tool list, deadline, and caller
environment to that boundary; it reads the resulting normalized event file and
projects `RunEvent` values. Its temporary raw-event/stderr directory is deleted
before return. A pre-cancelled signal fails before subprocess startup. AF-160
does not claim mid-process cancellation beyond the existing bounded
subprocess/timeout behavior.

## Runtime boundary

The existing restricted Claude Code command contract remains authoritative:

- direct executable argument vector only;
- safe mode and no session persistence;
- explicit normalized tool allow-list;
- caller environment passed only to the subprocess boundary;
- no credential, gateway, raw event, raw stderr, or prompt value enters CLI
  errors, serialized runtime configuration, or normalized result metadata.

The runtime adapter continues to own its own artifact shaping. AF-160 does not
add provider discovery, dynamic runtime selection, credentials configuration,
login automation, retries, a daemon, or a second CLI.

## Safe interface verification

Tests use an injected fake subprocess and checked-in stream fixtures. They
must demonstrate that the installed registry selects the Claude binding by
exact ID, constructs the restricted command, preserves a supplied credential
sentinel only at the mocked subprocess environment boundary, projects one
protocol-valid event stream, and exposes no sentinel in public output or
returned metadata.

The unauthenticated real-CLI check is limited to `claude auth status`; it is
not a provider request. If it reports no authorization, AF-160 records the
content-free availability block and stops. It does not attempt a prompt just
to confirm failure.

## CLI behavior

The generic CLI accepts `claude-code.reference` only for an application whose
declared `runtime_ids` includes that exact ID. Asterion's bundled DCI provider
currently declares `pi.reference` only, so AF-160 verifies the factory through
its public registry boundary and fixture runtime calls rather than falsely
claiming an installed DCI provider-backed run.

A future application may declare `claude-code.reference` after an explicit
provider/runtime product decision. This design deliberately does not change
the DCI provider's installed runtime list.

## Acceptance

- The installed Asterion runtime registry exposes an exact
  `claude-code.reference` binding without modifying Pi behavior.
- Constructing the binding performs no provider request and requires no
  account.
- Fixture-driven `ClaudeCodeRuntimeClient` execution proves command,
  capability, environment, normalization, temporary artifact cleanup, and
  redaction boundaries.
- Missing executable, invalid working directory, malformed fixture output, and
  unauthenticated backend failures are content-free public failures.
- The single wheel contains the necessary generic Claude modules while still
  excluding `dci`; no source baseline file under `src/dci/benchmark/` changes.

## Revalidation triggers

Add a bundled application runtime declaration or real provider-backed UAT only
when an operator supplies an authorized Claude login or compatible gateway.
Add other runtimes only through their own explicit factory, fixture contract,
and selected application compatibility decision.
