# Live Session Checkpoint

> Updated: 2026-07-12 20:53 +0800. **Session remains active — the Claude Code independent adapter is being implemented.**

## TL;DR

- The project north star is the multi-runtime, multi-language Agent Application Framework; DCI/Pi is the first reference capability and adapter surface.
- AF-000 is verified complete: the worklist, scope audit, manager repair, climb parent enforcement, and recoverable state are installed.
- AF-010 is verified complete: the language-neutral schemas, fixtures, and Python reference validator pass full repository checks.
- AF-020 is verified complete: Pi emits isolated conformant attempts and passed a provider-backed agent-plus-judge run.
- AF-030 is the only authorized active package. Claude Code 2.1.199 is the selected first independent runtime.
- Legacy Pi/Judge climb H-001 through H-019 remains completed reference maintenance and must not be restarted without a new parented package.

## Active work package

Active work package: AF-030

- Design: `docs/superpowers/specs/2026-07-12-claude-code-protocol-adapter-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-claude-code-protocol-adapter.md`
- Acceptance in progress: sanitized Claude stream-json fixtures, pure translation, restricted subprocess runtime, and cross-runtime DCI research evidence.

## Next action

1. Probe the tools-disabled Claude stream-json envelope and sanitize it into fixtures.
2. Write failing translator tests, then implement only observed stable mappings.
3. Add the restricted subprocess runtime and run the tiny local-corpus vertical slice.

## Guardrails

- Run `python3 tools/project_scope_check.py` before autonomous work or dispatch.
- Preserve the independent dirty `pi/` checkout; do not edit or commit it.
- Do not reopen legacy H-001 through H-019; a new framework hypothesis must carry its `work_package_id`.
