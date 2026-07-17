# Live Session Checkpoint

> Updated: 2026-07-17 12:49 +0800. **Session remains active — not a final handoff.**

Active work package: AF-330

Package: AF-330 complete application and dual-runtime exposure

Currently running: no process. AF-330-H-001 through H003 are confirmed 4/4; H004 fail-closed real Claude Code application acceptance is next.

## TL;DR

- AF-320 is complete; AF-330 now owns five-stage application composition and bounded real Pi/Claude semantics.
- AF-330 uses exact Read/Grep/Glob visibility plus fail-closed sandbox/settings identity for Claude; prompt-only restriction is rejected.
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

1. Replace Claude's current Read/Bash command with exact Read/Grep/Glob, `dontAsk`, strict MCP, and fail-closed sandbox settings.
2. Persist attempt-scoped private Claude artifacts so evaluation and the terminal binder can revalidate them.
3. Run and bind one real bounded Claude Code complete application without a full dataset.

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
git -C pi rev-parse HEAD
git -C pi status --short
sed -n '175,310p' docs/superpowers/specs/2026-07-16-paper-aligned-dci-complete-implementation-design.md
```
