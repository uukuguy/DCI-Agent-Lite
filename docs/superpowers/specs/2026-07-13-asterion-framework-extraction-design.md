# Asterion Framework Identity and Extraction Design

> Status: ready for written-spec review.

## Goal

Make **Asterion** the independent top-level agent-application framework and make
DCI one capability package and reference application built on it. Extract the
framework from `src/dci/framework/` without breaking the verified
`dci-agent-lite` CLI or the two `.env`-driven examples in `scripts/examples/`.

## Naming

- Product and framework name: **Asterion**.
- Python distribution: `asterion`.
- Python import root: `asterion`.
- TypeScript package working name: `asterion-runtime` while packages remain
  private; a scoped public name requires ownership of the corresponding npm
  organization.
- Protocol namespace target: `asterion.runtime/v1`, `asterion.package/v1`,
  `asterion.assembly/v1`, and `asterion.executor/v1`.

Exact registry probes on 2026-07-13 returned 404 for both PyPI `asterion` and
npm `asterion`. AF-095 uses the same `asterion` spelling for the local Python
distribution, import root, and private TypeScript working package. Availability
is evidence, not a reservation; actual publication remains outside this package.
Early registry reservation is explicitly non-blocking and deferred.

Protocol literals do not change during the directory extraction. A later
versioned compatibility package must define whether `dci.*` literals are aliases
or replaced by a new protocol version; AF-095 does not silently rewrite public
wire values.

## Target repository structure

```text
src/
  asterion/
    runtime/            # protocol types, validation, client contract
    packages/           # package protocol, catalog, composition
    assembly/           # manifest validation and immutable plans
    services/           # host-service contracts
    adapters/           # Pi and Claude Code protocol adapters
  dci/
    capability/         # DCI integration with Asterion
    benchmark/          # existing benchmarks and judge
    config.py

capabilities/
  dci-research/         # DCI package manifests and capability documentation
  controlled-code/      # second reference capability graph

applications/
  dci-agent-lite/       # reference application assembly and documentation

packages/
  typescript/asterion-runtime/
  rust/controlled-executor/

schemas/
  runtime/v1/
  packages/v1/
  assembly/v1/
  executor/v1/

scripts/examples/       # verified user entry examples remain stable
tests/
  framework/
  capabilities/
  applications/
  compatibility/
```

Python-importable code remains under `src/`; top-level `capabilities/` and
`applications/` contain declarative assets and product documentation rather
than a second Python packaging mechanism.

## Dependency direction

`asterion` must never import `dci`. DCI capability and benchmark code may
import Asterion. The `dci-agent-lite` CLI remains a DCI product entry point and
is not renamed into the framework CLI.

The first extraction moves only already-generic modules:

- runtime protocol and host client contracts;
- Pi and Claude Code normalized adapters/runtimes where their public boundary is
  generic;
- package protocol, catalog, and composer;
- assembly protocol and resolver;
- executor protocol validation.

Benchmark runner, judge, system-prompt bridge, corpus tools, and DCI-specific
configuration remain in `src/dci/`.

## Compatibility strategy

Migration is incremental:

1. Create the authoritative `src/asterion/` modules with the existing
   behavior and public types.
2. Replace `src/dci/framework/*` implementations with thin compatibility
   re-exports. No duplicated implementation is allowed.
3. Move internal tests and new consumers to `asterion.*`; retain explicit
   compatibility tests for `dci.framework.*`.
4. Add the `asterion` distribution while preserving all existing
   `dci-agent-lite` console scripts and the current `dci` distribution during
   the transition.
5. Relocate declarative manifests and assemblies only after loaders accept their
   new canonical roots without changing their identities.

Compatibility re-exports are temporary and receive a documented removal trigger,
not an immediate deprecation deadline.

## Verified upstream baselines

The following commands are acceptance baselines and must remain operational with
the repository `.env` configuration:

- `scripts/examples/dci_basic_example.sh`
- `scripts/examples/dci_runtime_context_example.sh`

They invoke `uv run dci-agent-lite` and exercise the real DCI capability path.
Model-free tests verify command construction and configuration behavior on every
change. When valid credentials are available, both scripts are run as provider-
backed UAT; missing credentials do not justify replacing them with a new runner.

AF-100 must integrate the established DCI entry/capability boundary. It may not
reimplement DCI research logic merely to demonstrate Asterion execution.

## Schema and cross-language layout

Schema directories become product-neutral filesystem paths during AF-095, while
their `const` protocol literals remain unchanged. TypeScript copies schemas from
the new canonical paths and keeps validation-only ownership. The Rust executor
directory may be renamed mechanically, but its authorization and process
boundaries remain unchanged.

No language package is published as part of AF-095. Publication names, npm scope,
protocol aliasing, and repository renaming require separate decisions after the
local structure is stable.

## Failure and security behavior

- A compatibility import must expose the same object identity where practical,
  not a forked implementation.
- Import cycles between Asterion and DCI fail the extraction gate.
- Migration must not read or persist `.env` secrets, print provider keys, or
  modify the independent `pi/` checkout.
- File moves must preserve unrelated user changes and Git history.
- The two example scripts, CLI argument compatibility, normalized protocol
  fixtures, and content-safe error behavior remain protected by tests.

## Verification

Acceptance requires:

- architecture tests prove `asterion` contains no DCI imports;
- compatibility tests prove old `dci.framework.*` imports re-export the
  authoritative Asterion objects;
- the existing Python, TypeScript, and Rust suites pass without duplicated
  framework implementations;
- both example scripts pass model-free configuration/command tests, and
  provider-backed UAT when credentials are available;
- wheel metadata contains both transition packages and preserves all existing
  console scripts;
- schema copy paths and checked-in manifests/assemblies remain canonical;
- compile, Ruff, TypeScript clean install/tests, Rust fmt/Clippy/tests, shell,
  scope, and diff gates pass.

## Non-goals

- No application runner implementation; AF-100 follows this package.
- No public protocol literal rename or compatibility alias semantics.
- No repository rename, remote package publication, npm organization creation,
  or domain acquisition.
- No DCI CLI rewrite, benchmark redesign, provider/model configuration redesign,
  workflow engine, registry, or control plane.

## Acceptance

- Asterion is the documented framework owner and has an independent authoritative
  Python import root.
- DCI is a dependent capability/reference application, never a framework parent.
- Existing DCI imports and both verified example entry paths remain compatible.
- Generic implementation exists only once under Asterion.
- AF-100 can add its runner under `asterion/runner/` without reinforcing
  the obsolete `src/dci/framework/` boundary.
