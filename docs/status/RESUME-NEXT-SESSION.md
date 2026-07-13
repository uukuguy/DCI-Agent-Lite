# Live Session Checkpoint

> Updated: 2026-07-13. **Session remains active — not a final handoff.**

Active work package: AF-160

## TL;DR

- Asterion remains exactly one buildable `asterion` wheel. `src/dci` is the enhanced source-run comparison baseline and is not packaged; `src/dci/benchmark/` was not modified.
- AF-150 is complete through `e7ab64a` and `e576122`: the installed CLI accepts only explicit binary/policy/validation configuration for controlled-code, validates it before runtime or subprocess construction, starts one direct-argv minimal-environment sidecar, injects it explicitly, forwards correlated cancellation, discards stderr in bounded chunks, and reaps the child.
- The final fresh wheel verification lists `controlled-code` and `dci-agent-lite`, confirms `import dci` fails, and runs `code.quality@1.0.0` successfully with the Rust sidecar using a deliberately minimal `/usr/bin/true` trusted policy.

## Verified state

- Branch: `main`; no long-running process is active. No external Pi checkout was modified.
- Latest implementation commits: `e7ab64a feat: forward controlled executor cancellation`; `e576122 fix: bound controlled executor stderr draining`.
- Current state-document closure/transition commit is pending; its expected scope is only `docs/status/{JOURNAL,CURRENT-STATE,DECISIONS,WORKLIST,RESUME-NEXT-SESSION}.md`.
- Final verification completed: 362 Python tests, 11 Node tests, and 19 Rust tests; Python compilation, Ruff, shell syntax, scope audit, and `git diff --check` all passed.

## Next action

Run AF-160's safe availability probe for the existing Claude Code runtime. If an authorized local login or compatible gateway is available, perform the already-designed tiny local-corpus provider-backed acceptance. Otherwise record a content-free block and make no runtime/protocol change. Do not create a speculative executor protocol/daemon package: D-033 deliberately defers supervised connection, persistent reuse, and health negotiation until a concrete deployment requires them.

## Guardrails

- Do not modify `src/dci/benchmark/`; it remains the runnable baseline.
- Do not add separate Asterion/DCI wheels or package the source baseline.
- Do not permit provider, manifest, or agent input to choose binary, policy, commands, paths, or automatic sidecar startup.
- Do not claim the Rust executor is an operating-system sandbox.

## Ready-to-paste recovery commands

```bash
sed -n '1,220p' docs/status/INDEX.md
sed -n '1,260p' docs/status/CURRENT-STATE.md
sed -n '1,260p' docs/status/WORKLIST.md
tail -n 45 docs/status/JOURNAL.md
python3 tools/project_scope_check.py
git status --short
git log --oneline -8
```
