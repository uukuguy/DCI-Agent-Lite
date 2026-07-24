# Live Session Checkpoint

> Updated: 2026-07-24 16:32 +0800. **Session remains active — not a final handoff.**

Active work package: none

Project lifecycle: complete

Currently running: no process.

## TL;DR

- The real `make setup-pi` failure is fixed and committed: locked Pi 0.80.6 builds reproducibly from checked-in catalogs with the lock-installed toolchain.
- The standalone project now has one canonical `asterion/examples/` directory; the redundant `asterion/scripts/examples/` hierarchy is removed.
- The user reconfirmed that root `make example`, `runtime-example`, `asterion-example`, and `asterion-runtime-example` all run successfully. The earlier Pi failure was transient credential state, not an example implementation regression.
- AF-360 is complete. Both executable scripts live beside the existing example surface, while behavior and Make target names remain unchanged.

## Where things stand

- `main` contains standalone-example implementation commit `fa0b0c9`; all current session commits are local and unpushed.
- Real Pi verification is clean at locked revision `8479bd84743e8889f728acb21a62794102db0529`; the external checkout is detached and has no tracked changes.
- Final Pi repair evidence: two fresh real Pi 0.80.6 builds, 206 standalone tests, 94 mixed-root regressions, 16 Markdown/32-link checks, and 18 full clean-copy promotion commands; provider operations 0 and no full dataset.
- Current mixed-root `corpus/` is external and ignored, with populated `wiki_corpus` and `bc_plus_docs`; standalone Asterion can reuse it by an explicit exported absolute resource root.
- The configuration probe showed `make setup-resources-basic --check` fails without an exported resource root and passes when `ASTERION_DCI_RESOURCE_ROOT` points at the mixed root.
- A separate cwd probe proved `uv run --project /path/to/asterion` preserves the caller directory rather than changing into the project.
- The temporary 2026-07-24 Pi authentication failures were resolved outside the code path; all four root Make examples now execute normally.
- Final correction evidence: 210 standalone tests, 125 relevant mixed-root regressions, 16 Markdown/32-link checks, and 9 quick clean-copy promotion commands passed; provider operations 0 and no full dataset.

## Completed correction

Implemented:

1. Moved both shell examples into the existing `asterion/examples/` directory.
2. Updated Make, tests, promotion, and documentation to use the canonical paths.
3. Removed `asterion/scripts/examples/`.
4. Kept behavior, authentication, resources, Pi, and mixed-root examples unchanged.

The shared resolver and live-auth-probe redesign are rejected as unnecessary for this work package correction.

## Next steps

1. Keep lifecycle complete until a new work package is explicitly selected.
2. If publishing `asterion/` later, use a separately authorized publication package.

## Ruled-out paths

- Do not copy original `src/dci` or its provider-specific product scripts into the standalone Asterion product.
- Do not redesign authentication, preflight, resource resolution, or the four working root Make examples for this correction.
- Do not duplicate the existing mixed-root corpus unless an independent standalone checkout actually needs its own external resource tree.
- Do not disturb the completed source-pinned Pi repair or accept a global Pi executable as runtime authority.

## Open questions

- No product-design question remains; the canonical location is `asterion/examples/` and consolidation is complete.
- No publication, remote creation/push, full dataset, or provider-backed operation is authorized.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py
git status --short --branch
python3 tools/project_scope_check.py
git status --short --branch
```
