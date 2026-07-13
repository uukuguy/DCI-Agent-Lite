# Live Session Checkpoint

> Updated: 2026-07-13 10:50. **Session remains active — not a final handoff.**

Active work package: AF-170

## TL;DR

- AF-170's explicit DCI Pi/Claude compatibility design is approved and committed as `d6a5af4`; D-035 fixes the paired-assembly and generic-selection boundary.
- The written specification is awaiting user review. Until it is reviewed, no implementation, AF-170 Climb hypothesis, or Climb cycle may start.
- AF-160 remains closed. No Claude provider request, authorization, or credential configuration was attempted.

## Verified state

- The DCI provider currently supports Pi only; the proposed change uses two immutable, composition-equivalent assembly declarations rather than mutating one runtime ID.
- Generic CLI runtime-to-assembly selection is required because an assembly binds exactly one runtime identity. It must stay DCI-neutral and fail before factory construction for zero or ambiguous matches.
- `python3 tools/project_scope_check.py` passed with AF-170 as the sole active package before the design commit.
- Old Climb state is a hard-paused AF-100 record. It contains no AF-170 hypothesis and cannot be reused without failing scope governance.

## Next action

1. User reviews `docs/superpowers/specs/2026-07-13-installed-dci-claude-compatibility-design.md`.
2. After explicit approval, create the AF-170 implementation plan, register scoped AF-170 Climb hypotheses, rerun scope preflight, and begin fixture-only implementation.

## Guardrails

- Do not modify `src/dci/benchmark/`, package the source baseline, create a second wheel, or add DCI-specific generic CLI behavior.
- Do not invoke Claude, automate login, persist credentials, or treat fixture evidence as provider-backed UAT.
- Do not run old AF-050–AF-100 Climb hypotheses under AF-170.

## Ready-to-paste recovery commands

```bash
sed -n '1,260p' docs/superpowers/specs/2026-07-13-installed-dci-claude-compatibility-design.md
sed -n '180,205p' docs/status/WORKLIST.md
tail -n 12 docs/status/JOURNAL.md
python3 tools/project_scope_check.py
git status --short
git log --oneline -5
```
