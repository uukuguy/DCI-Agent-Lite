# Asterion Makefile Entry Points Design

## Goal

Make the accepted Asterion DCI discovery and verification workflow runnable
from memorable repository-root Make targets without requiring users to copy the
full generic CLI invocation from documentation.

## Public targets

The root Makefile exposes exactly five new phony targets:

```text
asterion-describe
asterion-verify-preflight
asterion-verify-basic
asterion-verify-acceptance
asterion-verify-complete
```

Each target delegates directly to `uv run asterion`; no shell wrapper or second
verification implementation is introduced. The two provider-backed targets
remain explicitly named `basic` and `complete`, so a generic or provider-free
sounding target cannot unexpectedly spend provider quota.

## Configuration

The Makefile defines overridable defaults:

```make
ASTERION_PROVIDER ?= dci-agent-lite
ASTERION_ENV_FILE ?= .env
ASTERION_CORPUS_ROOT ?= $(CURDIR)/corpus
ASTERION_VERIFY_OUTPUT_ROOT ?= $(CURDIR)/outputs/asterion-verification
```

`describe` needs only the provider. `acceptance` needs only the provider and
level because it is source-checkout, provider-free verification. `preflight`
receives the environment and corpus roots. `basic` and `complete` additionally
receive the output root. Existing process-environment precedence and `.env`
loading remain owned by Asterion; Make does not source or print credential
values.

Callers can override one value without editing the repository, for example:

```bash
make asterion-verify-preflight ASTERION_CORPUS_ROOT=/path/to/corpus
```

## Documentation

README and `docs/guides/asterion-capability-usage.md` put the Make targets next
to their full CLI equivalents. The guide continues to explain which levels are
provider-free and which run two bounded Pi operations plus one Judge operation.
The full CLI remains canonical and usable outside this source checkout; Make is
the repository convenience surface.

## Failure behavior and safety

Make returns the delegated Asterion exit status unchanged. Missing `.env`,
corpora, Pi, Judge, or provider configuration is reported by the existing
preflight checks. Target recipes use direct fixed arguments plus quoted Make
variable expansions; they do not evaluate shell fragments, source `.env`, run
a full dataset, or contain credential values.

## Verification

- A focused test parses or dry-runs the Makefile and proves all five targets,
  their exact levels, required arguments, overridable defaults, and phony
  declarations.
- `make -n` verifies rendered commands without executing Pi or Judge.
- `make asterion-describe` and `make asterion-verify-acceptance` are safe live
  smoke checks because neither makes provider requests.
- Shell/diff/scope checks close the bounded work package; no full dataset or
  provider-backed rerun is required.

## Non-goals

- No parameterized `LEVEL=` target or ambiguous `asterion-verify` alias.
- No new scripts, Python behavior, verification profiles, or provider protocol.
- No changes to the original DCI examples, Asterion runtime, external Pi, or
  credential configuration.
