# Reproducible Pi Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DCI-Agent-Lite install and revalidate one immutable Pi commit by default without overwriting an independently modified Pi checkout.

**Architecture:** A root `pi-revision.txt` is the sole default pin. A focused `scripts/setup_pi.sh` implements a safe Git state machine and is called by `setup.sh`; temporary local Git repositories provide integration coverage without touching the real `pi/`. A tracked climb adapter records acceptance coverage and future dependency-policy hypotheses.

**Tech Stack:** Bash 3.2+, Git, Python 3.10+ `unittest`, YAML/JSON/CSV climb state.

## Global Constraints

- Initial default Pi revision: `8479bd84743e8889f728acb21a62794102db0529`.
- Pi remains an external checkout; never commit or mutate the existing dirty `pi/` during verification.
- Preserve `DCI_PI_DIR`, `DCI_PI_REPO_URL`, and `DCI_PI_REVISION` overrides.
- Never run `git reset`, `git clean`, automatic stash, or automatic pull in Pi setup.
- Existing correct dirty checkouts are warned about but left untouched; dirty mismatched checkouts fail before mutation.
- Root `task_plan.md`, `findings.md`, and `progress.md` remain local and uncommitted.

---

### Task 1: Bootstrap the tracked DCI climb adapter

**Files:**
- Create: `docs/status/climb/config.yaml`
- Create: `docs/status/climb/session-target.md`
- Create: `docs/status/climb/hypotheses.yaml`
- Create: `docs/status/climb/runs.csv`
- Create: `docs/status/climb/calibration.json`
- Create: `docs/status/climb/pending-lb.json`
- Create: `docs/status/climb/session-state.json`
- Create: `docs/status/climb/adjudicator-log.md`
- Create: `docs/status/climb/research-tree.md`
- Create: `tools/climb/regen-tree.py`
- Create: `tools/climb/check-target.py`
- Create: `tools/climb/decision-gate.py`
- Create: `tools/climb/consult-ais.sh`
- Create: `tools/climb/hooks/post-commit`
- Modify: `docs/status/INDEX.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: project-state files under `docs/status/` and the climb framework templates.
- Produces: deterministic `python3 tools/climb/regen-tree.py`, a best-effort session target, and ranked hypotheses H-001 through H-003.

- [ ] **Step 1: Create the adapter configuration and initial hypotheses**

```yaml
# docs/status/climb/config.yaml
score_name: setup_policy_acceptance
score_direction: max
subscores: [immutable_resolution, repeat_validation, dirty_checkout_safety, override_compatibility]
push_mode: manual-csv
state_dir: docs/status/climb
artifact_dir: runs/climb
run_tag_marker: dci-climb-
paradigm_field: dependency_policy
```

Create H-001 for exact-pin safe checkout (rank `1.0`), H-002 for explicit upgrade verification (rank `0.7`), and H-003 for Pi RPC protocol compatibility probes (rank `0.5`). Keep all results append-only.

- [ ] **Step 2: Copy and adapt deterministic framework scripts**

Run:

```bash
mkdir -p tools/climb/hooks docs/status/climb
cp ~/.claude/shared-templates/climb/regen-tree.py.tmpl tools/climb/regen-tree.py
cp ~/.claude/shared-templates/climb/check-target.py.tmpl tools/climb/check-target.py
cp ~/.claude/shared-templates/climb/decision-gate.py.tmpl tools/climb/decision-gate.py
cp ~/.claude/shared-templates/climb/consult-ais.sh.tmpl tools/climb/consult-ais.sh
cp ~/.claude/shared-templates/climb/hooks/post-commit.tmpl tools/climb/hooks/post-commit
chmod +x tools/climb/{check-target.py,decision-gate.py,consult-ais.sh,regen-tree.py} tools/climb/hooks/post-commit
```

Adapt the decision-gate disaster threshold from `total < 10` to `total < 1`; the DCI acceptance score ranges from 0 to 4 and has no `f_surv` dimension.

- [ ] **Step 3: Generate and validate the research tree**

Run:

```bash
python3 tools/climb/regen-tree.py
python3 tools/climb/check-target.py
```

Expected: the tree reports three active hypotheses and zero runs; target output reports best-effort mode.

- [ ] **Step 4: Register every new status asset and ignored artifact path**

Add one active `docs/status/climb/` roll-up row to `docs/status/INDEX.md` describing `research-tree.md` as resume-load and the remaining files as storage. Add `/runs/climb/` to `.gitignore`.

- [ ] **Step 5: Commit the adapter**

```bash
git add .gitignore docs/status tools/climb
git commit -m "chore: initialize DCI climb adapter"
```

Expected: the commit includes the pending design JOURNAL entry and no temporary planning files.

---

### Task 2: Specify the safe checkout state machine with failing tests

**Files:**
- Create: `tests/test_setup_pi.py`
- Test: `tests/test_setup_pi.py`

**Interfaces:**
- Consumes: executable `scripts/setup_pi.sh`; environment variables `DCI_PI_DIR`, `DCI_PI_REPO_URL`, and optional `DCI_PI_REVISION`.
- Produces: six subprocess integration tests using local temporary Git repositories.

- [ ] **Step 1: Add local Git repository fixtures**

Implement a `PiSetupTests(unittest.TestCase)` helper that creates a source repository with two commits. Each commit tracks `packages/coding-agent/dist/cli.js`, so setup tests never run npm. Copy `scripts/setup_pi.sh` and `pi-revision.txt` into a temporary project root for each invocation.

```python
def git(self, *args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()

def run_setup(self, *, revision: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"DCI_PI_DIR": str(self.pi_dir), "DCI_PI_REPO_URL": str(self.source)})
    if revision is not None:
        env["DCI_PI_REVISION"] = revision
    else:
        env.pop("DCI_PI_REVISION", None)
    return subprocess.run(
        ["bash", str(self.project / "scripts/setup_pi.sh")],
        cwd=self.project, env=env, text=True, capture_output=True
    )

