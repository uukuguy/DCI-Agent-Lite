# AF-300 Task 4 Checkpoint

> Updated: 2026-07-16 +0800. AF-300 execution is active; Tasks 1–3 are committed and Task 4 has reached its verified commit boundary.

Active work package: AF-300

## TL;DR

- Asterion Python, cross-language packages, schemas, examples, and launchers now live under the top-level `asterion/` project root.
- Task 4 moves the product documentation hub, architecture north star, product guides, verification guide, and operator guide under `asterion/docs/`; focused, consumer, link, static, and scope gates pass.
- Original DCI, cross-product parity/acceptance evidence, `docs/status/`, and `docs/superpowers/` remain mixed-repository dependencies at the root.
- Installed identities, runtime behavior, provider-backed evidence, and full-dataset status remain unchanged.

## Committed / unpushed state

- AF-300 Tasks 1–3 and their JOURNAL entries are committed through `48158ef`.
- Task 4 starts from `48158ef`; its implementation and append-only JOURNAL entry are separate commit boundaries.
- The user-owned `.superpowers/sdd/task-0-review.md` remains intentionally untouched.

## Next concrete action

Review the Task 4 report and implementation commit; after acceptance, execute Task 5's project-local test/fixture migration from the AF-300 plan.

## Open questions

- None for Task 4. Full datasets, publication/release automation, and plugin splitting remain deferred.

## Ruled-out paths

- Do not move `docs/status/`, `docs/superpowers/`, original DCI documentation, root parity assets, or the external `pi/` checkout into Asterion.
- Do not leave forwarding stubs at obsolete product-documentation paths.
- Do not reinterpret historical provider-backed acceptance or full-dataset evidence during this path-only convergence.
- Do not begin the Task 5 test/fixture migration from this checkpoint.

## Ready commands

```bash
python3 tools/project_scope_check.py
uv run python -m unittest tests.test_asterion_project_root tests.test_asterion_documentation tests.test_distribution_boundaries -v
git diff --check
git status --short
```
