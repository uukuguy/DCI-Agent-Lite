"""Self-description and bounded verification for the Asterion DCI product."""

from __future__ import annotations

import os
import re
import secrets
import subprocess
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from asterion.dci.ablation import (
    paper_ablation_matrix_sha256,
    paper_ablation_row_ids,
)
from asterion.applications.product import (
    CapabilityFunction,
    CapabilityProductDescription,
    ConfigurationRequirement,
    InstalledCapabilityProduct,
    VerificationCheckResult,
    VerificationProfile,
    VerificationRequest,
    VerificationResult,
)
from asterion.dci.config import (
    DciPaths,
    DciRuntimeOptions,
    load_asterion_dci_env,
    resolve_dci_paths,
    resolve_dci_runtime_options,
)
from asterion.dci.evaluation import evaluate_run_directory
from asterion.dci.judge import JudgeConfig
from asterion.dci.context_profiles import context_profile_names
from asterion.dci.paper_benchmarks import (
    paper_benchmark_ids,
    paper_benchmark_inventory_sha256,
    paper_experiment_scope_ids,
    paper_experiment_scopes_sha256,
    resolve_paper_benchmark,
)
from asterion.dci.run import DciRunRequest, DciRunResult, run_pi_research


@dataclass(frozen=True)
class BasicVerificationCase:
    case_id: str
    question: str
    corpus_subdir: str
    expected_answer: str | None
    max_turns: int | None
    thinking_level: str


BASIC_CASES = (
    BasicVerificationCase(
        case_id="basic-corpus-research",
        question=(
            "Answer the following question using only wiki_dump.jsonl in the current "
            "directory. Do not use web search. Use rg instead of grep for fast searching. "
            "Question: In which street did the Great Fire of London originate?"
        ),
        corpus_subdir="wiki_corpus",
        expected_answer=None,
        max_turns=6,
        thinking_level="high",
    ),
    BasicVerificationCase(
        case_id="runtime-context-and-judge",
        question=(
            "Read the files in the current directory. Do not use web search. Use rg instead "
            "of grep when searching. Question: In the Bonang Matheba interview where the "
            "third-to-last question asks about the origin of the name given to her by radio "
            "listeners, what is the interviewer's first name? Answer with just the first "
            "name and one supporting file path."
        ),
        corpus_subdir="bc_plus_docs",
        expected_answer="Adaku",
        max_turns=6,
        thinking_level="high",
    ),
)


