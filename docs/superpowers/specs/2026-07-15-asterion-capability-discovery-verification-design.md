# Asterion Capability Discovery and Verification Design

## Problem

Asterion capability packages are implemented and tested, but a user cannot
discover their functions, required configuration, runnable examples, or
verification levels from the generic `asterion` command. The DCI guide exposes
the evidence, but its audit vocabulary and many environment variables force a
new user to read documentation or source code before running anything.

The original DCI product has two obvious basic example scripts. Asterion needs
an equally obvious single entry point, while also making complete capability
verification available for DCI and future packages.

## User contract

Users do not read package source to discover functionality. The installed
generic CLI provides:

```text
asterion describe --provider PROVIDER
asterion verify --provider PROVIDER --level LEVEL
```

`describe` lists the selected provider's applications, capability functions,
normal execution commands, required configuration names, verification levels,
provider-cost classification, and expected artifacts. It loads only the
explicitly selected provider and supports a stable JSON form.

`verify` runs a provider-owned structured verification profile through the
generic CLI. It never executes a shell command string and never loads adjacent
providers. Explicit selection of a provider-backed level is the operator's
authorization for the bounded requests named by that level.

Providers without discovery or verification support remain valid and receive
a clear `not supported by provider` result rather than an inferred command.

## Generic package descriptor

The Asterion provider boundary gains immutable public values for:

- product summary and version;
- application and capability-function descriptions;
- normal runnable command examples expressed as argument arrays;
- configuration fields with name, purpose, required/optional status, default,
  secret flag, and validation hint;
- verification profiles with level, cost class, checks, prerequisites, and
  the number of provider-backed operations and whether full datasets are allowed;
- verification results with check ID, status, safe message, artifact
  references, and aggregate counts.

Secret values are never part of descriptors or results. Configuration reports
only `present`, `missing`, source (`process`, `.env`, CLI), and a safe fix hint.

## Configuration experience

The repository-root `.env` remains the normal shared configuration surface.
`asterion verify` automatically loads it using the established precedence;
`--env-file PATH` selects another file without printing its contents.
`--corpus-root PATH` and `--output-root PATH` provide understandable operator
arguments so users do not need to learn Asterion-specific environment names.

For DCI, `describe` and failed preflight name at least:

- `DCI_PROVIDER` and `DCI_MODEL`;
- the credential required by the selected provider;
- `DCI_PI_DIR` with the `./pi` default;
- corpus directories required by the selected verification level;
- Judge configuration only for levels that use the Judge.

Missing configuration fails before Pi or Judge starts and prints copyable
variable names and example placeholders, never values.

## Original DCI functional map

The user-facing complete DCI surface is grouped as follows:

| Function group | Original DCI behavior | Asterion execution/discovery | Verification |
|---|---|---|---|
| Configuration and Pi controls | shared `.env`, provider/model/tools, Pi paths, timeout, thinking, heap, session and literal extra arguments | `asterion describe --provider dci-agent-lite`; normal execution through the installed Pi application or `asterion-dci run` | preflight plus configuration/Pi-argv contract |
| Basic corpus research | ask Pi to search a local raw corpus and return an answer | `asterion verify --provider dci-agent-lite --level basic` case 1 | bounded real Pi run equivalent to `dci_basic_example.sh` |
| Runtime-context research and Judge | bounded multi-turn research with tools, context controls, expected-answer evaluation | the same `basic` command, case 2 | bounded real Pi plus Judge run equivalent to `dci_runtime_context_example.sh` |
| Interactive and terminal operation | stdin/question file, prompt files, direct TTY session, exit status | described `asterion-dci run`, `system-prompt`, and `terminal` commands | model-free lifecycle/argv tests plus basic live evidence |
| Durable evidence and resume | state, events, full/processed conversation, tool results, final, stderr, provenance, isolated attempts and compatible resume | described `asterion-dci run` and `resume` commands | artifact-schema, failure, resume and locking checks |
| Evaluation and exact cache | explicit run evaluation, safe Judge request, fingerprinted result reuse | described `asterion-dci evaluate` and run-time evaluation options | model-free cache/fingerprint checks plus basic Judge evidence |
| Batch QA/IR, metrics and analysis | BCPlus, QA and BRIGHT datasets; concurrency, cancellation, resume/reuse, accuracy/NDCG, summaries, analysis and figures | described `asterion-dci benchmark`, twelve installed profiles and launchers | 533 delegated checks, six product extras, and bounded one-row evidence |
| Corpus and dataset export | BCPlus document export, BRIGHT subset export, BCPlus QA extraction/decryption | described `asterion-dci export bcplus`, `bright`, and `bcplus-qa` | deterministic transform, atomic output and safe-failure checks |
| Installed product boundary | runnable installed command, profiles/resources, Pi-default application, no source-DCI dependency | generic `asterion run` and package-local `asterion-dci` | isolated wheel and installed application checks |

