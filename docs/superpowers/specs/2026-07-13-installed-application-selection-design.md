# Installed Application Selection and Product Usability Design

> Status: approved direction; written specification pending review.
>
> Active package: AF-130.

## Goal

Let operators discover and run an installed Asterion application by stable exact
identity without locating a package-internal assembly file. Preserve explicit
provider and runtime authority, metadata-only global listing, and the AF-120
selected-only load boundary.

The primary command is:

```text
asterion run \
  --provider dci-agent-lite \
  --application dci.research-capability@1.0.0 \
  --runtime pi.reference
```

## Exact application selector

An application selector is exactly `<application_id>@<semantic-version>`.
`application_id` uses the existing portable identifier grammar and the version
is the existing three-part semantic version. Whitespace, missing components,
version ranges, aliases, case folding, implicit latest versions, and partial
matches are rejected.

Selection occurs only inside the already explicitly selected provider. Exactly
one `InstalledApplication` must match both fields. Zero or multiple matches fail
closed before runtime selection or construction. Public errors remain fixed and
do not expose provider objects, module paths, resources, input, or environment.

## Listing contract

Plain `asterion list` remains metadata-only. It reports installed provider IDs
and distribution metadata without calling any entry point.

`asterion list --provider <provider-id>` is the explicit authorization to load
exactly that provider. It emits deterministic JSON containing:

- provider ID;
- application ID and version;
- exact selector;
- sorted compatible runtime IDs.

It does not resolve an assembly, construct a runtime, read operator input, or
load adjacent providers. Missing, duplicate, invalid, or failing selected
providers use the existing safe provider failure classes.

## Run selection and compatibility

`asterion run` accepts exactly one assembly selection mode:

1. `--application <application_id@version>` — preferred installed-product path;
2. `--assembly <path>` — explicit advanced path selection within the selected
   provider's declared canonical assembly paths;
3. the current positional assembly path — retained as a deprecated compatibility
   spelling for AF-120 callers.

Supplying more than one mode or no mode is a command error before provider load.
The positional spelling and `--assembly` have identical canonical path, symlink,
provider-root, and exact membership checks. No arbitrary assembly outside the
selected provider becomes executable.

For `--application`, the selected application must declare exactly one assembly
path. Applications with multiple assembly variants remain runnable only through
explicit `--assembly` until a separately designed variant identity exists. This
avoids inventing implicit defaults.

After application/assembly selection, the AF-120 sequence is unchanged:
provider validation, runtime compatibility, assembly/catalog resolution, exact
implementation preflight, runtime factory construction, composed execution, and
one normalized JSON result.

## API boundaries

Application-selector parsing and exact matching live in a focused Asterion
application-selection module. The CLI orchestrates it but does not duplicate
identity parsing or inspect DCI-specific values. Provider declarations remain
immutable and unchanged; no schema or entry-point protocol version bump is
needed because AF-130 consumes existing `InstalledApplication` fields.

The built-in DCI provider remains ordinary provider data. Synthetic provider
tests prove generic behavior without importing the DCI implementation.

## Failures and privacy

All selector and mode failures occur before provider load when possible. Unknown
application identity and multi-assembly ambiguity occur after only the selected
provider is validated, but before assembly resolution or runtime construction.

Errors may identify the structural class but never echo:

- raw CLI input or application selector;
- assembly paths or package resource roots;
- entry-point values, module names, factories, or implementation objects;
- environment variables, credentials, provider/model payloads, or tool output.

## Verification

Tests must prove:

- exact selector parsing accepts one canonical identity and rejects malformed,
  ranged, partial, or whitespace forms;
- exact application matching returns one immutable provider application and
  safely rejects zero, duplicates, and multi-assembly ambiguity;
- plain `list` never loads provider code;
- `list --provider` loads only the selected provider and emits deterministic
  application/runtime metadata;
- run rejects missing or conflicting selection modes before provider load;
- `--application` resolves the built-in DCI assembly without exposing its path;
- `--assembly` and the legacy positional spelling preserve AF-120 security and
  behavior;
- provider/application/binding preflight still precedes the runtime factory;
- generic selection and CLI modules contain no DCI import or identity literal;
- installed-wheel tests exercise list and application selection outside the
  repository while `dci` remains absent;
- all Python, Node, Rust, compile, lint, shell, scope, and diff gates pass.

## Acceptance

- Installed applications are discoverable and runnable through exact stable
  identity rather than internal resource paths.
- Provider/runtime selection remains explicit and global listing remains
  metadata-only.
- Advanced explicit assembly selection remains available without weakening
  canonical resource containment.
- No registry, version solver, aliases, implicit latest selection, application
  variants, remote installation, or control plane is introduced.

## Revalidation triggers

Add assembly variant identities only when one installed application genuinely
needs multiple user-selectable assemblies. Add global application discovery only
with a metadata contract that does not import all provider code. Add version
ranges only with a separately reviewed deterministic resolution policy.
