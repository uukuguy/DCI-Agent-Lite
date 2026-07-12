# Session Handoff

> Finalized: 2026-07-12 21:51 +0800. **AF-050 is the only active package. This handoff is self-contained; do not rely on prior chat.**

## TL;DR

- The product is the multi-runtime, multi-language Agent Application Framework. DCI/Pi is the first reference capability/runtime, not the product boundary.
- AF-000 through AF-040 are complete. The repository has governed scope, Agent Runtime Protocol v1, Pi and Claude Code adapters, and matching Python/TypeScript host contracts.
- Claude Code provider-backed UAT is deliberately deferred because the local account is unavailable. The runtime supports stored login and inherited `ANTHROPIC_*`/cloud-provider environments; this is not a mainline blocker.
- AF-050 is active. `dci.executor/v1` schemas/fixtures/reference validation and the Rust trusted-policy layer are committed.
- Rust process execution is not implemented. Resume with request authorization, then direct bounded execution, then deadline/cancellation and JSONL service.

## Git and process boundary

- Branch: `main` tracking `origin/main`.
- Final handoff commit: this state closeout commit; its parent is `74dfd79`.
- Last functional commit: `0fa33d9` (`feat: enforce trusted executor policy`).
- After this closeout, local `main` is 19 commits ahead of `origin/main`; nothing was pushed during handoff.
- Parent repository is clean after the closeout commit.
- No Cargo, npm, Python, or Claude task belonging to this repository remains running.
- `pi/` is an independent dirty repository and was intentionally untouched. Its existing package/model files and untracked `.pi/agent/` must not enter parent commits.

## Active work package

Active work package: AF-050

- Design: `docs/superpowers/specs/2026-07-12-rust-executor-boundary-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-rust-executor-boundary.md`
- Completed: language-neutral execute/cancel/result/ack contract; Python reference validator; Rust crate/lock; sparse registry configuration; canonical trusted workspace and absolute program allowlist; protocol resource ceilings.
- Remaining: Rust request types and policy authorization; no-shell cleared-environment process execution; concurrent bounded stdout/stderr draining; deadline kill/reap; explicit cancellation; JSONL service; operator documentation and final cross-language verification.

## First resume action

Write failing Rust tests for:

1. unknown `program_id` denial;
2. workspace-relative `cwd` escape/missing-directory denial;
3. request deadline/output values above trusted policy denial;
4. a valid request producing an `AuthorizedExecution` that contains only canonical executable/cwd, arguments, and bounded numeric values.

Then implement only enough Rust protocol/request authorization code to pass those tests. Do not start process spawning before this boundary is green and committed.

## Ready commands

```bash
git status --short
git log --oneline -8
python3 tools/project_scope_check.py
cargo test --manifest-path packages/rust/executor/Cargo.toml
cargo fmt --manifest-path packages/rust/executor/Cargo.toml --check
cargo clippy --manifest-path packages/rust/executor/Cargo.toml --all-targets -- -D warnings
```

The repository `.cargo/config.toml` intentionally selects the sparse crates.io index; it overrides a user-level Git-index configuration that stalled fresh dependency resolution.

## Open questions

- Decide during the cancellation task whether one cancel acknowledgement may race with a naturally completed target; preserve exactly one terminal execution result either way.
- Select stronger OS/container isolation only as a later replaceable backend. No user decision is required for the current local policy executor.
- Re-run the deferred Claude tiny-corpus provider UAT only when a login or compatible gateway becomes available.

## Ruled-out paths and guardrails

- Do not call the local Rust backend a sandbox; it does not block network, arbitrary syscalls, absolute paths used by an allowed child, or descendants.
- Do not accept executable paths, environment variables, workspace roots, shell strings, or policy changes from agent-controlled requests.
- Do not authorize via `PATH` or basename resolution; trusted policy maps stable IDs to canonical absolute executables.
- Do not move agent orchestration, prompts, model access, or workflow scheduling into Rust.
- Do not reopen legacy H-001 through H-019 or substitute Pi/Judge maintenance for AF-050.
- Do not edit or commit the external `pi/` checkout.

## Verification evidence

- Latest full framework gate before AF-050: 126 Python tests, Python compilation/Ruff, clean `npm ci`, TypeScript build/shared-fixture tests, scope audit, and diff check passed.
- AF-050 protocol focused tests passed.
- Rust trusted-policy tests passed; `cargo fmt --check` and Clippy with `-D warnings` passed.
- Handoff recovery gate must still pass after the final state commit: scope audit, focused Rust tests/checks, clean Git, and consistent `INDEX → CURRENT-STATE → RESUME → JOURNAL → MEMORY` reading.
