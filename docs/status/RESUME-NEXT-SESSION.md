# Live Session Checkpoint

> Updated: 2026-07-19 07:37 +0800. **Session remains active — not a final handoff.**

Active work package: AF-340

Package: README reproduction and runtime-result parity

Currently running: no live process. Claude MiniMax r1/r2 were both rejected after 10 HTTP 401 retries on the international and China endpoints, so the current Coding Plan token is not authenticating. Pi r8 was rejected on the `openai-codex` usage limit; no full dataset is authorized.

## TL;DR

- The user approved AF-340's complete design: one layered CLI/application → `.env`/environment → runtime/Judge-default configuration contract.
- Pi defaults to `openai-codex`/`gpt-5.6-luna`; Claude Code defaults to local subscription login and supports explicit compatible MiniMax Coding Plan translation; Judge defaults independently to DeepSeek V4 Flash.
- Original DCI README Quick Start, Context Management Strategies, and all eleven Benchmark DCI-Agent-Lite launchers are the baseline acceptance paths. Asterion must run the same Pi experiment contract and the paper Claude Code path through source, application, and installed-wheel surfaces.
- The eight-task implementation plan is complete in isolated branch `codex/af-340-implementation`; Task 8 required three independent hardening rounds and now has no Critical, Important, or Minor findings.
- AF-340-H-001 through H-003 are confirmed 4/4. H-004 is the only remaining hypothesis and requires three retained real bounded reports plus separately authorized full-result evidence.

## Where things stand

- Project route: managed.
- Lifecycle: active.
- Active package: AF-340.
- Active Climb hypothesis: AF-340-H-004.
- Isolated worktree: `.worktrees/af-340-implementation`.
- Dependencies: AF-330 completed.
- No provider request or dataset run occurred while implementing or confirming H-001 through H-003.
- External `pi/` remains untouched; `.env` credentials were not read or printed.

## Next action

1. Restore one external runtime credential boundary: wait for the `openai-codex` usage limit to clear, refresh the MiniMax Coding Plan token, or log Claude Code into a subscription.
2. Re-run the restored bounded variant into a fresh private root; never reuse or stitch r1-r8 diagnostic outputs.
3. Bind successful bounded reports into H-004 state, but do not substitute them for full evidence.
4. Use the retained five-profile dry-run counts to request a named profile and real budget; require explicit authorization before any full dataset.

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
python3 tools/verify_af340_reproduction.py bounded --help
```