DCI_PRODUCT_DESCRIPTION = CapabilityProductDescription(
    product_id="asterion-dci",
    version="1.0.0",
    summary="DCI local-corpus research, evaluation, and benchmark capability",
    functions=(
        CapabilityFunction(
            "ablation",
            "Validate, list, and render deterministic paper/bounded matrices",
            ("asterion-dci", "ablation", "--help"),
        ),
        CapabilityFunction(
            "benchmark",
            "Run bounded QA and IR benchmarks with metrics and analysis",
            ("asterion-dci", "benchmark", "--help"),
        ),
        CapabilityFunction(
            "evaluate",
            "Evaluate one saved research run with the configured Judge",
            ("asterion-dci", "evaluate", "--help"),
        ),
        CapabilityFunction(
            "export",
            "Export BC+, BRIGHT, or QA result formats",
            ("asterion-dci", "export", "--help"),
        ),
        CapabilityFunction(
            "installed-application",
            "Run the installed DCI research capability through Asterion",
            (
                "asterion",
                "run",
                "--provider",
                "dci-agent-lite",
                "--application",
                "dci.research-capability@1.0.0",
                "--runtime",
                "pi.reference",
            ),
        ),
        CapabilityFunction(
            "paper-contracts",
            "Describe body-free paper benchmark, metric, and matrix identities",
            ("asterion-dci", "paper", "describe"),
        ),
        CapabilityFunction(
            "research",
            "Research a question against a local corpus with Pi",
            ("asterion-dci", "run", "--help"),
        ),
        CapabilityFunction(
            "resume",
            "Continue a saved Pi research session",
            ("asterion-dci", "resume", "--help"),
        ),
        CapabilityFunction(
            "terminal",
            "Open the interactive DCI terminal workflow",
            ("asterion-dci", "terminal", "--help"),
        ),
    ),
    configuration=(
        ConfigurationRequirement(
            "ASTERION_DCI_CORPUS_ROOT",
            "Parent directory containing wiki_corpus and bc_plus_docs",
            ("basic", "complete", "preflight"),
            False,
            "./corpus",
            "Usually pass --corpus-root instead of setting this value",
        ),
        ConfigurationRequirement(
            "ASTERION_DCI_OUTPUT_ROOT",
            "Directory for Asterion DCI run artifacts",
            ("basic", "complete"),
            False,
            "./outputs/asterion-dci-runs",
            "Usually pass --output-root when verifying",
        ),
        ConfigurationRequirement(
            "DCI_EVAL_JUDGE_API_KEY_ENV",
            "Name of the environment variable holding the Judge credential",
            ("basic", "complete", "preflight"),
            False,
            "OPENAI_API_KEY",
            "Set this name and then set the named secret variable in .env",
        ),
        ConfigurationRequirement(
            "DCI_EVAL_JUDGE_MODEL",
            "Judge model used for the evaluated basic case",
            ("basic", "complete", "preflight"),
            False,
            "gpt-5.4-nano",
            "Use the same Judge settings as original DCI",
        ),
        ConfigurationRequirement(
            "DCI_MODEL",
            "Pi model used for research",
            ("basic", "complete", "preflight"),
            False,
            None,
            "Set a model available from DCI_PROVIDER",
        ),
        ConfigurationRequirement(
            "DCI_PI_DIR",
            "External Pi checkout",
            ("basic", "complete", "preflight"),
            False,
            "./pi",
            "The checkout must contain packages/coding-agent and .pi/agent",
        ),
        ConfigurationRequirement(
            "DCI_PROVIDER",
            "Pi model provider",
            ("basic", "complete", "preflight"),
            False,
            None,
            "For example openai or anthropic",
        ),
        ConfigurationRequirement(
            "PROVIDER_API_KEY",
            "Credential selected from the provider name, such as OPENAI_API_KEY",
            ("basic", "complete", "preflight"),
            True,
            None,
            "Set the provider-specific key in .env; its value is never displayed",
        ),
    ),
    profiles=(
        VerificationProfile(
            "acceptance",
            "Check the complete local product inventory without model requests",
            "provider-free",
            0,
            False,
        ),
        VerificationProfile(
            "basic",
            "Run the two original DCI-equivalent examples and one Judge check",
            "bounded-provider-backed",
            3,
            False,
        ),
        VerificationProfile(
            "complete",
            "Run preflight, both basic examples, and local product acceptance",
            "bounded-provider-backed",
            3,
            False,
        ),
        VerificationProfile(
            "preflight",
            "Check configuration, Pi, Node, corpora, and Judge without requests",
            "provider-free",
            0,
            False,
        ),
    ),
)


def paper_product_contract() -> dict[str, object]:
    """Return the installed, body-free AF-320 product identity."""

    dataset_ids = paper_benchmark_ids()
    scope_ids = paper_experiment_scope_ids()
    matrix_sha256 = paper_ablation_matrix_sha256()
    inventory_sha256 = paper_benchmark_inventory_sha256()
    scopes_sha256 = paper_experiment_scopes_sha256()
    batch_profiles = tuple(
        sorted(
            {
                dataset.batch_profile
                for dataset_id in dataset_ids
                if (dataset := resolve_paper_benchmark(dataset_id)).batch_profile
                is not None
            }
        )
    )
    return {
        "schema": "dci.paper-product-contract/v1",
        "dataset_ids": list(dataset_ids),
        "experiment_scope_ids": list(scope_ids),
        "ablation_row_ids": list(paper_ablation_row_ids()),
        "context_profiles": list(context_profile_names()),
        "batch_profiles": list(batch_profiles),
        "beir_profiles": ["beir.arguana", "beir.scifact"],
        "resolution_metrics": [
            "coverage_any",
            "coverage_mean",
            "coverage_all",
            "localization",
            "retained_coverage",
        ],
        "analysis_configuration": {
            "alignment_version": "dci.paper-alignment/v1",
            "segment_characters": "required-positive-integer",
            "read_minimum_evidence_overlap": 0.5,
        },
        "safe_artifact_schemas": [
            "asterion.dci.batch-analysis/v1",
            "asterion.dci.batch-item/v1",
            "dci.trajectory-resolution-summary/v1",
        ],
        "benchmark_inventory_sha256": inventory_sha256,
        "experiment_scopes_sha256": scopes_sha256,
        "ablation_matrix_sha256": matrix_sha256,
        "resources": {
            "paper-ablation-matrix.json": matrix_sha256,
            "paper-benchmarks.json": inventory_sha256,
            "paper-experiment-scopes.json": scopes_sha256,
        },
        "paper_full_executable": False,
    }


