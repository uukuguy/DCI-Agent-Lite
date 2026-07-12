# Live Session Checkpoint

> Updated: 2026-07-12 21:20 +0800. **AF-030 is active; external Claude Code account acceptance is explicitly deferred and no longer blocks the framework mainline. This is not a final handoff.**

## TL;DR

- The project north star is the multi-runtime, multi-language Agent Application Framework; DCI/Pi is the first reference capability and adapter surface.
- AF-000 is verified complete: the worklist, scope audit, manager repair, climb parent enforcement, and recoverable state are installed.
- AF-010 is verified complete: the language-neutral schemas, fixtures, and Python reference validator pass full repository checks.
- AF-020 is verified complete: Pi emits isolated conformant attempts and passed a provider-backed agent-plus-judge run.
- AF-030 is the only authorized active package. Its sanitized translator and restricted subprocess runtime are locally complete; environment-configured compatible backends are the current finishing change.
- Two live Claude Code probes returned the CLI's unauthenticated path. Their normalized streams fail safely without persisting the raw authentication message.
- The user explicitly deferred account-backed acceptance. Claude Code must support both stored login and inherited `ANTHROPIC_*`/cloud-provider environment configuration, without putting it in command or protocol artifacts.
- Legacy Pi/Judge climb H-001 through H-019 remains completed reference maintenance and must not be restarted without a new parented package.

## Active work package

Active work package: AF-030

- Design: `docs/superpowers/specs/2026-07-12-claude-code-protocol-adapter-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-claude-code-protocol-adapter.md`
- Acceptance in progress: verify and commit explicit environment pass-through plus documentation. Local fixtures, translation, command safety, artifact separation, and failure handling already pass.

## Next action

1. Run the full AF-030 verification suite, scope audit, and diff check for environment pass-through.
2. Commit the cohesive AF-030 finishing change and mark AF-030 complete.
3. Prepare and activate AF-040. Run the deferred tiny-corpus Claude provider acceptance only when a login or compatible gateway becomes available.

## Guardrails

- Run `python3 tools/project_scope_check.py` before autonomous work or dispatch.
- Preserve the independent dirty `pi/` checkout; do not edit or commit it.
- Do not reopen legacy H-001 through H-019; a new framework hypothesis must carry its `work_package_id`.
- Do not treat unavailable Claude account authentication as a mainline blocker; preserve the deferred provider-acceptance item while advancing the framework worklist.
