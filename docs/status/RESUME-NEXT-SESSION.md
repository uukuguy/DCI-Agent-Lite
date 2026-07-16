# Live Session Checkpoint

> Updated: 2026-07-17 05:32 +0800. **Session remains active — not a final handoff.**

Active work package: AF-310

## TL;DR

- AF-300 remains fully closed; AF-310 is now the sole active package.
- Audit showed that current source-product parity is complete but paper-level DCI is not: exact L0–L4 live context policies, BEIR ArguAna/SciFact, paper coverage/localization and ablations, complete application exposure, bounded Claude semantics, and full experiment reproduction remain.
- The user approved the four-package AF-310 → AF-340 architecture and continuous package-parented Climb execution. The formal design is committed at `docs/superpowers/specs/2026-07-16-paper-aligned-dci-complete-implementation-design.md` [926bbf6].
- The reviewed AF-310 implementation plan is committed at `docs/superpowers/plans/2026-07-16-af-310-paper-aligned-runtime-context-management.md` [0454cca].

## Where things stand

- Branch: `main`; design and checkpoint state are committed through the immediately following state-maintenance commits, remain unpushed, and leave a clean working tree.
- Provider-free product verification still passes 8/8 rows, 533/533 selectors, 12/12 launcher pairs, 6/6 extras, and 7/7 bounded retained cases with zero provider operations.
- Correct Context/artifact/CLI focused tests pass 101/101; an earlier nonzero command was only an invalid guessed test-module selector.
- Governance, D-044, and a fresh AF-310 Climb pool are active; AF-310-H-001 is the next hypothesis.
- No implementation, full dataset, provider request, or Climb cycle has started.

## Approved package sequence

1. AF-310 — exact paper-aligned L0–L4 runtime context management through an Asterion-owned Pi extension, without modifying external `pi/`.
2. AF-320 — all thirteen paper datasets, coverage/localization, and bounded context/tool/corpus ablation surfaces.
3. AF-330 — complete capability/application composition plus bounded Pi and Claude Code semantic verification.
4. AF-340 — separately budget-authorized full paper experiment and score reproduction.

## Next steps

1. Run `python3 tools/project_scope_check.py`; it must name AF-310 and AF-310-H-001.
2. Commit the Task 0 governed start and journal its hash.
3. Write AF-310-H-001 failing profile-contract tests and observe the expected RED result.
4. Implement only the minimum closed profile contract needed for GREEN, then record the Climb cycle and advance continuously.

## Don't go down these paths again

- Do not call post-run conversation processing live runtime context management.
- Do not use generic Pi compaction as proof of the paper's exact L0–L4 thresholds.
- Do not modify or commit external `pi/`; use the official explicit extension boundary.
- Do not treat 533/533 current-source selectors as paper-experiment completeness.
- Do not reopen completed Climb hypotheses or reuse AF-250 session state.
- Do not run full datasets before AF-340 receives explicit budget authorization.

## Ready commands

```bash
git status --short
python3 tools/project_scope_check.py
sed -n '1,460p' docs/superpowers/specs/2026-07-16-paper-aligned-dci-complete-implementation-design.md
sed -n '1,220p' docs/superpowers/plans/2026-07-16-af-310-paper-aligned-runtime-context-management.md
uv run --project asterion python -m unittest tests.test_asterion_dci_context_profiles -v
```
