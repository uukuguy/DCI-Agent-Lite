# Current State

## Project Snapshot

- Project: Asterion framework under development in the DCI-Agent-Lite repository; DCI remains the first capability and reference application.
- Current branch: `main`
- Theme-level focus: AF-290 documentation is complete; directory structure and any remaining DCI implementation questions await explicit discussion and a new package.
- Project route: managed
- Canonical worklist: `docs/status/WORKLIST.md`
- Framework north star: `docs/architecture/agent-framework.md`
- Active work package: none; project lifecycle is complete.

## Current Architecture

- Product contract: a versioned Agent Runtime Protocol will normalize lifecycle, capabilities, events, artifacts, cancellation, and deadlines across adapters.
- Reference runtime: the existing Python controller drives external Pi through a hardened JSONL RPC boundary; it is the first reference adapter, not the framework boundary.
- Capability direction: Asterion DCI becomes the first complete reusable capability-package reference product. It will own the full original DCI workflow internally and expose it through capability contracts/application assemblies; no embedding index is required.
- Language roles: Python owns research/evaluation/orchestration, TypeScript owns Node/service integration, and Rust is reserved for controlled execution infrastructure.
- Governance: `docs/status/WORKLIST.md` is the sole active package ledger. A scope audit must pass before manager dispatch or climb execution.
- Maintenance history: Pi/Judge reliability H-001 through H-019 is completed and remains available as reference-maintenance evidence; it is not an active roadmap stream.
- Complete DCI result: `src/dci` remains an independent source-only comparison baseline. AF-180 through AF-250 completed shared `.env` forwarding, complete operator controls, batch/export semantics, Asterion examples, installed Pi application, and bounded provider-backed acceptance. Asterion shares normal `DCI_*` configuration with the baseline while keeping Asterion-owned output paths; neither product imports or launches the other.
- AF-220 acceptance: its four Climb hypotheses are confirmed 4/4. Using only process-local shared configuration and main-repository external resources, both model-free prerequisites, both real Pi examples, the project-entrypoint installed application, and the one-row Pi-plus-Judge benchmark passed. Native state/evaluation schemas and the application's single body-free JSON projection were verified; this closes AF-220 only.
- AF-230 acceptance: all four Climb hypotheses are confirmed 4/4. Asterion now owns the private descriptor-relative recorder, complete/processed conversation evidence, credential-safe Pi provenance, isolated digest-bound attempts, strict single-writer resume, package-local input/resource controls, and direct TTY-only Pi terminal mode. Full local closure passed, and one authorized Pi-default run completed with private parseable artifacts, truthful context state, safe provenance, a matching final digest, and a body-free application projection without a Judge request.
- AF-240 acceptance: all four Climb hypotheses are confirmed 4/4 and all 533 source inventory rows resolve to executable Asterion evidence. Asterion owns concurrent QA/IR orchestration, exact reuse, Judge cache identity, aggregates, detailed analysis/figures, exports, installed profiles, and 12 launchers. Closure passed 1204 Python, 11 TypeScript, and 19 Rust tests plus all static, shell, isolated-wheel, and governance gates. A bounded one-row Pi-plus-Judge batch produced one correct verdict and 28 credential-clean private artifacts; exact reuse preserved native/Judge hashes and mtimes without another protocol attempt or generation.
- AF-250 acceptance: all eight local/model-free product rows, all 533 delegated batch selectors, twelve launcher pairs, six batch extras, and AF-250-H-001 through H-005 pass. The independent Asterion package has no production import or launch of `src/dci`. Seven bounded real source/Asterion/application/Pi-plus-Judge/reuse cases completed successfully after the isolated worktree was given the shared main-repository corpus path; their credential-clean, body-free structural record is digest-bound into the product matrix and revalidated against retained private native artifacts. Final terminal closure passes 1275 Python, 11 TypeScript, and 19 Rust tests plus compile, Ruff, shell, scope, terminal-dispatch rejection, diff, installed-wheel/application, public-record, and private-artifact verifier gates. Independent closeout review reports no Critical or Important findings. No full dataset ran.
- AF-270 acceptance: generic provider-selected `asterion describe/verify` makes the complete DCI function map, shared `.env` configuration, and preflight/basic/acceptance/complete verification discoverable without source inspection. Source acceptance is loaded only from the trusted checkout containing the verifier module; an installed wheel never executes a current-directory lookalike. Both real Pi examples use six-turn limits, private retained evidence is genuinely revalidated, and public cost output counts two Pi run operations plus one Judge operation without misrepresenting multi-turn provider API calls. A real `complete` run passed with all product counts and no full dataset; closure passes 1297 Python, 11 TypeScript, and 19 Rust tests plus all static/governance gates.
- AF-280 acceptance: the root Makefile exposes five explicit, phony, cost-visible shortcuts for capability description and all four DCI verification levels. Defaults use the shared root `.env`, repository corpus, and Asterion verification output while remaining overridable. Exact dry-run argv, documentation, live description, and provider-free acceptance checks pass without a provider request or full dataset.
- AF-290 acceptance: the complete DCI reference, framework/capability integration guide, and standalone extraction guide are canonical and reachable from `docs/README.md`. They distinguish Implemented, Verified, External-limited, and Not rerun evidence; identify package-local `capabilities/` and `applications/` as authoritative; define complete third-party integration and seven reversible extraction phases; and correct stale claims that the current external Pi exposes typed context-management levels. Closure passes 16 focused tests plus compile, Ruff, CLI, scope, link, and diff gates without provider requests or a full dataset.
- Host contracts: Python and TypeScript expose the same schema-backed runtime manifest, request, event, and asynchronous client boundary without adapter-private types.
- Controlled execution: `dci.executor/v1` has a runnable concurrent Rust JSONL sidecar with trusted startup policy, direct execution, bounded dual-stream draining, deadline/cancel kill-and-reap, duplicate-ID denial, out-of-order correlation, safe parse errors, EOF draining, operator documentation, and root verification targets.
- Package composition: `dci.package/v1` and the deterministic Python composer resolve a portable policy → DCI research → evaluation → observability graph identically for Pi and Claude Code capability mappings. The TypeScript host exports the same manifest types and validates the canonical schema/fixtures without implementing a second composer.
- Controlled-code packages: portable policy → workflow → evaluation/observability manifests form the second static graph identically for Pi and Claude Code normalized read capabilities plus the shared `executor.controlled` host service. Capability, policy, event, artifact, and permutation boundaries are verified without changing the composer.
- TypeScript package parity: the public host validates all eight checked-in manifests through the canonical schema, and a source-boundary test prevents a second TypeScript composer.
- AF-070 acceptance: the controlled-code graph, host-service boundary, failure matrix, cross-language validation, and non-execution documentation pass full framework closure; the static contract did not require an execution engine change.
- Local catalog: the Python reference surface deterministically discovers and validates direct JSON children across explicit root/file permutations without recursion. Missing/file/symlink/duplicate roots, invalid/unreadable documents, symlink manifests, and duplicate exact identities fail closed with content-free public errors.
- Catalog selection: exact `package_id@version` refs return deterministic deep-fresh manifests; all eight checked-in packages are selectable and both reference graphs compose unchanged. Duplicate or unknown selections fail closed without implicit version policy.
- AF-080 acceptance: explicit-root discovery, filesystem/document/identity safety, exact selection, both graph integrations, Python-only ownership, and operator documentation pass full framework closure without registry, installation, or execution scope.
- Static assembly: all four AF-090 hypotheses are confirmed. `dci.assembly/v1`, its immutable Python resolver, both reference assemblies, TypeScript schema/type validation, and the non-execution guide pass full Python/Node/Rust closure.
- Asterion extraction: AF-095-H-001 is confirmed 4/4. Runtime protocol, host contracts, Pi/Claude adapters, and Claude runtime are authoritative under `src/asterion/`; `dci.framework.*` preserves object-identity compatibility and the wheel contains both roots.
- Asterion contract extraction: AF-095-H-002 is confirmed 4/4. Package protocol/catalog/composition, assembly, and executor protocol have sole authoritative implementations under Asterion with stable wire literals and definition-free DCI compatibility modules.
- Product directories: AF-095-H-003 is confirmed 4/4. DCI and controlled-code manifests live under `capabilities/`, DCI assemblies under `applications/dci-agent-lite/`, and TypeScript/Rust working directories are Asterion-owned without changing declared identities.
- AF-095 acceptance: all four extraction hypotheses pass; Asterion owns the sole generic implementation, DCI CLI/examples remain compatible, and 258 Python, 11 Node, and 19 Rust tests plus every compile/lint/scope gate pass.
- Application runner: resolved plans carry explicit runtime/host ownership; Python executes one explicit runtime request with cancellation, immutable normalized results, service/capability preflight, runtime parity, and content-free failures.
- AF-100 acceptance: all four runner hypotheses pass; 284 Python, 11 Node, and 19 Rust tests plus every compile/lint/scope gate pass. Formal package closure awaits successor governance.
- Capability execution direction: AF-110 binds independently owned implementations by exact package identity and executes them sequentially through declared event/artifact edges; applications remain the executable composition boundary.
- Distribution boundary: AF-120 produces one self-contained `asterion` wheel containing modular first-party DCI capability/application code and canonical resources; `src/dci` remains a repository-only runnable baseline excluded from all wheels. Generic provider code retains no hard-coded DCI identity, and external providers remain explicitly selected.
- AF-110 acceptance: reusable package implementations execute sequentially through exact bindings, declared artifact/event edges, explicit runtime/services, and safe cancellation/failure boundaries. The DCI research capability and Pi runtime are independent of `src/dci/benchmark/`; 311 Python, 11 Node, and 19 Rust tests plus all repository gates pass.
- AF-120 acceptance: exactly one independently installable Asterion wheel contains the framework, modular DCI capability/application, canonical resources, selected-only provider binding, generic CLI, and explicit Pi runtime factory. `src/dci` is an unpackaged repository baseline; 335 Python, 11 Node, and 19 Rust tests plus isolated installation and every repository gate pass.
- AF-130 acceptance: installed applications list and run by exact `application_id@version`; global listing stays metadata-only, selected listing loads one provider, explicit assembly modes remain compatible, and 342 Python, 11 Node, and 19 Rust tests plus isolated installation and all gates pass.
- AF-140 acceptance: the second `controlled-code` provider executes declarative policy plus three exact implementations through an explicit executor host service; caller-owned JSONL transport never starts a process or persists output bodies. 352 Python, 11 Node, and 19 Rust tests plus isolated installation and all gates pass.
- AF-150 acceptance: the generic installed CLI starts one operator-authorized controlled-executor sidecar only after complete provider/application/assembly/binding/configuration preflight. It uses direct binary-plus-policy argv, a minimal environment, pipe-level readiness, explicit service injection, correlated protocol cancellation, bounded stderr discard, and deterministic reap. The final closure passes 362 Python, 11 Node, and 19 Rust tests plus all repository gates; a fresh wheel installation lists both providers, excludes `dci`, and successfully executes `code.quality@1.0.0` against the Rust sidecar.
- Reference assemblies: checked-in DCI and controlled-code application manifests validate and resolve; DCI composition is identical for Pi/Claude runtime identities and controlled execution remains an explicit host service.
- AF-180 acceptance: all four Climb hypotheses are confirmed 4/4. The independent Asterion DCI module passes focused parity, full Python, compile/Ruff, TypeScript, Rust, shell, installed-command, wheel, scope, and diff gates without a provider request.
- AF-190 acceptance: all four Climb hypotheses are confirmed 4/4. Asterion DCI persists original-style transcript/context/tool-result references and state/protocol evidence, resumes only compatible failed/incomplete runs through `asterion-dci resume`, and projects durable references without bodies. Full Python, compile/Ruff, TypeScript, Rust, shell, workspace command-help, scope, wheel, and diff gates pass without a provider request.
- AF-200 acceptance: all four Climb hypotheses are confirmed 4/4. Asterion owns judge request shaping/fingerprints, exact cache-safe native evaluation, deterministic JSONL benchmark orchestration, product-local evaluation/benchmark commands, and conditional body-free evaluation references. Full local closure passes without a provider request.
- AF-210 acceptance: all four Climb hypotheses are confirmed 4/4. The installed DCI Pi application now shares the package-local native executor and durable body-free projection; native failures are redacted, the executor/provider ship in the wheel, and generic framework modules remain DCI-neutral. Full Python, compile/Ruff/shell, TypeScript, Rust, scope, and diff gates pass without a provider request. Claude remains a fixture-only protocol boundary rather than a semantic-parity claim.

