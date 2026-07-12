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
- A tiny local-corpus task runs under both the existing Pi adapter and Claude Code adapter, with each producing a valid protocol stream and the expected evidence path.
