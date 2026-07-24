# Next-Session Handoff

> Updated: 2026-07-24 12:35 +0800 end of session.

Active work package: AF-360

Project lifecycle: active

Currently running: no process.

## TL;DR

- The real `make setup-pi` failure is fixed and committed: locked Pi 0.80.6 builds reproducibly from checked-in catalogs with the lock-installed toolchain.
- Configuration probes then confirmed one remaining AF-360 defect: `.env` supplies `ASTERION_DCI_CORPUS_ROOT` to verification, but does not supply `ASTERION_DCI_RESOURCE_ROOT` to setup or shell launchers at the time they resolve paths.
- No configuration implementation has begun. Resume by presenting the recorded minimal design for approval; only then write the design addendum/plan and implement through TDD.

## Where things stand

- `main` contains the Pi repair commits `bf1c770` and `23f3b19`, followed by AF-360 closure state `083ce69`; all are local and unpushed.
- Real Pi verification is clean at locked revision `8479bd84743e8889f728acb21a62794102db0529`; the external checkout is detached and has no tracked changes.
- Final Pi repair evidence: two fresh real Pi 0.80.6 builds, 206 standalone tests, 94 mixed-root regressions, 16 Markdown/32-link checks, and 18 full clean-copy promotion commands; provider operations 0 and no full dataset.
- Current mixed-root `corpus/` is external and ignored, with populated `wiki_corpus` and `bc_plus_docs`; standalone Asterion can reuse it by an explicit exported absolute resource root.
- The configuration probe showed `make setup-resources-basic --check` fails without an exported resource root and passes when `ASTERION_DCI_RESOURCE_ROOT` points at the mixed root.
- A separate cwd probe proved `uv run --project /path/to/asterion` preserves the caller directory rather than changing into the project.

## Pending design decision

Recommended approach:

1. Add one safe Python resource-root resolver that loads the Asterion project `.env` without overriding inherited values.
2. Make resource setup and all fourteen shell launchers use that resolver.
3. Ensure launcher Python execution begins from the Asterion project root, while keeping explicit CLI/exported values above `.env` and project defaults.
4. Never shell-source `.env`; it may contain credentials and is dotenv syntax, not trusted shell code.

Alternatives rejected as defaults:

- Requiring users to export `ASTERION_DCI_RESOURCE_ROOT` and removing the `.env` promise is simpler but contradicts the normal configuration surface.
- Shell-sourcing `.env` is concise but unsafe and semantically incorrect for a credential-bearing dotenv file.

## Next steps

1. Ask the user to approve or revise the recommended design above.
2. After approval, record the design addendum and implementation plan, then run `python3 tools/project_scope_check.py`.
3. Add failing tests for setup `.env` loading, exported-value precedence, launcher execution from outside the project root, and all fourteen launchers using the shared resolver.
4. Implement the smallest shared resolver and rerun standalone, launcher, documentation, promotion, and mixed-root configuration regressions before reclosing AF-360.

## Ruled-out paths

- Do not claim `ASTERION_DCI_RESOURCE_ROOT` is effective merely because it appears in `.env.template`.
- Do not rely on `uv run --project` to change cwd.
- Do not shell-source `.env`.
- Do not duplicate the existing mixed-root corpus unless an independent standalone checkout actually needs its own external resource tree.
- Do not disturb the completed source-pinned Pi repair or accept a global Pi executable as runtime authority.

## Open questions

- User approval of the recommended shared Python resolver design is pending.
- No publication, remote creation/push, full dataset, or provider-backed operation is authorized.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py
git status --short --branch
make -C asterion check-pi
ASTERION_DCI_RESOURCE_ROOT="$PWD" \
  uv run --project asterion python asterion/tools/setup_resources.py \
  --profile basic --check --json
```
