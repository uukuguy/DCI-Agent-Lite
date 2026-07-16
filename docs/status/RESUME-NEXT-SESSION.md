# AF-300 Design Checkpoint

> Updated: 2026-07-16 +0800. AF-300 is design-only until written-spec approval.

Active work package: AF-300

## TL;DR

- Converge Python, TypeScript, Rust, schemas, examples, scripts, product docs, and Asterion tests under a complete top-level `asterion/` project root.
- Keep original DCI, cross-product parity/acceptance evidence, and repository governance at the mixed repository root.
- Preserve installed identities, behavior, wheel contents, DCI independence, and provider-free parity; leave no obsolete path stubs.
- Defer full datasets, published-score reproduction, standalone release packaging, and plugin splitting until broader framework convergence.

## Committed / unpushed state

- Documentation design, plan, complete DCI reference, integration guide, and extraction guide are committed on local `main`.
- Final navigation/truth reconciliation is committed, followed only by the AF-290 state checkpoint.
- The user-owned untracked `.superpowers/sdd/task-0-review.md` remains intentionally untouched.

## Next concrete action

Obtain written-spec approval, then create the AF-300 implementation plan. Do not move files before that gate.

## Open questions

- Written-spec review remains the only AF-300 design gate; target paths, ownership classification, preservation boundaries, and deferred work are otherwise decided.

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
