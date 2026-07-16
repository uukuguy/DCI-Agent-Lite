# AF-290 Closure Checkpoint

> Updated: 2026-07-16 +0800. Project lifecycle is complete; no active work package.

Active work package: none

## TL;DR

- The complete DCI product reference, framework/capability integration guide, standalone extraction guide, and documentation hub are finished.
- Current package-local `asterion/capabilities` and `asterion/applications` are authoritative; top-level names are reference/compatibility material, not extra installable products.
- Saved-conversation context processing is implemented and verified. The current external Pi typed runtime context level remains External-limited and is recorded as unsupported.
- Asterion implements the benchmark product surface, but AF-290 did not rerun full datasets or reproduce the published 62.9% result.

## Committed / unpushed state

- Documentation design, plan, complete DCI reference, integration guide, and extraction guide are committed on local `main`.
- Final navigation/truth reconciliation is committed, followed only by the AF-290 state checkpoint.
- The user-owned untracked `.superpowers/sdd/task-0-review.md` remains intentionally untouched.

## Next concrete action

Discuss the current directory structure and DCI completeness using `docs/README.md` and the three canonical AF-290 documents. If the discussion selects implementation work, create a new work-package ID and reopen lifecycle before modifying directories or code.

## Open questions

- Should a future standalone Asterion keep DCI in the first wheel release or pass the documented separately-versioned plugin decision gate?
- Which top-level reference/compatibility hosts still have users before any cleanup proposal?
- Does the user require an authorized full-dataset rerun, or only implementation/structural verification?

## Ruled-out paths

- Do not treat unsupported Pi context levels as effective merely because arbitrary extra args can be forwarded.
- Do not equate 533 model-free selectors with full-dataset score reproduction.
- Do not move or split directories under the completed documentation-only package.
- Do not modify or vendor the external `pi/` checkout.

## Ready commands

```bash
python3 tools/project_scope_check.py
sed -n '1,240p' docs/README.md
sed -n '1,260p' docs/architecture/asterion-framework-capability-integration.md
sed -n '1,260p' docs/architecture/asterion-standalone-extraction.md
git status --short
```
