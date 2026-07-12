# Live Session Checkpoint

> Updated: 2026-07-12 20:37 +0800. **Session remains active — Agent Runtime Protocol v1 is being implemented.**

## TL;DR

- The project north star is the multi-runtime, multi-language Agent Application Framework; DCI/Pi is the first reference capability and adapter surface.
- AF-000 is verified complete: the worklist, scope audit, manager repair, climb parent enforcement, and recoverable state are installed.
- AF-010 is the only authorized active package. It defines the language-neutral Agent Runtime Protocol v1, schemas, fixtures, and Python reference validation.
- Legacy Pi/Judge climb H-001 through H-019 remains completed reference maintenance and must not be restarted without a new parented package.

## Active work package

Active work package: AF-010

- Design: `docs/superpowers/specs/2026-07-12-agent-runtime-protocol-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-agent-runtime-protocol.md`
- Acceptance in progress: canonical schemas, valid and invalid JSONL fixtures, and dependency-free Python lifecycle validation.

## Next action

1. Write the failing AF-010 fixture and protocol tests.
2. Add canonical JSON schemas and a dependency-free Python reference validator.
3. Run full conformance verification and advance to AF-020 only with evidence.

## Guardrails

- Run `python3 tools/project_scope_check.py` before autonomous work or dispatch.
- Preserve the independent dirty `pi/` checkout; do not edit or commit it.
- Do not reopen legacy H-001 through H-019; a new framework hypothesis must carry its `work_package_id`.
