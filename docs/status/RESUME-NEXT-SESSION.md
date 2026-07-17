# Live Session Checkpoint

> Updated: 2026-07-17 08:36 +0800. **Session remains active — not a final handoff.**

Active work package: AF-320

Package: Paper benchmark and metric parity

Currently running: no process. AF-310 and its Climb session are complete. AF-320 design and plan passed independent review with no findings and are committed at `9de29e3`; governance and a fresh Climb pool are being activated before Task 1 RED tests.

## TL;DR

- AF-320 is the sole active package; its reviewed design separates the thirteen dataset identities from experiment-specific selection scopes.
- The contract preserves BrowseComp all-830, two distinct n=100 scopes, Appendix random-50, full BRIGHT/Bamboogle, and applicable random-50 selections with deterministic manifests.
- AF-320 first repairs duplicate-inflated NDCG@10, then adds BEIR profiles, exact coverage/localization/retained metrics, native evidence alignment, and deterministic ablation surfaces by TDD.
- `paper-full` rows remain unconditionally non-executable; AF-340 remains the only package that may add full-run authorization and budget.
- External `pi/` retains pre-existing user changes and must remain untouched.

## Verified closure

- Tracked provider evidence SHA: `65c43d4fecdacc296dfc1997ae49f5ec870e22e6a1b78f70c8a134f955f28e15`.
- Report SHA: `6003346ffc4e8e4e07663747fd1d235f050ad03fa32cceb04358645e3638cd7b` (revalidate from the tracked binding if paths move).
- Extension: `0.2.0`, digest `4e9833b3b78c5d0223638e225bb167694a2e6f6247c2e2f3e2631cb16beefe8a`.
- Full local closure: 1288/1288 Python and 11/11 TypeScript tests; product verifier 8/8, 533/533, 12/12, 6/6, and 7/7; compile, Ruff, installed product, scope, and diff checks pass.
- Independent review found no Critical issue; its dirty-Pi and stale-state blockers were resolved by r9 clean-clone evidence, a no-override binder, security negative tests, and this state reconciliation.

## Next concrete action

1. Finish AF-320 governance activation and verify scope with `AF-320-H-001`.
2. Add Task 1 inventory/scope RED tests and prove they fail for the intended missing contracts.
3. Implement only the minimal schema/resource loader needed to turn Task 1 GREEN; do not download or execute datasets.

## Boundaries

- Do not modify or clean the external `pi/`; use clean disposable clones for acceptance when required.
- Do not treat 533 current-source selectors as all thirteen paper datasets.
- Do not run full datasets before AF-340 receives explicit budget authorization.
- AF-320 owns dataset adapters, paper coverage/localization metrics, and bounded ablation surfaces; AF-330 owns complete dual-runtime application semantics.
- Exact GPT-4.1 is required only for the terminal bounded QA Judge evidence; model-free work must keep provider/Judge counts at zero.

## Ready commands

```bash
git status --short
python3 tools/project_scope_check.py
sed -n '1,280p' docs/superpowers/specs/2026-07-17-af-320-paper-benchmark-metric-parity-design.md
sed -n '1,240p' docs/superpowers/plans/2026-07-17-af-320-paper-benchmark-metric-parity.md
```
