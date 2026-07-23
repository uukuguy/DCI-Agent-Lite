# Asterion

Asterion is a composable, multi-runtime agent application framework. This
repository includes the framework, built-in controlled-code and DCI application
providers, packaged schemas and resources, TypeScript runtime components, and a
Rust controlled executor.

## Quick start

```bash
uv sync --frozen
uv run asterion list
uv run asterion describe --provider dci-agent-lite
uv run asterion verify --provider dci-agent-lite --level acceptance
```

The `acceptance` profile is provider-free: it validates installed package and
resource closure without contacting an Agent or Judge and without running a full
dataset. Provider-backed profiles require an external Pi checkout, local
corpora, and credentials configured through `.env`.

Copy `.env.template` to `.env` only when using those external capabilities. Pi
defaults to `./pi`; it remains an independent checkout and is never vendored by
Asterion.

## Development

```bash
make help
make check
```

See the [documentation hub](docs/README.md) for framework architecture, DCI
usage, validation, external-resource boundaries, and extraction guidance.

