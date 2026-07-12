# Agent Runtime Protocol v1 Design

> Status: approved for autonomous AF-010 delivery under the Agent Application Framework north star.

## Goal

Define a versioned, language-neutral contract that allows a Python, TypeScript, or Rust host to observe and control an agent run without taking a dependency on Pi, Claude Code, Hermes-agent, Pydantic AI, or LangGraph internals.

AF-010 defines contracts, validation, fixtures, and a Python reference surface. It does not migrate the Pi runner; that is AF-020.

## Canonical representation

- Protocol identifier: `dci.agent-runtime/v1`.
- Wire format: UTF-8 JSON objects; streaming transport is JSON Lines, one complete event object per line.
- Canonical schema assets live under `schemas/agent-runtime/v1/` and are language-neutral source material.
- Python reference types in `src/dci/framework/protocol.py` validate and serialize the same wire objects without a new runtime dependency.
- A single immutable event sequence is the audit trail for a run. Sequence numbers begin at `1` and strictly increase by one.

## Run request

Every adapter accepts this normalized request shape:

```json
{
  "protocol": "dci.agent-runtime/v1",
  "run_id": "run-123",
  "input": {"text": "Investigate the corpus"},
  "requested_capabilities": ["shell", "filesystem.read"],
  "deadline_ms": 300000
}
```

- `protocol`, `run_id`, and non-empty `input.text` are required.
- `requested_capabilities` is an optional ordered list of non-empty capability identifiers.
- `deadline_ms` is optional; when supplied it is an integer from `1` through `86_400_000`.
- A request names intent, not a particular provider, model, tool implementation, or prompting strategy.

## Event envelope

Every streamed event has these fields:

```json
{
  "protocol": "dci.agent-runtime/v1",
  "run_id": "run-123",
  "sequence": 1,
  "type": "run.started",
  "payload": {}
}
```

- `protocol` and `run_id` must equal the request values.
- `sequence` must be a positive integer and contiguous within the validated stream.
- `type` is one of the v1 event types below.
- `payload` is an object whose required fields depend on `type`.
- Unknown event types, missing required payload fields, duplicate sequences, and events after a terminal event are protocol errors.

## V1 event types

| Type | Required payload | Meaning |
|---|---|---|
| `run.started` | `capabilities` (array) | Adapter accepted the request and declares its effective capabilities. |
| `text.delta` | `text` (non-empty string) | User-visible incremental output. |
| `tool.call` | `call_id`, `name`, `arguments` | Adapter requested a tool invocation. |
| `tool.result` | `call_id`, `output`, `is_error` | Result paired with an earlier tool call. |
| `usage.reported` | `input_tokens`, `output_tokens` (non-negative integers) | Cumulative or final usage reported by the runtime. |
| `artifact.created` | `artifact` | Immutable metadata for an output, evidence file, or transcript. |
| `run.completed` | `status` (`completed` or `cancelled`) | Successful terminal event. |
| `run.failed` | `code`, `message` | Failed terminal event; messages must be safe for persisted artifacts. |

`artifact` contains `artifact_id`, `kind`, `media_type`, and optional `uri` and `sha256`. The contract records references and integrity metadata; it does not prescribe local or remote storage.

## Lifecycle rules

1. The first event is `run.started`.
2. A `tool.result.call_id` must have appeared in a preceding `tool.call` event; multiple results for one call are invalid in v1.
3. `run.completed` and `run.failed` are terminal. Exactly one must end a complete stream.
4. Cancellation is represented by `run.completed` with `status: "cancelled"`; adapters may emit ordinary text, tool, usage, or artifact events before it.
5. Deadline expiry is represented by `run.failed` with `code: "deadline_exceeded"` unless the host successfully cancels before the deadline.

## Capability semantics

`run.started.payload.capabilities` is the truth for a specific execution. A requested capability absent from that list is a degraded-but-valid run unless the host declares it mandatory in a future protocol version. No adapter may invent a capability merely to match another runtime.

## Conformance strategy

- Valid JSON fixtures cover a normal DCI-style research run, a cancelled run, and an artifact-producing run.
- Invalid fixtures cover non-contiguous sequence numbers, unmatched tool results, and post-terminal events.
- Python unit tests validate the fixtures through the reference parser and provide the executable semantics for later TypeScript/Rust implementations.
- AF-020 must adapt Pi events to these fixtures or add explicitly versioned, capability-gated events; it may not add Pi-specific fields to the core envelope.

## Compatibility and non-goals

- V1 is additive only through a new protocol version; unknown v1 event types are rejected.
- The protocol does not expose hidden reasoning, provider request bodies, API keys, raw tool environment data, or model-private session state.
- The protocol does not define remote transport, multi-agent scheduling, memory persistence, authentication, or sandbox implementation. Those consume this contract in later packages.
