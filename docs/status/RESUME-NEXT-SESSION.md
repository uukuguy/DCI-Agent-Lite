# Live Session Checkpoint

> Updated: 2026-07-18 17:44 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

Package: README reproduction and runtime-result parity

Currently running: no repository-owned process.

## TL;DR

- The user approved AF-340's complete design: one layered CLI/application → `.env`/environment → runtime/Judge-default configuration contract.
- Pi defaults to `openai-codex`/`gpt-5.6-luna`; Claude Code defaults to local subscription login and supports explicit compatible MiniMax Coding Plan translation; Judge defaults independently to DeepSeek V4 Flash.
- Original DCI README Quick Start, Context Management Strategies, and all eleven Benchmark DCI-Agent-Lite launchers are the baseline acceptance paths. Asterion must run the same Pi experiment contract and the paper Claude Code path through source, application, and installed-wheel surfaces.
- The design review gate passed and the eight-task test-first implementation plan is written. No implementation has started; the next action is to choose inline or user-authorized subagent-driven execution.

## Where things stand

- Project route: managed.
- Lifecycle: active.
- Active package: AF-340.
- Dependencies: AF-330 completed.
- No provider request or dataset run occurred while preparing the design.
- External `pi/` remains untouched; `.env` credentials were not read or printed.

## Next action

1. Run `python3 tools/project_scope_check.py` before implementation execution.
2. Start Task 1 in `docs/superpowers/plans/2026-07-18-af-340-readme-reproduction-runtime-parity.md` with RED configuration tests.
3. Execute each task test-first and commit/journal its verified boundary.
4. Stop after the full dry-run manifest unless the user separately authorizes the named profiles and estimated budget; `.env` never supplies that authority.

## Accepted boundaries

- `.env` and CLI are complementary layers, not alternate modes.
- `DCI_PROVIDER`/`DCI_MODEL` are common public fields interpreted by the selected runtime.
- Original DCI supports Pi only; Asterion supports Pi and Claude Code.
- Agent and Judge roles remain independently configured and credentialed.
- Local, bounded, and full verification are distinct evidence classes.
- Full comparison retains per-query evidence and versioned non-inferiority/confidence criteria.

## Ruled-out paths

- Do not create runtime-specific public provider variable families.
- Do not apply Pi provider compatibility or defaults to Claude Code.
- Do not substitute internal fixtures for the literal README user paths.
- Do not claim full or comparable results from bounded `--limit 1` evidence.
- Do not make Asterion import or launch original DCI to manufacture parity.
- Do not let `.env`, generic verification, or cache presence authorize full-dataset cost.

## Ready command

```bash
python3 tools/project_scope_check.py
```
