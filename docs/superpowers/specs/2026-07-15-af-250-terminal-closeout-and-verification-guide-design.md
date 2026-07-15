# AF-250 Terminal Closeout and Verification Guide Design

## Objective

Finish the Asterion DCI migration as a recoverable terminal milestone rather
than leaving AF-250 active after implementation and acceptance have passed.
Publish one authoritative operator guide that lets a fresh maintainer verify
the original DCI baseline, the independent Asterion DCI product, the installed
Pi-default application, batch/evaluation/export behavior, and the checked-in
acceptance evidence without relying on worklist claims or chat history.

## Scope

This closeout has two deliverables:

1. `docs/verification/asterion-dci-validation-guide.md`, linked from the
   README, with runnable verification tiers and explicit success criteria.
2. An explicit terminal lifecycle state in repository governance so AF-250 can
   be `completed` with no artificial successor or lingering `in_progress`
   package.

It does not add DCI behavior, change runtime protocols, run a full dataset,
modify the external Pi checkout, or broaden provider support.

## Verification Guide Structure

The guide is organized by cost and authority:

- **Tier 0 — prerequisites and safety:** repository/worktree selection, shared
  root `.env`, external `DCI_PI_DIR`, corpus authority, private output roots,
  credential and body-handling rules.
- **Tier 1 — provider-free smoke checks:** CLI help/listing, source/Asterion
  import independence, product-matrix validation, focused acceptance tests.
- **Tier 2 — original and migrated examples:** the two original
  `scripts/examples/dci_*.sh` commands and their two Asterion counterparts,
  including expected state, events, final, and optional Judge artifacts.
- **Tier 3 — complete Asterion operator surface:** installed application,
  `run`, `resume`, `terminal`, `system-prompt`, `evaluate`, `benchmark`,
  exports, installed profiles, and the twelve deliberate batch launchers.
- **Tier 4 — product acceptance:** public 7/7 manifest validation and optional
  private-root rehash/semantic/credential/reuse verification.
- **Tier 5 — repository closure:** Python, TypeScript, Rust, compile, Ruff,
  shell, scope, and diff gates.

Every section states whether it is provider-free, bounded provider-backed, or
full-dataset; provider-backed commands are never presented as automatic. The
guide distinguishes structural verification from performance evaluation and
gives body-free pass/fail criteria instead of reproducing private outputs.

## Terminal Governance Contract

`docs/status/WORKLIST.md` gains a repository-level lifecycle marker with two
valid values:

- `active`: exactly one package must be `in_progress`.
- `complete`: zero packages may be `in_progress`, and all governed packages
  must be `completed`.

`tools/project_scope_check.py` continues to fail closed. It accepts zero active
packages only when the worklist explicitly declares the complete lifecycle;
it rejects an unknown marker, a complete lifecycle with an active/incomplete
package, or an active lifecycle without exactly one active package.

At terminal closure:

- AF-250 becomes `completed`.
- CURRENT-STATE names no active package and records the completed migration.
- RESUME uses `Active work package: none` and contains verification/maintenance
  commands rather than an implementation next action.
- the Climb session phase becomes `completed` with no pending or in-flight
  hypothesis.
- the scope checker reports a successful terminal result with
  `active_package: null` and `lifecycle: complete`.

This is a governance closeout only. New work must explicitly reopen the
lifecycle and activate a properly specified successor package before dispatch.

## Error Handling and Privacy

- The guide never embeds credential values, provider bodies, private corpus
  paths, or private acceptance-root paths.
- Commands use environment-variable placeholders for caller-owned private
  roots.
- Missing corpora or Pi paths are documented as prerequisite failures, not
  product-parity failures.
- Full-dataset launchers remain deliberate and are labeled with their cost and
  external-request implications.
- Terminal scope validation fails rather than inferring completion from the
  absence of an active package.

## Testing and Acceptance

The closeout is complete only when:

1. the validation guide contains every tier, command class, expected artifact,
   and success criterion described above;
2. documentation tests prove its canonical commands and independence language;
3. scope-check tests cover valid active, valid terminal, missing marker,
   conflicting terminal, and invalid package states;
4. the public verifier reports 8/8 product rows, 533/533 delegated selectors,
   12/12 launchers, 6/6 extras, and 7/7 bounded acceptance;
5. the optional retained private root reports private acceptance 7/7;
6. the full Python, TypeScript, Rust, static, shell, scope, and diff gates pass;
7. an independent read-only review reports no Critical or Important issue;
8. all closeout changes and state updates are committed, leaving only the
   expected append-only post-commit journal entry if the state hook creates it.

## Non-Goals

- Full-dataset performance or quality benchmarking.
- A new provider or runtime implementation.
- Packaging the source-only `src/dci` baseline.
- Copying or modifying the external `pi/` repository.
- Replacing native private artifacts with the public acceptance manifest.
