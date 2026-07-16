# Asterion Top-Level Project Root Convergence Design

## Status

Revised direction approved on 2026-07-16; written-spec review is pending. This revision supersedes the earlier example-only AF-300 design before any implementation began.

## Goal

Make Asterion a visibly complete, independently buildable project beneath one top-level `asterion/` directory in the current DCI-Agent-Lite repository. The resulting subtree must be promotable to the root of a future standalone Asterion repository without another conceptual directory redesign.

This package converges structure and path ownership. It does not publish a release, split DCI into a plugin, run full datasets, reproduce the published 62.9% result, or change framework/DCI behavior.

## Why the Current Layout Is Insufficient

The current `packages/python/asterion-core/` path is technically valid for a multilingual monorepo, but it no longer describes the product:

- Asterion is the primary framework, not one incidental workspace package.
- the `asterion-core` directory contains the framework, bundled DCI product, controlled-code application, resources, and both `asterion` and `asterion-dci` CLIs; it is not merely a core library;
- TypeScript, Rust, schemas, examples, scripts, tests, and documentation are scattered across the repository root;
- top-level `applications/` looks like another product root even though it contains only two repository examples;
- future standalone extraction would require a second large path rewrite.

The root workspace also contains the independent original DCI baseline. Flattening Asterion directly into the current root `src/` would put the two products back under one source root and weaken their already verified independence.

## Chosen Structure in the Current Repository

```text
DCI-Agent-Lite/
├── pyproject.toml                  # non-buildable development workspace
├── Makefile                        # workspace compatibility/developer entry points
├── .env                            # shared local configuration; never committed
├── .env.template
├── asterion/                       # complete Asterion project root
│   ├── pyproject.toml              # buildable Python project: distribution `asterion`
│   ├── src/
│   │   └── asterion/               # framework and bundled products
│   ├── packages/
│   │   ├── typescript/
│   │   │   └── asterion-runtime/
│   │   └── rust/
│   │       └── controlled-executor/
│   ├── schemas/
│   │   ├── agent-runtime/v1/
│   │   ├── assembly/v1/
│   │   ├── executor/v1/
│   │   └── packages/v1/
│   ├── examples/
│   │   └── applications/
│   │       ├── controlled_code.py
│   │       └── dci_research.py
│   ├── scripts/                    # Asterion DCI launchers and product helpers
│   ├── docs/                       # product, architecture, verification, operator docs
│   └── tests/                      # Asterion-owned framework/product tests and fixtures
├── src/
│   └── dci/                        # original DCI source-only comparison baseline
├── scripts/examples/               # original DCI and cross-product runnable examples
├── assets/dci/                     # migration/parity/acceptance evidence
├── tests/                           # original-DCI and cross-product parity tests
└── docs/status/                     # current repository governance and migration history
```

The top-level directory and Python import package intentionally share the name `asterion` at different levels: `asterion/` is a project root; `asterion/src/asterion/` is the standard src-layout import package.

## Future Standalone Promotion

When standalone extraction is authorized, the contents of the current `asterion/` directory become the new repository root:

```text
asterion-standalone/
├── pyproject.toml
├── src/asterion/
├── packages/typescript/asterion-runtime/
├── packages/rust/controlled-executor/
├── schemas/
├── examples/
├── scripts/
├── docs/
└── tests/
```

Promotion may add repository-level CI, release configuration, license, changelog, and root README. It must not require moving product source a second time.

## Ownership Classification

### Moves into `asterion/`

- `packages/python/asterion-core/pyproject.toml` and its complete `src/asterion/` tree;
- `packages/typescript/asterion-runtime/`, excluding generated `node_modules/` and `dist/`;
- `packages/rust/controlled-executor/`, excluding generated `target/`;
- all four Asterion-owned schema families under `schemas/`;
- the two repository application composition examples currently under top-level `applications/`;
- `scripts/asterion/` launchers and Asterion-only product scripts;
- Asterion product, framework, verification, and operator documentation;
- Asterion-only tests plus the protocol/application fixtures they own.

### Remains at the current repository root

