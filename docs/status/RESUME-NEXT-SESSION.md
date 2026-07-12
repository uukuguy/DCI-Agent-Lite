# Live Session Checkpoint

> Updated: 2026-07-12 21:34 +0800. **AF-050 is active; this is a live checkpoint, not a final handoff.**

## TL;DR

- The project north star is the multi-runtime, multi-language Agent Application Framework; DCI/Pi is the first reference capability and adapter surface.
- AF-000 is verified complete: the worklist, scope audit, manager repair, climb parent enforcement, and recoverable state are installed.
- AF-010 is verified complete: the language-neutral schemas, fixtures, and Python reference validator pass full repository checks.
- AF-020 is verified complete: Pi emits isolated conformant attempts and passed a provider-backed agent-plus-judge run.
- AF-030 is complete at the local protocol boundary. Claude Code accepts stored login or inherited environment-configured backends; provider-backed UAT remains explicitly deferred.
- AF-040 is complete: Python and TypeScript publish matching schema-backed host contracts and pass shared-fixture parity checks.
- Two live Claude Code probes returned the CLI's unauthenticated path. Their normalized streams fail safely without persisting the raw authentication message.
- The user explicitly deferred account-backed acceptance. Claude Code must support both stored login and inherited `ANTHROPIC_*`/cloud-provider environment configuration, without putting it in command or protocol artifacts.
- Legacy Pi/Judge climb H-001 through H-019 remains completed reference maintenance and must not be restarted without a new parented package.

## Active work package

Active work package: AF-050

- Design: `docs/superpowers/specs/2026-07-12-rust-executor-boundary-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-rust-executor-boundary.md`
- Acceptance in progress: define a controlled Rust execution/isolation sidecar boundary without duplicating orchestration.

## Next action

1. Write and commit the AF-050 executor-boundary design and implementation plan.
2. Define the smallest language-neutral execution request/result/policy contract under the framework protocol boundary.
3. Implement and verify the Rust sidecar test-first without moving orchestration out of Python/TypeScript hosts.

## Guardrails

- Run `python3 tools/project_scope_check.py` before autonomous work or dispatch.
- Preserve the independent dirty `pi/` checkout; do not edit or commit it.
- Do not reopen legacy H-001 through H-019; a new framework hypothesis must carry its `work_package_id`.
- Do not treat unavailable Claude account authentication as a mainline blocker; preserve the deferred provider-acceptance item while advancing the framework worklist.
