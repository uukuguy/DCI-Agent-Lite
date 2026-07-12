# Pi Agent Runtime Protocol Adapter Design

> Status: approved for autonomous AF-020 delivery under the framework worklist.

## Goal

Make the existing Pi JSONL RPC runner the first Agent Runtime Protocol v1 adapter without changing benchmark prompts, Pi lifecycle handling, raw event artifacts, evaluation, or the external `pi/` checkout.

## Boundary

`src/dci/framework/adapters/pi.py` translates stable Pi RPC events to protocol events. It has no process-launch, benchmark, judge, or persistence policy. The existing runner remains responsible for Pi process control and raw artifacts; `RunRecorder` owns protocol-attempt files and invokes the translator.

## Attempt isolation

Each new run or resume attempt gets a distinct protocol run ID and two files:

- `protocol/attempt-0001.request.json`
- `protocol/attempt-0001.events.jsonl`

Resume increments the attempt number. Sequence numbers restart at `1` for the new run ID, so a previous failed terminal event never shares a stream with resumed work.

## Capability mapping

Pi CLI tool names map conservatively:

| Pi tool | Protocol capability |
|---|---|
| `read` | `filesystem.read` |
| `bash` | `shell` |
| `write` | `filesystem.write` |
| `edit` | `filesystem.write` |
| other non-empty names | `pi.tool.<name>` |

The emitted `run.started` event is the execution truth. The request retains the requested mapped capabilities.

## Event mapping

| Pi RPC event | Protocol event |
|---|---|
| adapter start | `run.started` with effective capabilities |
| `message_update` / `text_delta` | `text.delta` |
| `tool_execution_start` | `tool.call` using `toolCallId`, `toolName`, and object `args` |
| `tool_execution_end` | `tool.result` using `result` and boolean `isError` |
| assistant `message_end` with numeric usage | `usage.reported` using Pi `input` and `output` |
| successful recorder finalization | `artifact.created` for `final.txt`, then `run.completed` |
| failed recorder finalization | `run.failed` with a stable safe code/message |

Thinking events, partial tool-call construction inside `message_update`, provider context, prompt acknowledgements, turn markers, `agent_end`, and `agent_settled` are not normalized directly. Completion is emitted only after existing Pi settlement and idle-state checks succeed.

## Safety and compatibility

- Raw Pi events remain in the existing `events.jsonl`; the normalized stream contains no hidden reasoning or provider request payload.
- A failed protocol event mapping fails the run before it can be treated as complete.
- Failure messages in the normalized stream are generic and safe; detailed stderr remains in the existing protected artifact.
- Existing CLI arguments, stdout behavior, raw artifacts, evaluation, and resume validation remain backward compatible.
- Final conformance validates every attempt stream using `validate_event_stream`.

## Acceptance

- Unit tests prove capability, text, tool, usage, terminal, and reasoning-omission mappings.
- Recorder tests prove isolated attempt request/event files for success, failure, and resume.
- Existing Pi lifecycle tests remain green.
- No files under the external `pi/` checkout change.