- `src/dci/` and original DCI-only configuration/benchmark code;
- original DCI shell examples and any cross-product comparison entry point;
- `assets/dci/product-parity.json`, `batch-parity.json`, and the immutable provider-backed acceptance record;
- cross-product parity tests that intentionally read both `src/dci` and `asterion/`;
- `docs/status/`, worklist, decisions, journal, climb state, and migration design history;
- repository-root `.env` and `.env.template` while both products share one development workspace;
- external `pi/`, corpora, datasets, outputs, caches, credentials, and local worktrees.

### Classified during implementation

Every root test, document, script, fixture, and Make target must be classified by dependency, not filename alone:

- imports or validates only Asterion → move into `asterion/`;
- imports or validates only original DCI → remain at root;
- compares both products or validates migration evidence → remain at root and update its Asterion path;
- generic repository governance → remain at root.

No asset may be copied into both locations merely to avoid classification.

## Path Mapping

| Current path | Converged path |
|---|---|
| `packages/python/asterion-core/pyproject.toml` | `asterion/pyproject.toml` |
| `packages/python/asterion-core/src/asterion/` | `asterion/src/asterion/` |
| `packages/typescript/asterion-runtime/` | `asterion/packages/typescript/asterion-runtime/` |
| `packages/rust/controlled-executor/` | `asterion/packages/rust/controlled-executor/` |
| `schemas/` | `asterion/schemas/` |
| `applications/dci-agent-lite/python/dci_research_host.py` | `asterion/examples/applications/dci_research.py` |
| `applications/controlled-code/python/controlled_code_host.py` | `asterion/examples/applications/controlled_code.py` |
| `scripts/asterion/` | `asterion/scripts/` |
| Asterion-owned `docs/*` | `asterion/docs/*` |
| Asterion-owned `tests/*` and fixtures | `asterion/tests/*` |

After convergence, no tracked product or example tree remains under root `packages/`, `applications/`, `capabilities/`, or `schemas/`. A root directory may remain only if it contains explicitly classified non-Asterion material; otherwise it disappears with the last tracked move.

## Workspace and Build Behavior

The repository-root `pyproject.toml` remains non-buildable and changes its uv member from `packages/python/asterion-core` to `asterion`. Its `asterion` source override points to that member. Existing root development commands remain usable through the workspace.

`asterion/pyproject.toml` remains the sole buildable Python project and continues to define:

- distribution name `asterion`;
- import root `asterion`;
- console scripts `asterion` and `asterion-dci`;
- installed providers `controlled-code` and `dci-agent-lite`;
- wheel package `src/asterion`.

No additional Python distribution is introduced. The old path `packages/python/asterion-core` receives no compatibility project, symlink, or forwarding build file.

The TypeScript package and Rust crate retain their current package names, versions, lock files, and publish/private settings. Relative schema paths and workspace commands change only as required by the move.

## Configuration and Runtime Behavior

During the nested-project stage, normal development still starts from the DCI-Agent-Lite repository root. The shared root `.env` remains the normal configuration surface for original DCI and Asterion. Path resolution must be explicit and tested; it must not depend on accidentally finding an ancestor checkout.

The move preserves:

- `DCI_PI_DIR` preference for external `./pi`, with legacy `./pi-mono` fallback;
- shared provider/model/Judge configuration;
- Asterion-specific output roots;
- corpus and dataset overrides;
- installed-wheel behavior outside the source checkout.

Standalone release design will later decide whether `.env.template`, Pi checkout conventions, and default data paths change when `asterion/` becomes the repository root.

## Documentation and Test Split

`asterion/docs/README.md` becomes the Asterion documentation hub. Product and architecture links must resolve entirely within the subtree except for clearly labelled links to original-DCI comparison evidence.

The current repository keeps only migration/governance documentation at root. Historical design files may stay under root `docs/superpowers/` because they describe how this mixed repository evolved; standalone product documentation cannot depend on them.

Test execution has two explicit layers:

1. Asterion project tests run from or against `asterion/` and require no import from `src/dci`.
2. Root parity tests intentionally combine original DCI, Asterion, and checked-in migration evidence.

The Asterion isolated-project gate runs with the original DCI source path unavailable. The root parity gate then proves that relocation did not change the established source/Asterion comparison.

## Implementation Phases

### Phase 1 — Inventory and path contracts