The first two real scenarios are the approachable smoke proof. The remaining
checks prove complete product behavior without spending provider quota on every
failure, resume, cache, batch, export, and installation branch.

## DCI verification levels

### `preflight` — provider-free

Loads configuration, resolves Pi and Node, checks required corpus directories,
selects the provider credential name, validates Judge configuration when
needed, and shows the exact checks that later levels will run. It sends no
external request.

### `basic` — bounded provider-backed

Runs exactly two Asterion-owned cases through the shared `.env` and Pi:

1. wiki corpus question, matching the original basic example;
2. runtime-context corpus question with bounded turns and Judge evaluation,
   matching the original runtime-context example.

The summary reports each case, answer artifact, evaluation verdict when
applicable, and output directory. The command exits nonzero if either fails.

### `acceptance` — provider-free replay

Runs the public product verifier and reports the eight functional groups:
8/8 product rows, 533/533 fine-grained batch selectors, 12/12 launcher pairs,
6/6 additional batch checks, isolated wheel/application proof, and the
digest-bound 7/7 bounded-real acceptance record. It makes zero provider calls.
When a private acceptance root is explicitly supplied, it additionally
revalidates native artifacts and every manifest-referenced credential scan.

### `complete` — bounded end-to-end aggregate

Runs `preflight`, `basic`, then `acceptance` and presents one feature-oriented
summary. It makes only the two named bounded Pi cases and the required Judge
evaluation; it never launches a full dataset. Each Pi case has an explicit turn
limit. The public count is the number of provider-backed operations (two Pi
runs plus one Judge evaluation), not a claim that a multi-turn Pi run maps to
one provider API request. This is the recommended command
for answering “is the complete Asterion DCI capability working in my
environment?”

Canonical operator flow:

```bash
asterion describe --provider dci-agent-lite
asterion verify --provider dci-agent-lite --level preflight --corpus-root ./corpus
asterion verify --provider dci-agent-lite --level complete --corpus-root ./corpus
```

## Output and errors

Human output uses plain function names and four statuses: `PASS`, `FAIL`,
`SKIP`, and `NOT RUN`. A final table distinguishes configuration, real request,
local contract, retained evidence, and full-dataset checks. It states
provider-backed operation counts and whether a full dataset ran.

`--json` emits the closed result schema without questions, answers,
conversations, credentials, provider bodies, or private absolute paths.
Failures name the missing configuration or failed check and give the next safe
command. Partial success never becomes an overall success exit code.

## Documentation

README and the verification guide begin with the three canonical commands and
a minimal `.env` example. Audit terminology and individual test commands move
under an advanced section. The two Asterion example scripts remain supported,
but `asterion verify ... --level basic` is the primary entry point.

## Testing and acceptance

- TDD covers descriptor validation, immutable results, redaction, provider
  selection, unsupported providers, level parsing, exit codes, and JSON output.
- Fixture providers prove that only the selected provider loads and that
  provider-free levels cannot declare external requests.
- DCI tests prove `basic` maps to the two existing Asterion example semantics,
  `acceptance` delegates to the current product verifier, and `complete`
  executes levels in order without full-dataset launchers.
- Source acceptance is loaded only from the verifier module's trusted source
  checkout ancestor, never from the process working directory. Isolated-wheel
  tests prove `describe` and preflight work outside the repository while source
  acceptance reports `NOT RUN`.
- One bounded real `complete` run is allowed using the shared `.env`; no full
  dataset is authorized.

## Non-goals

- No generic shell-script runner or arbitrary command execution protocol.
- No secret storage, interactive credential editor, or automatic login.
- No full-dataset execution as part of `complete`.
- No requirement that third-party providers implement verification.
- No change to original `src/dci` behavior or its two example scripts.