class DciVerificationBackend(Protocol):
    def node_major_version(self) -> int | None: ...

    def run_research_case(
        self, paths: DciPaths, request: DciRunRequest, *, output_dir: Path
    ) -> DciRunResult: ...

    def evaluate_case(
        self,
        output_dir: Path,
        *,
        expected_answer: str,
        judge_config: JudgeConfig,
    ) -> bool: ...


class LocalDciVerificationBackend:
    """Read-only local prerequisite adapter."""

    def node_major_version(self) -> int | None:
        try:
            completed = subprocess.run(
                ["node", "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        match = re.fullmatch(r"v([0-9]+)(?:\.[0-9]+){2}\s*", completed.stdout)
        return None if match is None else int(match.group(1))

    def run_research_case(
        self, paths: DciPaths, request: DciRunRequest, *, output_dir: Path
    ) -> DciRunResult:
        return run_pi_research(paths, request, output_dir=output_dir)

    def evaluate_case(
        self,
        output_dir: Path,
        *,
        expected_answer: str,
        judge_config: JudgeConfig,
    ) -> bool:
        result = evaluate_run_directory(
            output_dir,
            gold_answer=expected_answer,
            judge_config=judge_config,
        )
        return result.get("is_correct") is True


def _run_product_acceptance(root: Path, acceptance_root: Path | None = None) -> object:
    runner = _load_product_acceptance_runner(root)
    return runner(root, acceptance_root=acceptance_root)


def _load_product_acceptance_runner(root: Path) -> Callable[..., object]:
    """Load the exact source-checkout verifier without relying on ``sys.path``."""

    path = Path(root).resolve() / "tools/verify_asterion_dci_product.py"
    if not path.is_file() or path.is_symlink():
        raise ImportError("product acceptance verifier is unavailable")
    module_name = "_asterion_dci_product_acceptance"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError("product acceptance verifier is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        runner = getattr(module, "verify_product_acceptance")
    except Exception:
        sys.modules.pop(module_name, None)
        raise ImportError("product acceptance verifier is unavailable") from None
    if not callable(runner):
        raise ImportError("product acceptance verifier is unavailable")
    return runner


@dataclass(frozen=True)
class DciProductVerifier:
    repo_root: Path
    backend: DciVerificationBackend
    acceptance_runner: Callable[[Path, Path | None], object] = _run_product_acceptance
    acceptance_source_root: Path | None = None

    def __call__(self, request: VerificationRequest) -> VerificationResult:
        if request.level == "preflight":
            return self.preflight(
                env_file=request.env_file, corpus_root=request.corpus_root
            )
        if request.level == "basic":
            return self.basic(request)
        if request.level == "acceptance":
            return self.acceptance(request.acceptance_root)
        if request.level == "complete":
            return self.complete(request)
        return VerificationResult(
            product_id=DCI_PRODUCT_DESCRIPTION.product_id,
            level=request.level,
            status="NOT RUN",
            checks=(
                VerificationCheckResult(
                    check_id="implementation",
                    summary="This verification level is not available yet",
                    status="NOT RUN",
                ),
            ),
            provider_backed_operation_count=0,
            full_dataset_ran=False,
        )

    def acceptance(self, acceptance_root: Path | None) -> VerificationResult:
        """Run source-checkout product acceptance without provider requests."""

        try:
            if self.acceptance_source_root is None:
                raise ImportError("product acceptance verifier is unavailable")
            summary = self.acceptance_runner(
                self.acceptance_source_root, acceptance_root
            )
            values = (
                ("batch-extras", summary.batch_extras),
                ("bounded-acceptance", summary.bounded_acceptance),
                ("delegated-inventory", summary.delegated_inventory),
                ("launcher-pairs", summary.launcher_pairs),
                ("product-rows", summary.product_rows),
            )
            checks = tuple(
                VerificationCheckResult(
                    check_id=check_id,
                    summary=(
                        "Accepted product evidence is complete"
                        if actual == expected
                        else "Accepted product evidence is incomplete"
                    ),
                    status="PASS" if actual == expected else "FAIL",
                    counts=(("actual", actual), ("expected", expected)),
                )
                for check_id, (actual, expected) in values
            ) + (
                VerificationCheckResult(
                    check_id="provider-requests",
                    summary="Product acceptance made no provider requests",
                    status=(
                        "PASS"
                        if summary.provider_backed_executed == 0
                        else "FAIL"
                    ),
                    counts=(("actual", summary.provider_backed_executed),),
                ),
            )
        except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
            return VerificationResult(
                product_id=DCI_PRODUCT_DESCRIPTION.product_id,
                level="acceptance",
                status="NOT RUN",
                checks=(
                    VerificationCheckResult(
                        check_id="source-checkout",
                        summary="Product acceptance requires the DCI source checkout",
                        status="NOT RUN",
                    ),
                ),
                provider_backed_operation_count=0,
                full_dataset_ran=False,
            )
        return VerificationResult(
            product_id=DCI_PRODUCT_DESCRIPTION.product_id,
            level="acceptance",
            status="PASS" if all(check.status == "PASS" for check in checks) else "FAIL",
            checks=checks,
            provider_backed_operation_count=0,
            full_dataset_ran=False,
        )

    def complete(self, request: VerificationRequest) -> VerificationResult:
        """Run preflight, bounded examples, and provider-free acceptance in order."""

        preflight = self.preflight(
            env_file=request.env_file, corpus_root=request.corpus_root
        )
        aggregate = [
            VerificationCheckResult(
                check_id="preflight",
                summary="All local and configured prerequisites are ready",
                status=preflight.status,
            )
        ]
        if preflight.status != "PASS":
            return _complete_result(aggregate, provider_backed_operations=0)
        basic = self.basic(request)
        aggregate.extend(basic.checks)
        if basic.status != "PASS":
            return _complete_result(
                aggregate, provider_backed_operations=basic.provider_backed_operation_count
            )
        acceptance = self.acceptance(request.acceptance_root)
        aggregate.extend(acceptance.checks)
        return _complete_result(
            aggregate,
            provider_backed_operations=basic.provider_backed_operation_count,
            forced_status=acceptance.status,
        )

    def basic(self, request: VerificationRequest) -> VerificationResult:
        """Run exactly the two accepted DCI examples and one Judge evaluation."""

        preflight = self.preflight(
            env_file=request.env_file, corpus_root=request.corpus_root
        )
        if preflight.status != "PASS":
            return VerificationResult(
                product_id=DCI_PRODUCT_DESCRIPTION.product_id,
                level="basic",
                status="FAIL",
                checks=(
                    VerificationCheckResult(
                        check_id="preflight",
                        summary="Prerequisites must pass before bounded verification",
                        status="FAIL",
                    ),
                ),
                provider_backed_operation_count=0,
                full_dataset_ran=False,
            )
        paths = resolve_dci_paths(self.repo_root)
        options = resolve_dci_runtime_options()
        corpus_root = _corpus_root(self.repo_root, request.corpus_root)
        output_root = (
            paths.output_root
            if request.output_root is None
            else request.output_root
        )
        private_root = output_root / f"verify-{secrets.token_hex(8)}"
        judge_config = JudgeConfig.from_env()
        checks: list[VerificationCheckResult] = []
        external_requests = 0
        for case in BASIC_CASES:
            run_request = _basic_request(case, options, paths, corpus_root)
            destination = private_root / case.case_id
            try:
                external_requests += 1
                run_result = self.backend.run_research_case(
                    paths, run_request, output_dir=destination
                )
                passed = run_result.status == "completed"
                judge_requests = 0
                if passed and case.expected_answer is not None:
                    external_requests += 1
                    judge_requests = 1
                    passed = self.backend.evaluate_case(
                        run_result.output_dir,
                        expected_answer=case.expected_answer,
                        judge_config=judge_config,
                    )
            except Exception:
                passed = False
                judge_requests = 0
            counts = [("native-runs", 1)]
            if judge_requests:
                counts.insert(0, ("judge-requests", judge_requests))
            checks.append(
                VerificationCheckResult(
                    check_id=case.case_id,
                    summary=(
                        "Bounded example completed"
                        if passed
                        else "Bounded example failed"
                    ),
                    status="PASS" if passed else "FAIL",
                    artifact_refs=(f"{case.case_id}/run",),
                    counts=tuple(counts),
                )
            )
            if not passed:
                break
        return VerificationResult(
            product_id=DCI_PRODUCT_DESCRIPTION.product_id,
            level="basic",
            status="PASS" if len(checks) == len(BASIC_CASES) and all(check.status == "PASS" for check in checks) else "FAIL",
            checks=tuple(checks),
            provider_backed_operation_count=external_requests,
            full_dataset_ran=False,
        )

    def preflight(
        self, *, env_file: Path | None, corpus_root: Path | None
    ) -> VerificationResult:
        loaded = load_asterion_dci_env(self.repo_root, env_file=env_file)
        paths = resolve_dci_paths(self.repo_root)
        options = resolve_dci_runtime_options()
        requested_env = self.repo_root / ".env" if env_file is None else env_file
        environment_ready = loaded is not None and requested_env.is_file()
        provider_key = _provider_key_name(options.provider)
        pi_auth = paths.pi.agent_dir / "auth.json"
        pi_managed_auth = pi_auth.is_file() and not pi_auth.is_symlink()
        configuration_ready = bool(
            options.provider
            and options.model
            and (
                (provider_key and os.environ.get(provider_key, "").strip())
                or pi_managed_auth
            )
        )
        judge_key_name = (
            os.environ.get("DCI_EVAL_JUDGE_API_KEY_ENV", "").strip()
            or os.environ.get("ASTERION_DCI_JUDGE_API_KEY_ENV", "").strip()
            or "OPENAI_API_KEY"
        )
        judge_ready = bool(
            os.environ.get("DCI_EVAL_JUDGE_MODEL", "").strip()
            or os.environ.get("ASTERION_DCI_JUDGE_MODEL", "").strip()
            or "gpt-5.4-nano"
        ) and bool(
            os.environ.get("DCI_EVAL_JUDGE_API_KEY", "").strip()
            or os.environ.get("ASTERION_DCI_JUDGE_API_KEY", "").strip()
            or os.environ.get(judge_key_name, "").strip()
        )
        node_major = self.backend.node_major_version()
        pi_ready = (
            paths.pi.repo_dir.is_dir()
            and paths.pi.package_dir.is_dir()
            and (paths.pi.package_dir / "package.json").is_file()
            and paths.pi.agent_dir.is_dir()
        )
        resolved_corpus = _corpus_root(self.repo_root, corpus_root)
        corpora_ready = all(
            (resolved_corpus / name).is_dir()
            for name in ("wiki_corpus", "bc_plus_docs")
        )
        checks = (
            _check("configuration", "Provider and model configuration is present", configuration_ready),
            _check("corpora", "Both example corpora are available", corpora_ready),
            _check("environment", "The selected environment file is available", environment_ready),
            _check("judge", "Judge configuration and credential are present", judge_ready),
            _check("node", "Node.js major version is at least 20", node_major is not None and node_major >= 20),
            _check("pi", "The external Pi checkout is ready", pi_ready),
        )
        return VerificationResult(
            product_id=DCI_PRODUCT_DESCRIPTION.product_id,
            level="preflight",
            status="PASS" if all(check.status == "PASS" for check in checks) else "FAIL",
            checks=checks,
            provider_backed_operation_count=0,
            full_dataset_ran=False,
        )


def create_dci_product(
    *,
    repo_root: Path | None = None,
    backend: DciVerificationBackend | None = None,
) -> InstalledCapabilityProduct:
    """Build the installed DCI product contract without performing verification."""

    root = Path.cwd().resolve() if repo_root is None else Path(repo_root).resolve()
    acceptance_source_root = (
        Path(repo_root).resolve()
        if repo_root is not None
        else _trusted_source_checkout_root()
    )
    verifier = DciProductVerifier(
        repo_root=root,
        backend=LocalDciVerificationBackend() if backend is None else backend,
        acceptance_source_root=acceptance_source_root,
    )
    return InstalledCapabilityProduct(
        description=DCI_PRODUCT_DESCRIPTION,
        verifier=verifier,
    )


def _trusted_source_checkout_root() -> Path | None:
    """Return only the checkout that physically contains this verifier module."""

    module = Path(__file__).resolve()
    relative_module = Path(
        "asterion/src/asterion/dci/verification.py"
    )
    for candidate in module.parents:
        if (candidate / relative_module).resolve() != module:
            continue
        verifier = candidate / "tools/verify_asterion_dci_product.py"
        acceptance = candidate / "assets/dci/product-acceptance.json"
        if (
            verifier.is_file()
            and not verifier.is_symlink()
            and acceptance.is_file()
            and not acceptance.is_symlink()
        ):
            return candidate
    return None


def _provider_key_name(provider: str | None) -> str | None:
    if provider is None or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", provider) is None:
        return None
    aliases = {"google": "GOOGLE_API_KEY", "gemini": "GOOGLE_API_KEY"}
    return aliases.get(provider.lower(), f"{provider.upper().replace('-', '_')}_API_KEY")


def _corpus_root(repo_root: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    configured = os.environ.get("ASTERION_DCI_CORPUS_ROOT", "").strip()
    if configured:
        path = Path(configured).expanduser()
        return path.resolve() if path.is_absolute() else (repo_root / path).resolve()
    return repo_root / "corpus"


def _check(check_id: str, summary: str, passed: bool) -> VerificationCheckResult:
    return VerificationCheckResult(
        check_id=check_id,
        summary=summary,
        status="PASS" if passed else "FAIL",
    )


def _basic_request(
    case: BasicVerificationCase,
    options: DciRuntimeOptions,
    paths: DciPaths,
    corpus_root: Path,
) -> DciRunRequest:
    return DciRunRequest(
        run_id=case.case_id,
        question=case.question,
        cwd=(corpus_root / case.corpus_subdir).resolve(),
        provider=options.provider,
        model=options.model,
        tools=options.tools,
        max_turns=case.max_turns,
        timeout_seconds=options.timeout_seconds,
        runtime_context_level=options.runtime_context_level,
        thinking_level=case.thinking_level,
        node_max_old_space_size_mb=options.node_max_old_space_size_mb,
        keep_session=False,
        extra_args=options.extra_args,
        pi_package_dir=paths.pi.package_dir,
        pi_agent_dir=paths.pi.agent_dir,
        stream_text=False,
    )


def _complete_result(
    checks: list[VerificationCheckResult],
    *,
    provider_backed_operations: int,
    forced_status: str | None = None,
) -> VerificationResult:
    ordered = tuple(sorted(checks, key=lambda check: check.check_id))
    if forced_status is None:
        status = "PASS" if all(check.status == "PASS" for check in ordered) else "FAIL"
    else:
        status = forced_status if forced_status != "PASS" else (
            "PASS" if all(check.status == "PASS" for check in ordered) else "FAIL"
        )
    return VerificationResult(
        product_id=DCI_PRODUCT_DESCRIPTION.product_id,
        level="complete",
        status=status,
        checks=ordered,
        provider_backed_operation_count=provider_backed_operations,
        full_dataset_ran=False,
    )