def clone_at(self, revision: str) -> None:
    subprocess.run(["git", "clone", str(self.source), str(self.pi_dir)], check=True)
    subprocess.run(
        ["git", "checkout", "--detach", revision], cwd=self.pi_dir, check=True
    )
```

- [ ] **Step 2: Add six acceptance tests**

Test these exact outcomes:

```python
def test_new_checkout_uses_locked_commit(self):
    result = self.run_setup()
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.pi_dir), self.commit_a)

def test_built_checkout_at_pin_is_unchanged(self):
    self.clone_at(self.commit_a)
    before = self.git("status", "--porcelain", cwd=self.pi_dir)
    result = self.run_setup()
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(self.git("status", "--porcelain", cwd=self.pi_dir), before)

def test_clean_mismatched_checkout_moves_to_pin(self):
    self.clone_at(self.commit_b)
    result = self.run_setup()
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.pi_dir), self.commit_a)

def test_dirty_mismatched_checkout_fails_without_mutation(self):
    self.clone_at(self.commit_b)
    marker = self.pi_dir / "local-change.txt"
    marker.write_text("keep me\n")
    before_head = self.git("rev-parse", "HEAD", cwd=self.pi_dir)
    result = self.run_setup()
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("dirty", result.stderr.lower())
    self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.pi_dir), before_head)
    self.assertEqual(marker.read_text(), "keep me\n")

def test_revision_override_selects_exact_commit(self):
    result = self.run_setup(revision=self.commit_b)
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.pi_dir), self.commit_b)

def test_malformed_default_lock_fails_before_clone(self):
    (self.project / "pi-revision.txt").write_text("main\n")
    result = self.run_setup()
    self.assertEqual(result.returncode, 2)
    self.assertIn("40-character", result.stderr)
    self.assertFalse(self.pi_dir.exists())
