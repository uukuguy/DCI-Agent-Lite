# Live Session Checkpoint

> Updated: 2026-07-16 23:41 +0800. **Session remains active — not a final handoff.**

Active work package: none

## TL;DR

- AF-300 remains fully closed and the repository lifecycle remains `complete` with no active package.
- Audit showed that current source-product parity is complete but paper-level DCI is not: exact L0–L4 live context policies, BEIR ArguAna/SciFact, paper coverage/localization and ablations, complete application exposure, bounded Claude semantics, and full experiment reproduction remain.
- The user approved the four-package AF-310 → AF-340 architecture and continuous package-parented Climb execution. The formal design is committed at `docs/superpowers/specs/2026-07-16-paper-aligned-dci-complete-implementation-design.md` [926bbf6].

## Where things stand

- Branch: `main`; design and checkpoint state are committed through the immediately following state-maintenance commits, remain unpushed, and leave a clean working tree.
- Provider-free product verification still passes 8/8 rows, 533/533 selectors, 12/12 launcher pairs, 6/6 extras, and 7/7 bounded retained cases with zero provider operations.
- Correct Context/artifact/CLI focused tests pass 101/101; an earlier nonzero command was only an invalid guessed test-module selector.
- Governance is intentionally not reopened yet: `brainstorming` requires written-spec review before `writing-plans`, while the scope checker requires a real plan before an active package can be valid.
- No implementation, full dataset, provider request, or Climb cycle has started.

## Approved package sequence

1. AF-310 — exact paper-aligned L0–L4 runtime context management through an Asterion-owned Pi extension, without modifying external `pi/`.
2. AF-320 — all thirteen paper datasets, coverage/localization, and bounded context/tool/corpus ablation surfaces.
3. AF-330 — complete capability/application composition plus bounded Pi and Claude Code semantic verification.
4. AF-340 — separately budget-authorized full paper experiment and score reproduction.

## Next steps

1. User reviews the committed design spec and approves it or requests corrections.
2. After approval, invoke `writing-plans` for AF-310.
3. Activate AF-310 only when the real plan exists; update WORKLIST, DECISIONS, CURRENT-STATE, RESUME, and fresh package-parented Climb state together, then run `python3 tools/project_scope_check.py`.
4. Execute AF-310 through continuous Climb hypothesis cycles until a defined hard pause or package acceptance.

## Don't go down these paths again

- Do not call post-run conversation processing live runtime context management.
- Do not use generic Pi compaction as proof of the paper's exact L0–L4 thresholds.
- Do not modify or commit external `pi/`; use the official explicit extension boundary.
- Do not treat 533/533 current-source selectors as paper-experiment completeness.
- Do not activate AF-310 with a missing or placeholder Plan link.
- Do not run full datasets before AF-340 receives explicit budget authorization.

## Ready commands

```bash
git status --short
python3 tools/project_scope_check.py
sed -n '1,460p' docs/superpowers/specs/2026-07-16-paper-aligned-dci-complete-implementation-design.md
```
