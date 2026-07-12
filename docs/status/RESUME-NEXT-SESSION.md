# Live Session Checkpoint

> Updated: 2026-07-12 21:02 +0800. **AF-030 is hard-paused on external Claude Code authentication; this is not a final handoff.**

## TL;DR

- The project north star is the multi-runtime, multi-language Agent Application Framework; DCI/Pi is the first reference capability and adapter surface.
- AF-000 is verified complete: the worklist, scope audit, manager repair, climb parent enforcement, and recoverable state are installed.
- AF-010 is verified complete: the language-neutral schemas, fixtures, and Python reference validator pass full repository checks.
- AF-020 is verified complete: Pi emits isolated conformant attempts and passed a provider-backed agent-plus-judge run.
- AF-030 is the only authorized active package. Its sanitized translator and restricted subprocess runtime are locally complete and pass 121 repository tests.
- Two live Claude Code probes returned the CLI's unauthenticated path. Their normalized streams fail safely without persisting the raw authentication message.
- Legacy Pi/Judge climb H-001 through H-019 remains completed reference maintenance and must not be restarted without a new parented package.

## Active work package

Active work package: AF-030

- Design: `docs/superpowers/specs/2026-07-12-claude-code-protocol-adapter-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-claude-code-protocol-adapter.md`
- Acceptance in progress: provider-backed Claude Code DCI research evidence. Local fixtures, translation, command safety, artifact separation, and failure handling pass.

## Next action

1. Authenticate the installed Claude Code CLI without placing credentials in repository files or chat output.
2. Re-run the tools-disabled protocol probe, then the tiny local-corpus `Read`/`Bash` vertical slice.
3. Mark AF-030 complete only after the live stream and evidence artifact pass protocol validation.

## Guardrails

- Run `python3 tools/project_scope_check.py` before autonomous work or dispatch.
- Preserve the independent dirty `pi/` checkout; do not edit or commit it.
- Do not reopen legacy H-001 through H-019; a new framework hypothesis must carry its `work_package_id`.
- Do not substitute another maintenance task while AF-030 awaits authentication; resume from this exact external acceptance gate.
