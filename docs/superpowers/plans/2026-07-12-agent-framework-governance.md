# Agent Framework Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Steps use checkbox syntax.

**Goal:** Make the agent-application framework recoverable and mechanically block unscoped manager or climb work.

**Architecture:** `docs/architecture/agent-framework.md` is the north star; `docs/status/WORKLIST.md` is the canonical package ledger. `tools/project_scope_check.py` validates its relationship to `CURRENT-STATE`, `RESUME`, and climb state before dispatch. The global manager skill and local instructions require that validation.

**Tech Stack:** Markdown state files, Python standard library, PyYAML, `unittest`, Bash, and the existing skill validator.

## Global Constraints

- Preserve the external `pi/` checkout and prior Pi/Judge commits.
- Do not add a second state system or GSD artifacts.
- Keep `JOURNAL.md` append-only and register every new status file in `INDEX.md`.
- A climb cycle must name a work package; H-001 through H-019 must not be silently reused.
- This plan implements AF-000 only. AF-010 and later remain pending.

---

### Task 1: Establish the durable control plane

**Files:**
- Create: `docs/architecture/agent-framework.md`
- Create: `docs/status/WORKLIST.md`
- Modify: `docs/status/{INDEX,CURRENT-STATE,DECISIONS,RESUME-NEXT-SESSION}.md`
- Modify: `docs/status/climb/{session-state.json,session-target.md}`

**Interfaces:** Produces AF-000 and the markers consumed by the scope auditor.

- [ ] **Step 1: Create the north-star architecture**

Write `docs/architecture/agent-framework.md` with this exact product boundary:

```markdown
# Agent Application Framework

## Product objective

Build a multi-runtime, multi-language agent-application framework. DCI is a reference capability and benchmark, not the product boundary.

## Layers

1. Versioned Agent Runtime Protocol: run/session lifecycle, capability manifest, normalized events, artifacts, cancellation and deadlines.
2. Runtime adapters: Pi first, then one independent runtime, Pydantic AI, LangGraph, Claude Code and Hermes-agent as their supported contracts permit.
3. Capability packages: DCI research, tool/policy, workflow, memory/observability and evaluation.
4. Language hosts: Python for research/evaluation/orchestration, TypeScript for Node/service integration, Rust for controlled execution infrastructure.

## Non-goals

- Do not claim identical native semantics across runtimes.
- Do not rewrite Pi integration before protocol conformance requires it.
- Do not make Pi/Judge maintenance the roadmap without a parent work package.
```

- [ ] **Step 2: Create one canonical worklist**

Create `docs/status/WORKLIST.md` using package headings and fixed `- Field: value` lines. AF-000 is the only active record:

```markdown
## AF-000 — Framework control plane

- Status: in_progress
- Parent objective: Agent Application Framework
- Scope: north star, worklist, scope audit, manager repair, climb parent enforcement, and state migration only.
- Dependencies: none
- Acceptance: resume recovers AF-000; audit passes valid state and rejects invalid package/resume/climb relationships; manager and climb dispatch invoke it.
- Design: `docs/superpowers/specs/2026-07-12-agent-framework-governance-design.md`
- Plan: `docs/superpowers/plans/2026-07-12-agent-framework-governance.md`
```

Add AF-010 through AF-060 as `Status: pending` with the outcomes and dependencies in the approved governance design. The file also states: `No action may begin without exactly one in_progress package or explicit user authorization recorded in its package.`

- [ ] **Step 3: Migrate state and retire the old climb continuation**

Update `CURRENT-STATE.md` with these exact markers:

```markdown
- Framework north star: `docs/architecture/agent-framework.md`
- Active work package: `AF-000` — Framework control plane.
```

Keep Pi as the reference implementation but classify Pi/Judge reliability as completed/deferred maintenance. Rewrite the live checkpoint to contain `Active work package: AF-000`. Change the legacy climb `next_action` to say that H-001 through H-019 are retired maintenance and a new cycle needs a parented framework hypothesis.

- [ ] **Step 4: Record the decisions and indexes**

