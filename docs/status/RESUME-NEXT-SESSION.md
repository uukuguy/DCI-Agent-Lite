# Live Session Checkpoint

> Updated: 2026-07-23 09:31 +0800. **Session remains active — not a final handoff.**

Active work package: AF-350

Package: AF-350 — Asterion standalone promotion readiness

Currently running: no process.

## TL;DR

- Tasks 1–5 are complete: repository skeleton, package-owned acceptance, 14 standalone launchers, and root-contained documentation are GREEN.
- Standalone tests pass 157/157; 16 Markdown files and 32 links pass both in place and after copying.
- Continue inline with Task 6: implement the clean-copy promotion verifier and provider-free GitHub Actions workflow.

## Where things stand

- `09b47e8` adds standalone root assets, complete Make targets, package metadata, and reproducible locks.
- `945261b` makes installed acceptance package-owned and source/wheel equivalent while preserving mixed-root parity.
- `ef03e3c` makes all 14 launchers resolve project/external-resource roots without parent traversal.
- `cace918` replaces parent-workspace operational docs with standalone commands and adds the deterministic docs checker.
- Mixed 538-selector and 12-launcher-pair counts are explicitly historical mixed-repository integration evidence, not standalone live acceptance.
- AF-350 authorizes no provider request, full dataset, paper reproduction, publication, remote push, release, or external `pi/` mutation.
- No evaluator, verifier, test, Rust, Node, or promotion process is running.

## Next steps

1. Execute Task 6 RED/GREEN for `tools/check_promotion.py` and `.github/workflows/ci.yml`.
2. Make quick/full clean-copy modes deterministic and provider-free.
3. Route `make promotion-check` and CI through the same full verifier.

## Open questions

- No design question remains. Execution mode is inline; promotion automation is the next boundary.
- Creating a remote, publishing, or running provider-backed validation remains outside AF-350.

## Ruled-out paths

- Do not copy original `src/dci`, parent governance, retained private evidence, corpora, datasets, credentials, or external Pi into `asterion/`.
- Do not reconstruct the mixed-root verifier inside standalone acceptance or promotion checks.
- Do not weaken missing/escaping documentation links into warnings.
- Do not run providers, a Judge, or a full dataset during AF-350 promotion readiness.

## Ready commands

```bash
python3 tools/project_scope_check.py
git status --short --branch
sed -n '740,860p' docs/superpowers/plans/2026-07-23-af-350-asterion-standalone-promotion-readiness.md
(cd asterion && uv run python -m unittest -v tests.test_check_promotion)
git diff --check
```