```

The dirty mismatch test records `HEAD` and the modified file contents before setup, expects a nonzero result containing `dirty`, and asserts both values are identical afterward.

- [ ] **Step 3: Run the tests and verify the red phase**

Run:

```bash
uv run python -m unittest tests.test_setup_pi -v
```

Expected: tests fail because `scripts/setup_pi.sh` and `pi-revision.txt` do not exist.

- [ ] **Step 4: Commit the tests**

```bash
git add tests/test_setup_pi.py
git commit -m "test: specify reproducible Pi checkout policy"
```

---

### Task 3: Implement immutable and non-destructive Pi setup

**Files:**
- Create: `pi-revision.txt`
- Create: `scripts/setup_pi.sh`
- Modify: `setup.sh:69-92`
- Test: `tests/test_setup_pi.py`

**Interfaces:**
- Consumes: root lock file and existing Pi environment variables.
- Produces: an executable setup command that exits nonzero before mutating a dirty mismatched checkout.

- [ ] **Step 1: Add the canonical lock**

```text
8479bd84743e8889f728acb21a62794102db0529
```

- [ ] **Step 2: Implement input and lock validation**

Start `scripts/setup_pi.sh` with `set -euo pipefail`, derive `PROJECT_ROOT` from the script location, and use:

```bash
PI_DIR="${DCI_PI_DIR:-$PROJECT_ROOT/pi}"
PI_REPO_URL="${DCI_PI_REPO_URL:-https://github.com/earendil-works/pi.git}"
PI_LOCK_FILE="$PROJECT_ROOT/pi-revision.txt"
PI_REVISION="${DCI_PI_REVISION:-}"
if [ -z "$PI_REVISION" ]; then
    PI_REVISION="$(tr -d '[:space:]' < "$PI_LOCK_FILE")"
    [[ "$PI_REVISION" =~ ^[0-9a-fA-F]{40}$ ]] || {
        echo "ERROR: $PI_LOCK_FILE must contain one full 40-character Git commit." >&2
        exit 2
    }
fi
```

- [ ] **Step 3: Implement clone, resolution, and safe checkout**

Use `git clone --no-checkout`, resolve `"$PI_REVISION^{commit}"` locally, and fall back once to `git fetch --no-tags origin "$PI_REVISION"` plus `FETCH_HEAD^{commit}`. For an existing mismatch:

```bash
if [ -n "$(git -C "$PI_DIR" status --porcelain)" ]; then
    echo "ERROR: Pi checkout is dirty at $current_commit; refusing to switch to $desired_commit." >&2
    exit 3
fi
git -C "$PI_DIR" checkout --detach "$desired_commit"
source_changed=1
```

For a newly cloned no-checkout worktree, check out the desired commit directly without treating the intentionally empty worktree as user dirt.

- [ ] **Step 4: Preserve build behavior while rebuilding changed sources**

```bash
PI_CLI="$PI_DIR/packages/coding-agent/dist/cli.js"
if [ "$source_changed" -eq 1 ] || [ ! -f "$PI_CLI" ]; then
    (cd "$PI_DIR" && npm install)
    (cd "$PI_DIR/packages/tui" && npm run build)
    (cd "$PI_DIR/packages/ai" && npm run build)
    (cd "$PI_DIR/packages/agent" && npm run build)
    (cd "$PI_DIR/packages/coding-agent" && npm run build)
else
    echo "==> Pi CLI already built at verified commit $desired_commit; skipping build."
