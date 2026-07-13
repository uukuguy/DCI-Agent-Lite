# Live Session Checkpoint

> Updated: 2026-07-13 19:20. **Session remains active — not a final handoff.**

Active work package: AF-200

## TL;DR

- AF-170 is closed: generic application selection accepts multiple assemblies then selects the unique `--runtime` match; DCI ships paired Pi/Claude assemblies and runs through a fixture-only Claude CLI proof. No account, gateway, credential, or provider request was used.
- The user approved a new product direction: Asterion DCI becomes the first complete capability-package reference product, independently owning the full original DCI behavior. Old `src/dci` stays untouched and independent; Asterion does not import or execute it.
- AF-180 and AF-190 are closed. AF-190 completed all four Climb hypotheses at 4/4, adding original-style durable native evidence, safe compatible resume, isolated protocol attempts, and body-free durable projections. AF-200 now owns evaluation and benchmark parity.

## Verified state

- AF-170 repository closure gates previously passed: Python full suite, Python compilation/Ruff, TypeScript tests, Rust tests, shell syntax, scope audit, diff check, and isolated-wheel resource verification.
- D-030 remains authoritative: one Asterion wheel, with an independently owned DCI module inside it. Old `src/dci` stays excluded and must not become a shim, import, or subprocess dependency.
- AF-190 closure is verified without any Pi, judge, or Claude provider request: focused durable/resume/CLI/bridge/boundary tests, full Python discovery, Python compilation/Ruff, TypeScript and Rust tests, shell syntax, `uv run asterion-dci resume --help`, wheel proof, scope, and diff checks all passed.
- The single Asterion wheel now contains the independent `asterion.dci` product, durable original-style artifact layout, `asterion-dci run`/`resume` commands, isolated resume attempts, and body-free capability-result projections. Old `src/dci` remains a separate source baseline.
- No Pi, judge, or Claude provider request was sent.

## Next action

1. Start AF-200 with `python3 tools/project_scope_check.py`, then inspect original `src/dci` judge/cache/batch paths and the approved complete-capability design before writing its bounded implementation plan.
2. Register a new AF-200 Climb session and hypotheses; do not reuse the completed AF-190 session.
3. Do not send Pi, judge, or Claude provider requests without the applicable operator authorization.

## Guardrails

- Do not invoke Claude, automate login, store credentials, or represent fixture evidence as real UAT.
- Do not modify `src/dci`, add a second wheel, make either product a runtime dependency of the other, or introduce DCI-specific generic CLI behavior.

## Ready-to-paste recovery commands

```bash
sed -n '184,245p' docs/status/WORKLIST.md
sed -n '1,260p' docs/superpowers/specs/2026-07-13-complete-dci-capability-package-design.md
tail -n 18 docs/status/JOURNAL.md
python3 tools/project_scope_check.py
git status --short
git log --oneline -8
```
