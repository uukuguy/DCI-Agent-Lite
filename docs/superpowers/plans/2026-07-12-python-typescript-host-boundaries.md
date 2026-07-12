# Python and TypeScript Host Boundaries Implementation Plan

> **For agentic workers:** use test-driven development task-by-task under AF-040.

**Goal:** Publish matching Python and TypeScript host contracts for Agent Runtime Protocol v1 without exposing adapter-private types.

**Architecture:** Keep JSON Schema and shared fixtures canonical. Add one minimal runtime manifest, then build public host-native request/event/client types plus runtime validators in both languages.

**Tech stack:** Python 3.10+, `typing.Protocol`, JSON Schema Draft 2020-12, TypeScript, Ajv, Node test runner.

## Global constraints

- Do not import Pi or Claude Code types from either public host package.
- Do not add a network/process transport, workflow engine, provider registry, or enterprise package.
- Do not put credentials, model settings, executable paths, or provider metadata in manifests.
- Every implementation step starts with a focused failing test and ends with shared-fixture verification.

### Task 1: Complete portable discovery contract

**Files:** `schemas/agent-runtime/v1/runtime-manifest.schema.json`, `tests/fixtures/agent_runtime/v1/`, `src/dci/framework/protocol.py`, `tests/test_agent_runtime_protocol.py`.

- Add valid and invalid runtime-manifest fixtures first.
- Define the minimal manifest schema: protocol, runtime identifier, unique capabilities.
- Extend the Python reference validator and prove schema/fixture behavior.

### Task 2: Publish the Python host API

**Files:** `src/dci/framework/host.py`, `tests/test_python_runtime_host.py`.

- Write interface tests that use only the public host module.
- Add typed manifest/request/event records and an async `AgentRuntimeClient` protocol.
- Add public validation helpers that delegate to the canonical protocol validator.
- Prove an in-memory fake client emits a conformant shared-fixture stream without adapter imports.

### Task 3: Publish the TypeScript host package

**Files:** `packages/typescript/asterion-runtime/package.json`, `tsconfig.json`, `src/`, `test/`, package lock.

- Write failing Node tests against shared protocol fixtures.
- Add discriminated public protocol types and the async client interface.
- Load the canonical schemas through Ajv for runtime validation; do not fork schema rules into adapter code.
- Test positive and negative manifest/request/event streams plus a fake async client.

### Task 4: Lock cross-language parity and delivery checks

**Files:** root developer commands/documentation as needed.

- Add one repeatable TypeScript build/test command without changing Pi's external checkout.
- Verify Python and TypeScript suites consume the same fixtures and public modules contain no adapter imports.
- Run Python unit tests, compilation, Ruff, TypeScript build/tests, scope audit, and `git diff --check`.
- Record completion evidence, then advance only to the next worklist package.
