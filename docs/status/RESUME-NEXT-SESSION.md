# Live Session Checkpoint

> Updated: 2026-07-13. **Session remains active — not a final handoff.**

Active work package: AF-170

## TL;DR

- Asterion remains exactly one buildable `asterion` wheel. `src/dci` is the enhanced source-run comparison baseline and is not packaged; `src/dci/benchmark/` was not modified.
- AF-150 is complete through `e7ab64a` and `e576122`: the installed CLI accepts only explicit binary/policy/validation configuration for controlled-code, validates it before runtime or subprocess construction, starts one direct-argv minimal-environment sidecar, injects it explicitly, forwards correlated cancellation, discards stderr in bounded chunks, and reaps the child.
- The final fresh wheel verification lists `controlled-code` and `dci-agent-lite`, confirms `import dci` fails, and runs `code.quality@1.0.0` successfully with the Rust sidecar using a deliberately minimal `/usr/bin/true` trusted policy.
- AF-160 is closed through `4072971` and `3708732`: exact `claude-code.reference` selection plus fixture-driven command/environment/redaction checks pass without a provider request. AF-170 is active and requires a dedicated DCI compatibility design before implementation.

## Verified state

- Branch: `main`; no long-running process is active. No external Pi checkout was modified.
- Latest implementation commits: `4072971 feat: register installed Claude runtime factory`; `3708732 docs: document installed Claude runtime factory`.
- AF-170 transition is committed as `45eb3be`; no process is live and Git was clean before this handoff checkpoint.
- Final verification completed: 362 Python tests, 11 Node tests, and 19 Rust tests; Python compilation, Ruff, shell syntax, scope audit, and `git diff --check` all passed.

## Next action

Design AF-170's explicit DCI provider runtime declaration and fixture-only generic CLI proof. Do not change provider behavior until that design is approved. The implementation must not send provider requests. Real UAT resumes only when an operator supplies authorization. Do not create a speculative executor protocol/daemon package: D-033 deliberately defers supervised connection, persistent reuse, and health negotiation until a concrete deployment requires them.

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
