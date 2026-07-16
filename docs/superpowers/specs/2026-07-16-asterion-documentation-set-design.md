# Asterion Complete Documentation Set Design

## Goal

Produce a coherent, evidence-backed documentation set that lets an operator use
the complete Asterion DCI product, lets an integrator add a new capability and
application without reverse-engineering the repository, and lets maintainers
evaluate a future standalone Asterion repository without prematurely moving
code.

## Documentation set

### Complete Asterion DCI product reference

Create `docs/guides/asterion-dci-complete-reference.md`. It covers:

- installation/source-checkout prerequisites and shared `.env` configuration;
- `run`, `terminal`, `system-prompt`, `resume`, `evaluate`, `benchmark`, and
  `export` command families with representative commands;
- native artifacts, privacy, provenance, resume, Judge request/cache identity,
  QA/IR orchestration, metrics, analysis, figures, exports, installed
  application execution, and unified verification;
- all benchmark families, bundled profiles, launcher mapping, required corpus
  and dataset locations, concurrency/turn/reuse controls, and output surfaces;
- two separate context-management layers: Pi model-input runtime behavior and
  saved-conversation artifact processing;
- an evidence matrix classifying every major claim as `implemented`,
  `verified`, `external-limited`, or `not rerun`.

The document must state that conversation clearing, keep-last, externalization,
thinking stripping, and usage stripping are implemented. It must also state
that the configured current Pi CLI does not expose the typed runtime
context-management level, so Asterion records a request as `unsupported` and
does not fabricate the flag. Arbitrary explicit `--extra-arg` forwarding is
not evidence that a given Pi checkout supports that option.

Benchmark implementation evidence includes the complete QA/IR orchestration,
Judge, reuse, metrics, analysis, figures, exports, 12 launcher pairs, and 533
delegated selectors. It must not claim that AF-290 reran full datasets or
reproduced README accuracy numbers.

### Framework and capability integration guide

Create `docs/architecture/asterion-framework-capability-integration.md`. It
explains the concrete responsibility and dependency direction of:

- runtime protocol, runtime factories and runtime implementations;
- adapters and normalized event/artifact boundaries;
- package manifests, catalogs, composition, implementation bindings and
  sequential execution;
- capability directories and domain-owned implementation code;
- application assemblies, installed application providers, selected-only
  discovery and exact application selection;
- host services and the controlled-executor example;
- generic CLI versus package-local product CLI.

The guide includes a current-tree map and explicitly identifies
`packages/python/asterion-core/src/asterion/capabilities/` and
`.../applications/` as the canonical wheel-owned assets. It describes the
top-level `applications/*/python` files as repository reference/compatibility
hosts and the top-level `capabilities/` directory as non-authoritative. It must
not imply that those top-level directories are separately installable
packages.

A complete worked integration path starts with a new package manifest, adds an
immutable Python implementation binding, defines an application assembly,
registers an installed provider entry point, lists and runs the application,
and adds discovery, packaging, safety, and isolated-wheel tests. The example
uses neutral placeholder identity such as `example.research`; it does not copy
DCI-specific behavior into generic framework modules.

### Standalone extraction design

Create `docs/architecture/asterion-standalone-extraction.md`. It inventories
what the current `asterion` wheel already contains and what remains external:

- generic Python framework, bundled DCI and controlled-code capabilities,
  assemblies, provider entry points, and `asterion`/`asterion-dci` commands;
- separate TypeScript runtime-host and Rust controlled-executor packages;
- canonical schemas and cross-language fixtures;
- external Pi checkout, Node runtime, corpora, benchmark datasets, credentials,
  and repository-only source DCI comparison baseline;
- repository-only acceptance matrices, scripts, guides, and test assets needed
  for continued parity maintenance.

It proposes a phased extraction rather than a direct filesystem copy:

1. freeze and verify the current distribution manifest;
2. remove or relocate top-level compatibility/reference ambiguity;
3. create the standalone repository skeleton and copy authoritative packages,
   schemas, tests, docs, and build metadata;
4. replace repository-relative assumptions with package resources or explicit
   operator inputs;
5. preserve DCI as an optional bundled reference capability initially;
6. prove isolated source install, wheel contents, provider discovery, Pi-backed
   bounded examples, model-free acceptance, and cross-language gates;
7. only then decide whether DCI becomes a separately versioned plugin.

The design includes a proposed target tree, dependency graph, migration table,
release gates, rollback boundary, and explicit exclusions. AF-290 does not
perform any extraction.

## Truth and evidence policy

Every feature table uses these terms consistently:

- **Implemented**: production code exists in authoritative Asterion modules.
- **Verified**: an executable test or bounded run directly proves the claim.
- **External-limited**: Asterion carries the configuration or boundary but an
  external dependency does not expose the required capability.
- **Not rerun**: code and model-free parity exist, but a costly/full experiment
  or published numerical result was not reproduced during migration closure.

Statements link to canonical source modules, commands, manifests, tests, or
acceptance assets. Worklist status alone is never cited as functional proof.

## Existing-document reconciliation

- Update README with a clear entry point to all three documents and a concise
  context-management/benchmark evidence caveat.
- Correct `assets/docs/running.md` so it no longer asserts that the configured
  current Pi checkout supports runtime levels that its CLI does not expose.
- Link the new DCI reference from the beginner usage guide and advanced
  verification guide; do not duplicate entire command references.
- Add documentation contract tests that require the evidence vocabulary,
  canonical directory explanation, standalone target tree, and cross-links.

## Verification

- Static documentation tests prove required sections, commands, evidence
  labels, canonical directory boundaries, and links.
- Source checks prove every linked authoritative local path exists.
- CLI `--help`, `asterion describe`, bundled profiles, product matrix, and
  package metadata are read or rendered without provider requests to validate
  factual tables.
- Scope, Ruff for touched tests, compilation, Markdown link checks where
  available, and `git diff --check` close the work package.

## Non-goals

- No directory move, repository split, packaging change, protocol change, or
  external Pi modification.
- No full benchmark dataset run or published-score reproduction.
- No claim that arbitrary future runtimes preserve Pi-native reasoning or
  context-management semantics.
- No decision yet to keep DCI bundled forever or split it into a separately
  versioned plugin; the extraction document defines the decision gate.