## Open Problems (theme-level)

- No active implementation package. The next discussion may evaluate directory simplification and any DCI gaps against the three AF-290 documents; implementation requires reopening governance with a new scoped package.

## Key Files

### Loaded every session

- `AGENTS.md` — shared repository operating rules and framework scope control.
- `docs/architecture/agent-framework.md` — framework north star.
- `docs/status/WORKLIST.md` — active package ledger.
- `~/.claude/projects/-Users-sujiangwen-sandbox-agentic-2026-DCI-Agent-Lite/memory/MEMORY.md` — concise collaboration-memory index.

### State / handoff

- `docs/status/INDEX.md` — status-file discovery hub.
- `docs/status/JOURNAL.md` — append-only event log.
- `docs/status/RESUME-NEXT-SESSION.md` — current session handoff baton.
- `docs/status/DECISIONS.md` — architecture decisions and revalidation triggers.
- `docs/status/climb/research-tree.md` — generated summary of legacy or parented autonomous research state.

### Implementation entry points

- `src/dci/benchmark/pi_rpc_runner.py` — existing Pi RPC reference runtime.
- `src/dci/benchmark/pi_system_prompt.py` — Pi-owned system-prompt bridge.
- `src/dci/framework/host.py` — public Python Agent Runtime Protocol host contract.
- `src/dci/framework/package_catalog.py` — explicit-root deterministic local package discovery and catalog types.
- `packages/typescript/asterion-runtime/` — public TypeScript host package and shared-fixture validator.
- `src/dci/framework/executor_protocol.py` — Python reference validator for `dci.executor/v1`.
- `packages/rust/controlled-executor/` — runnable Rust controlled-executor sidecar and library with complete AF-050 policy/process/resource/service acceptance.
- `docs/superpowers/specs/2026-07-12-composable-framework-packages-design.md` — active AF-060 package contract and non-goals.
- `docs/superpowers/specs/2026-07-12-controlled-code-validation-packages-design.md` — active AF-070 second-graph contract and non-goals.
- `docs/superpowers/specs/2026-07-13-local-package-catalog-design.md` — active AF-080 discovery, exact-selection, and trust-boundary contract.
- `docs/architecture/composable-packages.md` — package authoring, static composition, extension, and security boundary guide.
- `docs/architecture/controlled-code-validation-packages.md` — second-graph, shared host-service, non-execution, and non-sandbox guide.
- `docs/architecture/local-package-catalog.md` — explicit-root discovery, exact selection, filesystem trust, and non-execution guide.
- `docs/architecture/static-application-assembly.md` — exact runtime/catalog/service binding, language ownership, safe failure, and non-execution guide.
- `docs/architecture/application-runner.md` — explicit runtime/service execution boundary, cancellation, immutable results, and non-goals.
- `docs/superpowers/specs/2026-07-13-application-runner-vertical-slice-design.md` — approved AF-100 scope and execution/security boundaries.
- `docs/superpowers/plans/2026-07-13-application-runner-vertical-slice.md` — AF-100 implementation and verification slices.
- `docs/superpowers/specs/2026-07-13-asterion-framework-extraction-design.md` — Asterion naming, directory ownership, compatibility, and migration boundaries.
- `docs/superpowers/specs/2026-07-13-dci-application-runtime-parity-design.md` — approved provider-bound Pi application integration boundary for AF-210.
- `docs/superpowers/plans/2026-07-13-dci-application-runtime-parity.md` — AF-210 TDD and Climb acceptance plan.
- `scripts/bcplus_eval/run_bcplus_eval.py` — DCI reference benchmark harness.
- `tools/climb/` — autonomous-work adapter; future cycles require a work-package parent.

## Resume Instructions

1. Read this file, then `docs/architecture/agent-framework.md` and `docs/status/WORKLIST.md`.
2. Read `RESUME-NEXT-SESSION.md`, recent JOURNAL entries, and the relevant collaboration-memory entry.
3. Run `git status --short`, `git log --oneline -5`, and `python3 tools/project_scope_check.py`.
4. Work only on the named active package; when lifecycle is complete, explicitly reopen governance before implementation.
