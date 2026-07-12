# Live Session Checkpoint

> Updated: 2026-07-12 20:45 +0800. **Session remains active — the Pi reference adapter is being implemented.**

## TL;DR

- The project north star is the multi-runtime, multi-language Agent Application Framework; DCI/Pi is the first reference capability and adapter surface.
- AF-000 is verified complete: the worklist, scope audit, manager repair, climb parent enforcement, and recoverable state are installed.
- AF-010 is verified complete: the language-neutral schemas, fixtures, and Python reference validator pass full repository checks.
- AF-020 is the only authorized active package. It maps stable Pi RPC events into isolated protocol v1 attempts without changing the benchmark runtime.
- Legacy Pi/Judge climb H-001 through H-019 remains completed reference maintenance and must not be restarted without a new parented package.

## Active work package

Active work package: AF-020

- Design: `docs/superpowers/specs/2026-07-12-pi-protocol-adapter-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-pi-protocol-adapter.md`
- Acceptance in progress: Pi event translation and per-attempt conformant request/event artifacts.

## Next action

1. Write failing unit tests for Pi capability, text, tool, usage, terminal, and reasoning-omission mappings.
2. Persist isolated protocol attempts through `RunRecorder` without altering raw artifacts.
3. Run full compatibility verification and record whether provider-backed runtime acceptance is available.

## Guardrails

- Run `python3 tools/project_scope_check.py` before autonomous work or dispatch.
- Preserve the independent dirty `pi/` checkout; do not edit or commit it.
- Do not reopen legacy H-001 through H-019; a new framework hypothesis must carry its `work_package_id`.