Append D-017 (protocol first, Pi reference adapter) and D-018 (all autonomous work needs an active package parent) to `DECISIONS.md`. Register `WORKLIST.md` as active and the architecture document as an external anchor in `INDEX.md`. Append one factual JOURNAL entry for the committed migration.

- [ ] **Step 5: Verify and commit the control plane**

Run:

```bash
rg -n "Framework north star|Active work package: AF-000|AF-000|D-017|D-018" docs/architecture docs/status
git diff --check
git add docs/architecture docs/status
git commit -m "docs: establish framework control plane"
```

Expected: all markers are present and the diff has no whitespace errors.

### Task 2: Add a test-first project scope auditor

**Files:**
- Create: `tests/test_project_scope_check.py`
- Create: `tools/project_scope_check.py`

**Interfaces:** Returns exit `0` and JSON `{ "ok": true, "active_package": "AF-000", "errors": [] }` for valid state; returns exit `1` and all errors otherwise.

- [ ] **Step 1: Write failing behavior tests**

Use isolated temporary repository fixtures. Include these public tests plus missing-marker, multiple-active, missing-required-field, and unparented-active-climb cases:

```python
def test_valid_repository_state_reports_the_single_active_package(self) -> None:
    result = self.run_check()
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(json.loads(result.stdout)["active_package"], "AF-000")

def test_resume_package_mismatch_is_rejected(self) -> None:
    self.write("docs/status/RESUME-NEXT-SESSION.md", "Active work package: AF-999\n")
    result = self.run_check()
    self.assertEqual(result.returncode, 1)
    self.assertIn("resume names AF-999", json.loads(result.stdout)["errors"])
```

- [ ] **Step 2: Prove RED**

```bash
uv run python -m unittest tests.test_project_scope_check -v
```

Expected: the command fails because `tools/project_scope_check.py` does not exist.

- [ ] **Step 3: Implement the minimal auditor**

Implement `parse_worklist`, `validate_required_fields`, `validate_markers`, and `validate_active_climb` in `tools/project_scope_check.py`. Parse `## ID — title` headings and `- Field: value` lines. Require exactly one `Status: in_progress`, its Scope/Dependencies/Acceptance/Design/Plan fields, the north-star marker in CURRENT, and the active marker in RESUME. For climb phases other than `hard-pause` or `completed`, require `work_package_id` to match the active package; when a hypothesis argument is supplied, require its `work_package_id` to match too. The command entry point must emit the result using this exact control flow:

```python
payload = {
    "ok": not errors,
    "active_package": active_id,
    "errors": errors,
}
print(json.dumps(payload, sort_keys=True))
return 0 if payload["ok"] else 1
```

- [ ] **Step 4: Prove GREEN and commit**

```bash
uv run python -m unittest tests.test_project_scope_check -v
python3 tools/project_scope_check.py
git add tests/test_project_scope_check.py tools/project_scope_check.py
git commit -m "feat: audit framework work-package scope"
```

Expected: tests pass and the checker reports AF-000.

### Task 3: Gate climb dispatch on parent scope

**Files:**
- Modify: `tests/test_climb_tools.py`
- Modify: `tools/climb/cycle.sh`
- Modify: `tools/project_scope_check.py`

**Interfaces:** `cycle.sh HYPOTHESIS_ID` runs the audit before creating a run directory or invoking `train.sh`.

- [ ] **Step 1: Write the failing dispatch test**

```python
def test_cycle_rejects_a_legacy_unparented_hypothesis_before_training(self) -> None:
    result = subprocess.run(
        ["bash", "tools/climb/cycle.sh", "H-001"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("unparented climb hypothesis H-001", result.stdout + result.stderr)
```

- [ ] **Step 2: Prove RED**

```bash
uv run python -m unittest tests.test_climb_tools.ClimbToolTests.test_cycle_rejects_a_legacy_unparented_hypothesis_before_training -v
```

Expected: the old cycle reaches the training adapter instead of failing at the scope boundary.

- [ ] **Step 3: Insert the pre-dispatch guard**

After `HYPOTHESIS_ID="$1"` and before the cycle number or `train.sh`, add:

```bash
python3 "$ROOT/tools/project_scope_check.py" --climb-hypothesis "$HYPOTHESIS_ID"
```

