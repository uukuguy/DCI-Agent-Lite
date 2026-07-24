# AF-360 Standalone First-Run Readiness Design

> Design direction approved interactively on 2026-07-24. This package closes
> the gap between a promotion-ready source tree and an operator-ready fresh
> clone without vendoring Pi, data, credentials, or private evidence.

## Objective

Make a freshly exported Asterion repository provide a complete, documented,
provider-free path to prepare its external runtime and minimum DCI resources.
After setup, an operator who supplies their own Agent and Judge authentication
must be able to pass `asterion verify --provider dci-agent-lite --level
preflight` without referring to the parent DCI-Agent-Lite checkout.

AF-360 does not publish a repository, execute an Agent or Judge, run a full
dataset, or make external resources part of the wheel. It makes those external
dependencies reproducibly provisionable and their readiness failures
actionable.

## Problem Statement

AF-350 proved that the contents of `asterion/` can build, test, install, and run
provider-free acceptance in a clean copy. It did not prove fresh-clone
provider-backed readiness.

The promoted tree currently has four disconnected contracts:

1. `DCI_PI_DIR=./pi` names an absent source checkout, while execution directly
   launches `packages/coding-agent/dist/cli.js` and does not consume a global
   `pi` executable.
2. Pi authentication defaults to `<DCI_PI_DIR>/.pi/agent`, while the supported
   `DCI_PI_AGENT_DIR` override is absent from the standalone template and
   operator path.
3. `ASTERION_DCI_RESOURCE_ROOT` and `ASTERION_DCI_CORPUS_ROOT` name external
   layouts, but the standalone repository provides no command that creates or
   validates those layouts.
4. empty provider/model values resolve to Pi runtime defaults in production,
   while `describe` reports null defaults and preflight cannot tell an operator
   how the effective values were selected.

A clean standalone preflight therefore passes Node only and fails environment,
configuration, Pi, corpora, and Judge readiness. This is a product onboarding
failure, not an installation or user-error boundary.

## Chosen Architecture

### Pinned source checkout remains authoritative

The supported Pi runtime remains an external Git checkout at the exact commit
recorded by `pi-revision.txt`. A globally installed `pi` executable is not a
substitute for that checkout because it cannot independently prove the source
revision, built package graph, Asterion extension compatibility, or recorded
runtime provenance.

The standalone project owns a safe `setup-pi` command that:

- resolves `DCI_PI_DIR`, defaulting to project-local ignored `./pi`;
- clones only the configured Pi repository when the target is absent;
- checks out the full locked commit in detached mode;
- refuses to switch a dirty existing checkout;
- installs and builds only when the selected source lacks the required
  `packages/coding-agent/dist/cli.js`;
- provides a read-only check mode that never fetches or mutates;
- never reads, copies, prints, or creates authentication material.

The command is idempotent. Repository URL and revision overrides remain
explicit advanced controls and never become duplicate tracked defaults.

### Authentication is separate from executable source

`DCI_PI_AGENT_DIR` is the public Asterion DCI authentication-directory
selection. The standalone environment template explicitly points operators to
their existing user-managed Pi authentication directory, normally
`~/.pi/agent`, while preserving explicit overrides and the legacy
checkout-local layout.

Setup never copies `auth.json` into the external checkout. Preflight reports
the resolved authentication-directory class and an actionable missing-auth
message without exposing file contents or credentials. A global Pi installation
may be used to establish its own login, but Asterion still executes the pinned
checkout.

### Resource provisioning has explicit tiers

The standalone project owns one resource setup tool with two named profiles:

- `basic` prepares exactly the external corpora needed by the bounded
  preflight/basic cases: `corpus/wiki_corpus` and `corpus/bc_plus_docs`.
- `benchmark` prepares or validates the dataset and corpus paths referenced by
  the checked-in launchers, including `data/dci-bench`,
  `data/bcplus_qa.jsonl`, BRIGHT, BEIR, and their corresponding corpus trees.

Both profiles write beneath an explicit resource root. The default is the
standalone project root, whose `/corpus/` and `/data/` children remain ignored.
`ASTERION_DCI_RESOURCE_ROOT` names that parent; `ASTERION_DCI_CORPUS_ROOT`
names its `corpus/` child for preflight compatibility.

Every upstream resource has a declarative source/layout entry. Resources that
can be fetched from the configured upstream are downloaded idempotently and
converted through Asterion-owned export functions. Gated or unavailable
resources fail with the exact missing logical resource, expected path, upstream
identity, and authentication prerequisite. No command silently substitutes a
different corpus, sample, or dataset.

Resource setup may use network and disk only after the operator invokes it. It
never constructs a runtime provider or Judge, and it never authorizes a
benchmark run. The `basic` profile is the default onboarding boundary; the
larger `benchmark` profile is always separately named.

### One public configuration contract

The runtime resolver remains authoritative. For the Pi runtime, the effective
defaults are `openai-codex` and `gpt-5.6-luna` unless explicitly overridden.
The environment template, product description, JSON output, preflight, and
documentation all report the same defaults and source precedence.

The standalone `.env.template` contains:

- explicit Pi runtime/provider/model defaults;
- `DCI_PI_DIR`, `DCI_PI_AGENT_DIR`, output, corpus, and resource-root examples;
- complete safe Judge endpoint/model/request-shape defaults matching the
  product contract;
- empty, commented credential examples only.

Preflight separates readiness checks for source checkout, built CLI,
authentication, Agent selection, Judge configuration, resource layout, Node,
and environment file. Failures include stable repair commands or configuration
names and remain body-free.

