# AF-290 Design Checkpoint

> Updated: 2026-07-16 +0800. Accepted implementation remains unchanged; AF-290 is documentation-only.

Active work package: AF-290

## TL;DR

- Write three evidence-backed documents: complete Asterion DCI reference, framework/capability integration guide, and standalone extraction design.
- Clearly separate implemented behavior, executable verification, external-Pi limitations, and full-dataset results that were not rerun.
- Explain canonical package-local `capabilities/` and `applications/` versus top-level historical/reference directories.
- Do not move code or begin extraction in AF-290; directory restructuring and DCI gaps are discussed after the documents are accepted.

## Next action

After written-spec approval, create the implementation plan and write the documents from source and executable evidence.

## Ruled-out paths

- Do not claim Pi context-management levels are effective when the configured Pi CLI does not expose the flag.
- Do not equate 533 model-free behavior checks with rerunning every full benchmark dataset or reproducing published scores.
- Do not move directories, split repositories, or modify external `pi/` under this documentation package.

## Ready commands

```bash
python3 tools/project_scope_check.py
sed -n '1,260p' docs/superpowers/specs/2026-07-16-asterion-documentation-set-design.md
git status --short
```
