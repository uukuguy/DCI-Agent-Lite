# Live Session Checkpoint

> Updated: 2026-07-13. **Session remains active — not a final handoff.**

Active work package: AF-160

## TL;DR

- Asterion remains exactly one buildable `asterion` wheel. `src/dci` is the enhanced source-run comparison baseline and is not packaged; `src/dci/benchmark/` was not modified.
- AF-150 is complete through `e7ab64a` and `e576122`: the installed CLI accepts only explicit binary/policy/validation configuration for controlled-code, validates it before runtime or subprocess construction, starts one direct-argv minimal-environment sidecar, injects it explicitly, forwards correlated cancellation, discards stderr in bounded chunks, and reaps the child.
- The final fresh wheel verification lists `controlled-code` and `dci-agent-lite`, confirms `import dci` fails, and runs `code.quality@1.0.0` successfully with the Rust sidecar using a deliberately minimal `/usr/bin/true` trusted policy.
- AF-160 availability evidence: Claude Code 2.1.199 is installed, but `claude auth status` reports no login and no compatible gateway configuration is present. No provider request was sent; the package is safely waiting for operator-supplied authorization.

## Verified state

- Branch: `main`; no long-running process is active. No external Pi checkout was modified.
- Latest implementation commits: `e7ab64a feat: forward controlled executor cancellation`; `e576122 fix: bound controlled executor stderr draining`.
- AF-150 closure/AF-160 transition is committed as `f8416ed`; the current pending state checkpoint records AF-160's content-free authorization block.
- Final verification completed: 362 Python tests, 11 Node tests, and 19 Rust tests; Python compilation, Ruff, shell syntax, scope audit, and `git diff --check` all passed.

## Next action

When an operator provides an authorized Claude login or compatible gateway, re-run the safe availability probe, then perform the already-designed tiny local-corpus provider-backed acceptance. Until then, make no runtime/protocol change and do not send provider requests. Do not create a speculative executor protocol/daemon package: D-033 deliberately defers supervised connection, persistent reuse, and health negotiation until a concrete deployment requires them.

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
