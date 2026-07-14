# AF-240 Task 6 Independent Review

Verdict: **APPROVED**

## Scope

Reviewed Task 6 implementation and repair commits `fa2000a`, `450f4f0`,
`7789fcf`, `7f13f38`, `bae6b7e`, `1a18315`, `48eed46`, `db53f46`,
`58204d9`, and `865f970` against
`docs/superpowers/plans/2026-07-14-af-240-batch-evaluation-export-parity.md`.

The review covered the package-local profile resource, complete benchmark CLI
mapping, all public Judge overrides, profile/CLI/environment precedence,
repository-independent wheel resources, twelve one-to-one launchers, dynamic
BCPlus argv handling, body-free failures, destination safety, documentation,
inventory evidence, and the prohibition on production dependencies on
`src/dci` or source launchers.

## Findings and repairs

The initial implementation had three blocking defects:

1. Invalid runtime values such as `--thinking-level INVALID` reached the batch
   coordinator, created durable output, and returned success with a failed row.
2. The dynamic launcher consumed `--limit` as the optional thinking value when
   thinking was omitted, and unchecked positional values could alter the
   normalized output destination.
3. Task 6 inventory rows initially referenced non-resolving or insufficiently
   behavior-specific evidence.

The repairs now preflight the complete runtime request before `run_benchmark`,
parse the optional positional thinking value without consuming options,
allowlist context/thinking values before output construction, and bind every
Task 6 row to executable CLI or launcher evidence. The final documentation also
states the actual profile precedence and analysis/figure control behavior.

No CRITICAL, HIGH, MEDIUM, or LOW findings remain.

## Verification

- `python3 tools/project_scope_check.py`: passed for active package AF-240.
- `uv run python -m unittest -v tests.test_asterion_dci_batch_launchers tests.test_asterion_dci_cli tests.test_climb_tools.Af240InventoryTests`: 109 tests passed.
- Focused launcher/CLI suite before inventory combination: 88 tests passed; the repaired suite expanded the behavior-specific coverage.
- `uv run ruff check packages/python/asterion-core/src/asterion/dci/cli.py tests/test_asterion_dci_batch_launchers.py tests/test_asterion_dci_cli.py`: passed.
- `find scripts/asterion -name '*.sh' -print0 | xargs -0 -n1 bash -n`: passed.
- `git diff --check`: passed.
- Isolated wheel test built the Asterion wheel, confirmed the packaged
  `batch-profiles.json`, and loaded all twelve profiles without repository
  availability.
- Adversarial recheck: `level3 --limit 7` forwarded `--limit 7` without a
  thinking flag; traversal-like context input failed before command execution.
- Adversarial recheck: invalid benchmark thinking returned body-free status 2,
  did not call the batch boundary, and created no output directory.
- Static inspection found no Asterion production or launcher import/exec path to
  `src/dci`, the source benchmark runner, or the external Pi checkout.

Task 6 satisfies its acceptance contract and is ready for Task 7 bounded
acceptance and AF-240 closure work.
