# Live Session Checkpoint

> Updated: 2026-07-20 23:26 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

Package: README reproduction and runtime-result parity

Currently running: no evaluator process. H004 Pi bounded r13 ended failed after 21 Agent/14 Judge operations; it completed all original and Asterion QA paths, then exposed missing strict normalization for the published BRIGHT source row shape before the first Asterion BRIGHT provider call. No full dataset is authorized.

## TL;DR

- The user approved AF-340's complete design: one layered CLI/application → `.env`/environment → runtime/Judge-default configuration contract.
- Pi defaults to `openai-codex`/`gpt-5.6-luna`; Claude Code defaults to local subscription login and supports explicit compatible MiniMax Coding Plan translation; Judge defaults independently to DeepSeek V4 Flash.
- Original DCI README Quick Start, Context Management Strategies, and all eleven Benchmark DCI-Agent-Lite launchers are the baseline acceptance paths. Asterion must run the same Pi experiment contract and the paper Claude Code path through source, application, and installed-wheel surfaces.
- The eight-task implementation is recovered from `codex/af-340-implementation` onto `main` by merge commit `6706b42`; Task 8's three hardening rounds and subsequent bounded fixes are preserved.
- AF-340-H-001 through H-003 are confirmed 4/4. H-004 requires exactly three retained bounded reports; one valid MiniMax report exists. H-005 is the separate full-result hypothesis and remains explicitly authorization/budget gated.
- Pi bounded r12 completed the original paths and the first Asterion launcher. Its real Pi conversation exercised the symmetric one-request/one-turn finalization recovery and produced valid text, proving the r11 blocker is repaired.
- r12 exposed dataset parity as the next blocker: public QA rows may encode `answer` as a non-empty string array of aliases, while Asterion accepted only a scalar string. The source runner accepts these rows and sends `str(row["answer"])` to Judge.
- The dataset-parity repair now accepts strict non-empty string aliases, preserves the source JSON array in row/cache identity, and uses the source runner's exact Judge string in initial evaluation and exact reuse. Six public QA datasets and the full local/product boundaries pass; independent review is 0/0/0.
- r13 proves that repair in all seven real Asterion QA paths. Its next local blocker is the published BRIGHT schema: exact source rows contain integer/string query IDs plus source-only metadata and must normalize to immutable IR rows without weakening the generic dataset loader.

## Where things stand

- Project route: managed.
- Lifecycle: active.
- Active package: AF-340.
- Active Climb hypothesis: AF-340-H-004.
- Preserved evidence worktree: `.worktrees/af-340-implementation` (do not remove until H-004 evidence is relocated or closed).
- Dependencies: AF-330 completed.
- Post-fix verification: 1456 root business tests, 134 Asterion tests, the AF-210 four-dimension closure, product 8/8, delegated 538/538, launchers 12/12, extras 6/6, and bounded 7/7 pass; all six public QA datasets preflight, and the provider-free local coordinator, scope preflight, Ruff, compile, shell, TypeScript, Rust, and diff gates pass with zero provider/Judge operations.
- BRIGHT normalization verification: 1459 root business tests, 134 Asterion tests, 129 dataset/batch tests, all four complete public BRIGHT sources, product 8/8+538/538+12/12+6/6+7/7, AF-340 local, TypeScript, Rust, static, scope, and diff gates pass; review is 0/0/0.
- First incremental review found two Important gaps: whitespace protocol projection and missing Asterion cache consumption of the recovery prompt identity. Both are repaired; second review reports 0 Critical, 0 Important, and 0 Minor findings and approves the change.
- Valid retained bounded evidence: `claude-minimax` r6, report file SHA-256 `792c8767c936935d9cf0aca5a50422ff195fecc33ed41c3d8c65b0451612b62c`, canonical report SHA-256 `efabac9ad548f1530de76017195c174ffdcf05d4a3841dc815a6ff92e15c9039`, 2 agent and 2 Judge operations, no full dataset.
- Pi diagnostic r12 is rejected evidence: original paths and first Asterion launcher completed, then the second Asterion QA launcher failed locally before provider construction; 15 Agent/8 Judge, no full dataset. Its first Asterion native evidence proves the empty-final recovery works against real Pi.
- Pi diagnostic r13 is rejected evidence: all original and seven Asterion QA paths completed; first Asterion BRIGHT failed locally before provider construction, for 21 Agent/14 Judge and no full dataset. It proves empty-final and answer-alias repairs against real Pi/Judge.
- External `pi/` remains untouched; `.env` values were loaded only for body-free credential-presence checks and were never printed.

## Next action

1. Run Pi bounded r14 from `ec21de8` in a fresh root; never stitch r10-r13.
2. Inspect the retained r14 report and native evidence before accepting it.
3. Recheck Claude subscription login without a provider request and collect its fresh bounded report only if authentication is restored.
4. Inspect the MiniMax, Pi, and subscription reports together to close H-004. Do not start H-005 without explicit profile/budget authorization.

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
