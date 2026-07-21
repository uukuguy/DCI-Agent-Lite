# Live Session Checkpoint

> Updated: 2026-07-21 23:01 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

Package: README reproduction and DCI capability-package usability

## TL;DR

- User-approved D-053 makes complete Asterion DCI capability-package usability the project objective; strict DCI paper reproduction is optional evidence.
- AF-340-H-004 now requires retained Pi r14 plus Claude MiniMax r6, covering `original-pi`, `asterion-pi`, and `asterion-claude-minimax`. Claude subscription is supported but optional.
- AF-340-H-005 no longer gates AF-340. Any future paper-model, full-dataset, published-score, or statistical comparison needs a new active work package and explicit finite-budget authorization.

## Where things stand

- Governance/design commit: `ecc5400` (`docs: redefine AF-340 around DCI capability usability`).
- Implementation-plan commit: `8e99b57` (`docs: plan AF-340 capability usability closure`).
- The framework north star, AF-340 canonical design, WORKLIST acceptance, D-053, and CURRENT-STATE are aligned.
- The canonical implementation plan is `docs/superpowers/plans/2026-07-21-af-340-dci-capability-usability-closure.md`; its six tasks specify RED/GREEN verifier changes, Climb migration, operator docs, retained-evidence confirmation, core-capability terminal gates, and managed closure.
- The approved DCI core-capability matrix covers research execution; L0-L4 context and conversation evidence; artifacts/resume/cancellation/deadlines; Judge/cache/QA/IR evaluation; benchmark profiles/launchers/reuse; analysis/figures/exports; source/application/wheel and Pi/Claude delivery; and configuration/privacy/body-free safety.
- The implementation plan, public `inspect` verifier, and Climb H-004/H-005 state still encode the superseded three-report/full-closure rule. H-004 and AF-340 remain `in_progress` until those are changed and terminally revalidated.
- Scope preflight passes for AF-340. All 12 focused documentation tests, design self-review, and `git diff --check` passed before the design commit.
- Evaluators/background processes: none. No provider request or full dataset ran.
- External `pi/` remains an independent checkout and was not edited or committed.

## Retained bounded evidence

- Claude MiniMax r6: `.worktrees/af-340-implementation/outputs/verification/af340-bounded-claude-minimax-r6/af340-bounded-report.json`; dimension `asterion-claude-minimax`; 2 Agent/2 Judge; canonical SHA `efabac9a…c9039`.
- Pi r14: `outputs/verification/af340-bounded-pi-r14/af340-bounded-report.json`; dimensions `original-pi`, `asterion-pi`; 30 Agent/16 Judge; canonical SHA `74ccd39a…eaa`; plan SHA `57225e9c…d11`.
- Both reports previously passed fresh bottom-level validation. Public `inspect` still rejects them together only because its acceptance set has not yet been migrated.

## Next actions

1. Select plan execution mode: subagent-driven task gates or inline execution in this session.
2. Start Task 1 test-first: make `inspect` require Pi plus MiniMax while accepting compatible subscription evidence optionally.
3. Migrate Climb state/evaluator and user-facing verification docs, then confirm H-004 using the two retained reports.
4. Revalidate the complete local/static/product/privacy/governance matrix, then close AF-340 only if package closure preflight passes.

## Ruled-out paths

- Do not wait for or require a Claude subscription account for AF-340 closure.
- Do not remove subscription support; it remains an optional supported authentication mode.
- Do not treat MiniMax functional evidence as paper-model, published-score, or full-result evidence.
- Do not run former H-005 or any full dataset without a new governed package and explicit invocation/budget authority.
- Do not modify or commit the external `pi/` checkout.

## Ready commands

```bash
python3 tools/project_scope_check.py
uv run python -m unittest -v tests.test_asterion_documentation
git show --stat --oneline ecc5400
```
