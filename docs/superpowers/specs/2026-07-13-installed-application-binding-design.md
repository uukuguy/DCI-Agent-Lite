# Installed Application Binding and Generic Entry Point Design

> Status: approved in discussion; awaiting written-spec review before implementation planning.
>
> Active package: AF-120.

## Goal

Let independently installed applications supply exact Asterion capability
implementations to a generic `asterion` command without making Asterion core
depend on DCI, embedding executable module paths in portable manifests, or
silently importing arbitrary modules.

Prove the contract with the independently owned DCI research application while
leaving `src/dci/benchmark/`, `dci-agent-lite`, and both baseline example scripts
unchanged.

## Trust model

An installed Python distribution is executable code trusted by the environment
operator. Installing it grants the same code-execution authority as installing
any other Python package. Asterion does not claim to sandbox or make a malicious
installed distribution safe.

Asterion narrows when that trusted code executes:

- application providers register only through the fixed
  `asterion.applications` entry-point group;
- a run names one explicit provider ID;
- that selected ID is the invocation allowlist;
- Asterion loads only the unique entry point whose name exactly matches the
  selected provider ID;
- zero or multiple matches fail closed;
- listing installed providers reads distribution metadata but does not load
  provider code.

There is no arbitrary `--host module.path`, import-path field in an assembly,
directory scanning, implicit provider fallback, or load-all plug-in hook.

## Provider identity and discovery

The entry-point name is the stable provider ID, for example
`dci-agent-lite`. Provider IDs use the existing portable identifier grammar and
are compared exactly.

Discovery reads `importlib.metadata.EntryPoint` metadata from the current
Python environment. `asterion list` reports sorted unique provider names and
their distribution names/versions when available. It never calls
`EntryPoint.load()`.

`asterion run --provider dci-agent-lite <assembly-path>` selects only entry
points named `dci-agent-lite`. Before load, Asterion rejects a missing match,
duplicate matches, invalid provider ID, non-file assembly path, or invalid CLI
configuration. It does not load adjacent providers while diagnosing a failure.

## Installed provider contract

The selected entry point loads one callable with no arguments. Calling it
returns an immutable `InstalledApplicationProvider` using only Asterion public
types. The provider has:

```python
@dataclass(frozen=True)
class InstalledApplicationProvider:
    protocol: str
    provider_id: str
    resource_root: Path
    applications: tuple[InstalledApplication, ...]

@dataclass(frozen=True)
class InstalledApplication:
    application_id: str
    version: str
    assembly_paths: tuple[Path, ...]
    catalog_roots: tuple[Path, ...]
    implementations: tuple[tuple[PackageRef, PackageImplementation], ...]
    runtime_ids: tuple[str, ...]
```

Concrete field names may be refined during planning, but these semantics are
fixed:

- provider and application identities are stable, exact, unique, and immutable;
- `protocol` is exactly `asterion.application-provider/v1`;
- `resource_root` is one existing canonical non-symlink directory owned by the
  installed distribution;
- every assembly path and catalog root is an existing canonical regular
  file/directory beneath the installed distribution's declared resource root;
- symlink paths and escapes outside that root fail closed;
- implementation bindings use exact `PackageRef` values and the AF-110
  `PackageImplementation` contract;
- runtime IDs are compatibility declarations, not runtime factories;
- provider values contain no runtime instances, host services, credentials,
  model names, commands, environment values, mutable state, or automatic
  startup behavior.

The loaded object's `provider_id` must equal the selected entry-point name.
Duplicate application identities, duplicate implementation refs, empty runtime
sets, or unrecognized fields/types fail before runtime construction.

## Runtime and host ownership

The application provider supplies portable application resources and package
implementations only. It cannot construct or start a runtime or host service.

The Asterion command owns an explicit runtime-factory registry configured by
the host distribution. Runtime selection is explicit through a stable runtime
ID. The first reference binding uses the Asterion-owned `pi.reference` runtime
factory and existing `.env`/CLI configuration surface; credentials remain in
the caller environment and never enter provider values, manifests, commands
printed by Asterion, or results.

The selected runtime ID must appear in both the provider application's declared
runtime IDs and the assembly. Host services remain explicit caller-owned
objects. AF-120 does not add automatic provider/model selection, automatic
service discovery, or service startup.

## CLI contract

Add an independent `asterion` console script while preserving every existing
DCI console script.

The first public commands are:

```text
asterion list
asterion run --provider <provider-id> --runtime <runtime-id> <assembly-path>
```

