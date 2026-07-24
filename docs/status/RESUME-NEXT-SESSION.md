# Live Session Checkpoint

> Updated: 2026-07-24 15:07 +0800. **Session remains active — not a final handoff.**

Active work package: AF-360

Project lifecycle: active

Currently running: no process.

## TL;DR

- The real `make setup-pi` failure is fixed and committed: locked Pi 0.80.6 builds reproducibly from checked-in catalogs with the lock-installed toolchain.
- AF-300 left runnable DCI/Asterion shell examples only in the mixed repository; the standalone `asterion/` tree has framework-composition Python examples but no equivalent user-facing DCI launchers.
- Three 2026-07-24 example runs failed before the first model response because the saved `openai-codex` OAuth credential expired and Pi refresh returned no API key. Preflight incorrectly passed authentication by checking only that `auth.json` exists, while the root Make wrapper also resolved `.env` from the wrong directory.
- No implementation has begun. Resume by confirming whether standalone should receive only the two Asterion-native examples or all provider-specific variants, then approve the combined configuration/example/auth-preflight design.

## Where things stand

- `main` contains the Pi repair commits `bf1c770` and `23f3b19`, followed by AF-360 closure state `083ce69`; all are local and unpushed.
- Real Pi verification is clean at locked revision `8479bd84743e8889f728acb21a62794102db0529`; the external checkout is detached and has no tracked changes.
- Final Pi repair evidence: two fresh real Pi 0.80.6 builds, 206 standalone tests, 94 mixed-root regressions, 16 Markdown/32-link checks, and 18 full clean-copy promotion commands; provider operations 0 and no full dataset.
- Current mixed-root `corpus/` is external and ignored, with populated `wiki_corpus` and `bc_plus_docs`; standalone Asterion can reuse it by an explicit exported absolute resource root.
- The configuration probe showed `make setup-resources-basic --check` fails without an exported resource root and passes when `ASTERION_DCI_RESOURCE_ROOT` points at the mixed root.
- A separate cwd probe proved `uv run --project /path/to/asterion` preserves the caller directory rather than changing into the project.
- `outputs/asterion-dci-runs/asterion-dci-20260724T065055.607338Z-ab0e0e9c`, `...T065110.548031Z-071423bc`, and `outputs/runs/20260724-145236` all recorded the same Pi provider failure before any tool call or output token.
- The selected OAuth record exists for `openai-codex` but expired on 2026-07-22; Pi preserved it after refresh failure. Reauthentication requires the pinned Pi interactive `/login openai-codex` flow.
- Provider-free preflight reported `agent-authentication` PASS solely because `auth.json` exists. It separately failed `environment` because root `ASTERION_ENV_FILE=.env` became `asterion/.env` after `make -C asterion`.

## Pending design decision

Recommended approach:

1. Add one safe Python resource-root resolver that loads the Asterion project `.env` without overriding inherited values.
2. Put standalone Asterion-native basic and runtime-context launchers under `asterion/scripts/examples/`; retain original DCI/provider-specific comparison scripts only in the mixed repository.
3. Make resource setup, standalone examples, mixed-root Asterion wrappers, and all fourteen benchmark launchers use the resolver; do not duplicate resolution logic.
4. Resolve explicit env-file arguments before `make -C asterion`, and begin launcher Python execution from the Asterion project root.
5. Make preflight validate the selected provider entry rather than treating any `auth.json` file as usable; expired/unrefreshable OAuth must fail with the pinned Pi `/login` repair.
6. Never shell-source `.env`; it may contain credentials and is dotenv syntax, not trusted shell code.

Alternatives rejected as defaults:

- Requiring users to export `ASTERION_DCI_RESOURCE_ROOT` and removing the `.env` promise is simpler but contradicts the normal configuration surface.
- Shell-sourcing `.env` is concise but unsafe and semantically incorrect for a credential-bearing dotenv file.

## Next steps

1. Ask the user to approve or revise the recommended design above.
2. Confirm whether standalone gets only the two Asterion-native examples (recommended) or every provider-specific root variant.
3. After approval, update the AF-360 design/worklist acceptance and implementation plan, then run `python3 tools/project_scope_check.py`.
4. Add failing tests for safe `.env` loading, absolute env-file forwarding, standalone example presence, root wrapper delegation, expired OAuth rejection, and all launchers using the shared resolver.
5. Implement the smallest shared resolver and rerun standalone, example, launcher, documentation, promotion, and mixed-root configuration regressions before reclosing AF-360.

## Ruled-out paths

- Do not claim `ASTERION_DCI_RESOURCE_ROOT` is effective merely because it appears in `.env.template`.
- Do not rely on `uv run --project` to change cwd.
- Do not shell-source `.env`.
- Do not treat the existence of `auth.json` as proof that the selected provider is usable.
- Do not copy original `src/dci` or its provider-specific product scripts into the standalone Asterion product.
- Do not duplicate the existing mixed-root corpus unless an independent standalone checkout actually needs its own external resource tree.
- Do not disturb the completed source-pinned Pi repair or accept a global Pi executable as runtime authority.

## Open questions

- User choice on the standalone example set and approval of the combined resolver/example/auth-preflight design are pending.
- No publication, remote creation/push, full dataset, or provider-backed operation is authorized.

## Ready-to-paste commands

```bash
python3 tools/project_scope_check.py
git status --short --branch
make -C asterion check-pi
PI_CODING_AGENT_DIR="$HOME/.pi/agent" \
  node pi/packages/coding-agent/dist/cli.js
# In Pi: /login openai-codex
ASTERION_DCI_RESOURCE_ROOT="$PWD" \
  uv run --project asterion python asterion/tools/setup_resources.py \
  --profile basic --check --json
```
