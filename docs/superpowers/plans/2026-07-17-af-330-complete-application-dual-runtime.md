# AF-330 Complete Application and Dual-Runtime Implementation Plan

> Execute autonomously with TDD. Repository policy forbids unsolicited
> sub-agent dispatch. Full datasets and published-score claims are forbidden.

**Goal:** Ship the complete five-stage DCI application and bounded, evidence-bound
Pi/Claude semantic acceptance.

## Task 1 — Governance and closed composition contract

- Activate AF-330 and its four package-parented Climb hypotheses.
- RED: reject missing/extra stages, undeclared artifact/event edges, runtime
  contract drift, duplicate bindings, and unparented hypotheses.
- GREEN: add evaluation, benchmark, analysis, and export manifests plus Pi and
  Claude complete-application assemblies.
- Verify focused package/catalog/application tests, scope, Ruff, compile, diff;
  commit, journal, and close H001 only after implementation tests pass.

## Task 2 — Production implementations and product identity

- RED: prove generic stages cannot execute and CLI/application identities drift.
- GREEN: implement typed stage adapters over existing DCI evaluation, benchmark,
  analysis, and export modules; validate upstream artifact hashes before work.
- Bind the provider, generic runner, product CLI, installed application, and
  isolated wheel to the same implementation/resource digests.
- Verify source/install/wheel parity and close H002.

## Task 3 — Restricted Pi semantic application path

- RED: reject Bash, web, subagent, path escape, symlink escape, unbounded corpus,
  missing context extension, or provider construction before preflight.
- GREEN: execute the complete application over a tiny attempt-local corpus with
  dedicated read/grep and existing native evidence/cancellation semantics.
- Add a body-free bounded report and independent binder. Close H003 after a real
  Pi run; fixtures alone are insufficient.

## Task 4 — Restricted Claude Code runtime

- RED: reject ambient tools/settings/MCP, missing `dontAsk`, sandbox fallback,
  unsandboxed escape, HOME/outside reads, web/subagent tools, mutable corpus,
  invalid streams, cancellation/deadline failures, and public body/path leakage.
- GREEN: exact Read/Grep/Glob command, strict MCP, safe/no-session mode, inline
  fail-closed sandbox settings, attempt-local corpus, private 0600 artifacts,
  safe public projection, and preflight identity.
- Run one bounded real Claude execution and independently bind it. Close H004
  only with real semantic evidence.

## Task 5 — Shared agent provider configuration

**Goal:** Make one `DCI_PROVIDER`/`DCI_MODEL`/provider-key selection work through
Pi or Claude Code without user-authored Claude-native aliases.

**Files:**

- Modify `asterion/src/asterion/runtime/defaults.py` to translate supported
  shared providers into a private Claude subprocess environment.
- Modify `asterion/tests/test_default_runtime_factory.py` to prove MiniMax
  international/China mappings, stale native-variable replacement, missing-key
  failure, and unsupported-provider failure before process construction.
- Modify `.env.template` and `README.md` to document only the shared agent
  selection plus the independent Judge role.

**Interface:**

```python
def _claude_provider_environment(
    environment: Mapping[str, str],
) -> dict[str, str]:
    """Return a copied environment with derived Claude-native provider values."""
```

The mapping is closed:

```python
{
    "anthropic": ("https://api.anthropic.com", "ANTHROPIC_API_KEY"),
    "minimax": ("https://api.minimax.io/anthropic", "MINIMAX_API_KEY"),
    "minimax-cn": ("https://api.minimaxi.com/anthropic", "MINIMAX_CN_API_KEY"),
}
```

For MiniMax, the helper derives `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, and all
three Claude default model aliases from `DCI_MODEL`. It maps Token Plan
credentials with the documented `sk-cp-` prefix to `ANTHROPIC_AUTH_TOKEN`, and
ordinary API keys to `ANTHROPIC_API_KEY`, matching the locked Pi provider's
header behavior; existing conflicting native values are replaced in the copy.
For official Anthropic, it derives the model aliases and retains the single
`ANTHROPIC_API_KEY`. Missing provider/model/key or an unmapped provider raises a
safe `RuntimeFactoryError` without values.

- [ ] Add failing factory tests for `minimax` and `minimax-cn` translation.
- [ ] Run `cd asterion && uv run python -m unittest -v tests.test_default_runtime_factory` and confirm missing derived values fail.
- [ ] Implement the closed mapping and pass the derived copy to `ClaudeCodeRuntimeClient`.
- [ ] Run the focused factory/runtime/complete-application tests until green.
- [ ] Add failing documentation assertions that required configuration names only the shared selection and provider key.
- [ ] Update `.env.template` and `README.md`; rerun documentation/distribution tests.
- [ ] Run all Asterion tests, root focused tests, compile, Ruff, `bash -n`, scope, and diff gates.
- [ ] Commit the verified implementation and journal it.
- [ ] With a configured MiniMax key, run one bounded Claude application plus DeepSeek Judge, bind body-free evidence, and execute AF-330-H-004 Climb 4/4.

## Task 6 — Terminal closure

- Run focused and full Python suites, compile, Ruff, shell syntax, product/static
  verifier, source/install/wheel checks, privacy/credential scan, scope preflight,
  `git diff --check`, and independent inline review.
- Synchronize WORKLIST, CURRENT-STATE, JOURNAL, DECISIONS when needed, RESUME,
  Climb ledger/tree, and user documentation. Commit cohesive closure without
  touching external `pi/`; leave AF-340 inactive pending explicit budget.
