# Live Session Checkpoint

> Updated: 2026-07-24 10:45 +0800. **Session remains active — not a final handoff.**

Active work package: none

Project lifecycle: complete

Currently running: no process.

## TL;DR

- AF-360 standalone first-run readiness is implemented, reviewed, verified, and closed.
- A fresh standalone checkout now has explicit pinned-Pi, authentication, basic/benchmark resource, configuration, doctor, and first-run workflows.
- The isolated `codex/af-360-first-run` branch is ready to merge into `main`.

## Where things stand

- Implementation commits run from `b363013` through `aa4b490`; governance closure is the next commit.
- `make setup-pi` provisions the exact full commit in `pi-revision.txt`; `make check-pi` is read-only. A global `pi` executable is intentionally not authoritative.
- `DCI_PI_AGENT_DIR=~/.pi/agent` selects separately managed authentication. Setup never reads, copies, creates, or prints credentials.
- `make setup-resources-basic` creates the wiki and BC+ onboarding layouts; benchmark setup/check reports every packaged and launcher resource, including unavailable/manual sources.
- `.env.template`, runtime resolution, `describe`, `doctor`, and preflight now agree on effective Pi/provider/model/resource/Judge defaults and safe repair actions.
- Final verification passes 202 standalone tests, 117 mixed-root regressions, 16 Markdown files/32 links, and full clean-copy promotion with 18 commands.
- All verification performed zero Agent/Judge operations and no full dataset. No external Pi checkout was mutated.

## Next concrete action

1. Commit the AF-360 governance closure.
2. Merge `codex/af-360-first-run` into `main`.
3. Re-run `python3 tools/project_scope_check.py` and a focused post-merge smoke, then record the merge checkpoint.

## Open questions

- None for AF-360.
- Any publication, remote creation/push, global-Pi trust, vendored resources, or full-dataset reproduction requires separate user authority and governance.

## Ruled-out paths

- Do not replace `DCI_PI_DIR` with an unpinned global executable.
- Do not conflate `DCI_PI_DIR` source ownership with `DCI_PI_AGENT_DIR` authentication state.
- Do not embed Pi, credentials, corpora, benchmark datasets, private evidence, or parent-only tools into the standalone project.
- Do not treat setup or preflight success as Agent/Judge or full-execution authority.
- `tests.test_asterion_standalone_integration` is not a real root module; the current mixed-root boundary lives in structure, project-root, documentation, distribution, configuration, verification, and scope modules.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py
git status --short --branch
cd asterion
uv run python tools/check_promotion.py --quick
```