The matching auditor branch reports `unparented climb hypothesis <ID>` when the hypothesis is absent or lacks a matching parent package.

- [ ] **Step 4: Prove GREEN and commit**

```bash
uv run python -m unittest tests.test_project_scope_check tests.test_climb_tools.ClimbToolTests.test_cycle_rejects_a_legacy_unparented_hypothesis_before_training -v
bash -n tools/climb/cycle.sh
git add tests/test_climb_tools.py tools/climb/cycle.sh tools/project_scope_check.py
git commit -m "feat: gate climb cycles on framework scope"
```

### Task 4: Repair manager instructions and local operating rules

**Files:**
- Modify: `AGENTS.md`
- Modify: `/Users/sujiangwen/.agents/skills/ai-project-manager/SKILL.md`
- Modify: `~/.claude/projects/-Users-sujiangwen-sandbox-agentic-2026-DCI-Agent-Lite/memory/MEMORY.md`
- Create: `~/.claude/projects/-Users-sujiangwen-sandbox-agentic-2026-DCI-Agent-Lite/memory/feedback_framework_scope_control.md`

**Interfaces:** Manager preflight runs the scope auditor and blocks unscoped dispatch; AGENTS requires it before autonomous work.

- [ ] **Step 1: Amend the global manager skill**

Add a mandatory `Scope preflight` section requiring the manager to read the north star and worklist, run the scope audit, require exactly one active package with scope/dependencies/acceptance/design/plan links, and stop to repair state rather than substitute nearby maintenance work. It must treat climb, reliability, and experiments as child work; rerun the audit before package closure; and turn every detected governance failure into a verified repair item.

- [ ] **Step 2: Amend AGENTS and collaboration memory**

Add `Framework scope control` to `AGENTS.md`:

```markdown
- `docs/architecture/agent-framework.md` is the north star; `docs/status/WORKLIST.md` is the sole active package ledger.
- Before autonomous work, manager dispatch, or a climb cycle, run `python3 tools/project_scope_check.py`; do not implement when it fails.
- Every task names one active work-package ID. Pi/Judge maintenance and climb hypotheses require a parent package and may not redefine the roadmap.
```

Create a concise verified memory entry recording the user's requirement that framework scope must recover from repository files and autonomous work must not drift to local detail; link it from `MEMORY.md` without exceeding 15 active entries.

- [ ] **Step 3: Validate and commit repository-owned governance**

```bash
python3 /Users/sujiangwen/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/sujiangwen/.agents/skills/ai-project-manager
rg -n "Scope preflight|project_scope_check|WORKLIST|north star" AGENTS.md /Users/sujiangwen/.agents/skills/ai-project-manager/SKILL.md
git add AGENTS.md docs/status
git commit -m "docs: require framework scope gates"
```

The global skill and collaboration-memory files are outside the repository and must be reported, not added to this Git commit.

### Task 5: Verify and advance AF-000

**Files:**
- Modify: `docs/status/{JOURNAL,RESUME-NEXT-SESSION,WORKLIST}.md`

**Interfaces:** Consumes Tasks 1–4 verification evidence and produces the next package state.

- [ ] **Step 1: Run full verification**

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q src tools/project_scope_check.py
uv run ruff check tools/project_scope_check.py tests/test_project_scope_check.py
bash -n tools/climb/cycle.sh
git diff --check
python3 tools/project_scope_check.py
```

- [ ] **Step 2: Prove the prior drift is blocked**

```bash
python3 tools/project_scope_check.py --climb-hypothesis H-001
```

Expected: exit `1` with `unparented climb hypothesis H-001`.

- [ ] **Step 3: Record the verified transition**

Append evidence to JOURNAL. If every AF-000 acceptance criterion passes, set AF-000 to `completed`, AF-010 to `in_progress`, and set RESUME to `Active work package: AF-010` with its first protocol-contract action. Otherwise keep AF-000 active and name the failed check.

- [ ] **Step 4: Commit the package boundary**

```bash
git add docs/status
git commit -m "docs: advance framework worklist after governance verification"
```

Only after AF-010 receives its own design and plan may a new hypothesis with `work_package_id: AF-010` start. Never reuse H-001 through H-019.
