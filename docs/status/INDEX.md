# docs/status INDEX

Catalog of every file in `docs/status/`. Categorized so Claude knows which to read, which to skip, and which are decision history kept for traceability only.

**Status legend**:
- 🟢 **active** — read on resume; reflects current truth
- 🟡 **decision-history** — historical record of a decision/finding; don't act on the recommendations inside (they may be reversed by later sessions)
- 🔴 **superseded** — replaced by a newer file or by a memory entry; safe to ignore on resume
- ⚫ **scratch** — one-off experiment scratch / data dump; not meant to be read again

When adding a new file to `docs/status/`, **also add its row here** — otherwise it becomes orphan exhaust.

## Active (read these on every resume)

| File | Status | Purpose |
|---|---|---|
| `JOURNAL.md` | 🟢 active | Append-only event log. `project-state journal "..."` 追加。 |
| `RESUME-NEXT-SESSION.md` | 🟢 active | Session handoff baton. |
| `CURRENT-STATE.md` | 🟢 active | Structural snapshot. |
| `DECISIONS.md` | 🟢 active | Current architecture decisions with confidence labels and revalidation triggers. |
| `WORKLIST.md` | 🟢 active | Sole multi-package ledger: scope, dependencies, acceptance, status, and plan links. |
| `climb/` | 🟢 active | `research-tree.md` is the climb resume summary; sibling YAML/JSON/CSV files are storage-layer state. |
| `INDEX.md` (this file) | 🟢 active | Discovery hub. |

## Decision history (kept for traceability — verdicts may be outdated)

| File | Status | What it recorded | Outcome / supersession |
|---|---|---|---|
| (empty initially) | | | |

## Archived

| Bucket | Files | Notes |
|---|---|---|
| (empty initially) | | |

> When adding new archive buckets, append a row here pointing to `_archive/<label>/`. Do not list individual files.

## External anchors

| Path | Purpose |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | Local cross-agent operating rules, including the fast `handoff` protocol. |
| `docs/architecture/agent-framework.md` | Framework north star, runtime strategy, language roles, and non-goals. |
| `~/.claude/projects/-Users-sujiangwen-sandbox-agentic-2026-DCI-Agent-Lite/memory/MEMORY.md` | Collaboration-memory index; linked detail files carry confidence and supersession metadata. |

## Don't add new files unless they fit one of the categories above

If you want to record a **finding/lesson** that's a long-lived project fact, write it to `CLAUDE.md` under structural facts. If it's a collaboration lesson, write it to `MEMORY.md`. If it's a complete audit or experiment report, write `docs/status/<topic>.md` here and add its INDEX row simultaneously.
