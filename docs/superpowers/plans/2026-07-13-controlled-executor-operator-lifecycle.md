# Controlled Executor Operator Lifecycle Implementation Plan

> **For agentic workers:** Execute inline with test-driven development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the bundled controlled-code application from the installed CLI through one explicit, policy-bound, reaped stdio sidecar.

**Architecture:** `OperatorExecutorConfig` validates three explicit operator files before any runtime or child construction. `ManagedControlledExecutor` starts direct `[binary, policy]` argv with a minimal environment, exposes the existing JSONL client, and always closes/reaps. CLI injects this service only for plans requiring `executor.controlled`.

**Tech Stack:** Python asyncio subprocess streams, frozen dataclasses, existing executor JSONL protocol/Rust sidecar, argparse, unittest.

## Global Constraints

- Require all-or-none `--executor-binary`, `--executor-policy`, and `--executor-validation-config` for controlled-code only.
- Reject symlink/missing/directory/malformed configuration before runtime or subprocess construction.
- Never execute through a shell or search PATH; child argv is binary and policy only.
- Do not forward environment credentials or persist/print paths, config, stderr, input, or payload bodies.
- Always reap the child; no daemon, socket transport, or provider-driven startup.

---

### Task 1: Validate operator executor configuration

**Files:**
- Create: `packages/python/asterion-core/src/asterion/services/managed_controlled_executor.py`
- Create: `tests/test_managed_controlled_executor.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class OperatorExecutorConfig:
    binary_path: Path
    policy_path: Path
    validation_config: TrustedValidationConfig

def load_operator_executor_config(binary: str | Path, policy: str | Path,
                                  validation: str | Path) -> OperatorExecutorConfig: ...
```

- [ ] Write RED tests for all-or-none mode, canonical regular files, symlink/directory rejection, closed validation JSON, and content-free errors.
- [ ] Run `uv run python -m unittest tests.test_managed_controlled_executor -v`; expect import failure.
- [ ] Implement canonical path/JSON validation with fixed `ControlledExecutorError` classes.
- [ ] Re-run focused tests, compile, Ruff, scope, diff; commit `feat: validate executor operator configuration`.

### Task 2: Managed stdio sidecar lifecycle

**Files:**
- Modify: `asterion/services/managed_controlled_executor.py`
- Modify: `tests/test_managed_controlled_executor.py`

**Interfaces:**

```python
class ManagedControlledExecutor:
    async def __aenter__(self) -> ControlledExecutorJsonlClient: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
```

- [ ] Write RED fake-subprocess tests asserting exact argv `[binary, policy]`, empty/minimal env, immediate-exit readiness failure, and stdin-close → wait → terminate → kill/reap fallback.
- [ ] Implement direct `asyncio.create_subprocess_exec`, one event-loop readiness checkpoint, bounded stderr drain, and idempotent shutdown.
- [ ] Re-run focused service tests plus compile/Ruff/scope/diff; commit `feat: manage controlled executor sidecars`.

### Task 3: Inject authorized service through the generic CLI

**Files:**
- Modify: `packages/python/asterion-core/src/asterion/cli.py`
- Modify: `tests/test_asterion_cli.py`
- Modify: `tests/test_builtin_controlled_code_application.py`
- Modify: `README.md`, `docs/architecture/controlled-code-validation-packages.md`

**Interfaces:** `asterion run` has the three executor options. A resolved plan requiring `executor.controlled` validates the complete configuration before runtime construction, enters `ManagedControlledExecutor`, injects `{ "executor.controlled": client }`, then calls `run_composed_application`.

- [ ] Write RED tests for controlled-code config preflight ordering, DCI rejection of lifecycle flags, one managed service injection, and safe public failure.
- [ ] Implement plan-derived service decision; preserve existing DCI selection/run behavior.
- [ ] Build/install the sole wheel in an isolated venv, run both provider listings, and use a fixture sidecar for one controlled-code CLI run.
- [ ] Run full Python/Node/Rust/compile/Ruff/shell/scope/diff gates; update state and close AF-150 with commit `docs: close controlled executor operator lifecycle`.
