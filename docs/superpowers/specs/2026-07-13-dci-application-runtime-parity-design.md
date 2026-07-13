# AF-210 DCI Application Runtime Parity Design

> Status: approved.
>
> Active package: AF-210.

## Goal

Make the installed `dci.research-capability@1.0.0` application execute the
same independent Asterion DCI Pi workflow as `asterion-dci run`.  The generic
`asterion` command remains a domain-neutral application selector; it must not
learn DCI flags, paths, provider settings, or artifact formats.

## Chosen approach

The first-party DCI provider binds `DciLocalResearchImplementation` to an
explicit, provider-owned native executor.  When the selected assembly runtime
is `pi.reference`, the implementation translates its immutable package
invocation into a `DciRunRequest`, runs the existing Asterion-owned Pi
workflow, and projects its completed native result through `project_dci_run`.

The executor is configured only from the existing Asterion DCI configuration
surface and the generic runtime working-directory setting.  It owns the native
output root and never imports, launches, or discovers `src/dci`.

For `claude-code.reference`, the implementation retains the current
runtime-protocol execution path.  That preserves the existing fixture contract
without representing it as full DCI semantic parity or sending any provider
request.

## Boundaries

- `asterion.cli`, the application runner, assembly resolution, and runtime
  factory registry remain generic and contain no DCI-specific branching.
- The DCI provider alone supplies the native executor binding.  This is a
  first-party composition detail, not a new generic host-service protocol.
- The Pi path uses the installed application's selected `pi.reference`
  identity for compatibility preflight, then invokes the owned native DCI
  workflow so native artifacts, resume state, evaluation, and benchmark
  surfaces remain one implementation.
- The Claude path does not obtain a native executor and cannot claim parity
  from fixture behavior.  Provider-backed evidence remains separately
  operator-authorized.
- Public results retain only body-free references.  Native protected evidence
  stays in the Asterion DCI output directory.

## Data flow

1. `asterion run` selects one provider, application, and exact runtime
   assembly, then performs its existing generic preflight.
2. The provider-bound DCI implementation receives the package invocation.
3. With `pi.reference`, it creates `DciRunRequest(run_id, question, cwd)` from
   the invocation and configured application environment, invokes the native
   executor, and validates/projects the resulting `DciRunResult`.
4. The composed runner returns the declared `research.completed` event and one
   body-free `application/vnd.dci.research+json` artifact reference.
5. With `claude-code.reference`, the implementation continues to consume a
   conformant runtime event stream; fixture success is explicitly limited to
   that protocol-level contract.

## Failure and cancellation

The Pi executor converts native DCI failures to the existing safe package
failure boundary.  It must not expose question text, credentials, raw provider
responses, protected stderr, or absolute private artifact paths in CLI output.
Cancellation remains governed by the existing application signal and native Pi
execution behavior; tests use fixtures and do not issue provider requests.

## Verification

Focused tests prove that the Pi application path invokes the provider-bound
native executor exactly once, passes the application run ID/input/cwd, exposes
the same body-free references as the package-local path, and rejects invalid
native results without leaking bodies.  Existing Claude fixture tests continue
to prove assembly selection and normalized protocol behavior only.  The final
AF-210 closure matrix compares application and package-local Pi artifacts,
resume, evaluation, and benchmark behavior, then runs all repository gates.

## Rejected approaches

- Adding DCI arguments or output handling to the generic `asterion` CLI would
  violate the framework's domain-neutral boundary.
- Moving native artifacts into the generic Pi runtime adapter would make an
  adapter own DCI domain behavior and break the one-package implementation
  rule.
- Treating the existing Claude fixture as semantic parity would claim
  authorization and evidence that do not exist.
