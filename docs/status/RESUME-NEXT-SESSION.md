# Live Session Checkpoint

> Updated: 2026-07-24 16:02 +0800. **Session remains active — not a final handoff.**

Active work package: AF-360

Project lifecycle: active

Currently running: no process.

## TL;DR

- The real `make setup-pi` failure is fixed and committed: locked Pi 0.80.6 builds reproducibly from checked-in catalogs with the lock-installed toolchain.
- AF-300 left runnable DCI/Asterion shell examples only in the mixed repository; the standalone `asterion/` tree has framework-composition Python examples but no equivalent user-facing DCI launchers.
- The user reconfirmed that root `make example`, `runtime-example`, `asterion-example`, and `asterion-runtime-example` all run successfully. The earlier Pi failure was transient credential state, not an example implementation regression.
- Scope is now deliberately minimal: add only the two existing Asterion-native runnable examples and matching Make entry points to the standalone `asterion/` project. Do not redesign authentication, preflight, or the working mixed-root examples.

## Where things stand

- `main` contains the Pi repair commits `bf1c770` and `23f3b19`, followed by AF-360 closure state `083ce69`; all are local and unpushed.
- Real Pi verification is clean at locked revision `8479bd84743e8889f728acb21a62794102db0529`; the external checkout is detached and has no tracked changes.
- Final Pi repair evidence: two fresh real Pi 0.80.6 builds, 206 standalone tests, 94 mixed-root regressions, 16 Markdown/32-link checks, and 18 full clean-copy promotion commands; provider operations 0 and no full dataset.
- Current mixed-root `corpus/` is external and ignored, with populated `wiki_corpus` and `bc_plus_docs`; standalone Asterion can reuse it by an explicit exported absolute resource root.
- The configuration probe showed `make setup-resources-basic --check` fails without an exported resource root and passes when `ASTERION_DCI_RESOURCE_ROOT` points at the mixed root.
- A separate cwd probe proved `uv run --project /path/to/asterion` preserves the caller directory rather than changing into the project.
- The temporary 2026-07-24 Pi authentication failures were resolved outside the code path; all four root Make examples now execute normally.

## Pending design decision

Approved minimal approach:

1. Add standalone copies of `asterion_dci_basic_example.sh` and `asterion_dci_runtime_context_example.sh` under `asterion/scripts/examples/`, adjusted only to resolve the standalone project root.
2. Add standalone Make entry points for the two examples.
3. Keep the root examples, authentication flow, preflight, provider selection, and original DCI provider-specific examples unchanged.
4. Extend standalone promotion/tests/docs only enough to prove the copied project contains and can invoke the two examples.

The shared resolver and live-auth-probe redesign are rejected as unnecessary for this work package correction.

## Next steps

1. Record the minimal standalone-example design correction and update AF-360 acceptance.
2. Run `python3 tools/project_scope_check.py`.
3. Add failing tests for the two standalone scripts, Make entry points, documentation, and clean-copy promotion.
4. Copy/adapt the existing working Asterion scripts and run focused standalone/root regression gates before reclosing AF-360.

## Ruled-out paths

- Do not copy original `src/dci` or its provider-specific product scripts into the standalone Asterion product.
- Do not redesign authentication, preflight, resource resolution, or the four working root Make examples for this correction.
- Do not duplicate the existing mixed-root corpus unless an independent standalone checkout actually needs its own external resource tree.
- Do not disturb the completed source-pinned Pi repair or accept a global Pi executable as runtime authority.

## Open questions

- No product-design question remains; the approved scope is the two standalone Asterion examples only.
- No publication, remote creation/push, full dataset, or provider-backed operation is authorized.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py
git status --short --branch
make -C asterion check-pi
make example
make runtime-example
make asterion-example
make asterion-runtime-example
```
