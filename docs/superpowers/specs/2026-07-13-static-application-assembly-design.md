# Static Application Assembly Design

> Status: approved for autonomous delivery after AF-080.

## Goal

Define a portable `dci.assembly/v1` contract that binds one application identity
to one runtime identity, exact local package identities, and explicit host-service
edges. Resolve that declaration into an immutable, auditable composition plan
without starting a runtime, executor, tool, or workflow.

## Chosen approach

Use a closed JSON assembly manifest plus a pure Python resolver.

1. **Static assembly manifest — selected.** It connects the verified runtime,
   catalog, and composer boundaries while preserving their ownership.
2. **Execution engine.** Rejected because both package graphs compose without one.
3. **Network registry/distribution.** Rejected because explicit local catalog roots
   currently satisfy the package-source requirement.

## Assembly manifest

The canonical manifest contains:

```json
{
  "protocol": "dci.assembly/v1",
  "application_id": "dci.local-research",
  "version": "1.0.0",
  "runtime_id": "pi.reference",
  "packages": [
    {"package_id": "dci.evaluation", "version": "1.0.0"},
    {"package_id": "dci.research", "version": "1.0.0"},
    {"package_id": "policy.local-corpus", "version": "1.0.0"},
    {"package_id": "protocol.observability", "version": "1.0.0"}
  ],
  "host_capabilities": [],
  "host_policies": [],
  "host_events": ["artifact.created", "run.completed", "run.started", "tool.result"],
  "host_artifacts": ["text/plain"]
}
```

Package refs and every host edge array are sorted and unique. `runtime_id` must
match the supplied Agent Runtime Protocol manifest exactly. Runtime capabilities
come only from that runtime manifest; `host_capabilities` contains separately
provided services such as `executor.controlled` and must not be used to invent a
native runtime capability.

The manifest contains no prompt, input text, provider/model selection,
credentials, environment, executable path, command, arguments, workspace,
transport, endpoint, mutable state, source path, or adapter-private type.

## Public Python API

Add `src/dci/framework/assembly.py`:

```python
@dataclass(frozen=True)
class AssemblyPlan:
    application_id: str
    version: str
    runtime_id: str
    package_refs: tuple[PackageRef, ...]
    composition: PackageComposition

def validate_assembly_manifest(value: Mapping[str, object]) -> None: ...

def resolve_assembly(
    assembly: Mapping[str, object],
    *,
    catalog: PackageCatalog,
    runtime_manifest: Mapping[str, object],
) -> AssemblyPlan: ...
```

Validation is backed by `schemas/assembly/v1/assembly.schema.json` plus explicit
sorted-array checks matching the package protocol's canonical ordering.

Resolution validates both assembly and runtime manifests, checks exact
`runtime_id`, converts package objects to exact `PackageRef` values, selects fresh
manifests from the catalog, unions runtime capabilities with declared host-service
capabilities, and calls `compose_packages` with the declared host policy/event/
artifact edges. The resulting plan contains only portable identities and the
existing immutable composition summary.

## Data flow

1. Operator configuration selects a validated assembly document, explicit local
   catalog, and one validated runtime manifest.
2. The assembly validator rejects unknown fields, invalid identities, duplicates,
   and noncanonical order.
3. The resolver checks that the runtime manifest identity equals `runtime_id`.
4. Exact package refs select fresh manifests from `PackageCatalog`.
5. Runtime-native capabilities and separately declared host-service capabilities
   form the composer input; policy/event/artifact host edges remain explicit.
6. The existing composer returns the deterministic graph summary.
7. The resolver returns `AssemblyPlan`; no execution side effect occurs.

## Error and security behavior

Expose `AssemblyError(ValueError)` with content-free structural messages for
invalid assembly, invalid runtime manifest, runtime mismatch, unavailable package
refs, duplicate refs, and composition failure. Chain underlying local exceptions
without echoing manifest contents, prompts, source documents, credentials, or
provider payloads.

Assembly host edges are operator-authored claims, not authorization. A future
runner must still obtain real service implementations and enforce runtime and
executor policy. Resolving `executor.controlled` does not start or authorize the
Rust sidecar and does not make a runtime a sandbox.

## Reference assemblies

Check in two assemblies:

- DCI local research against Pi and Claude Code runtime manifests through their
  portable read/shell capabilities.
- Controlled code validation against a read-capable runtime plus the separately
  declared `executor.controlled` host service.

Model-free fixtures may use stable reference runtime identities and capability
sets. They do not claim provider-backed execution.

## Language boundary

Python owns resolution because it owns catalog and composition. TypeScript copies
and validates the canonical assembly schema and fixtures, exports portable
assembly types, and does not implement a second resolver.

## Verification

Tests prove closed schema validation, canonical arrays, runtime identity matching,
exact catalog selection, both reference plans, Pi/Claude portable parity,
host-service separation, safe failures, deterministic results, TypeScript fixture
parity, and the absence of execution or a TypeScript resolver. Full Python,
TypeScript, Rust, compile, lint, format, shell, scope, and diff gates close AF-090.

## Non-goals

- No runtime/executor/tool/workflow execution, cancellation transport, or retry.
- No prompts, model/provider choice, application input, or output persistence.
- No network registry, installation, publishing, dependency solving, or version
  ranges.
- No service discovery, dependency injection container, process manager, API
  server, authentication, tenancy, or remote control plane.

## Acceptance

- `dci.assembly/v1` is closed, portable, canonical, and shared across languages.
- Exact catalog refs plus one runtime manifest resolve both existing graphs into
  deterministic immutable plans.
- Runtime-native and host-service capabilities remain distinguishable and no
  authorization or sandbox claim is implied.
- Every failure is safe and resolution performs no execution.
- Documentation and every repository closure gate pass with fresh evidence.
