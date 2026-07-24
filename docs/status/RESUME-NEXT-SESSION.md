# Next-Session Handoff

> Updated: 2026-07-24 16:45 +0800 end of session.

Active work package: none

Project lifecycle: complete

Currently running: no project batch or evaluation process.

## TL;DR

- AF-360 is complete and project lifecycle is `complete`; no work package is active.
- The standalone project has one canonical `asterion/examples/` directory containing the existing Python composition examples and both executable Asterion DCI shell examples. `asterion/scripts/examples/` is absent.
- `make -C asterion example` and `make -C asterion runtime-example` resolve to the canonical paths. Authentication, resource handling, Pi behavior, and the four working mixed-root examples were not changed.

## Where things stand

- `main` contains implementation commit `eb67c4b` and closure commit `34ef4c8`; all session commits are local and unpushed.
- The parent repository working tree is clean at the handoff boundary.
- External `pi/` is an independent repository and intentionally remains dirty: tracked package manifests/model-catalog sources plus untracked `.pi/agent/` are excluded from this repository and were neither inspected nor modified during closeout.
- Final Pi repair evidence: two fresh real Pi 0.80.6 builds, 206 standalone tests, 94 mixed-root regressions, 16 Markdown/32-link checks, and 18 full clean-copy promotion commands; provider operations 0 and no full dataset.
- Current mixed-root `corpus/` is external and ignored, with populated `wiki_corpus` and `bc_plus_docs`; standalone Asterion can reuse it by an explicit exported absolute resource root.
- The configuration probe showed `make setup-resources-basic --check` fails without an exported resource root and passes when `ASTERION_DCI_RESOURCE_ROOT` points at the mixed root.
- A separate cwd probe proved `uv run --project /path/to/asterion` preserves the caller directory rather than changing into the project.
- The temporary 2026-07-24 Pi authentication failures were resolved outside the code path; all four root Make examples now execute normally.
- Final correction evidence: 211 standalone tests, 141 relevant mixed-root regressions, 16 Markdown/32-link checks, and 9 quick clean-copy promotion commands passed; provider operations 0 and no full dataset.

## What this session delivered

Implemented:

1. Moved both shell examples into the existing `asterion/examples/` directory.
2. Updated Make, tests, promotion, and documentation to use the canonical paths.
3. Removed `asterion/scripts/examples/`.
4. Kept behavior, authentication, resources, Pi, and mixed-root examples unchanged.

- `eb67c4b` consolidated the executable scripts into `asterion/examples/`, updated Make, tests, promotion, and docs, and removed the duplicate directory.
- `34ef4c8` closed AF-360 after the single-directory acceptance passed.
- Collaboration memory now records the verified preference for one canonical standalone example surface.

## Next steps

1. Run `project-state resume`; it should recover lifecycle `complete` with no active package.
2. Do not implement further work until a new work package is explicitly selected.
3. If publishing `asterion/` later, open a separately authorized publication package before remote creation or push.

## Ruled-out paths

- Do not copy original `src/dci` or its provider-specific product scripts into the standalone Asterion product.
- Do not recreate `asterion/scripts/examples/`; standalone examples belong in the existing top-level `asterion/examples/`.
- Do not redesign authentication, preflight, resource resolution, or the four working root Make examples for this correction.
- Do not duplicate the existing mixed-root corpus unless an independent standalone checkout actually needs its own external resource tree.
- Do not disturb the completed source-pinned Pi repair or accept a global Pi executable as runtime authority.

## Open questions

- No product-design question remains; the canonical location is `asterion/examples/`.
- No publication, remote creation/push, full dataset, or provider-backed operation is authorized.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py
git status --short --branch
make -C asterion -n example runtime-example
```
