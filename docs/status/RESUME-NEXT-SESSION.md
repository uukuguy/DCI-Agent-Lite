# Live Session Checkpoint

> Updated: 2026-07-19 11:59 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

Package: README reproduction and runtime-result parity

Currently running: no repository-owned process.

## TL;DR

- The user approved AF-340's complete design: one layered CLI/application → `.env`/environment → runtime/Judge-default configuration contract.
- Pi defaults to `openai-codex`/`gpt-5.6-luna`; Claude Code defaults to local subscription login and supports explicit compatible MiniMax Coding Plan translation; Judge defaults independently to DeepSeek V4 Flash.
- Original DCI README Quick Start, Context Management Strategies, and all eleven Benchmark DCI-Agent-Lite launchers are the baseline acceptance paths. Asterion must run the same Pi experiment contract and the paper Claude Code path through source, application, and installed-wheel surfaces.
- Bounded AF-340 verification has started and passed for the Claude-Minimax path: `af340-bounded-claude-minimax-r6` (`agent:installed-claude-minimax` + `agent:wheel-claude-minimax`), with no full dataset.

## Where things stand

- Project route: managed.
- Lifecycle: active.
- Active package: AF-340.
- Dependencies: AF-330 completed.
- A bounded AF-340 provider-backed verification run has completed (no full dataset). Process and `.env` precedence was explicitly aligned during execution.
- External `pi/` remains untouched; `.env` credentials were not read or printed.
- Asterion DCI config/runtimes fix committed locally: unified layered contract now resolves runtime defaults and provider/model by runtime, keeps `--runtime` optional in CLI, and routes resolved options into runtime factory context. `.env.template` now documents the contract and defaults.
- Latest state has a passing full targeted test set for changed files (`asterion` CLI/factory/config/product parity + `dci` batch/config + batch parity).

## Next action

1. Confirm no active `git`-owned process is running (already none), then continue AF-340 test-first execution for remaining tasks with the same evidence discipline.
2. Add explicit bounded/full-authorization `--runtime=pi` and `--runtime=claude-code` evidence for any remaining README-labeled paths.
3. Log each completed verification boundary in `JOURNAL` before moving to subsequent tasks.
4. Proceed to full comparison evidence only after explicit `--authorize-full` profile, explicit budget review, and unchanged scope boundaries.

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
- Keep `AF-340 Task` evidence aligned to scoped runtime-contract assertions before any full comparison.

- Latest verifier output: `/Users/sujiangwen/sandbox/agentic-2026/DCI-Agent-Lite/.worktrees/af-340-implementation/outputs/verification/af340-bounded-claude-minimax-r6/af340-bounded-report.json` (status pass, agent ops 2, judge ops 2).

## Ready command

```bash
python3 tools/project_scope_check.py
```
