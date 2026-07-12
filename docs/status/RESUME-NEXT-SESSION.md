# Live Session Checkpoint

> Updated: 2026-07-12 19:32 +0800. **Session remains active — not a final handoff.**

## TL;DR

- H-016 is confirmed at 4/4 and committed as `7db038f`: judge base URLs now require an absolute HTTP(S) origin before endpoint construction, safe metadata, cache identity, or transport setup.
- The H-016 cycle ran its complete local acceptance path and regenerated the tracked climb state; the pool is empty again.
- The next grounded direction is H-017: prevent automatic judge redirects from forwarding evaluated input or authorization headers beyond the configured origin.

## Where things stand

- Fresh verification: 87 unit tests, Python compilation, Ruff on touched Python files, touched-Bash syntax, `git diff --check`, and `make check-pi-rpc` passed.
- No live judge preflight ran: H-016 only validates configuration ingress and leaves request shape, credentials, and endpoint selection unchanged.
- The parent worktree is clean after `7db038f`; the independent dirty `pi/` checkout remains deliberately excluded.

## Next step

1. Run the Knowledge Layer for H-017, add a failing redirect-containment transport test, then implement the smallest compatible no-redirect policy.

## Guardrails

- Preserve valid remote HTTPS and explicitly configured local HTTP judge origins, including path prefixes such as `/v1`.
- Never put keys in base URLs; use `DCI_EVAL_JUDGE_API_KEY` or the configured key environment variable.
- Do not touch or commit the independent `pi/` checkout.

```bash
uv run python -m unittest tests.test_judge -v
uv run python -m unittest discover -v
make check-pi-rpc
```
