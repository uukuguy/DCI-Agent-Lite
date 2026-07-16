# Live Session Checkpoint

> Updated: 2026-07-16 22:16 +0800. **Session remains active — not a final handoff.**

Active work package: AF-300

Live state: AF-300 final command remediation in_progress

## TL;DR

- AF-300 is reopened only to correct the standalone guide's invalid `--level provider-free` command to the real provider-free acceptance profile.
- Prior final-review remediation, relocation, parity, wheel, and immutable acceptance evidence remain unchanged.
- No provider/Judge operation, dataset, production code, or external boundary is authorized.

## Committed / unpushed state

- AF-300 Tasks 1–5 and review fixes are committed through `6fd4a0b`; Task 6 implementation and terminal governance are committed at `08eff1c`.
- Review remediation governance reopened at `6ce0db5`; documentation/tests landed at `d5b5cd6`; terminal governance closed at `c1625a5`.
- The Task 0 local-only review, external `pi/`, credentials, datasets, outputs, generated artifacts, and immutable provider-backed acceptance record remain untouched.

## Next concrete action

Add a RED documentation contract for legal standalone verification levels, then minimally repair the guide and close AF-300 again.

## Open questions

- None for this bounded command remediation.

## Ruled-out paths

- Do not restore obsolete Asterion roots or add compatibility stubs/symlinks.
- Do not reinterpret retained provider-backed evidence as a new run; Task 6 executed zero provider-backed operations.
- Do not expand AF-300 into full datasets, published-score reproduction, release automation/publication, remote switching, or a separately versioned DCI plugin.

## Ready commands

```bash
python3 tools/project_scope_check.py
git status --short
git log --oneline -5
uv run asterion describe --provider dci-agent-lite
```
