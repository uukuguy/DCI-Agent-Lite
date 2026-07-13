# Asterion Framework Layout

## Ownership

**Asterion owns framework contracts.** Its authoritative Python implementation
lives under `src/asterion/`: runtime protocol and hosts, normalized adapters,
package catalogs and composition, static assembly, and host-service contracts.

**Asterion must not import DCI.** DCI is the first capability package, benchmark,
and reference application built on Asterion. During the compatibility window,
`dci.framework.*` directly re-exports Asterion objects so existing consumers keep
working without a second implementation.

```text
src/asterion/                         framework implementation
src/dci/                              DCI capability, benchmark, configuration
packages/python/asterion-core/src/asterion/capabilities/dci_research/  bundled DCI capability and manifests
capabilities/controlled-code/         controlled-code declarative packages
applications/dci-agent-lite/          DCI reference application assemblies
packages/typescript/asterion-runtime/ TypeScript validation and host types
packages/rust/controlled-executor/    explicit controlled-execution service
```

## Stable DCI product entry

`dci-agent-lite` remains the user-facing DCI CLI. The verified
`scripts/examples/dci_basic_example.sh` and
`scripts/examples/dci_runtime_context_example.sh` continue loading repository
`.env` configuration and invoking that CLI. Asterion extraction does not replace
their provider/model configuration or duplicate their research behavior.

## Wire compatibility

Filesystem and import ownership changed before protocol identity. AF-095 retains
`dci.agent-runtime/v1`, `dci.package/v1`, `dci.assembly/v1`, and
`dci.executor/v1` exactly. Any future `asterion.*` wire namespace requires a
separate versioned compatibility decision; directory extraction does not create
silent aliases.

## Boundaries

- Asterion may be used without importing DCI.
- DCI may import Asterion and remains responsible for benchmark and prompt logic.
- Capability and application roots are declarative; they are not alternate
  Python import roots.
- TypeScript validates canonical contracts but does not duplicate Python
  composition or resolution.
- The Rust service is never started or authorized merely by importing Asterion.
- Registry publication, workflow scheduling, automatic service discovery, and
  the AF-100 application runner are outside AF-095.

## Verification

```bash
uv run python -m unittest tests.test_asterion_structure -v
uv run python -m unittest discover -v
npm --prefix packages/typescript/asterion-runtime test
make test-rust-executor check-rust-executor
```
