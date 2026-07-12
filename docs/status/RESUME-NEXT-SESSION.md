# Live Session Checkpoint

> Updated: 2026-07-13 01:51 +0800. **AF-090 is implementation-complete; package closure awaits the next governed design.**

Active work package: AF-090

## TL;DR

- AF-050 is complete with a runnable, verified Rust controlled-executor sidecar at `ef8f898`.
- AF-060 is active under the package-first design and implementation plan; workflow-engine/control-plane-first paths are explicitly excluded.
- `AF-060-H-001` is confirmed: closed manifests, all six kinds, forbidden fields, identifiers, and sorted/unique edges are validated.
- `AF-060-H-002` is confirmed: composition order is stable and duplicate, ambiguous, missing-edge, and cyclic graphs are rejected.
- `AF-060-H-003` is confirmed: Pi and Claude Code compose the same policy/research/evaluation/observability graph.
- `AF-060-H-004` is confirmed: TypeScript exports portable package types and validates the canonical schema/fixtures without a second composer.
- `AF-060-H-005` is confirmed: the static boundary/extension guide and full framework closure gate pass.
- AF-060 is complete with all five hypotheses confirmed and full framework closure evidence.
- AF-070 is active under the approved controlled-code validation design and implementation plan.
- `AF-070-H-001` is confirmed: four portable manifests use the workflow kind, form a stable graph, and exclude runtime-controlled fields.
- `AF-070-H-002` is confirmed: Pi/Claude parity, permutation stability, portable outputs, and every missing boundary pass without changing the composer.
- `AF-070-H-003` is confirmed: TypeScript validates all eight reference manifests and retains no composer implementation.
- `AF-070-H-004` is confirmed: documentation and the independent full framework closure gate pass.
- AF-070 is complete with all four hypotheses and full framework closure evidence.
- AF-080 is active under the approved explicit-root, exact-version local catalog design and implementation plan.
- `AF-080-H-001` is confirmed: explicit roots yield stable validated direct-child catalogs across root and file permutations.
- `AF-080-H-002` is confirmed: filesystem, document, symlink, and duplicate-identity ambiguity fails closed with safe errors.
- `AF-080-H-003` is confirmed: exact selections are deterministic/fresh, compose both graphs, and reject duplicate/unknown refs.
- `AF-080-H-004` is confirmed: catalog documentation and independent full framework closure pass.
- AF-080 remains active only until the knowledge layer records the next governed package.
- AF-080 is complete; AF-090 is active under the approved static application assembly design and plan.
- `AF-090-H-001` is confirmed: the closed canonical assembly contract and shared Python fixtures pass.
- `AF-090-H-002` is confirmed: runtime identity, exact catalog refs, host-service separation, and safe immutable resolution pass 4/4.
- AF-090-H-003 product evidence is green: both checked-in reference assemblies validate, DCI has Pi/Claude plan parity, and controlled execution stays host-owned.
- `AF-090-H-003` and `AF-090-H-004` are confirmed 4/4; TypeScript parity, documentation, and full closure are green.
- Fresh closure evidence: 237 Python, 11 Node, and 19 Rust tests plus compile, Ruff, clean npm install, fmt, Clippy, shell, scope, and diff gates.

## Durable boundary

- Branch: `main`; AF-050 functional closure is committed at `ef8f898`.
- AF-060 governance/design/climb transition is committed at `826ccb9`.
- AF-060-H-001 package manifests are committed at `a4266ad`.
- AF-060-H-002 deterministic composer is committed at `0e7c15b`.
- AF-060-H-003 DCI reference graph is committed at `fc9b9cd`.
- AF-060-H-004 TypeScript parity is committed at `e0e1ae4`.
- No long-running process is active; external `pi/` remains intentionally untouched and dirty.

## Immediate next action

After strategic approval, write and commit the AF-100 minimal application-runner design, activate it in WORKLIST, and formally close AF-090.

## Guardrails

- Static composition precedes workflow execution.
- Do not put prompts, credentials, executable paths, commands, mutable state, or adapter-private types in package manifests.
- Do not recurse, load code, follow symlinks, install packages, access a network, solve versions, or execute packages in AF-080.

## Ready commands

```bash
python3 tools/project_scope_check.py --climb-hypothesis AF-090-H-004
uv run python -m unittest tests.test_application_assembly -v
```
