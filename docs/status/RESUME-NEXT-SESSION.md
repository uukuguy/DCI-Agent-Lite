# AF-280 Design Checkpoint

> Updated: 2026-07-16 +0800. AF-270 remains accepted; AF-280 is a bounded Makefile usability follow-up.

Active work package: AF-280

## TL;DR

- The full Asterion DCI migration and unified `asterion describe/verify` implementation remain complete.
- AF-280 adds five explicit Make targets for discovery and the four verification levels.
- Defaults use root `.env`, `./corpus`, and `./outputs/asterion-verification`; callers may override Make variables.
- No DCI runtime, provider protocol, external Pi checkout, or full-dataset behavior changes.

## Next action

After the user approves the committed written spec, create the implementation plan and execute it with TDD.

## Ruled-out paths

- Do not hide provider-backed verification behind an ambiguous default Make target.
- Do not add wrapper scripts or duplicate verification logic.
- Do not modify external `pi/`, credentials, or original DCI behavior.

## Ready commands

```bash
python3 tools/project_scope_check.py
sed -n '1,240p' docs/superpowers/specs/2026-07-16-asterion-make-entry-points-design.md
git status --short
```
