# Asterion

Asterion is a composable, multi-runtime agent application framework. This
repository contains the Python framework, built-in controlled-code and DCI
application providers, schemas, examples, launchers, TypeScript runtime
components, and a Rust controlled executor.

## Installation

Install the locked development environment from the repository root:

```bash
uv sync --frozen
```

Python 3.10 or newer and `uv` are required. Node.js and Rust are needed only for
their corresponding cross-language checks.

## Discovery and installed acceptance

These commands inspect the installed package and make no provider request:

```bash
uv run asterion list
uv run asterion describe --provider dci-agent-lite
uv run asterion verify --provider dci-agent-lite --level acceptance
```

`acceptance` verifies package-owned closure: providers, applications,
assemblies, capability manifests, context profiles, benchmark identities, and
paper scopes. It does not contact an Agent or Judge and does not run a dataset.

## External Pi and resources

Pi is an external checkout, never vendored into this repository. Its expected
revision is recorded in `pi-revision.txt`; set `DCI_PI_DIR` when the checkout is
not at `./pi`. Benchmark launchers resolve datasets and corpora from the project
root by default, or from `ASTERION_DCI_RESOURCE_ROOT` when those resources live
elsewhere.

Copy `.env.template` to `.env` only for provider-backed work. Keep Agent and
Judge credentials in `.env` or exported environment variables; never commit
them. External `pi/`, `datasets/`, `corpora/`, generated outputs, and private
evidence remain outside the distribution.

## Cost boundaries

- `acceptance`, `list`, `describe`, `make test`, and `make check` are
  provider-free.
- `preflight` checks external readiness but does not call a provider.
- `basic` performs bounded Agent/Judge work when correctly configured.
- `complete` includes the bounded provider-backed path plus acceptance.
- Full datasets, paper-score reproduction, and publication require separate
  governance, an explicit invocation, and a finite budget.

Use `make help` to see the same boundary beside every command group.

## Development

```bash
make test
make lint
make docs-check
make check
```

The [documentation hub](docs/README.md) links the framework architecture,
capability usage, complete DCI reference, and functional verification guide.

## Promotion

Before making this directory the root of a Git repository, run:

```bash
make check
make promotion-check
```

`promotion-check` copies the standalone tree into a temporary directory and
re-runs the provider-free repository gates there. It does not create a remote,
publish a package, or run a provider.

## Mixed-repository integration parity

The historical `538/538` delegated-selector matrix is a **mixed-repository only**
integration gate maintained by DCI-Agent-Lite. It compares the original DCI
baseline with Asterion and is not a current standalone acceptance result. The
standalone package deliberately does not ship that baseline, its governance
ledger, retained private evidence, or its integration verifier.
