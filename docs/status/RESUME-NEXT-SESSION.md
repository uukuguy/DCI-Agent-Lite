# Live Session Checkpoint

> Updated: 2026-07-12 20:22 +0800. **Session remains active — framework governance is being implemented.**

## TL;DR

- The project north star is the multi-runtime, multi-language Agent Application Framework; DCI/Pi is the first reference capability and adapter surface.
- AF-000 is the only authorized active package. It establishes the worklist, scope audit, manager repair, climb parent enforcement, and recoverable state.
- Legacy Pi/Judge climb H-001 through H-019 remains completed reference maintenance and must not be restarted without a new parented package.

## Active work package

Active work package: AF-000

- Design: `docs/superpowers/specs/2026-07-12-agent-framework-governance-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-agent-framework-governance.md`
- Acceptance in progress: persistent north star/worklist and an auditable dispatch gate.

## Next action

1. Implement the test-first `tools/project_scope_check.py` validator and its isolated repository tests.
2. Gate `tools/climb/cycle.sh` on a parented work package, then repair the global manager skill and local operating rules.
3. Verify AF-000, transition the worklist only with evidence, and then plan AF-010.

## Guardrails

- Run `python3 tools/project_scope_check.py` before autonomous work or dispatch once it exists.
- Preserve the independent dirty `pi/` checkout; do not edit or commit it.
- Do not reopen legacy H-001 through H-019; a new framework hypothesis must carry its `work_package_id`.