- classify every affected test, document, script, fixture, Make target, and asset;
- add failing tests for the target root and forbidden obsolete paths;
- record current wheel member set, entry points, provider list, TypeScript/Rust tests, schema fixtures, and provider-free DCI parity counts.

### Phase 2 — Primary Python project

- create `asterion/` by moving the Python project metadata and `src/asterion` tree;
- update the root uv workspace and all Python/test/build paths;
- prove both source-workspace CLIs and the isolated wheel before proceeding.

### Phase 3 — Schemas and cross-language packages

- move schemas, TypeScript runtime, and Rust executor beneath `asterion/`;
- update schema-copy, fixture, Make, documentation, and test paths;
- run clean TypeScript and Rust gates without moving generated directories.

### Phase 4 — Examples and scripts

- move both composition hosts into `asterion/examples/applications/` with an explanatory README;
- move Asterion launchers/helpers into `asterion/scripts/`;
- preserve root Make shortcuts and shared `.env` behavior through explicit paths.

### Phase 5 — Product documentation and tests

- move Asterion-owned docs, tests, and fixtures into the subtree;
- leave original-DCI and cross-product parity assets at root;
- update all links, inventory paths, selector names only where ownership requires it, and local discovery commands.

### Phase 6 — Closure and extraction-readiness proof

- reject obsolete tracked product roots;
- run Asterion project-only tests with `src/dci` unavailable;
- run root cross-product parity and all 533 delegated selectors without provider requests;
- build/install the wheel in isolation and verify provider/CLI/resource boundaries;
- verify TypeScript, Rust, shell, documentation, scope, and clean-diff gates;
- document the exact remaining external dependencies and future promotion command sequence.

Each phase must end green and in a cohesive commit. A later phase may not hide a failed earlier boundary.

## Compatibility and Non-Goals

Paths inside this repository are updated atomically; obsolete source paths do not receive stubs or symlinks. Installed Python imports, distribution metadata, protocol literals, application/package IDs, CLI argv, environment variables, artifact formats, and provider behavior are compatibility boundaries and do not change.

AF-300 explicitly does not:

- modify original DCI implementation behavior;
- modify or vendor external Pi;
- introduce a second Python wheel or split DCI into a plugin;
- rename TypeScript/npm or Rust/crate identities;
- redesign schemas or protocol versions;
- run full benchmark datasets or claim published-score reproduction;
- publish packages, create release automation, or switch the remote repository;
- copy corpora, datasets, credentials, outputs, caches, `.worktrees`, `node_modules`, or Rust `target` into Asterion.

## Verification Gates

Acceptance requires fresh evidence for:

- target/forbidden path contract tests;
- complete Asterion project-only Python suite and compile/Ruff checks;
- root original-DCI and cross-product parity suite;
- 533/533 delegated product selectors and 12/12 launcher mappings;
- TypeScript clean build/tests against relocated schemas;
- Rust fmt, Clippy, unit/integration tests against relocated schemas/fixtures;
- shell syntax and exact Make argv;
- source-workspace `asterion` and `asterion-dci` help/describe/verify behavior;
- isolated wheel member set, both entry points, both providers, resources, and absence of `dci`/repository examples;
- Asterion-local and root migration documentation links;
- project scope and `git diff --check`.

All AF-300 gates are provider-free. Full datasets and release-package publication remain separate future packages after framework convergence.

## Rollback

The six phases are rollback boundaries. A failure is repaired inside the current phase or that phase's cohesive path/reference commit is reverted. Do not partially restore old roots, preserve symlinks, or mix old and new canonical paths.

Provider-backed acceptance artifacts remain immutable. Updating repository path metadata in `product-parity.json` does not rewrite `product-acceptance.json` or claim new provider evidence.

## Acceptance

AF-300 is complete when:

- `asterion/` is the complete, sole Asterion project root and can be promoted to a standalone repository root without another product-source re-layout;
- the mixed repository root clearly contains the original DCI baseline, cross-product evidence, and governance rather than a second Asterion product tree;
- only `asterion/pyproject.toml` builds the `asterion` wheel;
- Asterion project tests pass without original DCI, and root parity tests still validate both products;
- all language, packaging, CLI, provider-free parity, documentation, static, and governance gates pass;
- full-dataset validation and release implementation remain explicitly deferred.
