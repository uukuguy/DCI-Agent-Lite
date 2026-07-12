# Reproducible Pi Revision Design

## Objective

Make a fresh or repeated DCI-Agent-Lite setup resolve the same verified Pi source revision by default, while preserving explicit downstream overrides and never overwriting changes in the independent `pi/` repository.

## Constraints

- Pi remains an external Git checkout; DCI-Agent-Lite does not vendor it or commit its files.
- The default must be immutable and reviewable in the parent repository.
- Existing `DCI_PI_DIR`, `DCI_PI_REPO_URL`, and `DCI_PI_REVISION` overrides remain supported.
- Setup must verify the source revision even when a built Pi CLI already exists.
- A dirty checkout is user-owned state. Setup may inspect it but must not switch revisions or discard changes.
- Normal setup must work without network access when the requested commit already exists locally.

## Approaches Considered

### 1. Duplicate the commit in `setup.sh` and `.env.template`

This is the smallest patch, but it creates two authoritative values that can drift. Tests could catch divergence, yet the duplicated pin remains unnecessary maintenance risk.

### 2. Add a single tracked revision lock file

Store the verified full commit in repository-root `pi-revision.txt`. `setup.sh` reads it when `DCI_PI_REVISION` is unset; `.env.template` documents the override without restating a second authoritative value. Manual setup instructions check out `$(cat pi-revision.txt)`.

This is the selected approach. It provides one reviewable source of truth, keeps overrides backward compatible, and makes upgrades an explicit one-line dependency change accompanied by verification.

### 3. Convert Pi to a submodule or vendor it

A submodule supplies an immutable pointer, but it changes clone/setup semantics and makes the parent repository manage the external checkout. Vendoring is heavier still. Both conflict with the accepted boundary that `pi/` remains independent.

## Components

### `pi-revision.txt`

Contains exactly one full 40-character commit SHA and a trailing newline. The initial pin is `8479bd84743e8889f728acb21a62794102db0529`, the fork commit used by the verified runtime acceptance run.

### `scripts/setup_pi.sh`

Owns external Pi checkout verification and build orchestration. The top-level `setup.sh` delegates to it, keeping dependency lifecycle logic independently testable.

Inputs are existing environment variables:

- `DCI_PI_DIR`, default `pi`
- `DCI_PI_REPO_URL`, default `https://github.com/earendil-works/pi.git`
- `DCI_PI_REVISION`, default contents of `pi-revision.txt`

The script resolves the desired revision to a commit, cloning or fetching only when necessary. It records whether source revision changed so compiled output is rebuilt after a safe checkout.

### Documentation and examples

`.env.template` explains that the lock file is the default and shows `DCI_PI_REVISION` as an optional exact-commit override. README and setup documentation use the lock file in manual commands and describe the safe mismatch behavior.

## Checkout State Machine

1. Validate that the lock file contains a full commit when no override is supplied.
2. If `DCI_PI_DIR` does not exist, clone without checking out a moving branch, resolve the requested revision, and check it out detached.
3. If the directory exists but is not a Git worktree, fail with a precise error.
4. Resolve the requested revision locally. If absent, fetch that revision from the configured origin and resolve the fetched commit.
5. If `HEAD` equals the requested commit, leave the checkout—including any user modifications—untouched.
6. If `HEAD` differs and the checkout is dirty, fail before mutation and print the current/requested commits plus override guidance.
7. If `HEAD` differs and the checkout is clean, check out the requested commit detached and mark the source changed.
8. Build when the coding-agent CLI is absent or the source changed; otherwise report the verified commit and skip the build.

The setup script never runs `reset`, `clean`, stash, or an automatic pull.

## Failure Handling

- Missing/malformed default lock: fail before cloning.
- Unresolvable revision after one targeted fetch: fail and identify the URL and revision.
- Dirty mismatched checkout: fail safely without changing files or refs.
- Build failure: propagate the original nonzero exit status.
- Existing correct but dirty checkout: warn that local changes make the runtime customized, but do not fail or mutate it.

## Verification

Shell integration tests use temporary local Git repositories and never touch the real `pi/` checkout. Acceptance cases are:

1. A new checkout lands on the pinned commit.
2. An already-built checkout at the pin is not rebuilt or changed.
3. A clean checkout at another commit moves to the pin.
4. A dirty checkout at another commit fails and remains unchanged.
5. `DCI_PI_REVISION` selects an alternate exact commit.
6. A malformed default lock fails clearly.

Repository verification also includes `bash -n`, focused unit tests, Python compilation/Ruff for any touched Python test helper, `git diff --check`, and the existing full unit suite. The real `pi/` worktree is checked before and after to prove it was not modified.

## Climb Evaluation Contract

This dependency-policy cycle uses deterministic acceptance coverage as its local ground truth. The score is the fraction of four policy dimensions passing: immutable resolution, repeat-run validation, dirty-checkout safety, and override compatibility. H-001 is confirmed only at `4/4` with the real external checkout unchanged. Subsequent hypotheses may address upgrade ergonomics or protocol compatibility, but cannot weaken these invariants.
