# AF-350 Asterion Standalone Promotion Readiness Design

> Approved interactively on 2026-07-23. This design prepares the existing
> `asterion/` subtree to be promoted to a Git repository root without creating,
> publishing, or pushing a separate repository in this package.

## Objective

Make the contents of `asterion/` a complete promotion-ready repository root.
Copying those contents into an empty directory must produce a project whose
provider-free Python build and tests, installed CLI verification, documentation
checks, TypeScript tests, Rust checks, and Makefile entry points run without the
parent DCI-Agent-Lite source tree.

External Pi, corpora, benchmark datasets, model credentials, and Judge
credentials remain explicit external dependencies. Source self-containment does
not mean vendoring those resources or claiming that a full dataset was rerun.

## Current Boundary

The subtree already owns the sole buildable `asterion` Python distribution,
`src/asterion`, project-local tests, schemas, documentation, benchmark launchers,
the TypeScript runtime packages, and the Rust controlled executor. It does not
yet own a repository README, license, ignore rules, environment template,
Makefile, lockfile, CI workflow, or a promotion smoke gate. Several launchers
still compute the mixed-repository root, and DCI `acceptance` dynamically loads
the mixed-root product verifier and cross-product evidence.

The mixed repository also retains the original `src/dci` comparison baseline,
the 538-selector cross-product verifier, retained bounded evidence, project
governance, and historical state. Those assets are integration evidence, not
dependencies of the standalone Asterion product.

## Chosen Architecture

### One subtree, two physical placements

`asterion/` is treated as a project root while it remains nested and after its
contents are promoted. All project-owned paths resolve from that root. No
production source, project test, launcher, Make target, or standalone document
may require a parent `src/dci`, parent `tools/`, the root uv workspace, or an
absolute path from the development machine.

The mixed repository may call into the nested project, but the nested project
must never call back into the mixed repository except through an explicitly
configured external resource path.

### Separate product acceptance from integration parity

`asterion verify --provider dci-agent-lite --level acceptance` becomes a
package-owned, provider-free structural verification. It validates the installed
providers, applications, capability manifests, assemblies, schemas, packaged DCI
resources, configuration safety, and exact internal identities. It performs zero
Agent and Judge operations and works from both a source checkout and an isolated
wheel. It does not dynamically execute a verifier discovered in the current
directory.

The existing mixed-root `tools/verify_asterion_dci_product.py` remains the
cross-product integration gate. Its original DCI/Asterion product rows,
538 delegated selectors, launcher parity, retained bounded record, and historical
evidence claims remain owned by DCI-Agent-Lite. They are not relabeled as live
standalone verification.

### Source and installed verification layers

The standalone project has three provider-free layers:

1. Installed acceptance validates the immutable package/resource closure.
2. Source `make check` validates tests, compile, Ruff, wheel construction,
   isolated installation, CLI smoke, documentation, TypeScript, and Rust.
3. Promotion smoke copies only the tracked Asterion project contents to a fresh
   temporary directory and repeats the standalone gates there.

Provider-backed `preflight`, `basic`, and `complete` retain their existing
explicit cost and resource boundaries. Missing external resources fail before
provider construction and do not weaken provider-free acceptance.

## Repository Assets

The promotion-ready subtree owns:

- `README.md` as the standalone product landing page and quick start;
- the existing MIT `LICENSE` terms and copyright notice;
- `.gitignore` covering Python, uv, Node, Rust, credentials, corpora, datasets,
  outputs, local Pi, and editor/build caches;
- `.env.template` containing only Asterion/DCI variables with empty credential
  examples and standalone-relative defaults;
- `Makefile` as the complete documented project command surface;
- `uv.lock` for reproducible Python dependency resolution;
- `.github/workflows/ci.yml` for provider-free Python, documentation,
  TypeScript, Rust, wheel, and promotion checks;
- `pi-revision.txt` as the immutable default revision hint for an external Pi
  checkout;
- project-owned promotion and documentation checking utilities where a shell or
  existing test module cannot express the invariant safely.

No credential, `.env`, corpus, dataset, output, retained private evidence,
external Pi checkout, worktree, collaboration memory, or mixed-repository status
file enters the subtree.

## Makefile Contract

The standalone Makefile exposes:

- lifecycle targets: `help`, `sync`, `build`, `test`, `lint`, `docs-check`,
  `check`, and `promotion-check`;
- framework targets: `asterion-list`, `asterion-describe`,
  `asterion-verify-preflight`, `asterion-verify-basic`,
  `asterion-verify-acceptance`, `asterion-verify-complete`, and `asterion-run`;
- DCI targets: `dci-system-prompt`, `dci-run`, `dci-terminal`, `dci-resume`,
  `dci-evaluate`, `dci-benchmark`, `dci-export`, `dci-ablation`, and `dci-paper`;
