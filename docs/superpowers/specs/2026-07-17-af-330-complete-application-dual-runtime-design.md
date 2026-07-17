# AF-330 Complete Application and Dual-Runtime Design

> Status: approved by the parent paper-aligned design and refined on 2026-07-17.

## Goal

Make research, evaluation, benchmark, analysis, and export first-class Asterion
capability/application units, then prove the restricted local-corpus research
edge with bounded real Pi and Claude Code runs. This is functional reproduction;
AF-340 alone owns full datasets and published-score comparison.

## Application graph

The installed application is one declared five-stage graph:

`research -> evaluation -> benchmark -> analysis -> export`

Each stage has its own package manifest, implementation, declared input/output
artifacts, and completion event. Implementations call the existing Asterion DCI
domain modules rather than duplicating CLI behavior. The product CLI and generic
application therefore bind the same implementation identity and native artifact
digests. Pi and Claude assemblies share package and artifact contracts; only the
research runtime adapter differs.

Evaluation consumes research evidence, benchmark consumes dataset rows and the
same evaluation contract, analysis consumes immutable benchmark/evidence
artifacts, and export consumes analysis. Invalid, missing, reordered, or
identity-mismatched upstream artifacts fail before provider construction.
Each consumed artifact must carry the exact complete-application schema and the
current implementation digest; matching media type alone is insufficient.

## Claude Code restriction boundary

Claude Code runs from an attempt-specific directory containing only the selected
bounded corpus and task input. Asterion exposes exactly `Read,Grep,Glob`; Bash,
WebFetch, WebSearch, Task/subagents, editing, MCP, plugins, hooks, skills, Chrome,
and session persistence are absent. `--permission-mode dontAsk` hard-denies any
tool outside the allow surface, and `--strict-mcp-config` prevents ambient MCP
discovery.

An inline settings object enables the native sandbox with
`failIfUnavailable=true`, `allowUnsandboxedCommands=false`, home-directory read
denial, and an explicit attempt-root read allowance. Although Bash is not in the
tool surface, keeping the OS boundary mandatory prevents a later tool expansion
from silently weakening acceptance. Preflight checks the installed CLI help,
version, exact flags, settings identity, corpus containment, and credential
availability before a provider request. The command and public evidence record
only safe identities and counts.

The raw Claude stream, normalized events, final answer, and corpus manifest are
private 0600 evidence. The public projection contains schemas, hashes, runtime
identity, tool names, turn/operation counts, cancellation/deadline status, and
artifact references without prompts, answers, tool bodies, credentials, or
private paths.

Private policy evidence also records the resolved runtime working directory.
The independent auditor requires it to equal the separately supplied resolved
corpus root before resolving relative tool arguments. The runtime owns the child
process after start: cancellation terminates and reaps it, deadlines cannot
leave provider work running, and a nonzero process exit always fails even if a
syntactically successful result event was emitted.

## Shared agent configuration

Runtime selection and model-provider selection are separate. The application or
CLI selects `pi.reference` or `claude-code.reference`; both adapters consume the
same `DCI_PROVIDER` and `DCI_MODEL` agent selection. Users do not duplicate a
logical provider, model, or credential into Claude-native configuration.

Each adapter translates only providers it actually supports. Pi continues to
use its provider registry. For `minimax` and `minimax-cn`, the Claude adapter
derives its private Anthropic-compatible subprocess environment from the same
provider/model and the provider's existing `MINIMAX_API_KEY` or
`MINIMAX_CN_API_KEY`. Token Plan credentials (`sk-cp-`) derive Claude's bearer
auth token; ordinary MiniMax API keys derive Claude's API-key header, matching
the locked Pi provider. The derived base URL, credential, primary model, and
Claude model aliases exist only at the subprocess boundary and are never persisted.
An unsupported provider/runtime combination or a missing credential fails
before Claude starts. Judge selection remains independently configured through
`DCI_EVAL_JUDGE_*` because evaluation is a distinct role, not an agent runtime.

The restricted child environment is rebuilt from a small operational allowlist
(executable lookup, home/temp/locale, certificate, and proxy settings) plus the
adapter-derived provider values. It does not inherit Judge credentials,
arbitrary caller secrets, stored-OAuth selectors, or competing Claude auth
modes. Provider and Judge role separation is therefore enforced, not merely
documented.

## Pi restriction boundary

Pi continues to use the Asterion-owned extension and native recorder. AF-330's
bounded application profile exposes only dedicated read/grep operations over an
attempt-local corpus, rejects Bash/web/subagent capabilities, and binds the same
research artifact contract used by Claude Code. The external checkout remains
unmodified.

## Acceptance

- Five discoverable packages have exact event/artifact edges and executable
  implementations.
- Source, product CLI, generic application, installed application, and isolated
  wheel resolve identical implementation and artifact identities.
- Model-free tests prove composition, cache invalidation, privacy, cancellation,
  deadline, failure, resume, and restriction behavior.
- One bounded real Pi run and one bounded real Claude Code run read only the
  selected local corpus, use no web/subagent/outside answer-bearing source, and
  produce independently rebound private evidence plus a body-free public record.
- Fixture-only Claude evidence cannot close AF-330. No full dataset runs.
- One MiniMax provider/model/key configuration selects the same agent backend
  through either runtime without user-authored `ANTHROPIC_*` duplication.
- Terminal acceptance reruns the auditor against retained private evidence and
  verifies its report, implementation, source, and tracked-record digests; a
  counter-only tracked assertion cannot close the package.

Original DCI durable resume remains exposed through the native DCI run and
`asterion-dci resume` path. The generic five-stage composer is deliberately one
invocation and does not add a second persistent workflow control plane; a failed
generic invocation is retried under a fresh run identity.

## Rejected shortcuts

- Wrapping product CLI subprocesses as capability implementations.
- Treating `allowedTools` alone as a tool restriction.
- Relying on prompts to prohibit web, subagents, or outside-file access.
- Retaining Bash with command-string filtering as the Claude corpus boundary.
- Claiming paper experiment reproduction from bounded application acceptance.
- Exposing runtime-native credential aliases as required project configuration.
