# Live Session Checkpoint

> Updated: 2026-07-24 10:45 +0800. **Session remains active — not a final handoff.**

Active work package: AF-360

Project lifecycle: active

Currently running: no process.

## TL;DR

- AF-360 is reopened for one post-merge Judge credential-name parity repair.
- A fresh standalone checkout now has explicit pinned-Pi, authentication, basic/benchmark resource, configuration, doctor, and first-run workflows.
- AF-360 implementation is integrated into `main` by merge commit `90cf244`; post-merge review found one remaining describe/template mismatch.

## Where things stand

- `.env.template` and `JudgeConfig` use `DEEPSEEK_API_KEY`, but `asterion describe` still reports `OPENAI_API_KEY`.
- `make setup-pi` provisions the exact full commit in `pi-revision.txt`; `make check-pi` is read-only. A global `pi` executable is intentionally not authoritative.
- `DCI_PI_AGENT_DIR=~/.pi/agent` selects separately managed authentication. Setup never reads, copies, creates, or prints credentials.
- `make setup-resources-basic` creates the wiki and BC+ onboarding layouts; benchmark setup/check reports every packaged and launcher resource, including unavailable/manual sources.
- `.env.template`, runtime resolution, `describe`, `doctor`, and preflight now agree on effective Pi/provider/model/resource/Judge defaults and safe repair actions.
- Final verification passes 202 standalone tests, 117 mixed-root regressions, 16 Markdown files/32 links, and full clean-copy promotion with 18 commands.
- All verification performed zero Agent/Judge operations and no full dataset. No external Pi checkout was mutated.

## Next concrete action

1. Add a failing description-parity assertion for the Judge API-key environment-name default.
2. Reuse `DEFAULT_JUDGE_API_KEY_ENV` in the product description, rerun focused/full provider-free gates, and close AF-360 again.

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