fi
```

Warn—but succeed—when `HEAD` equals the desired commit and status is dirty.

- [ ] **Step 5: Delegate from top-level setup**

Replace the inline Pi block in `setup.sh` with:

```bash
echo "==> Ensuring pinned Pi checkout..."
bash scripts/setup_pi.sh
```

- [ ] **Step 6: Run the focused tests and shell checks**

Run:

```bash
uv run python -m unittest tests.test_setup_pi -v
bash -n setup.sh scripts/setup_pi.sh
```

Expected: six tests pass and both scripts pass syntax validation.

- [ ] **Step 7: Commit implementation**

```bash
git add pi-revision.txt scripts/setup_pi.sh setup.sh
git commit -m "fix: pin and verify external Pi revision"
```

---

### Task 4: Align configuration and user-facing setup documentation

**Files:**
- Modify: `.env.template:4-10`
- Modify: `README.md:95-106`
- Modify: `assets/docs/setup.md:36-60`
- Modify: `assets/docs/running.md:8-14`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Test: `tests/test_setup_pi.py`

**Interfaces:**
- Consumes: `pi-revision.txt` and setup behavior from Task 3.
- Produces: one documented upgrade path: change the lock in a reviewed commit or set an exact `DCI_PI_REVISION` override.

- [ ] **Step 1: Update configuration guidance**

Replace `DCI_PI_REVISION=main` in `.env.template` with:

```dotenv
# By default setup reads the verified full commit from ./pi-revision.txt.
# Override only for a deliberate fork/revision test; prefer a full commit SHA.
# DCI_PI_REVISION=0123456789abcdef0123456789abcdef01234567
```

- [ ] **Step 2: Update manual setup commands**

README and `assets/docs/setup.md` must use:

```bash
git clone --no-checkout https://github.com/earendil-works/pi.git pi
git -C pi checkout --detach "$(cat pi-revision.txt)"
```

Document safe failure on dirty mismatches and clarify that changing `pi-revision.txt` is the normal reviewed upgrade mechanism.

- [ ] **Step 3: Record the accepted architecture decision**

Append D-003 to `docs/status/DECISIONS.md`: one tracked lock file is the canonical default; exact overrides are deliberate; dirty external checkouts are never switched automatically. Remove the resolved version-pinning open problem from `CURRENT-STATE.md` and retain protocol compatibility as an open theme.

- [ ] **Step 4: Add a documentation consistency assertion**

In `tests/test_setup_pi.py`, assert `.env.template` does not contain `DCI_PI_REVISION=main`, references `pi-revision.txt`, and the lock is a full SHA.

- [ ] **Step 5: Verify and commit documentation**

```bash
uv run python -m unittest tests.test_setup_pi -v
git diff --check
git add .env.template README.md assets/docs/setup.md assets/docs/running.md docs/status tests/test_setup_pi.py
git commit -m "docs: document locked Pi dependency upgrades"
```

---

### Task 5: Complete H-001, verify the repository, and advance climb

**Files:**
- Modify: `docs/status/climb/hypotheses.yaml`
- Modify: `docs/status/climb/runs.csv`
- Modify: `docs/status/climb/session-state.json`
- Regenerate: `docs/status/climb/research-tree.md`
- Modify: `docs/status/JOURNAL.md`
- Create: `tools/climb/train.sh`
- Create: `tools/climb/eval-local.sh`
- Create: `tools/climb/push.sh`
- Create: `tools/climb/apply-lb-score.sh`
- Create: `tools/climb/cycle.sh`

**Interfaces:**
- Consumes: focused and full verification commands.
- Produces: one append-only H-001 run scored from 0 to 4, a deterministic research tree, and `session-state.next_action` pointing at H-002.

- [ ] **Step 1: Implement the local cycle adapter**

`train.sh H-001` creates `runs/climb/${run_id}-h001/manifest.json` and runs the focused setup tests. `eval-local.sh "$RUN_DIR"` reruns the focused tests and emits JSON:

```json
{
  "total": 4,
  "per_task": {
    "immutable_resolution": 1,
    "repeat_validation": 1,
    "dirty_checkout_safety": 1,
    "override_compatibility": 1
  }
}
```

Each failed dimension is `0`; total is their sum. `push.sh` stores this JSON as a local verification artifact because DCI has no external LB for dependency setup.

- [ ] **Step 2: Ensure deterministic state synchronization**

`cycle.sh` must append exactly one `runs.csv` row, append an H-001 result, set H-001 to `confirmed` only when total is `4`, set `session-state.next_hypothesis` to H-002, run `regen-tree.py`, append one JOURNAL line, and call `check-target.py` on every exit branch.

- [ ] **Step 3: Run complete verification**

Record real `pi/` HEAD and status before and after, then run:

```bash
uv run python -m unittest discover -v
uv run python -m compileall -q tests
uv run ruff check tests/test_setup_pi.py
bash -n setup.sh scripts/setup_pi.sh tools/climb/*.sh tools/climb/hooks/post-commit
git diff --check
```

Expected: all tests and static checks pass; the real `pi/` HEAD/status snapshots are identical.

- [ ] **Step 4: Run H-001 and regenerate state**

```bash
bash tools/climb/cycle.sh H-001
python3 tools/climb/regen-tree.py
python3 tools/climb/check-target.py
```

Expected: H-001 is confirmed at `4/4`, best-effort target remains active, and H-002 is the next ranked hypothesis.

- [ ] **Step 5: Install the deterministic post-commit hook and commit**

```bash
cp tools/climb/hooks/post-commit .git/hooks/post-commit
chmod +x .git/hooks/post-commit
git add docs/status tools/climb
git commit -m "test: confirm pinned Pi setup policy"
```

- [ ] **Step 6: Continue instead of pausing**

Journal the final commit, refresh a live project-state checkpoint if the recovery threshold is met, and begin H-002 (upgrade ergonomics) immediately unless a climb hard-pause condition applies.
