# Live Session Checkpoint

> Updated: 2026-07-12 07:42 +0800. **Session remains active — not a final handoff.**

## TL;DR

- DCI runtime code is unchanged. The project now has an event-driven `project-state` policy: durable facts go to `JOURNAL` immediately, while `RESUME` is refreshed at recovery thresholds rather than only at final handoff.
- `project-state` now has one canonical source under `~/.agents/skills/`, with Codex and Claude Code skill/command entry points linked to it.
- Codex now reuses the existing lightweight-memory commit, long-task, and milestone reminders; hooks only inject context and never write state or create commits.
- A missed final handoff now recovers into `# Recovered Session Checkpoint`, never an implicit final handoff; SIGINT follows the same checkpoint rule.

## Current boundary

- Branch: `main`; tracked working tree is clean. `AGENTS.md` / `CLAUDE.md` are intentionally local and ignored; they now contain the concise checkpoint policy and long-task patterns.
- Remote roles remain `origin=https://github.com/uukuguy/DCI-Agent-Lite.git` and `upstream=https://github.com/DCI-Agent/DCI-Agent-Lite.git`.
- No DCI/Pi runtime, batch evaluator, watcher, or delegated task remains active.
- The external `pi/` checkout remains user-owned and outside parent-repository commits.
- The canonical skill is `~/.agents/skills/project-state/SKILL.md`; Codex and Claude entry points resolve to that same file.
- GSD hooks now require both `.planning/PROJECT.md` and `.planning/ROADMAP.md`, so this repository's empty `.planning/debug/` does not trigger GSD state writes.

## Verified in this live session

- `uv run python -m unittest discover -v` passed: 20 tests, 0 failures.
- The last live runtime acceptance remains `make runtime-example` → `Adaku`, with the configured DeepSeek judge reporting `is_correct: true`.
- A nested-CWD Codex-shaped hook request resolves the Git root and emits the commit and long-task reminder context correctly.
- The declared DCI batch shell/Python commands trigger the long-task hook; `make runtime-example` does not.
- `bash -n` passed for the changed shared hook script; Codex `config.toml` parsed with `tomllib`; `project-state` passed `quick_validate.py`.

## Next action

1. In a fresh Codex session, review and trust the new user-level hooks with `/hooks` if Codex asks; then normal work continues with `project-state resume`.
2. Continue the existing DCI priority: decide and document a reproducible Pi revision policy instead of leaving `DCI_PI_REVISION=main` moving.
3. At the actual session boundary, run `handoff` for the full closeout; do not treat this checkpoint as one.

## Guardrails

- Do not auto-write `JOURNAL` from a Git hook or auto-commit a state update: that leaves a dirty tree and can create a commit-refback loop.
- Do not use a `Stop` hook to force automatic handoff or continuation; it can loop on ordinary turns.
- Keep `CURRENT-STATE.md` structural and `DECISIONS.md` rationale-only; live activity belongs here and in `JOURNAL.md`.

## Ready commands

```bash
project-state resume

git status --short
uv run python -m unittest discover -v

# Only after deciding the remote should match local main:
git push origin main
```
