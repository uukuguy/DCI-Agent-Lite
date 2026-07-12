# Claude Code Protocol Adapter Design

> Status: approved for autonomous AF-030 delivery as the first independent runtime vertical slice.

## Goal

Run the same Agent Runtime Protocol v1 contract through Claude Code 2.1.199, independently of Pi, and prove a small DCI-style local-corpus research task produces conformant text, tool, usage, artifact, and terminal events.

## Why Claude Code first

The installed CLI provides non-interactive `--print`, `--output-format stream-json`, partial-message streaming, explicit tool restrictions, and session-persistence control. It introduces no project dependency and exercises a second external-agent implementation. Pydantic AI and LangGraph remain planned native-Python adapters after the external-runtime contract is proven.

## Components

- `ClaudeCodeProtocolAdapter`: pure translation from Claude stream-json objects to protocol events.
- `ClaudeCodeRuntime`: subprocess boundary that builds a restricted non-interactive command, sends one prompt, captures raw JSONL separately, and finalizes one protocol attempt.
- A model-free fixture suite derived from the observed CLI envelope.
- A provider-backed DCI research example using a tiny local corpus and explicit `Read`/`Bash` access.

## Command boundary

Use `claude -p --output-format stream-json --include-partial-messages --no-session-persistence`. Tool access is explicit; never use `--dangerously-skip-permissions`. Tests inject a fake process/fixture and do not require authentication.

## Authentication and provider boundary

The subprocess supports both Claude Code's stored login and its documented environment-based backends. It receives a copy of the complete caller environment so `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, model overrides, Bedrock/Vertex configuration, cloud credentials, and proxy settings retain native Claude Code semantics. Environment names and values are not copied into the command, Agent Runtime Protocol request, normalized events, or runtime return object.

The local Claude account is unavailable as of 2026-07-12. Model-free conformance and the observed safe unauthenticated path remain AF-030 acceptance; a provider-backed research run is explicitly deferred and does not block the host-language framework packages.

## Mapping policy

- System/init events establish effective capabilities but do not expose system prompt content.
- Streaming text deltas become `text.delta`.
- Final assistant `tool_use` blocks become `tool.call`; matching tool-result blocks become `tool.result`.
- Result usage becomes `usage.reported` when numeric fields are available.
- Successful result writes final text as an artifact then emits `run.completed`; CLI or protocol errors emit a safe `run.failed`.
- Thinking, signatures, raw provider payloads, session IDs, account metadata, and cost/account identifiers are excluded from normalized events.

## Acceptance

- Captured fixture translation is conformant and contains no forbidden hidden/provider keys.
- Subprocess tests prove explicit safe flags, JSONL error handling, timeout/cancellation, and safe failure artifacts.
- Environment pass-through is tested with a compatible-gateway configuration and no credential/configuration persistence in protocol artifacts.
- The Pi provider-backed evidence and Claude Code model-free/unauthenticated evidence establish both adapter boundaries. A Claude provider-backed tiny-corpus run remains a deferred acceptance item until a login or compatible gateway is available.
