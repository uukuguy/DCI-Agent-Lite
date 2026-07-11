# Next-Session Handoff

> Updated: 2026-07-12 06:05 +0800; direct user-authorized handoff.

## TL;DR

- `dci-agent-lite` now uses `.env` for the agent, external Pi checkout, and OpenAI-compatible judge; the primary judge example is DeepSeek `deepseek-v4-flash` over Chat Completions.
- Pi RPC is hardened around `agent_settled`, retry-safe answer capture, malformed-output/child-exit diagnostics, and `DCI_RPC_TIMEOUT_SECONDS`; 20 tests and the live runtime example pass.
- Keep Python + RPC for now. The first next-session action is to inspect the clean boundary and push the two local state commits if the GitHub mirror should be synchronized.

## Where things stand

- Branch: `main`; after this handoff commit the working tree is expected to be clean and local `main` is two commits ahead of `origin/main`.
- Remote roles: `origin=https://github.com/uukuguy/DCI-Agent-Lite.git`; `upstream=https://github.com/DCI-Agent/DCI-Agent-Lite.git`.
- Last live acceptance: `make runtime-example` returned `Adaku`; DeepSeek judge reported `is_correct: true`; recorded event sequence ended with `agent_settled`.
- Verification: 20/20 unit tests pass; compileall, Ruff, shell syntax, CLI help, and `git diff --check` passed.
- No DCI/Pi runtime, batch evaluator, watcher, or delegated agent remains active at handoff.
- The external `pi/` repository is intentionally dirty with user-owned changes and remains outside parent-repository version control. Do not clean or commit it from the parent project.
- Repository `.env`, outputs, corpora, data, Pi checkouts, local `AGENTS.md`/`CLAUDE.md`, and collaboration MEMORY are intentionally ignored/local.

## What this session delivered

- `ac78808` — configurable eval judge via `.env`, including OpenAI Responses and compatible Chat Completions transports.
- `9844dc8` — DeepSeek structured-output hardening and decoupled `pi`/legacy `pi-mono` path resolution.
- `2f9f271` — `.env`-driven representative examples and Make targets.
- `9bbd3ec` — initialized repository-native project state.
- `cd33679` — hardened Pi RPC lifecycle and made 20 first-party regression tests trackable.
- `829787e` — established the fast handoff protocol and indexed confidence-labeled collaboration MEMORY.
- This handoff adds `DECISIONS.md`, the first `RESUME-NEXT-SESSION.md`, journal backfill, and index updates.

## Decisions and confidence

- ✅ Verified: the representative runtime example passes end to end with the configured DeepSeek judge.
- ✅ Accepted: Pi remains an independent external checkout selected through `DCI_PI_DIR`; `pi-mono` is legacy compatibility only.
- 🟡 Current judgment: Python + hardened RPC is the best present controller architecture. Revalidate using the triggers in `DECISIONS.md`; prefer a thin TypeScript SDK sidecar if those triggers fire.
- 🔴 Superseded: stopping at the first `agent_end` is not valid for the current Pi protocol; completion must wait for `agent_settled` (legacy events without `willRetry` retain a compatibility fallback).

## Next steps

1. Run `git status --short && git log --oneline --decorate -5`; if the GitHub mirror should match the local branch, run `git push origin main`.
2. Decide and document a reproducible Pi revision policy, replacing the moving `DCI_PI_REVISION=main` default without committing the dirty external checkout.
3. When upgrading Pi, run the RPC lifecycle tests and `make runtime-example`; add a regression before adapting to any protocol change.

## Open questions

- Should completed autonomous commits also be pushed automatically, or should push remain an explicit/user-reviewed external action?
- Which upstream/fork Pi commit should become the reproducible default revision?

## Do not go down these paths again

- Do not hard-code `pi-mono`; resolve the checkout through `DCI_PI_DIR` with `pi` preferred and legacy fallback only.
- Do not treat `pi/` as parent-repository source or absorb its dirty state into DCI-Agent-Lite commits.
- Do not break RPC completion at the first `agent_end`.
- Do not rewrite the controller in TypeScript or Rust without one of D-001's measured revalidation triggers.
- Do not use GSD or `.planning/` state in this repository; temporary complex-task planning uses local `planning-with-files`, durable state uses `project-state`.

## Ready-to-paste commands

In a fresh agent session, invoke `$project-state resume` first.

```bash
git status --short
git log --oneline --decorate -5
git rev-list --left-right --count origin/main...HEAD

uv run python -m unittest discover -v
make runtime-example

# Optional only when remote synchronization is intended:
git push origin main
```

Normal configuration remains in repository-root `.env`; never copy API key values into status files or command transcripts. The main runtime deadline is `DCI_RPC_TIMEOUT_SECONDS=3600` (`0` disables it).