## Command Contract

The standalone Makefile adds:

- `setup` — sync dependencies, prepare pinned Pi, and prepare basic resources;
- `setup-pi` — mutate only the selected ignored external Pi checkout;
- `check-pi` — read-only Pi revision/build/layout verification;
- `setup-resources-basic` — fetch/convert the bounded onboarding corpora;
- `setup-resources-benchmark` — fetch/convert or precisely report every
  launcher resource;
- `check-resources-basic` and `check-resources-benchmark` — read-only layout
  checks;
- `doctor` — provider-free effective-configuration and external-readiness
  report.

`make help` labels setup targets as network/disk operations with zero
Agent/Judge operations. Existing provider-backed verification targets retain
their explicit cost labels. No target shells user-provided fragments or prints
credential values.

The supported first-run sequence is:

```bash
uv sync --frozen
make setup-pi
make setup-resources-basic
cp .env.template .env
# add operator-owned Agent and Judge authentication
make doctor
make asterion-verify-preflight
```

`make setup` is the explicit convenience composition of the first three
provisioning steps. It may access Git, npm, and declared resource hosts; it
cannot invoke an Agent, Judge, benchmark, or full execution.

## Distribution and Dependency Boundary

Pi, corpora, datasets, credentials, and generated output remain ignored
external assets and never enter the wheel or sdist. Setup/check tools and their
declarative resource manifest are project-owned repository utilities.

Any new Python acquisition dependency must be declared and locked by the
standalone project. Runtime library imports remain independent of download
dependencies unless the operator invokes resource setup. A wheel installation
continues to provide discovery and acceptance without external resources.

No production or setup code imports `src/dci`, executes parent repository
tools, follows parent-relative paths, or assumes the mixed repository exists.
A promoted copy remains the primary test boundary.

## Error and Safety Boundaries

- Existing dirty Pi checkouts are never reset, cleaned, or switched.
- Existing resource files are not overwritten unless their declared identity
  and incomplete state make replacement safe.
- Temporary clones/downloads are isolated and atomically promoted when
  practical; interrupted work remains distinguishable from complete resources.
- Symlinked Pi targets, authentication files, resource roots, and generated
  destination escapes fail closed.
- Setup diagnostics contain paths, resource IDs, revisions, and safe
  configuration names only; they never retain credentials or downloaded
  document bodies.
- Provider-free setup and doctor commands report Agent operations `0`, Judge
  operations `0`, and full dataset `no`.
- D-053 and D-055 remain unchanged. Resource presence, `.env`, setup success,
  cached artifacts, or a prior report cannot authorize full execution.

## Compatibility

Existing `DCI_PI_DIR`, `DCI_PI_PACKAGE_DIR`, `DCI_PI_AGENT_DIR`,
`ASTERION_DCI_*` aliases, CLI overrides, application IDs, provider IDs, runtime
IDs, schema identities, launcher names, and output formats remain compatible.

AF-360 changes the onboarding and diagnostic contract. It does not accept a
global Pi executable as a new runtime identity, change Pi RPC semantics, change
paper benchmark selection, embed data, or weaken mixed-repository integration.

## Test Strategy

Implementation follows red-green-refactor. Each behavior is first represented
by a focused failing test.

Required test groups are:

1. Pi setup against local fixture Git repositories: absent clone, exact pin,
   idempotence, missing revision fetch, dirty mismatch rejection, build
   invocation, read-only check, symlink rejection, and credential non-access.
2. Resource setup against local fixture sources: basic layout, conversions,
   idempotence, incomplete download recovery, gated/unavailable diagnostics,
   benchmark inventory coverage, and destination containment.
3. configuration parity: `.env.template`, runtime resolver, `describe --json`,
   doctor, and preflight expose the same Pi provider/model/path defaults.
4. authentication selection: explicit user-managed agent directory works;
   absent or unsafe auth produces a content-free actionable failure.
5. exact Make target rendering, help cost labels, and shell syntax.
6. clean-copy setup/check flows with local fixture sources and zero
   Agent/Judge operations.
7. existing standalone Python, documentation, wheel, TypeScript, Rust,
   promotion, and mixed-root integration regressions.

CI never contacts the real Pi remote, Hugging Face, an Agent, or a Judge.
Networked setup behavior is proven with injected local repositories and fixture
resource sources.

## Acceptance

AF-360 closes only when all of the following are true:

- a clean promoted copy exposes the complete setup, check, doctor, and
  preflight command sequence without parent-repository dependencies;
- local-fixture setup creates an exact pinned Pi checkout with the built CLI
  and an explicit external authentication-directory contract;
- local-fixture basic resource setup creates both required corpus directories,
  and benchmark checking accounts for every checked-in launcher path;
- `.env.template`, runtime resolution, product description, doctor, and
  preflight agree on effective runtime/provider/model/path defaults;
- every missing prerequisite reports the exact safe repair action before
  provider construction;
- setup and clean-copy verification perform zero Agent operations, zero Judge
  operations, and no full dataset;
- standalone provider-free, promotion, distribution, documentation,
  cross-language, mixed integration, scope, privacy, shell, Ruff, compile, and
  diff gates pass;
- no credential, external Pi state, corpus, dataset, private evidence,
  publication, remote push, or provider-backed operation is committed or
  performed during closure.

## Revalidation Triggers

Revisit this decision before accepting a global Pi executable as authoritative,
changing the locked Pi source/provenance model, changing default Agent or Judge
identities, embedding external resources, making network setup implicit,
publishing a release, or authorizing a full dataset.
