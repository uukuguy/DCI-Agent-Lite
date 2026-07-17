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

## Rejected shortcuts

- Wrapping product CLI subprocesses as capability implementations.
- Treating `allowedTools` alone as a tool restriction.
- Relying on prompts to prohibit web, subagents, or outside-file access.
- Retaining Bash with command-string filtering as the Claude corpus boundary.
- Claiming paper experiment reproduction from bounded application acceptance.
