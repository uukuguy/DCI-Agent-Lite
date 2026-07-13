# Live Session Checkpoint

> Updated: 2026-07-13 08:11 +0800. **Session remains active — not a final handoff.**

Active work package: AF-120

Package state: AF-120 single-wheel plan is executing inline; distribution and capability consolidation are complete, built-in DCI provider is next.

## TL;DR

- AF-110 is closed: capability packages are reusable executable units and applications are executable composition boundaries.
- AF-120 has implemented the Asterion/core split, frozen baseline-owned `dci.framework.*`, provider v1 validation, selected-only discovery, and generic `asterion list/run` through `444efc3`.
- The earlier four-distribution plan is superseded. User-approved D-030 requires exactly one buildable `asterion` wheel containing framework core, modular first-party DCI capability/application code, and canonical resources.
- `src/dci` remains the enhanced runnable comparison baseline in this repository, but produces no wheel and is never an Asterion dependency.
- The corrected design and plan are committed at `a0f0a7f` and `b8441f7`.
- `05813e0` makes the root a non-buildable workspace and preserves baseline source execution.
- `4a76c29` folds DCI research code/manifests into `asterion.capabilities.dci_research`; 108 focused Python and 11 Node tests pass.

## Where things stand

- Branch: `main`; no long-running process or in-flight climb hypothesis is active.
- No long-running process is active; nothing has been pushed in this session.
- AF-120 remains the sole active package and scope preflight passes.
- The interim root `dci` and `asterion-dci-research` build projects are removed. Application assemblies/provider still need to move into the Asterion wheel.
- External `pi/` remains an independent checkout and was not modified.

## Next steps (immediate)

1. Add failing built-in DCI provider/resource/entry-point tests.
2. Move application assemblies into `asterion.applications.dci_agent_lite` and register the provider in the sole wheel.
3. Convert repository baseline scripts/docs from removed console entry points to source invocation without modifying `src/dci/benchmark/`.

## Open questions

- None. Inline execution was already selected; only the written-spec review gate remains.

## Don't go down these paths again

- Do not extend AF-100 with scheduler, workflow-engine, registry, retry, persistence, API-server, tenancy, or control-plane scope.
- Do not infer runtime or service ownership from capability names; resolved plans and caller-supplied services remain authoritative.
- Do not rename stable `dci.*` wire literals or remove `dci.framework.*` compatibility imports during entry-point integration.
- Do not restore separate first-party capability, application, or baseline wheels.
- Do not modify `src/dci/benchmark/`; preserve the verified enhanced baseline as source.
- Do not treat the Rust controlled executor as an operating-system sandbox or accept executable policy from agent requests.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py
git status --short
git log --oneline -8
sed -n '1,260p' docs/status/WORKLIST.md
sed -n '1,340p' docs/superpowers/specs/2026-07-13-installed-application-binding-design.md
sed -n '128,138p' docs/status/WORKLIST.md
git status --short
```