- cross-language targets: `test-typescript`, `test-rust`, and `check-rust`.

Parameter-rich framework commands consume `ASTERION_ARGS`; DCI commands consume
`DCI_ARGS`. Targets do not evaluate shell fragments, print credentials, invent
defaults that bypass the CLI, or mint full-execution authority. `make help`
labels provider-free, bounded provider-backed, and dormant/full command classes.

The mixed-root Makefile delegates shared Asterion targets to `make -C asterion`
and retains a separately named mixed-repository integration target. This avoids
two definitions of the standalone commands while preserving original DCI checks.

## Launcher and External Resource Contract

Every Asterion launcher resolves `PROJECT_ROOT` to the directory containing the
standalone `pyproject.toml` and invokes `uv run --project "$PROJECT_ROOT"`.
Datasets and corpora resolve from `ASTERION_DCI_RESOURCE_ROOT` when supplied and
otherwise from the standalone root. Missing resources produce concise nonzero
preflight failures before provider construction.

`DCI_PI_DIR` defaults to `./pi` relative to the standalone root;
`./pi-mono` remains a documented compatibility fallback only. The external Pi
checkout is never edited, copied, or committed by AF-350.

## Documentation Contract

The standalone README links the existing `docs/README.md` hub and provides
installation, discovery, provider-free acceptance, external-resource setup,
cost boundaries, development gates, and promotion instructions. Documents use
standalone-root commands as the primary form. Mixed-repository comparison
commands are clearly labeled as integration-only and do not appear as standalone
requirements.

The full functional guide replaces stale closure counts with commands and current
evidence labels. Historical counts remain only where explicitly identified as
historical package closure evidence. All local Markdown links must resolve in the
promoted copy.

## Security and Failure Boundaries

- Installed acceptance executes package-owned Python only; it never imports a
  verifier from the invocation directory.
- Provider-free gates create no Agent or Judge request and never run a full
  dataset.
- Cost-bearing Make targets remain explicit passthroughs and cannot infer
  authorization from `.env`, cached artifacts, or target names.
- Promotion smoke rejects parent-tree references, absolute development paths,
  secrets, symlink escapes, and missing tracked assets.
- CI contains no provider credentials and runs only provider-free commands.
- D-053 and D-055 remain unchanged: strict paper/full-result execution requires
  separate successor governance, exact authority, explicit invocation, and a
  finite budget.

## Compatibility and Migration

The Python import names, wheel name, console scripts, provider IDs, application
IDs, runtime IDs, wire schemas, and packaged DCI resource identities remain
stable. AF-350 changes verification ownership and repository-relative paths, not
the runtime protocol or research behavior.

The mixed-root cross-product verifier continues to run against the nested
project and remains the authority for original DCI/Asterion parity. Root tests
are updated to distinguish standalone acceptance from integration parity instead
of assuming one verifier represents both claims.

No separate Git repository, remote, release, package publication, or deletion of
the mixed-root subtree occurs in AF-350. Those are later operator-controlled
steps after promotion readiness is verified.

## Test Strategy

Implementation follows red-green-refactor. Tests are added before production or
repository behavior changes.

Required test groups are:

1. repository asset and safe-template contracts;
2. exact Make target rendering and cost labels;
3. source and isolated-wheel standalone acceptance parity with zero provider
   operations;
4. launcher project-root and external-resource resolution;
5. absence of parent `src/dci`, parent `tools`, root-workspace, credential, and
   absolute-machine dependencies;
6. temporary promotion-copy Python, CLI, documentation, TypeScript, and Rust
   smoke;
7. mixed-root 538-selector integration and public documentation regression;
8. Python compile/Ruff, shell syntax, Node tests, Rust test/fmt/Clippy, scope,
   process, and diff gates.

## Acceptance

AF-350 closes only when all of the following are true:

- the contents of `asterion/` can be copied to an empty directory and treated as
  a Git repository root without further source edits;
- `uv sync --frozen`, the standalone Python tests, compile, Ruff, wheel build,
  isolated install, CLI list/describe/acceptance, documentation links,
  TypeScript tests, Rust test/fmt/Clippy, and Makefile checks pass in that copy;
- installed acceptance is package-owned, provider-free, body-free, and identical
  between source and wheel execution;
- every standalone launcher resolves the standalone root and accepts external
  resources only through documented paths;
- the mixed-root integration verifier and governance audit continue to pass;
- no provider request, full dataset, secret persistence, external Pi mutation,
  repository publication, or remote push occurs during closure.

## Revalidation Triggers

Revisit this design before splitting DCI into a separate distribution, renaming
the TypeScript or Rust packages, changing public wire identities, adding network
CI, embedding datasets/Pi, publishing a release, or replacing mixed-root parity
with standalone evidence.
