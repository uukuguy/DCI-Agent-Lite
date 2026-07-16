# AF-300 Design Checkpoint

> Updated: 2026-07-16 +0800. AF-300 is design-only until written-spec approval.

Active work package: AF-300

## TL;DR

- Move the two top-level repository-only application hosts into `examples/asterion/applications/`.
- Preserve function behavior, package-local authoritative paths, wheel contents, DCI behavior, and provider-free parity.
- Do not leave compatibility stubs under top-level `applications/`; no tracked top-level `capabilities/` product exists.
- Defer full datasets, published-score reproduction, standalone release packaging, and plugin splitting until broader framework convergence.

## Committed / unpushed state

- Documentation design, plan, complete DCI reference, integration guide, and extraction guide are committed on local `main`.
- Final navigation/truth reconciliation is committed, followed only by the AF-290 state checkpoint.
- The user-owned untracked `.superpowers/sdd/task-0-review.md` remains intentionally untouched.

## Next concrete action

Obtain written-spec approval, then create the AF-300 implementation plan. Do not move files before that gate.

## Open questions

- None for AF-300; target paths, preservation boundaries, and deferred work are decided.

## Ruled-out paths

- Do not treat unsupported Pi context levels as effective merely because arbitrary extra args can be forwarded.
- Do not equate 533 model-free selectors with full-dataset score reproduction.
- Do not begin the approved moves until the written spec and implementation plan gates pass.
- Do not modify or vendor the external `pi/` checkout.

## Ready commands

```bash
python3 tools/project_scope_check.py
sed -n '1,300p' docs/superpowers/specs/2026-07-16-asterion-repository-directory-convergence-design.md
git status --short
```
