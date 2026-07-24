# Live Session Checkpoint

> Updated: 2026-07-24 08:57 +0800. **Session remains active — not a final handoff.**

Active work package: AF-360

Project lifecycle: active

Currently running: no process.

## TL;DR

- AF-360 is the single active package for correcting standalone first-run readiness.
- The approved design keeps a pinned external Pi source checkout, adds provider-free Pi/resource setup, exposes explicit user-managed Pi authentication, and aligns template/describe/preflight defaults.
- No production implementation has started. The written design must be reviewed before the TDD implementation plan is created.

## Where things stand

- Branch: `main`; AF-360 design/governance is committed at `649eb63`, with only its journal/checkpoint synchronization pending.
- Clean standalone preflight was reproduced with Node passing and environment, configuration, Pi, corpora, and Judge readiness failing.
- Root cause is confirmed: AF-350 proved provider-free source/distribution promotion but did not ship external Pi/resource provisioning or one consistent public configuration contract.
- No Agent, Judge, benchmark, full dataset, external Pi mutation, resource download, publication, remote creation, or push occurred.

## Current design boundary

- Pi execution remains source-pinned through `pi-revision.txt`; a global `pi` executable is not accepted as authoritative.
- `DCI_PI_AGENT_DIR` explicitly selects user-managed authentication such as `~/.pi/agent`; setup never copies credentials.
- `basic` resource setup owns `corpus/wiki_corpus` and `corpus/bc_plus_docs`; separately named benchmark setup/check accounts for launcher resources.
- Setup may perform explicitly invoked Git/npm/resource network work but always performs zero Agent/Judge operations and no dataset execution.
- `.env.template`, runtime resolution, product description, doctor, and preflight must expose one effective provider/model/path contract.

## Next steps

1. Review `docs/superpowers/specs/2026-07-24-af-360-standalone-first-run-readiness-design.md`.
2. After written-spec approval, create `docs/superpowers/plans/2026-07-24-af-360-standalone-first-run-readiness.md` with the `writing-plans` skill.
3. Run `python3 tools/project_scope_check.py`, then execute the plan with test-first red/green slices.

## Don't go down these paths again

- Do not treat a global `pi` executable as equivalent to the locked source checkout without a new provenance/runtime decision.
- Do not copy Pi credentials, corpora, datasets, parent tools, original `src/dci`, or private evidence into the standalone project.
- Do not call a pointer-only `.env.template` or README a provisioning workflow.
- Do not let setup, cached resources, or preflight success authorize Agent/Judge or full-dataset execution.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py
git diff --check
git status --short --branch
```
