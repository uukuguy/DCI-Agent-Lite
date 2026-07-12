# Claude Code Protocol Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox syntax.

**Goal:** Add Claude Code as the first independent protocol runtime and prove a DCI-style research vertical slice.

**Architecture:** Capture the installed CLI's stream-json envelope as sanitized fixtures, implement a pure translator, then wrap it with a restricted subprocess runtime. Keep raw and normalized artifacts separate.

**Tech Stack:** Python standard library, Claude Code CLI 2.1.199, `unittest`, Agent Runtime Protocol v1.

## Global Constraints

- Never use `--dangerously-skip-permissions`.
- Never persist hidden thinking, signatures, account data, or provider payloads in normalized events.
- Tests must pass without credentials; the final vertical slice is a separate provider-backed acceptance.
- Do not modify Pi behavior while adding Claude Code.

---

### Task 1: Capture and lock the stream-json contract

- Run one tools-disabled, non-persistent `Reply exactly OK` probe under the active AF-030 package.
- Sanitize the envelope into valid and malformed fixtures without session/account/provider identifiers.
- Write failing tests that require recognized text/result events and reject malformed JSONL or forbidden hidden keys.

### Task 2: Implement the pure translator test-first

**Files:** `src/dci/framework/adapters/claude_code.py`, `tests/test_claude_code_protocol_adapter.py`, fixture JSONL files.

- Implement capability mapping and a stateful translator with contiguous sequences.
- Map only documented/observed stable fields; ignore hidden reasoning and metadata.
- Validate every completed stream with `validate_event_stream`.

### Task 3: Implement the restricted runtime boundary

**Files:** `src/dci/framework/runtimes/claude_code.py`, `tests/test_claude_code_runtime.py`.

- Build the exact non-interactive command with explicit tools, cwd, timeout, and no session persistence.
- Stream raw events to a raw artifact and normalized events to an attempt artifact.
- On timeout terminate the process and emit a safe failure; never echo raw stderr into protocol events.

### Task 4: Prove the cross-runtime research slice

- Create a tiny deterministic local corpus and one evidence question.
- Run Claude Code with `Read`/`Bash`; validate answer, evidence path, and protocol stream.
- Reuse the existing Pi runtime example evidence as the Pi side of the same capability contract.
- Run full tests, compile, Ruff, scope audit, and diff checks before advancing the worklist.
