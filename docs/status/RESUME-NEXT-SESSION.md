# Live Session Checkpoint

> Updated: 2026-07-18 18:22 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

Package: README reproduction and runtime-result parity

Currently running: no repository-owned process.

## TL;DR

- The user approved AF-340's complete design: one layered CLI/application → `.env`/environment → runtime/Judge-default configuration contract.
- Pi defaults to `openai-codex`/`gpt-5.6-luna`; Claude Code defaults to local subscription login and supports explicit compatible MiniMax Coding Plan translation; Judge defaults independently to DeepSeek V4 Flash.
- Original DCI README Quick Start, Context Management Strategies, and all eleven Benchmark DCI-Agent-Lite launchers are the baseline acceptance paths. Asterion must run the same Pi experiment contract and the paper Claude Code path through source, application, and installed-wheel surfaces.
- The eight-task plan is executing autonomously through Climb plus subagent-driven TDD in isolated branch `codex/af-340-implementation`. Four AF-340 hypotheses are active; Task 1 is next.

## Where things stand

- Project route: managed.
- Lifecycle: active.
- Active package: AF-340.
- Active Climb hypothesis: AF-340-H-001.
- Isolated worktree: `.worktrees/af-340-implementation`.
- Dependencies: AF-330 completed.
- No provider request or dataset run occurred while preparing the design.
- External `pi/` remains untouched; `.env` credentials were not read or printed.

## Next action

1. Read `docs/status/climb/research-tree.md` and `.superpowers/sdd/progress.md` in the isolated worktree.
2. Start Task 1 with RED original configuration/effective-projection tests.
3. Review each task for spec compliance and quality before advancing.
4. Continue autonomously through local and bounded evidence; stop before full datasets unless the named profiles and estimated budget receive explicit authorization.

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
