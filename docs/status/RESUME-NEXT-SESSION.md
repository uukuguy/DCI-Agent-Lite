# Live Session Checkpoint

> Updated: 2026-07-20 13:57 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

## TL;DR

- Task 7 is complete at `cc47393`; Climb H-001/H-002 are confirmed 4/4 and the next hypothesis is AF-340-H-003.
- Strict body-free manifests now preserve completed/failed/cancelled/timed-out/missing rows and bind profile, effective configuration, selection, metric, operation, token, cost, and evidence identities.
- Pi comparison uses deterministic 10,000-resample paired bootstrap with 5pp accuracy and 0.02 NDCG margins; Claude is separately labeled target-comparison against the versioned `arxiv:2605.05242v1` registry and never claims source parity.
- Full execution remains fail-closed behind an invocation-only authorization, finite budget, fresh 0700 root, 0600 record, and matching profile/scope/batch identity. No provider operation or full dataset ran.

## Where things stand

- Project route: managed; lifecycle: active; package: AF-340.
- Task 7 verification: 25 reproduction/resolution/product tests pass; deterministic report bytes, Python compile, Ruff, scope, and diff gates pass.
- Packaged product contract exposes the reproduction result schema plus target registry/schema identities; comparison reports require a 0700 parent and are created exclusively as 0600 files.
- Climb cycle 105 confirmed H-002 and regenerated the research tree with H-003 next.
- External `pi/` was not edited; no evaluator, provider verifier, or full execution is running.

## Next action

1. Begin AF-340 Task 8 / H-003 with RED tests for the provider-free local coordinator and literal command matrix.
2. Implement `tools/verify_af340_reproduction.py local`, preserving zero agent/Judge operations, private evidence, and body/path-free public output.
3. Keep bounded-provider evidence distinct from local acceptance; do not execute full profiles without a fresh explicit invocation authorization and budget.

## Ready command

```bash
uv run python -m unittest -v tests.test_af340_reproduction_verifier tests.test_original_readme_acceptance tests.test_asterion_documentation
```
