# Asterion Repository Directory Convergence Design

## Status

Approved direction on 2026-07-16. This design covers repository presentation only; it does not change Asterion runtime behavior, packaging, DCI semantics, or the external Pi checkout.

## Problem

The repository currently presents three different ownership classes beside one another:

1. `packages/python/asterion-core/src/asterion/` is the only installable Asterion Python product.
2. `src/dci/` is the independent, source-only original DCI comparison baseline.
3. top-level `applications/*/python` contains two small composition-root examples that are neither installed applications nor separate distributions.

The top-level name `applications/` visually competes with the authoritative package-local `asterion/applications/`. A local empty `capabilities/` directory creates the same impression even though Git tracks no files beneath it. Users therefore cannot determine ownership from the tree without reading packaging tests or source code.

## Decision

Move the two repository-only host examples into an explicit example namespace:

```text
examples/
└── asterion/
    ├── README.md
    └── applications/
        ├── controlled_code.py
        └── dci_research.py
```

The files remain executable Python composition examples with their existing public functions and behavior. They do not become wheel resources, installed providers, command entry points, or production application implementations.

After the move, the repository has no tracked top-level `applications/` or `capabilities/` product tree. The canonical application and capability implementations remain:

```text
packages/python/asterion-core/src/asterion/applications/
packages/python/asterion-core/src/asterion/capabilities/
```

## Considered Alternatives

### Package-local examples

`packages/python/asterion-core/examples/` would colocate examples with the wheel project, but it would blur whether they are packaged resources and add a deeper path for repository users. It is rejected for this convergence step.

### Test-only fixtures

Inlining the composition roots into tests would minimize tracked directories, but would remove readable integration examples that demonstrate explicit assembly, implementation binding, runtime, and host-service injection. It is rejected because Asterion needs reusable third-party integration examples.

### Compatibility stubs at old paths

Leaving forwarding files beneath top-level `applications/` would preserve obsolete filesystem paths but retain the exact ambiguity this work removes. The old paths are repository-internal and have no installed or public CLI contract, so no compatibility stubs will remain.

## Ownership Boundaries

| Path | Ownership after convergence | Installable |
|---|---|---|
| `packages/python/asterion-core/src/asterion/` | Asterion framework and bundled first-party products | yes, one `asterion` wheel |
| `examples/asterion/` | repository-readable integration examples | no |
| `src/dci/` | independent original DCI comparison baseline | no |
| `scripts/examples/` | runnable source/Asterion DCI shell examples | no |
| `scripts/asterion/` | Asterion DCI benchmark launchers | no; they invoke installed/source CLI |
| external `pi/` | independent Pi checkout | no; never modified by this package |

The repository example modules may import Asterion public Python APIs. Production Asterion must never import `examples/`, and neither the wheel nor the original DCI baseline may depend on them.

## File Mapping

| Current path | Target path |
|---|---|
| `applications/dci-agent-lite/python/dci_research_host.py` | `examples/asterion/applications/dci_research.py` |
| `applications/controlled-code/python/controlled_code_host.py` | `examples/asterion/applications/controlled_code.py` |

The function `run_dci_research_application` remains unchanged. The function `run_controlled_code_application` remains unchanged. Renaming only the modules removes distribution-like directory names while retaining semantic example names.

## Required Reference Updates

The implementation must update every checked-in consumer of the old paths:

- `tests/test_composed_application_runner.py` loads the new DCI example location.
- `assets/dci/product-parity.json` records the new DCI example source entry point without changing acceptance evidence or provider-backed artifacts.
- `docs/architecture/controlled-code-validation-packages.md` links the new controlled-code example.
- `docs/architecture/asterion-framework-capability-integration.md` describes `examples/asterion/` and no longer describes a top-level application product tree.
- `docs/architecture/asterion-standalone-extraction.md` maps the explicit example namespace rather than excluding an ambiguous application tree.
- documentation contract tests reject claims that top-level `applications/` or `capabilities/` are installable products and verify the new paths.

`examples/asterion/README.md` must explain what each example demonstrates, how it differs from an installed provider, and which normal CLI users should use instead.

## Behavior and Packaging Invariants

- The `asterion` wheel file set and entry points remain unchanged.
- `asterion list`, `describe`, `verify`, and `run` behavior remains unchanged.
- `asterion-dci` commands, configuration, artifacts, benchmark profiles, metrics, export formats, and launcher behavior remain unchanged.
- `src/dci` remains source-only, runnable, and independent.
- No Python import from `asterion` or `src/dci` points into `examples/`.
- No provider request, Judge request, full dataset, or external Pi modification is needed.
- The user-owned `.superpowers/sdd/task-0-review.md` remains untouched.

## Verification Strategy

The move is accepted only if all of the following pass:

1. A red/green path test proves old tracked application paths are gone and both new example modules exist.
2. Composed application runner tests load and execute the moved DCI example.
3. Controlled-code application and provider tests remain green.
4. Product parity validation resolves the updated example path and all 533 delegated selectors without provider requests.
5. Distribution tests prove one buildable wheel, no baseline/capability distribution, and unchanged bundled resources.
6. A built isolated wheel lists both providers and contains neither `examples` nor `dci` as a top-level import package.
7. Documentation contract and local-link checks pass.
8. Touched Python compiles and passes Ruff; `git diff --check` and the project scope audit pass.

The implementation may compare wheel archive member names before and after the move. A byte-identical wheel is not required because build metadata can vary; the authoritative invariant is an identical functional file set and entry-point/resource boundary.

## Sequencing Decision

This convergence package finishes before either of these future efforts:

- full-dataset benchmark validation or reproduction of the published 62.9% result;
- production release packaging, repository extraction, or splitting DCI into a separately versioned plugin.

Those efforts begin only after the broader Asterion framework has converged and each receives its own scope, authorization, cost disclosure, design, and acceptance criteria. Provider-free structural validation remains sufficient for this directory-only change.

## Rollback

The move is one cohesive Git rename plus reference updates. If any packaging, parity, or example behavior changes unexpectedly, restore both original paths and references together. Do not retain one old compatibility stub or a half-migrated path set.

## Acceptance

AF-300 is complete when:

- the two example hosts live only beneath `examples/asterion/applications/`;
- no tracked top-level `applications/` or `capabilities/` product tree remains;
- authoritative package-local application/capability paths are unchanged;
- all path, behavior, parity, distribution, isolated-wheel, documentation, static, and governance gates above pass without external provider operations;
- documentation records that full datasets and release packaging remain deliberately deferred.
