# Live Session Checkpoint

> Updated: 2026-07-20 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

Package: README reproduction and runtime-result parity

Currently running: no live provider or evaluator process. The interrupted implementation branch is being merged into `main`; focused and full local regressions pass. No full dataset is authorized.

## TL;DR

- The user approved AF-340's complete design: one layered CLI/application → `.env`/environment → runtime/Judge-default configuration contract.
- Pi defaults to `openai-codex`/`gpt-5.6-luna`; Claude Code defaults to local subscription login and supports explicit compatible MiniMax Coding Plan translation; Judge defaults independently to DeepSeek V4 Flash.
- Original DCI README Quick Start, Context Management Strategies, and all eleven Benchmark DCI-Agent-Lite launchers are the baseline acceptance paths. Asterion must run the same Pi experiment contract and the paper Claude Code path through source, application, and installed-wheel surfaces.
- The eight-task implementation is recovered from `codex/af-340-implementation` onto `main`; Task 8's three hardening rounds and subsequent bounded fixes are preserved.
- AF-340-H-001 through H-003 are confirmed 4/4. H-004 requires exactly three retained bounded reports; one valid MiniMax report exists. H-005 is the separate full-result hypothesis and remains explicitly authorization/budget gated.

## Where things stand

- Project route: managed.
- Lifecycle: active.
- Active package: AF-340.
- Active Climb hypothesis: AF-340-H-004.
- Preserved evidence worktree: `.worktrees/af-340-implementation` (do not remove until H-004 evidence is relocated or closed).
- Dependencies: AF-330 completed.
- Recovered verification: 127 AF-340 focused tests, 1443 root Python tests, 134 Asterion tests, and 153 Climb adapter tests pass; the provider-free local coordinator, scope preflight, Ruff, compile, shell, JSON, and diff gates pass. Final independent review reports 0 Critical and 0 Important findings.
- Valid retained bounded evidence: `claude-minimax` r6, report file SHA-256 `792c8767c936935d9cf0aca5a50422ff195fecc33ed41c3d8c65b0451612b62c`, canonical report SHA-256 `efabac9ad548f1530de76017195c174ffdcf05d4a3841dc815a6ff92e15c9039`, 2 agent and 2 Judge operations, no full dataset.
- External `pi/` remains untouched; `.env` values were loaded only for body-free credential-presence checks and were never printed.

## Next action

1. Commit the fully verified recovered merge, then record its exact commit identity in this checkpoint.
2. Recheck Pi saved-auth quota and Claude subscription login without making provider requests.
3. When a blocked boundary is restored, run that bounded variant into a fresh private root; never reuse or stitch rejected diagnostic outputs.
4. Inspect the MiniMax, Pi, and subscription reports together to close H-004.
5. Do not start H-005 until a named profile, finite budget, and explicit invocation authorization are supplied.

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
uv run python tools/verify_af340_reproduction.py local
```
