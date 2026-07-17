# Live Session Checkpoint

> Updated: 2026-07-17 15:23 +0800. **Session remains active — not a final handoff.**

Active work package: AF-330

Package: AF-330 complete application and dual-runtime exposure

Currently running: no process. AF-330-H-001 through H003 are confirmed 4/4. H004 implementation is committed; real Claude evidence is blocked only by `loggedIn=false`.

## TL;DR

- AF-320 is complete; AF-330 now owns five-stage application composition and bounded real Pi/Claude semantics.
- AF-330 uses exact Read/Grep/Glob visibility plus fail-closed sandbox/settings identity for Claude; prompt-only restriction is rejected.
- Commit `86363de` completes the restricted Claude application, private evidence, direct Judge evaluation, and independent body-free auditor in both original/Asterion runtime surfaces.
- The bounded real attempt failed at Claude authentication before DeepSeek was called; this is not H004 evidence and H004 remains pending.
- Bounded acceptance now uses the configured supported Judge and binds its endpoint/API/model/request-shaping identity plus prompt-contract digest; GPT-4.1 is not a functional gate.
- Final evidence SHA is `0d48c9f24a6a54335c8e80d4569ddb0e8ad6635c10c4849e6ec1cb3f171ccd55`; it binds a clean locked Pi runtime, DeepSeek Judge identity, two agents, one Judge, and no full dataset.
- `paper-full` rows remain unconditionally non-executable; AF-340 remains the only package that may add full-run authorization and budget.
- External `pi/` retains pre-existing user changes and must remain untouched.

## Verified closure

- AF-320 provider evidence SHA: `0d48c9f24a6a54335c8e80d4569ddb0e8ad6635c10c4849e6ec1cb3f171ccd55`.
- Bound private report SHA: `1b4d71388169a4fe126793cba11c7eb91b73644dffa417744f4e357a68dc2b75`.
- Runtime: clean Pi `8479bd84743e8889f728acb21a62794102db0529`; Judge: `deepseek-v4-flash` over `chat-completions`.
- Final closure: 1394 full Python tests, 246 final selectors, product 8/8, 533/533, 12/12, 6/6, and 7/7; compile, Ruff, installed wheel/product, privacy, clean-runtime, scope, and diff checks pass.
- Independent acceptance review found no Critical or Important issue; no full dataset or paper-score claim ran.

## Next concrete action

1. Restore an operator-owned Claude login with `claude auth login`, then confirm `claude auth status` reports `loggedIn=true`.
2. Run one new bounded complete application with a fresh run ID and the ignored `outputs/af330-claude-corpus` corpus.
3. Audit its private directory, write body-free tracked H004 evidence, run Climb, and close AF-330 only if all four H004 checks pass.

## Boundaries

- Do not modify or clean the external `pi/`; use clean disposable clones for acceptance when required.
- Do not treat 533 current-source selectors as all thirteen paper datasets.
- Do not run full datasets before AF-340 receives explicit budget authorization.
- AF-320 owns dataset adapters, paper coverage/localization metrics, and bounded ablation surfaces; AF-330 owns complete dual-runtime application semantics.
- The configured DeepSeek Judge is valid for AF-320 functional evidence; GPT-4.1 is paper provenance and AF-340 score-comparability scope.

## Ready commands

```bash
git status --short
python3 tools/project_scope_check.py
claude auth status
ASTERION_RUNTIME_CWD=outputs/af330-claude-corpus ASTERION_CLAUDE_OUTPUT_ROOT=outputs/af330-claude-runs uv run asterion run --provider dci-agent-lite --application dci.complete-application@1.0.0 --runtime claude-code.reference --run-id af330-claude-bounded-r2 --input '{"protocol":"asterion.dci.complete-input/v1","question":"Read the local corpus and report only the four-digit number paired with the bounded verification phrase silver compass.","gold_answer":"8426"}'
```
