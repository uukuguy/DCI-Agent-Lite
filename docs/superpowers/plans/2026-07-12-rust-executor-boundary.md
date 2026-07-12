# Rust Controlled Executor Boundary Implementation Plan

> **For agentic workers:** use test-driven development task-by-task under AF-050.

**Goal:** Deliver a policy-enforcing Rust process sidecar beneath Agent Runtime Protocol without moving agent orchestration into Rust.

**Architecture:** A trusted startup policy maps opaque program IDs to absolute executables and sets workspace/resource ceilings. An asynchronous JSONL service accepts execute/cancel requests, directly spawns cleared-environment children, and emits correlated bounded results.

**Tech stack:** stable Rust, Tokio process/runtime primitives, Serde/serde_json, JSON Schema fixtures, Cargo test/Clippy/rustfmt.

## Global constraints

- Never invoke a shell or authorize through `PATH`/basename resolution.
- Never accept child environment variables, executable paths, workspace roots, or policy changes from an execution request.
- Never claim the local backend provides OS-level sandboxing.
- Kill and reap every timed-out or cancelled child before reporting terminal status.
- Keep stdout machine-readable JSONL; safe diagnostics go to stderr.

### Task 1: Define the executor wire contract

**Files:** `schemas/executor/v1/`, `tests/fixtures/executor/v1/`, focused schema/reference tests.

- Write valid execute/cancel/result fixtures and invalid unknown-field, limit, and envelope fixtures.
- Add Draft 2020-12 schemas with closed request/response shapes and explicit protocol constants.
- Prove fixtures model correlation and exactly the portable fields described by the design.

### Task 2: Build trusted policy and request validation

**Files:** `packages/rust/controlled-executor/Cargo.toml`, `src/policy.rs`, `src/protocol.rs`, unit tests.

- Start with failing tests for relative executables, duplicate program IDs, invalid limits, unknown fields, and workspace traversal.
- Canonicalize trusted workspace/program paths at startup.
- Deserialize closed request enums and return safe denials without spawning.

### Task 3: Enforce process and resource boundaries

**Files:** executor/process modules and integration fixtures.

- Prove argument-vector execution without shell expansion.
- Clear the child environment and close stdin.
- Drain stdout/stderr concurrently with independent caps and truncation flags.
- Enforce deadlines by killing and reaping the child.

### Task 4: Add concurrent cancellation and JSONL service

**Files:** executor service/main modules and process-level tests.

- Keep the input loop responsive while executions run and correlate out-of-order responses.
- Reject duplicate in-flight IDs; acknowledge cancel requests and terminate the target exactly once.
- Ensure malformed input produces a safe response and never contaminates stdout with diagnostics.

### Task 5: Verify the framework boundary

- Document operator policy and explicit non-sandbox limitations.
- Add repeatable root build/test commands.
- Run Rust format, Clippy, tests, Python/TypeScript regressions, scope audit, and diff checks.
- Record completion evidence before advancing to AF-060.