`list` produces deterministic metadata-only output. `run` accepts application
input through an explicit argument or stdin, plus runtime-specific options
supported by the host runtime factory. Normal defaults remain in `.env`; CLI
overrides remain backward-compatible with those settings and never print
credential values.

The run sequence is fixed:

1. Parse and validate CLI input.
2. Select exactly one metadata entry matching the explicit provider ID.
3. Load and validate only that provider.
4. Canonicalize the requested assembly path and match its exact
   `application_id@version` to one provider application.
5. Validate provider resource roots, exact implementation bindings, and runtime
   compatibility.
6. Construct the explicitly selected runtime through the host-owned factory.
7. Resolve the assembly from provider catalog roots.
8. Invoke `run_composed_application` with the provider's exact implementation
   bindings and explicit host services.
9. Write one normalized JSON result to stdout.

No provider or runtime starts before steps 1–5 complete.

## DCI provider

The DCI research capability distribution registers the first
`asterion.applications` provider under `dci-agent-lite`. Its provider object
binds the checked-in `dci.research-capability@1.0.0` application to:

- `applications/dci-agent-lite/assemblies/dci-research-capability.json`;
- `capabilities/dci-research/manifests/`;
- `dci.research@1.0.0 -> DciLocalResearchImplementation`;
- compatible runtime ID `pi.reference`.

The provider implementation lives with the DCI capability/application product,
not in `src/asterion/` and not in `src/dci/benchmark/`. Asterion core must work
with a synthetic independently installed provider in tests and contain no DCI
import or hard-coded DCI identity.

## Failures and privacy

All failures are fail-closed and occur as early as their evidence permits.
Public messages may identify provider ID, application ID/version, runtime ID,
package ID/version, and structural failure class. They never include:

- entry-point reprs or Python module paths;
- filesystem contents outside canonical public resource paths;
- input text or stdin contents;
- environment names/values, credentials, tokens, or provider/model payloads;
- raw tool output, implementation reprs, runtime objects, or service objects;
- import exceptions or tracebacks from provider code.

Provider load exceptions become a fixed provider-load failure. Contract errors,
resource escape/symlink failures, assembly mismatch, runtime mismatch, missing
implementation, and composed-run failures retain distinct structural classes
without echoing unsafe values.

## Security boundaries

Entry points provide controlled selection, not sandboxing. A selected installed
provider can execute arbitrary Python during `EntryPoint.load()` or factory
invocation. The operator's protection is installation control plus explicit
per-run provider selection.

Portable manifests remain data-only. Provider metadata does not authorize
runtime tools or host services. Runtime and service policy continue to enforce
actual authority. AF-120 does not add signatures, provenance verification,
remote registries, automatic installation, dependency solving, provider
sandboxing, service startup, tenancy, or a remote control plane.

## Verification

Tests must prove:

- `asterion list` enumerates metadata without importing provider code;
- listing order and output are deterministic and contain no module path;
- run rejects invalid, missing, duplicate, or unselected providers before load;
- only the explicitly selected provider is loaded;
- provider ID mismatch, duplicate applications/bindings, invalid types, mutable
  containers, empty runtime compatibility, and unsafe resources fail closed;
- provider assembly/resource paths reject symlinks and canonical-root escape;
- provider declarations cannot override assembly application/runtime identity;
- runtime construction happens only after provider, resource, assembly, and
  exact binding preflight;
- a synthetic independent provider runs without any DCI import in Asterion;
- the DCI installed provider executes the research application through the
  generic command and AF-110 composed runner;
- application provider and capability implementation can be packaged and
  imported independently from Asterion core;
- provider/import/runtime/input/tool sentinels never appear in public errors or
  normalized CLI output;
- `src/dci/benchmark/`, `dci-agent-lite`, and existing DCI examples remain
  unchanged;
- all Python, TypeScript, Rust, compilation, lint, shell, scope, and diff gates
  pass.

## Acceptance

- An installed application can bind exact independently owned capability
  implementations through a versioned Asterion provider contract.
- `asterion list` is metadata-only and `asterion run` loads only one explicitly
  selected trusted provider.
- The generic command runs both a synthetic provider and the DCI research
  application without Asterion core importing DCI.
- Runtime/service authority and credential ownership remain outside provider
  metadata.
- Invalid or malicious provider structure fails before unintended runtime work
  and without unsafe error content.
- Existing DCI baseline behavior, commands, examples, and source remain
  independent and unchanged.

## Revalidation triggers

Add signed provenance only when providers cross an untrusted distribution
boundary. Add a remote registry or automatic installation only when a concrete
external application source requires it. Add provider sandboxing only through a
real process/container isolation design rather than entry-point validation.
