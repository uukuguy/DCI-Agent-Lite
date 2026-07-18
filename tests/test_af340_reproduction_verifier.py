from __future__ import annotations

import importlib.util
import io
import json
import stat
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/verify_af340_reproduction.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_af340_reproduction", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("AF-340 verifier cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecordingExecutor:
    def __init__(self, *, fail_at: int | None = None, kinds: list[str] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail_at = fail_at
        self.kinds = list(kinds or [])

    def __call__(self, command, **_kwargs):
        self.calls.append(tuple(str(value) for value in command))
        kind = self.kinds[len(self.calls) - 1] if self.kinds else "agent-and-judge"
        failed = self.fail_at == len(self.calls)
        return SimpleNamespace(
            status="failed" if failed else "completed",
            agent_operations=int(kind in {"agent", "agent-and-judge"}),
            judge_operations=int(kind in {"judge", "agent-and-judge"}),
            artifacts={
                "effective-config.json": b'{"schema":"test"}\n',
                "stdout.txt": b"private answer body must not be retained",
                "stderr.txt": b"private failure body must not be retained",
            },
        )


class TimeoutExecutor(RecordingExecutor):
    def __call__(self, command, **kwargs):
        self.calls.append(tuple(str(value) for value in command))
        if len(self.calls) == 2:
            raise subprocess.TimeoutExpired(command, 1)
        return SimpleNamespace(
            status="completed", agent_operations=1, judge_operations=1,
            artifacts={"effective-config.json": b"{}\n"},
        )


class NativeArtifactExecutor:
    """Stand in for subprocess.run while writing representative native evidence."""

    def __init__(
        self, *, kinds: list[str] | None = None, fail_at: int | None = None,
        timeout_at: int | None = None,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.kinds = list(kinds or [])
        self.fail_at = fail_at
        self.timeout_at = timeout_at

    def __call__(self, command, **kwargs):
        self.calls.append(tuple(str(value) for value in command))
        if self.timeout_at == len(self.calls):
            raise subprocess.TimeoutExpired(command, 1)
        evidence_root = Path(kwargs["env"]["ASTERION_DCI_OUTPUT_ROOT"])
        run = evidence_root / f"native-{len(self.calls)}"
        run.mkdir(parents=True, mode=0o700)
        run.chmod(0o700)
        if kwargs["env"].get("DCI_RUNTIME") == "claude-code":
            (run / "request.json").write_text(
                json.dumps({"run_id": f"native-{len(self.calls)}"}) + "\n"
            )
            (run / "request.json").chmod(0o600)
            (run / "events.jsonl").write_text(
                json.dumps({"type": "run.started"}) + "\n"
                + json.dumps({"type": "run.completed"}) + "\n"
            )
            (run / "events.jsonl").chmod(0o600)
        else:
            protocol = run / "protocol"
            protocol.mkdir(mode=0o700)
            (protocol / "attempt-0001.request.json").write_text(
                json.dumps({"schema": "dci.protocol-request/v1"}) + "\n",
                encoding="utf-8",
            )
            (protocol / "attempt-0001.request.json").chmod(0o600)
            (run / "state.json").write_text(
                json.dumps({"status": "completed", "attempts": [{"status": "completed"}]})
                + "\n",
                encoding="utf-8",
            )
            (run / "state.json").chmod(0o600)
        (run / "native-config.json").write_text(
            json.dumps({"runtime": kwargs["env"].get("DCI_RUNTIME")}) + "\n",
            encoding="utf-8",
        )
        (run / "native-config.json").chmod(0o600)
        kind = self.kinds[len(self.calls) - 1] if self.kinds else kwargs["env"].get(
            "AF340_TEST_KIND", "agent"
        )
        if "judge" in kind:
            (run / "eval_result.json").write_text(
                json.dumps({"is_correct": True, "judge_request_fingerprint": "a" * 64})
                + "\n",
                encoding="utf-8",
            )
            (run / "eval_result.json").chmod(0o600)
        return subprocess.CompletedProcess(
            command, int(self.fail_at == len(self.calls)),
            stdout="private answer", stderr="private failure body",
        )


class Af340ReproductionVerifierTests(unittest.TestCase):
    @staticmethod
    def _preflight(_args, _root, _plan, environment):
        return SimpleNamespace(
            environment=dict(environment),
            wheel_asterion=Path("/private/fake-wheel/bin/asterion"),
            cleanup_root=None,
        )

    def _run(self, module, argv, **kwargs):
        return module.verify_af340_reproduction_main(
            argv, bounded_preflight=self._preflight, **kwargs
        )
    def _bounded_args(
        self, root: Path, variant: str, *, provider: str | None = None, model: str | None = None
    ) -> list[str]:
        env_file = root / "operator.env"
        env_file.write_text("PLACEHOLDER=value\n", encoding="utf-8")
        args = [
            "bounded",
            "--variant",
            variant,
            "--env-file",
            str(env_file),
            "--output-root",
            str(root / "evidence"),
        ]
        if provider is not None:
            args.extend(("--provider", provider))
        if model is not None:
            args.extend(("--model", model))
        return args

    def test_local_exact_matrix_has_zero_provider_operations(self) -> None:
        module = load_verifier()
        executor = RecordingExecutor()
        stdout = io.StringIO()
        result = module.verify_af340_reproduction_main(
            ["local"], repo_root=ROOT, executor=executor, stdout=stdout
        )
        self.assertEqual(result, 0)
        self.assertEqual(
            tuple(module.LOCAL_CHECK_IDS),
            tuple(call.operation_id for call in module.local_operation_plan(ROOT)),
        )
        self.assertEqual(len(executor.calls), len(module.LOCAL_CHECK_IDS))
        self.assertTrue(all(operation.kind == "local" for operation in module.local_operation_plan(ROOT)))
        self.assertIn("PASS", stdout.getvalue())
        self.assertIn("Agent operations: 0", stdout.getvalue())
        self.assertIn("Judge operations: 0", stdout.getvalue())
        self.assertIn("Full dataset ran: no", stdout.getvalue())

    def test_pi_bounded_matrix_has_exact_22_limit_one_launchers_and_installed_surfaces(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            plan = module.bounded_operation_plan(ROOT, "pi", None, None)
            executor = NativeArtifactExecutor(kinds=[item.kind for item in plan])
            stdout = io.StringIO()
            result = self._run(module,
                self._bounded_args(temporary_root, "pi"),
                repo_root=ROOT,
                executor=executor,
                stdout=stdout,
            )
            self.assertEqual(result, 0)
            launcher_operations = [item for item in plan if item.operation_id.startswith("launcher:")]
            self.assertEqual(len(launcher_operations), 22)
            for operation in launcher_operations:
                self.assertEqual(operation.command.count("--limit"), 1)
                limit_index = operation.command.index("--limit")
                self.assertEqual(operation.command[limit_index + 1], "1")
            ids = {operation.operation_id for operation in plan}
            self.assertTrue(
                {
                    "original:quick-start",
                    "original:context-level3",
                    "original:context-level4",
                    "asterion:pi-quick-start",
                    "asterion:pi-context-level3",
                    "asterion:pi-context-level4",
                    "asterion:installed-pi",
                    "asterion:wheel-pi",
                }.issubset(ids)
            )
            self.assertEqual(
                {
                    item.operation_id: item.kind
                    for item in plan
                    if item.operation_id in {"asterion:installed-pi", "asterion:wheel-pi"}
                },
                {
                    "asterion:installed-pi": "agent-and-judge",
                    "asterion:wheel-pi": "agent-and-judge",
                },
            )
            report_path = temporary_root / "evidence" / "af340-bounded-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["evidence_dimensions"], ["original-pi", "asterion-pi"])
            self.assertEqual(report["agent_operations"], 30)
            self.assertEqual(report["judge_operations"], 16)
            self.assertEqual(stat.S_IMODE((temporary_root / "evidence").stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(report_path.stat().st_mode), 0o600)
            self.assertIn("Agent operations: 30", stdout.getvalue())
            self.assertIn("Judge operations: 16", stdout.getvalue())

    def test_default_bounded_adapter_measures_native_artifacts_and_retains_safe_identity(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            executor = NativeArtifactExecutor()

            def preflight(_args, _root, _plan, environment):
                adjusted = dict(environment)
                adjusted["AF340_TEST_KIND"] = "agent"
                return SimpleNamespace(
                    environment=adjusted,
                    wheel_asterion=Path("/private/fake-wheel/bin/asterion"),
                    cleanup_root=None,
                )

            plan = (
                module.Operation("native-agent", "agent", ("native-agent",)),
            )
            with mock.patch.object(module, "bounded_operation_plan", return_value=plan):
                result = module.verify_af340_reproduction_main(
                    self._bounded_args(temporary_root, "pi"),
                    repo_root=ROOT,
                    executor=executor,
                    bounded_preflight=preflight,
                )
            self.assertEqual(result, 0)
            report = json.loads(
                (temporary_root / "evidence/af340-bounded-report.json").read_text()
            )
            self.assertEqual(report["agent_operations"], 1)
            self.assertEqual(report["judge_operations"], 0)
            config_ref = report["operations"][0]["artifacts"]["effective-config.json"]["ref"]
            safe_config = json.loads(
                (temporary_root / "evidence" / config_ref).read_text(encoding="utf-8")
            )
            self.assertEqual(safe_config["schema"], "dci.af340-effective-config/v1")
            self.assertEqual(safe_config["operation_id"], "native-agent")
            self.assertEqual(safe_config["runtime"]["identity"], "pi.reference")
            self.assertEqual(
                safe_config["runtime"]["authentication_mode"],
                "saved-auth-or-provider-key",
            )
            self.assertEqual(safe_config["actual_counts"], {"agent": 1, "judge": 0})
            self.assertNotIn("private answer", json.dumps(safe_config))
            self.assertRegex(safe_config["rendered_command_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(safe_config["native_artifacts"])

    def test_running_pi_state_never_counts_as_completed_agent_evidence(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            protocol = root / "run/protocol"
            protocol.mkdir(parents=True, mode=0o700)
            request = protocol / "attempt-0001.request.json"
            request.write_text('{"schema":"dci.protocol-request/v1"}\n')
            request.chmod(0o600)
            state = root / "run/state.json"
            state.write_text('{"status":"running","attempts":[{"status":"running"}]}\n')
            state.chmod(0o600)
            result = module._bounded_native_operation_result(
                completed=subprocess.CompletedProcess(("agent",), 0, "", ""),
                before={}, output_root=root,
                operation=module.Operation("agent", "agent", ("agent",)),
                command=("agent",), variant="pi", provider=None, model=None,
            )
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.agent_operations, 0)

    def test_inspect_rejects_rehashed_report_without_genuine_native_refs(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reports = []
            for variant, provider, model in (
                ("pi", None, None),
                ("claude-subscription", None, None),
                ("claude-minimax", "minimax", "MiniMax-M3"),
            ):
                variant_root = root / variant
                variant_root.mkdir()
                plan = module.bounded_operation_plan(ROOT, variant, provider, model)
                executor = NativeArtifactExecutor(kinds=[item.kind for item in plan])
                self.assertEqual(self._run(
                    module,
                    self._bounded_args(variant_root, variant, provider=provider, model=model),
                    repo_root=ROOT, executor=executor,
                ), 0)
                reports.append(variant_root / "evidence/af340-bounded-report.json")
            report_path = reports[0]
            report = json.loads(report_path.read_text())
            operation = report["operations"][0]
            config_identity = operation["artifacts"]["effective-config.json"]
            config_path = report_path.parent / config_identity["ref"]
            config = json.loads(config_path.read_text())
            config["native_artifacts"] = []
            body = json.dumps(config, sort_keys=True).encode() + b"\n"
            config_path.write_bytes(body)
            config_identity["sha256"] = __import__("hashlib").sha256(body).hexdigest()
            unsigned = dict(report)
            unsigned.pop("report_sha256")
            report["report_sha256"] = module._canonical_sha256(unsigned)
            report_path.write_text(json.dumps(report) + "\n")
            args = ["inspect"]
            for item in reports:
                args.extend(("--report", str(item)))
            self.assertEqual(module.verify_af340_reproduction_main(args, repo_root=ROOT), 2)

    def test_injected_operation_result_cannot_self_certify_native_evidence(self) -> None:
        module = load_verifier()
        operation = module.Operation("injected", "agent", ("fake",))
        forged = {
            "schema": "dci.af340-effective-config/v1",
            "operation_id": "injected",
            "kind": "agent",
            "variant": "pi",
            "runtime": module._bounded_runtime_identity("pi", None),
            "provider": None,
            "model": None,
            "command_template_sha256": module._command_sha256(operation.command),
            "rendered_command_sha256": module._command_sha256(operation.command),
            "native_artifacts": [{"artifact": "state.json", "kind": "state.json",
                                  "root_ref": ".", "sha256": "0" * 64}],
            "actual_counts": {"agent": 1, "judge": 0},
            "process": {"status": "completed"},
        }
        projected = module._coordinator_bounded_result(
            module.OperationResult(
                "completed", 1, 0,
                {"effective-config.json": json.dumps(forged).encode(),
                 "state.json": b'{"status":"completed"}\n'},
            ),
            operation=operation,
            command=operation.command,
            variant="pi",
            provider=None,
            model=None,
        )
        config = json.loads(projected.artifacts["effective-config.json"])
        self.assertEqual(config["native_artifacts"], [])
        self.assertNotIn("state.json", projected.artifacts)

    def test_private_tree_validation_rejects_loose_modes_and_symlinks(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "private"
            root.mkdir(mode=0o700)
            loose = root / "loose.json"
            loose.write_text("{}\n")
            loose.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "permissions"):
                module._validate_private_tree(root)
            loose.chmod(0o600)
            (root / "link.json").symlink_to(loose)
            with self.assertRaisesRegex(ValueError, "symlink"):
                module._validate_private_tree(root)

    def test_claude_subscription_and_minimax_are_distinct_installed_wheel_variants(self) -> None:
        module = load_verifier()
        subscription = module.bounded_operation_plan(ROOT, "claude-subscription", None, None)
        minimax = module.bounded_operation_plan(ROOT, "claude-minimax", "minimax", "MiniMax-M3")
        self.assertEqual(
            [item.operation_id for item in subscription],
            ["asterion:installed-claude-subscription", "asterion:wheel-claude-subscription"],
        )
        self.assertEqual(
            [item.operation_id for item in minimax],
            ["asterion:installed-claude-minimax", "asterion:wheel-claude-minimax"],
        )
        self.assertTrue(all(item.command[item.command.index("--provider") + 1] == "dci-agent-lite" for item in subscription))
        self.assertTrue(all("--model" not in item.command for item in subscription))
        for operation in (*subscription, *minimax):
            self.assertIn("dci-agent-lite", operation.command)
            self.assertIn("dci.complete-application@1.0.0", operation.command)
            self.assertIn("claude-code.reference", operation.command)
            self.assertIn("--input", operation.command)
            self.assertNotIn("--output-dir", operation.command)

    def test_h004_hooks_require_bounded_and_authorized_full_inspect_contracts(self) -> None:
        train = (ROOT / "tools/climb/train.sh").read_text(encoding="utf-8")
        evaluate = (ROOT / "tools/climb/eval-local.sh").read_text(encoding="utf-8")
        train_block = train[train.rindex('elif [ "$1" = "AF-340-H-004" ]; then') :]
        train_block = train_block[: train_block.index("elif ", 10)]
        self.assertIn("verify_af340_reproduction.py inspect", train_block)
        self.assertEqual(train_block.count('--report "$AF340_'), 4)
        self.assertIn("verify_af340_reproduction.py inspect-full", train_block)
        self.assertIn('AF340_FULL_REPORT', train_block)
        self.assertNotIn("verify_af340_reproduction.py bounded", train_block)
        evaluation_block = evaluate[evaluate.index("run_af340_evidence_dimension()") : evaluate.index("dimension_runner=", evaluate.index("run_af340_evidence_dimension()"))]
        self.assertIn("verify_af340_reproduction.py inspect", evaluation_block)
        self.assertEqual(evaluation_block.count('--report "$AF340_'), 4)
        self.assertIn("verify_af340_reproduction.py inspect-full", evaluation_block)
        self.assertIn('AF340_FULL_REPORT', evaluation_block)
        self.assertNotIn("--dimension", evaluation_block)

    def test_preflight_failure_stops_before_executor_and_existing_root_has_no_fallback(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executor = RecordingExecutor()
            stderr = io.StringIO()
            result = self._run(module,
                [
                    "bounded",
                    "--variant",
                    "pi",
                    "--env-file",
                    str(root / "missing.env"),
                    "--output-root",
                    str(root / "evidence"),
                ],
                repo_root=ROOT,
                executor=executor,
                stderr=stderr,
            )
            self.assertEqual(result, 2)
            self.assertEqual(executor.calls, [])
            existing = root / "existing"
            existing.mkdir()
            env_file = root / "operator.env"
            env_file.write_text("PLACEHOLDER=value\n", encoding="utf-8")
            result = module.verify_af340_reproduction_main(
                [
                    "full",
                    "--profile",
                    "current-default/pi",
                    "--output-root",
                    str(existing),
                    "--estimated-budget-usd",
                    "1",
                    "--authorize-full",
                ],
                repo_root=ROOT,
                executor=executor,
                stderr=stderr,
            )
            self.assertEqual(result, 2)
            self.assertEqual(executor.calls, [])

    def test_failure_report_preserves_counts_without_command_or_output_bodies(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executor = NativeArtifactExecutor(
                fail_at=2, kinds=["agent-and-judge"] * 2
            )
            result = self._run(module,
                self._bounded_args(root, "claude-subscription"),
                repo_root=ROOT,
                executor=executor,
            )
            self.assertEqual(result, 2)
            report_path = root / "evidence" / "af340-bounded-report.json"
            raw = report_path.read_text(encoding="utf-8")
            report = json.loads(raw)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["attempted_operations"], 2)
            self.assertEqual(report["agent_operations"], 2)
            self.assertEqual(report["judge_operations"], 2)
            for forbidden in (
                "private answer body",
                "private failure body",
                str(root),
                '"command":',
                '"argv":',
                "api_key",
                "credential",
                "prompt",
                "answer",
                "body",
            ):
                self.assertNotIn(forbidden, raw.lower())

    def test_timeout_is_retained_body_free_and_stops_the_plan(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executor = NativeArtifactExecutor(
                timeout_at=2, kinds=["agent-and-judge"] * 2
            )
            self.assertEqual(
                self._run(module,
                    self._bounded_args(root, "claude-subscription"),
                    repo_root=ROOT,
                    executor=executor,
                ),
                2,
            )
            report = json.loads(
                (root / "evidence/af340-bounded-report.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(report["status"], "timed_out")
            self.assertEqual(
                [item["status"] for item in report["operations"]],
                ["completed", "timed_out"],
            )
            self.assertEqual(len(executor.calls), 2)

    def test_full_dry_run_prints_profile_budget_and_maxima_without_authority_or_executor(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            executor = RecordingExecutor()
            stdout = io.StringIO()
            result = module.verify_af340_reproduction_main(
                [
                    "full",
                    "--profile",
                    "current-default/pi",
                    "--output-root",
                    str(Path(temporary) / "full"),
                    "--estimated-budget-usd",
                    "12.5",
                    "--dry-run",
                ],
                repo_root=ROOT,
                executor=executor,
                stdout=stdout,
            )
            self.assertEqual(result, 0)
            self.assertEqual(executor.calls, [])
            self.assertFalse((Path(temporary) / "full").exists())
            for expected in (
                "Profile: current-default/pi",
                "Profile SHA-256:",
                "Datasets: 13",
                "Experiment scopes: 16",
                "Selected queries:",
                "Maximum agent operations:",
                "Maximum Judge operations:",
                "Estimated budget USD: 12.5",
                "Full authorization issued: no",
                "Full dataset ran: no",
            ):
                self.assertIn(expected, stdout.getvalue())
            self.assertIn("Maximum agent operations: 3956", stdout.getvalue())
            self.assertIn("Maximum Judge operations: 2910", stdout.getvalue())

    def test_authorized_full_uses_task6_capability_before_injected_runner(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary) / "full"
            received = []

            def full_runner(authorizations, profile, _repo_root, _executor, _comparator):
                received.append((authorizations, profile))
                return module.FullRunResult(
                    agent_operations=0, judge_operations=0, full_dataset_ran=True
                )

            stdout = io.StringIO()
            result = module.verify_af340_reproduction_main(
                [
                    "full",
                    "--profile",
                    "current-default/pi",
                    "--output-root",
                    str(output_root),
                    "--estimated-budget-usd",
                    "0",
                    "--authorize-full",
                ],
                repo_root=ROOT,
                full_runner=full_runner,
                full_preflight=lambda *_args: None,
                stdout=stdout,
            )
            self.assertEqual(result, 0)
            self.assertEqual(len(received), 1)
            authorizations, profile = received[0]
            self.assertEqual(set(authorizations), {"original-dci", "asterion-dci"})
            for by_scope in authorizations.values():
                self.assertEqual(len(by_scope), 16)
                for authorization in by_scope.values():
                    self.assertEqual(authorization.profile_id, "current-default/pi")
                    self.assertTrue(authorization.invocation_authorized)
            self.assertEqual(profile.profile_id, "current-default/pi")
            self.assertEqual(stat.S_IMODE(output_root.stat().st_mode), 0o700)
            self.assertNotEqual(
                next(iter(authorizations["original-dci"].values())).output_root.parent,
                next(iter(authorizations["asterion-dci"].values())).output_root.parent,
            )
            self.assertIn("Full authorization issued: yes", stdout.getvalue())

    def test_default_full_runner_consumes_two_task6_roots_and_compares_all_scopes(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from asterion.dci.paper_benchmarks import (
            require_af320_executable_scope,
            resolve_paper_benchmark,
            resolve_paper_experiment_scope,
        )

        requests = []
        comparisons = []

        def scope_executor(request):
            requests.append(request)
            require_af320_executable_scope(request.scope_id, request.authorization)
            scope = resolve_paper_experiment_scope(request.scope_id)
            benchmark = resolve_paper_benchmark(scope.dataset_id)
            return module.FullScopeResult(
                scope.selection_count,
                scope.selection_count if benchmark.mode == "qa" else 0,
                SimpleNamespace(product=request.product, scope_id=request.scope_id),
            )

        def comparator(baseline, candidate, profile):
            comparisons.append((baseline, candidate, profile.profile_id))
            return SimpleNamespace(identity_sha256="0" * 64)

        with tempfile.TemporaryDirectory() as temporary:
            output_root = Path(temporary) / "full"
            stdout = io.StringIO()
            self.assertEqual(
                module.verify_af340_reproduction_main(
                    [
                        "full", "--profile", "current-default/pi",
                        "--output-root", str(output_root),
                        "--estimated-budget-usd", "0", "--authorize-full",
                    ],
                    repo_root=ROOT,
                    executor=scope_executor,
                    full_preflight=lambda *_args: None,
                    full_comparator=comparator,
                    stdout=stdout,
                ),
                0,
            )
            self.assertEqual(len(requests), 32)
            self.assertEqual(len(comparisons), 16)
            self.assertTrue(all(item[0] is not None for item in comparisons))
            self.assertTrue(all(request.output_root == request.authorization.output_root for request in requests))
            self.assertIn("Agent operations: 3956", stdout.getvalue())
            self.assertIn("Judge operations: 2910", stdout.getvalue())
            self.assertIn("Full dataset ran: yes", stdout.getvalue())

    def test_rejected_full_comparison_is_retained_then_fails_overall(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scope_id = "qa.nq.main.random50"
            original = SimpleNamespace(output_root=root / "original" / scope_id)
            candidate = SimpleNamespace(output_root=root / "asterion" / scope_id)
            original.output_root.mkdir(parents=True)
            candidate.output_root.mkdir(parents=True)
            profile = SimpleNamespace(scope_ids=(scope_id,), runtime="pi")

            def executor(request):
                return module.FullScopeResult(50, 50, SimpleNamespace(product=request.product))

            comparison = SimpleNamespace(accepted=False, to_dict=lambda: {})

            def retained_writer(path, _comparison):
                path.write_text('{"accepted":false}\n')

            with mock.patch(
                "asterion.dci.reproduction.write_comparison_report",
                side_effect=retained_writer,
            ), self.assertRaisesRegex(ValueError, "comparison-not-accepted"):
                module._default_full_runner(
                    {
                        "original-dci": {scope_id: original},
                        "asterion-dci": {scope_id: candidate},
                    },
                    profile,
                    ROOT,
                    executor,
                    lambda *_args: comparison,
                )
            retained = root / "comparisons" / f"{scope_id}.json"
            self.assertTrue(retained.is_file())

    def test_claude_full_runner_is_target_only(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from asterion.dci.paper_benchmarks import require_af320_executable_scope

        requests = []
        comparisons = []

        def scope_executor(request):
            requests.append(request)
            require_af320_executable_scope(request.scope_id, request.authorization)
            return module.FullScopeResult(1, 0, SimpleNamespace(product=request.product))

        def comparator(baseline, candidate, _profile):
            comparisons.append((baseline, candidate))
            return object()

        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(
                module.verify_af340_reproduction_main(
                    [
                        "full", "--profile", "current-default/claude-subscription",
                        "--output-root", str(Path(temporary) / "full"),
                        "--estimated-budget-usd", "0", "--authorize-full",
                    ],
                    repo_root=ROOT, executor=scope_executor,
                    full_preflight=lambda *_args: None,
                    full_comparator=comparator,
                ),
                0,
            )
            self.assertEqual(len(requests), 16)
            self.assertTrue(all(request.product == "asterion-dci" for request in requests))
            self.assertTrue(all(baseline is None for baseline, _candidate in comparisons))

    def test_original_and_asterion_native_artifacts_normalize_to_strict_body_free_manifests(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from asterion.dci.experiment_profiles import resolve_experiment_profile
        from asterion.dci.paper_benchmarks import published_scope_selected_ids

        profile = resolve_experiment_profile("current-default/pi")
        scope_id = "qa.nq.main.random50"
        query_id = sorted(published_scope_selected_ids(scope_id))[0]
        private_body = "TOP SECRET ANSWER BODY"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            manifests = []
            for product in ("original-dci", "asterion-dci"):
                output = base / product
                output.mkdir(mode=0o700)
                judge_config = {
                    "judge_base_url": profile.judge["base_url"],
                    "judge_api": profile.judge["api"],
                    "judge_model": profile.judge["model"],
                    "judge_api_key_env": profile.judge["key_source"],
                    "judge_thinking": "disabled",
                    "judge_json_mode": True,
                    "judge_strict_json_schema": False,
                    "judge_responses_store": False,
                }
                config = (
                    {
                        "provider": profile.provider, "model": profile.model,
                        "tools": profile.tools, "max_turns": profile.max_turns,
                        "runtime_context_level": profile.context_profile,
                        "pi_thinking_level": profile.reasoning, **judge_config,
                    }
                    if product == "original-dci"
                    else {
                        "schema": "asterion.dci.batch/v1",
                        "max_turns": profile.max_turns,
                        "runtime": {
                            "provider": profile.provider, "model": profile.model,
                            "tools": profile.tools,
                            "runtime_context_level": profile.context_profile,
                            "thinking_level": profile.reasoning,
                        },
                        "judge": judge_config,
                    }
                )
                (output / "config.json").write_text(
                    json.dumps(config) + "\n",
                    encoding="utf-8",
                )
                if product == "original-dci":
                    (output / "effective-config.json").write_text(
                        json.dumps(
                            {
                                "schema": "dci.effective-config/v1",
                                "product": "original-dci",
                                "runtime": "pi",
                                "agent": {
                                    "provider": profile.provider,
                                    "model": profile.model,
                                    "reasoning": profile.reasoning,
                                    "tools": profile.tools,
                                    "max_turns": profile.max_turns,
                                },
                            }
                        ) + "\n"
                    )
                native = {
                    "query_id": query_id,
                    "run_status": "completed",
                    "request_count": 1,
                    "is_correct": True,
                    "ndcg_at_10": None,
                    "agent_usage": {
                        "input_tokens": 11,
                        "cache_read_tokens": 3,
                        "cache_write_tokens": 2,
                        "output_tokens": 5,
                        "total_tokens": 21,
                        "cost_total": 0.25,
                    },
                    "judge_usage": {"input_tokens": 7, "output_tokens": 2},
                    "judge_cost_estimate_usd": {"total_cost": 0.5},
                    "final_text": private_body,
                }
                if product == "original-dci":
                    (output / "results.jsonl").write_text(
                        json.dumps(native) + "\n", encoding="utf-8"
                    )
                    metric_row = {
                        "query_id": query_id,
                        "run_status": "completed",
                        "is_correct": True,
                        "ndcg_at_10": None,
                        "agent_total_tokens": 21,
                        "judge_total_tokens": 9,
                        "overall_cost_total": 0.75,
                        "final_text": private_body,
                    }
                    (output / "analysis.json").write_text(
                        json.dumps(
                            {
                                "generated_at": "2026-01-01T00:00:00Z",
                                "cost_efficiency": {},
                                "slices": {},
                                "tool_summary": {},
                                "rankings": {},
                                "incorrect_queries": [],
                                "per_query_metrics": [metric_row],
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                else:
                    (output / "analysis.jsonl").write_text(
                        json.dumps(native) + "\n", encoding="utf-8"
                    )
                (output / "summary.json").write_text(
                    json.dumps(
                        {"counts": {"total": 1, "judged": 1, "failed_runs": 0}}
                    ) + "\n",
                    encoding="utf-8",
                )
                request = module.FullScopeRequest(
                    product, scope_id, object(), output, profile, ROOT
                )
                manifest = module.normalize_full_scope_manifest(request)
                manifests.append(manifest)
                self.assertEqual(manifest.product, product)
                self.assertEqual(manifest.aggregates.query_count, 50)
                self.assertEqual(manifest.aggregates.completed_count, 1)
                self.assertEqual(manifest.aggregates.missing_count, 49)
                self.assertEqual(manifest.aggregates.agent_operations, 1)
                self.assertEqual(manifest.aggregates.judge_operations, 1)
                self.assertEqual(manifest.aggregates.input_tokens, 18)
                self.assertEqual(manifest.aggregates.cached_input_tokens, 5)
                self.assertEqual(manifest.aggregates.output_tokens, 7)
                self.assertEqual(manifest.aggregates.cost_usd, 0.75)
                raw = (output / "af340-run-manifest.json").read_text(encoding="utf-8")
                self.assertNotIn(private_body, raw)
                self.assertEqual(stat.S_IMODE((output / "af340-run-manifest.json").stat().st_mode), 0o600)
            self.assertEqual(manifests[0].effective_config_sha256, manifests[1].effective_config_sha256)
            self.assertNotEqual(
                manifests[0].product_effective_config_sha256,
                manifests[1].product_effective_config_sha256,
            )

    def test_production_scope_adapters_are_recordable_without_provider_calls(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from asterion.dci.experiment_profiles import (
            authorize_full_execution,
            experiment_profile_sha256,
            resolve_experiment_profile,
        )
        from asterion.dci.paper_benchmarks import (
            published_scope_selected_ids,
            require_af320_executable_scope,
            resolve_paper_benchmark,
            resolve_paper_experiment_scope,
        )

        profile = resolve_experiment_profile("current-default/pi")
        scope_id = "qa.nq.main.random50"
        index = profile.scope_ids.index(scope_id)
        query_id = sorted(published_scope_selected_ids(scope_id))[0]

        def native_row():
            return {
                "query_id": query_id, "run_status": "completed", "request_count": 1,
                "is_correct": True,
                "ndcg_at_10": None,
                "agent_usage": {"input_tokens": 1, "output_tokens": 1},
                "judge_usage": {"input_tokens": 1, "output_tokens": 1},
                "judge_cost_estimate_usd": {"total_cost": 0},
            }

        def authorization(output):
            return authorize_full_execution(
                profile.profile_id, output, 0, True,
                preflight_profile_sha256=experiment_profile_sha256(profile.profile_id),
                preflight_dataset_inventory_sha256=profile.dataset_inventory_sha256,
                preflight_experiment_scopes_sha256=profile.experiment_scopes_sha256,
                preflight_scope_ids=(scope_id,),
                preflight_selected_ids_sha256=(profile.selected_ids_sha256[index],),
            )

        def materializer(request):
            scope = resolve_paper_experiment_scope(scope_id)
            benchmark = resolve_paper_benchmark(scope.dataset_id)
            staging = base / f"staging-{request.product}"
            staging.mkdir(exist_ok=True)
            dataset = staging / "selected-dataset.jsonl"
            dataset.write_text(
                json.dumps({"query_id": query_id, "query": "q", "answer": "a"}) + "\n"
            )
            return dataset, scope, benchmark

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            original_auth = authorization(base / "original")
            commands = []
            process_environments = []
            process_kwargs = []

            def process_executor(command, **kwargs):
                commands.append(tuple(command))
                process_environments.append(kwargs["env"])
                process_kwargs.append(kwargs)
                original_auth.output_root.joinpath("config.json").write_text(
                    json.dumps(
                        {
                            "provider": profile.provider, "model": profile.model,
                            "tools": profile.tools, "max_turns": profile.max_turns,
                            "runtime_context_level": profile.context_profile,
                            "pi_thinking_level": profile.reasoning,
                            "judge_base_url": profile.judge["base_url"],
                            "judge_api": profile.judge["api"],
                            "judge_model": profile.judge["model"],
                            "judge_api_key_env": profile.judge["key_source"],
                            "judge_thinking": "disabled",
                            "judge_json_mode": True,
                            "judge_strict_json_schema": False,
                            "judge_responses_store": False,
                        }
                    ) + "\n"
                )
                original_auth.output_root.joinpath("effective-config.json").write_text(
                    json.dumps(
                        {
                            "schema": "dci.effective-config/v1",
                            "product": "original-dci",
                            "runtime": "pi",
                            "agent": {
                                "provider": profile.provider,
                                "model": profile.model,
                                "reasoning": profile.reasoning,
                                "tools": profile.tools,
                                "max_turns": profile.max_turns,
                            },
                        }
                    ) + "\n"
                )
                original_auth.output_root.joinpath("results.jsonl").write_text(
                    json.dumps(native_row()) + "\n"
                )
                original_auth.output_root.joinpath("analysis.json").write_text(
                    json.dumps(
                        {
                            "generated_at": "2026-01-01T00:00:00Z",
                            "cost_efficiency": {}, "slices": {}, "tool_summary": {},
                            "rankings": {}, "incorrect_queries": [],
                            "per_query_metrics": [native_row()],
                        }
                    ) + "\n"
                )
                original_auth.output_root.joinpath("summary.json").write_text(
                    json.dumps({"counts": {"total": 1, "judged": 1, "failed_runs": 0}})
                    + "\n"
                )
                return subprocess.CompletedProcess(command, 0, stdout="private", stderr="")

            original_result = module.production_full_scope_executor(
                module.FullScopeRequest(
                    "original-dci", scope_id, original_auth,
                    original_auth.output_root, profile, ROOT,
                ),
                process_executor=process_executor,
                dataset_materializer=materializer,
            )
            self.assertEqual(original_result.manifest.product, "original-dci")
            self.assertEqual(len(commands), 1)
            self.assertEqual(process_kwargs[0]["umask"], 0o077)
            self.assertIn("scripts/bcplus_eval/run_bcplus_eval.py", commands[0])
            self.assertNotIn("asterion-dci", commands[0])
            self.assertIn(str(original_auth.output_root), commands[0])
            for flag, expected in (
                ("--judge-base-url", profile.judge["base_url"]),
                ("--judge-api", profile.judge["api"]),
                ("--judge-model", profile.judge["model"]),
                ("--judge-api-key-env", profile.judge["key_source"]),
            ):
                self.assertEqual(commands[0][commands[0].index(flag) + 1], expected)
            self.assertEqual(process_environments[0]["DCI_EVAL_JUDGE_THINKING"], "disabled")
            self.assertEqual(
                process_environments[0]["DCI_EVAL_JUDGE_STRICT_JSON_SCHEMA"],
                "false",
            )
            selected_dataset = Path(commands[0][commands[0].index("--dataset") + 1])
            self.assertNotEqual(selected_dataset.parent, original_auth.output_root)

            asterion_auth = authorization(base / "asterion")
            captured = []

            def asterion_runner(request, *, paths):
                captured.append((request, paths))
                require_af320_executable_scope(scope_id, request.full_execution_authorization)
                request.output_root.joinpath("config.json").write_text(
                    json.dumps(
                        {
                            "schema": "asterion.dci.batch/v1",
                            "max_turns": profile.max_turns,
                            "runtime": {
                                "provider": profile.provider, "model": profile.model,
                                "tools": profile.tools,
                                "runtime_context_level": profile.context_profile,
                                "thinking_level": profile.reasoning,
                            },
                            "judge": {
                                "judge_base_url": profile.judge["base_url"],
                                "judge_api": profile.judge["api"],
                                "judge_model": profile.judge["model"],
                                "judge_api_key_env": profile.judge["key_source"],
                                "judge_thinking": "disabled",
                                "judge_json_mode": True,
                                "judge_strict_json_schema": False,
                                "judge_responses_store": False,
                            },
                        }
                    ) + "\n"
                )
                request.output_root.joinpath("analysis.jsonl").write_text(
                    json.dumps(native_row()) + "\n"
                )
                request.output_root.joinpath("summary.json").write_text(
                    json.dumps({"counts": {"total": 1, "judged": 1, "failed_runs": 0}})
                    + "\n"
                )
                return SimpleNamespace(output_root=request.output_root)

            with mock.patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-only"}):
                asterion_result = module.production_full_scope_executor(
                    module.FullScopeRequest(
                        "asterion-dci", scope_id, asterion_auth,
                        asterion_auth.output_root, profile, ROOT,
                    ),
                    asterion_runner=asterion_runner,
                    dataset_materializer=materializer,
                )
            self.assertEqual(asterion_result.manifest.product, "asterion-dci")
            self.assertEqual(len(captured), 1)
            self.assertEqual(captured[0][0].full_execution_authorization, asterion_auth)
            self.assertEqual(captured[0][0].output_root, asterion_auth.output_root)
            self.assertNotEqual(captured[0][0].dataset.parent, asterion_auth.output_root)
            from asterion.dci.reproduction import compare_reproduction_runs
            comparison = compare_reproduction_runs(
                original_result.manifest, asterion_result.manifest, profile
            )
            self.assertEqual(comparison.dataset_id, "qa.nq")

    def test_paper_pi_asterion_adapter_transports_high_reasoning(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from asterion.dci.experiment_profiles import resolve_experiment_profile

        profile = resolve_experiment_profile("paper-reference/pi")
        captured = []

        def runner(request, *, paths):
            captured.append((request, paths))
            return SimpleNamespace(output_root=request.output_root)

        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(
            "os.environ", {"OPENAI_API_KEY": "test-only"}, clear=True
        ), mock.patch.object(
            module,
            "normalize_full_scope_manifest",
            return_value=SimpleNamespace(queries=()),
        ):
            output = Path(temporary) / "scope"
            output.mkdir(mode=0o700)
            module._execute_production_full_scope(
                module.FullScopeRequest(
                    "asterion-dci", "qa.nq.main.random50", object(), output,
                    profile, ROOT,
                ),
                Path(temporary) / "dataset.jsonl",
                SimpleNamespace(corpus_path="corpus/wiki_corpus", mode="qa", batch_profile=None),
                process_executor=subprocess.run,
                asterion_runner=runner,
            )
        self.assertEqual(captured[0][0].runtime_options.thinking_level, "high")

    def test_all_sixteen_full_scopes_route_through_af320_selection_verification(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from asterion.dci.experiment_profiles import resolve_experiment_profile
        from asterion.dci.paper_benchmarks import (
            resolve_paper_benchmark,
            resolve_paper_experiment_scope,
        )

        profile = resolve_experiment_profile("current-default/pi")
        calls = []

        def selector(scope_id, source_ids):
            calls.append((scope_id, len(source_ids)))
            scope = resolve_paper_experiment_scope(scope_id)
            return tuple(sorted(source_ids)[: scope.selection_count])

        for scope_id in profile.scope_ids:
            scope = resolve_paper_experiment_scope(scope_id)
            benchmark = resolve_paper_benchmark(scope.dataset_id)
            rows = tuple(
                {"query_id": f"source-{index}"}
                for index in range(benchmark.source_count)
            )
            with mock.patch.object(Path, "is_file", return_value=True), mock.patch.object(module, "_source_dataset_rows", return_value=rows), mock.patch(
                "asterion.dci.paper_benchmarks.select_and_verify_scope_ids",
                side_effect=selector,
            ):
                selected = module._scope_selection(ROOT, scope, benchmark)
            self.assertEqual(len(selected), scope.selection_count)
        self.assertEqual(
            [scope_id for scope_id, _count in calls],
            list(profile.scope_ids),
        )

    def test_full_preflight_loads_dotenv_nonoverriding_and_uses_profile_exact_keys(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from dataclasses import replace
        from asterion.dci.experiment_profiles import resolve_experiment_profile

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "pi/packages/coding-agent").mkdir(parents=True)
            (root / "pi/.pi/agent").mkdir(parents=True)
            (root / ".env").write_text(
                "OPENAI_API_KEY=file-paper\nDEEPSEEK_API_KEY=file-judge\n"
                "MINIMAX_CN_API_KEY=file-minimax\n",
                encoding="utf-8",
            )
            paper = replace(
                resolve_experiment_profile("paper-reference/pi"), scope_ids=()
            )
            minimax = replace(
                resolve_experiment_profile(
                    "current-default/claude-minimax",
                    invocation_provider="minimax-cn",
                    invocation_model="MiniMax-M3",
                ),
                scope_ids=(),
            )
            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "process-paper"}, clear=True):
                environment = module._root_environment(root)
                self.assertEqual(environment["OPENAI_API_KEY"], "process-paper")
                module._full_execution_preflight(SimpleNamespace(), root, paper)
                with mock.patch("shutil.which", return_value="/usr/bin/claude"):
                    module._full_execution_preflight(SimpleNamespace(), root, minimax)

    def test_bounded_pi_auth_preflight_fails_before_any_process(self) -> None:
        module = load_verifier()
        args = SimpleNamespace(variant="pi", provider=None, model=None)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "pi/packages/coding-agent").mkdir(parents=True)
            (root / "pi/.pi/agent").mkdir(parents=True)
            environment = {
                "DEEPSEEK_API_KEY": "judge-only",
                "DCI_PI_DIR": str(root / "pi"),
                "DCI_PROVIDER": "openai-codex",
            }
            with mock.patch(
                "asterion.dci.paper_benchmarks.paper_benchmark_ids", return_value=()
            ), mock.patch("subprocess.run") as process:
                with self.assertRaisesRegex(ValueError, "credential|auth"):
                    module._default_bounded_preflight(args, root, (), environment)
            process.assert_not_called()

    def test_pi_saved_auth_must_match_selected_provider_and_have_a_credential(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            agent = Path(temporary)
            auth = agent / "auth.json"
            auth.write_text(json.dumps({"wrong-provider": {"type": "oauth", "access": "x"}}))
            self.assertFalse(module._pi_auth_ready(agent, "openai-codex", {}))
            auth.write_text(json.dumps({"openai-codex": {"type": "oauth"}}))
            self.assertFalse(module._pi_auth_ready(agent, "openai-codex", {}))
            auth.write_text(
                json.dumps({"openai-codex": {"type": "oauth", "access": "expired",
                                              "expires": 0}})
            )
            self.assertFalse(module._pi_auth_ready(agent, "openai-codex", {}))
            auth.write_text(
                json.dumps({"openai-codex": {"type": "oauth", "refresh": "saved-token"}})
            )
            self.assertTrue(module._pi_auth_ready(agent, "openai-codex", {}))

    def test_bounded_subscription_checks_login_before_build_or_adapter(self) -> None:
        module = load_verifier()
        args = SimpleNamespace(
            variant="claude-subscription", provider=None, model=None
        )
        calls = []

        def process(command, **_kwargs):
            calls.append(tuple(command))
            return subprocess.CompletedProcess(
                command, 1, stdout='{"loggedIn":false}', stderr=""
            )

        with mock.patch(
            "asterion.dci.paper_benchmarks.paper_benchmark_ids", return_value=()
        ), mock.patch("shutil.which", return_value="/tool/claude"), mock.patch(
            "subprocess.run", side_effect=process
        ):
            with self.assertRaisesRegex(ValueError, "auth|login"):
                module._default_bounded_preflight(
                    args, ROOT, (), {"DEEPSEEK_API_KEY": "judge-only"}
                )
        self.assertEqual(calls, [("/tool/claude", "auth", "status", "--json")])

    def test_full_preflight_auth_checks_finish_before_scope_or_provider_work(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from dataclasses import replace
        from asterion.dci.experiment_profiles import resolve_experiment_profile

        subscription = replace(
            resolve_experiment_profile("current-default/claude-subscription"),
            scope_ids=(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text("DEEPSEEK_API_KEY=judge-only\n")
            auth_call = subprocess.CompletedProcess(
                ("claude",), 1, stdout='{"loggedIn":false}', stderr=""
            )
            with mock.patch("shutil.which", return_value="/tool/claude"), mock.patch(
                "subprocess.run", return_value=auth_call
            ) as process:
                with self.assertRaisesRegex(ValueError, "authentication"):
                    module._full_execution_preflight(SimpleNamespace(), root, subscription)
            self.assertEqual(
                process.call_args.args[0],
                ("/tool/claude", "auth", "status", "--json"),
            )

        minimax = replace(
            resolve_experiment_profile(
                "current-default/claude-minimax",
                invocation_provider="minimax-cn",
                invocation_model="MiniMax-M3",
            ),
            scope_ids=(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text(
                "DEEPSEEK_API_KEY=judge\nMINIMAX_API_KEY=competing\n"
                "MINIMAX_CN_API_KEY=selected\n"
            )
            with mock.patch("shutil.which", return_value="/tool/claude"), mock.patch(
                "subprocess.run"
            ) as process:
                with self.assertRaisesRegex(ValueError, "credential"):
                    module._full_execution_preflight(SimpleNamespace(), root, minimax)
            process.assert_not_called()

    def test_pi_full_preflight_uses_configured_external_checkout(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from dataclasses import replace
        from asterion.dci.experiment_profiles import resolve_experiment_profile

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            external = root / "external-pi"
            (external / "packages/coding-agent").mkdir(parents=True)
            (external / ".pi/agent").mkdir(parents=True)
            (root / ".env").write_text(f"DCI_PI_DIR={external}\n", encoding="utf-8")
            profile = replace(resolve_experiment_profile("paper-reference/pi"), scope_ids=())
            with mock.patch.dict(
                "os.environ", {"OPENAI_API_KEY": "test-only"}, clear=True
            ):
                module._full_execution_preflight(SimpleNamespace(), root, profile)

    def test_pi_full_preflight_rejects_unusable_saved_auth_before_scope_work(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from dataclasses import replace
        from asterion.dci.experiment_profiles import resolve_experiment_profile

        profile = replace(resolve_experiment_profile("current-default/pi"), scope_ids=())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "pi/packages/coding-agent").mkdir(parents=True)
            agent = root / "pi/.pi/agent"
            agent.mkdir(parents=True)
            (agent / "auth.json").write_text("{}\n")
            (root / ".env").write_text("DEEPSEEK_API_KEY=judge-only\n")
            with mock.patch("subprocess.run") as process:
                with self.assertRaisesRegex(ValueError, "authentication"):
                    module._full_execution_preflight(SimpleNamespace(), root, profile)
            process.assert_not_called()

    def test_shared_pi_path_resolution_uses_passed_merged_environment(self) -> None:
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from asterion.dci.config import resolve_dci_paths

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            configured = root / "configured-pi"
            with mock.patch.dict(
                "os.environ", {"DCI_PI_DIR": str(root / "wrong-pi")}, clear=True
            ):
                paths = resolve_dci_paths(
                    root, environment={"DCI_PI_DIR": str(configured)}
                )
            self.assertEqual(paths.pi.repo_dir, configured.resolve())
            self.assertEqual(
                paths.pi.package_dir,
                (configured / "packages/coding-agent").resolve(),
            )

    def test_minimax_cn_bounded_preflight_accepts_only_exact_key_source(self) -> None:
        module = load_verifier()
        args = SimpleNamespace(
            variant="claude-minimax", provider="minimax-cn", model="MiniMax-M3"
        )
        environment = {
            "DEEPSEEK_API_KEY": "test-judge",
            "MINIMAX_CN_API_KEY": "test-cn",
        }
        with mock.patch("shutil.which", return_value="/usr/bin/claude"), mock.patch(
            "asterion.dci.paper_benchmarks.paper_benchmark_ids", return_value=()
        ), mock.patch("tempfile.mkdtemp", side_effect=RuntimeError("past credential checks")):
            with self.assertRaisesRegex(RuntimeError, "past credential checks"):
                module._default_bounded_preflight(args, ROOT, (), environment)
        with mock.patch(
            "asterion.dci.paper_benchmarks.paper_benchmark_ids", return_value=()
        ):
            with self.assertRaisesRegex(ValueError, "credential"):
                module._default_bounded_preflight(
                    args,
                    ROOT,
                    (),
                    {**environment, "MINIMAX_API_KEY": "competing-key"},
                )

    def test_claude_full_uses_installed_application_runtime_and_native_evidence(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from asterion.dci.experiment_profiles import (
            authorize_full_execution,
            experiment_profile_sha256,
            resolve_experiment_profile,
        )
        from asterion.dci.paper_benchmarks import (
            published_scope_selected_ids,
            resolve_paper_benchmark,
            resolve_paper_experiment_scope,
        )

        profile = resolve_experiment_profile("current-default/claude-subscription")
        scope_id = "qa.nq.main.random50"
        index = profile.scope_ids.index(scope_id)
        query_id = sorted(published_scope_selected_ids(scope_id))[0]
        commands = []

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            authorization = authorize_full_execution(
                profile.profile_id,
                base / "claude",
                0,
                True,
                preflight_profile_sha256=experiment_profile_sha256(profile.profile_id),
                preflight_dataset_inventory_sha256=profile.dataset_inventory_sha256,
                preflight_experiment_scopes_sha256=profile.experiment_scopes_sha256,
                preflight_scope_ids=(scope_id,),
                preflight_selected_ids_sha256=(profile.selected_ids_sha256[index],),
            )

            def materializer(_request):
                scope = resolve_paper_experiment_scope(scope_id)
                benchmark = resolve_paper_benchmark(scope.dataset_id)
                staging = base / "staging-claude"
                staging.mkdir()
                dataset = staging / "selected-dataset.jsonl"
                dataset.write_text(
                    json.dumps({"query_id": query_id, "query": "q", "answer": "a"})
                    + "\n"
                )
                return dataset, scope, benchmark

            def process_executor(command, **kwargs):
                commands.append(tuple(command))
                self.assertEqual(kwargs["umask"], 0o077)
                self.assertEqual(
                    kwargs["env"]["DCI_MODEL"],
                    "" if profile.model is None else profile.model,
                )
                self.assertEqual(kwargs["env"]["DCI_TOOLS"], profile.tools)
                self.assertEqual(
                    kwargs["env"]["DCI_PI_THINKING_LEVEL"],
                    "" if profile.reasoning is None else profile.reasoning,
                )
                self.assertEqual(
                    kwargs["env"]["DCI_RUNTIME_CONTEXT_LEVEL"], profile.context_profile
                )
                run_id = command[command.index("--run-id") + 1]
                native = Path(kwargs["env"]["ASTERION_CLAUDE_OUTPUT_ROOT"]) / __import__(
                    "hashlib"
                ).sha256(run_id.encode()).hexdigest()
                native.mkdir(parents=True)
                (native / "events.jsonl").write_text(
                    "\n".join(
                        json.dumps(row)
                        for row in (
                            {"type": "run.started", "payload": {}},
                            {"type": "usage.reported", "payload": {"input_tokens": 3, "output_tokens": 2}},
                            {"type": "run.completed", "payload": {"status": "completed"}},
                        )
                    ) + "\n"
                )
                (native / "final.txt").write_text("answer\n")
                (native / "runtime-policy.json").write_text(
                    json.dumps(
                        {
                            "agent_model": profile.model,
                            "reasoning": profile.reasoning,
                            "tools": ["Read", "Grep"],
                            "context_profile": profile.context_profile,
                            "max_turns": profile.max_turns,
                        }
                    )
                    + "\n"
                )
                return subprocess.CompletedProcess(command, 0, stdout='{"status":"completed"}', stderr="")

            verdict = {
                "is_correct": True,
                "judge_request_fingerprint": "b" * 64,
                "usage": {"input_tokens": 5, "output_tokens": 1},
                "cost_estimate_usd": {"total_cost": 0.0},
            }
            with mock.patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-only"}), mock.patch(
                "asterion.dci.judge.judge_answer_sync", return_value=verdict
            ):
                result = module.production_full_scope_executor(
                    module.FullScopeRequest(
                        "asterion-dci", scope_id, authorization,
                        authorization.output_root, profile, ROOT,
                    ),
                    process_executor=process_executor,
                    dataset_materializer=materializer,
                )
            self.assertEqual(result.agent_operations, 1)
            self.assertEqual(result.judge_operations, 1)
            self.assertEqual(len(commands), 1)
            self.assertIn("dci.research-capability@1.0.0", commands[0])
            self.assertIn("claude-code.reference", commands[0])
            self.assertNotIn("asterion-dci", commands[0])
            self.assertTrue((authorization.output_root / "analysis.jsonl").is_file())

    def test_full_never_falls_back_without_explicit_authority(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            executor = RecordingExecutor()
            result = module.verify_af340_reproduction_main(
                [
                    "full",
                    "--profile",
                    "current-default/pi",
                    "--output-root",
                    str(Path(temporary) / "full"),
                    "--estimated-budget-usd",
                    "1",
                ],
                repo_root=ROOT,
                executor=executor,
            )
            self.assertEqual(result, 2)
            self.assertEqual(executor.calls, [])
            self.assertFalse((Path(temporary) / "full").exists())

    def test_inspect_requires_four_body_free_retained_dimensions(self) -> None:
        module = load_verifier()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reports = []
            for variant, provider, model in (
                ("pi", None, None),
                ("claude-subscription", None, None),
                ("claude-minimax", "minimax", "MiniMax-M3"),
            ):
                variant_root = root / variant
                variant_root.mkdir()
                plan = module.bounded_operation_plan(ROOT, variant, provider, model)
                executor = NativeArtifactExecutor(kinds=[item.kind for item in plan])
                self.assertEqual(
                    self._run(
                        module,
                        self._bounded_args(
                            variant_root, variant, provider=provider, model=model
                        ),
                        repo_root=ROOT,
                        executor=executor,
                    ),
                    0,
                )
                reports.append(variant_root / "evidence/af340-bounded-report.json")
            args = ["inspect"]
            for report in reports:
                args.extend(("--report", str(report)))
            stdout = io.StringIO()
            self.assertEqual(
                module.verify_af340_reproduction_main(args, repo_root=ROOT, stdout=stdout),
                0,
            )
            self.assertIn("Retained evidence dimensions: 4/4", stdout.getvalue())
            self.assertIn("Agent operations: 0", stdout.getvalue())
            self.assertIn("Judge operations: 0", stdout.getvalue())
            self.assertIn("Full dataset ran: no", stdout.getvalue())

            artifact = next((reports[0].parent / "private").rglob("effective-config.json"))
            artifact.write_bytes(b"tampered\n")
            self.assertEqual(
                module.verify_af340_reproduction_main(args, repo_root=ROOT),
                2,
            )

    def test_inspect_full_requires_authorized_complete_comparison_evidence(self) -> None:
        module = load_verifier()
        scope_id = "qa.nq.main.random50"
        profile_sha = "a" * 64
        profile = SimpleNamespace(scope_ids=(scope_id,), profile_id="fixture/pi")
        comparison = SimpleNamespace(
            selection_id=scope_id,
            accepted=True,
            profile_sha256=profile_sha,
            candidate=SimpleNamespace(agent_operations=50, judge_operations=50),
            baseline=SimpleNamespace(agent_operations=50, judge_operations=50),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "full"
            root.mkdir(mode=0o700)
            comparisons = root / "comparisons"
            comparisons.mkdir(mode=0o700)
            native = comparisons / "scope.json"
            native.write_text("{}\n")
            native.chmod(0o600)
            values = {
                "schema": module.FULL_REPORT_SCHEMA,
                "mode": "full", "status": "passed",
                "profile_id": "fixture/pi", "profile_sha256": profile_sha,
                "profile_provider": None, "profile_model": None,
                "authorization_issued": True, "full_dataset_ran": True,
                "agent_operations": 100, "judge_operations": 100,
                "agent_maximum": 100, "judge_maximum": 100,
                "comparisons": [{
                    "selection_id": scope_id,
                    "ref": "comparisons/scope.json",
                    "sha256": __import__("hashlib").sha256(native.read_bytes()).hexdigest(),
                    "accepted": True,
                }],
            }
            values["report_sha256"] = module._canonical_sha256(values)
            report = root / "af340-full-report.json"
            report.write_text(json.dumps(values) + "\n")
            report.chmod(0o600)
            stdout = io.StringIO()
            with mock.patch.object(
                module,
                "_full_preflight",
                return_value=(profile, {
                    "profile_sha256": profile_sha,
                    "agent_maximum": 100,
                    "judge_maximum": 100,
                }),
            ), mock.patch(
                "asterion.dci.reproduction.load_comparison_report",
                return_value=comparison,
            ):
                with self.assertRaisesRegex(ValueError, "schema|authorization|native"):
                    module._run_inspect_full(SimpleNamespace(report=report), ROOT, stdout)

            values["comparisons"][0]["accepted"] = False
            unsigned = dict(values)
            unsigned.pop("report_sha256")
            values["report_sha256"] = module._canonical_sha256(unsigned)
            report.write_text(json.dumps(values) + "\n")
            with mock.patch.object(
                module,
                "_full_preflight",
                return_value=(profile, {
                    "profile_sha256": profile_sha,
                    "agent_maximum": 100,
                    "judge_maximum": 100,
                }),
            ), mock.patch(
                "asterion.dci.reproduction.load_comparison_report",
                return_value=SimpleNamespace(**{**comparison.__dict__, "accepted": False}),
            ), self.assertRaisesRegex(ValueError, "schema|comparison-evidence"):
                module._run_inspect_full(SimpleNamespace(report=report), ROOT, io.StringIO())

    def test_inspect_full_binds_consumed_task6_roots_and_detects_native_mutation(self) -> None:
        module = load_verifier()
        source = str(ROOT / "asterion/src")
        if source not in __import__("sys").path:
            __import__("sys").path.insert(0, source)
        from dataclasses import replace
        from asterion.dci.experiment_profiles import (
            authorize_full_execution,
            consume_full_execution_authorization,
            experiment_profile_sha256,
            resolve_experiment_profile,
        )
        scope_id = "qa.nq.main.random50"
        full_profile = resolve_experiment_profile("current-default/pi")
        index = full_profile.scope_ids.index(scope_id)
        profile = replace(
            full_profile,
            scope_ids=(scope_id,),
            selected_ids_sha256=(full_profile.selected_ids_sha256[index],),
        )
        profile_sha = experiment_profile_sha256(profile.profile_id)
        manifests = {
            "original-dci": SimpleNamespace(
                product="original-dci", selection_id=scope_id,
                profile_id=profile.profile_id, profile_sha256=profile_sha,
                identity_sha256="1" * 64,
                aggregates=SimpleNamespace(agent_operations=50, judge_operations=50),
            ),
            "asterion-dci": SimpleNamespace(
                product="asterion-dci", selection_id=scope_id,
                profile_id=profile.profile_id, profile_sha256=profile_sha,
                identity_sha256="2" * 64,
                aggregates=SimpleNamespace(agent_operations=50, judge_operations=50),
            ),
        }
        comparison = SimpleNamespace(
            profile_id=profile.profile_id, profile_sha256=profile_sha,
            selection_id=scope_id, accepted=True,
            baseline_run_sha256="1" * 64, candidate_run_sha256="2" * 64,
            baseline=SimpleNamespace(agent_operations=50, judge_operations=50),
            candidate=SimpleNamespace(agent_operations=50, judge_operations=50),
        )
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "full"
            parent.mkdir(mode=0o700)
            parent = parent.resolve()
            authorizations = {"original-dci": {}, "asterion-dci": {}}
            for product in authorizations:
                authorization = authorize_full_execution(
                    profile.profile_id, parent / product / module._safe_slug(scope_id),
                    0, True, preflight_profile_sha256=profile_sha,
                    preflight_dataset_inventory_sha256=profile.dataset_inventory_sha256,
                    preflight_experiment_scopes_sha256=profile.experiment_scopes_sha256,
                    preflight_scope_ids=(scope_id,),
                    preflight_selected_ids_sha256=(profile.selected_ids_sha256[0],),
                )
                consume_full_execution_authorization(authorization, scope_id)
                manifest_path = authorization.output_root / "af340-run-manifest.json"
                manifest_path.write_text("{}\n")
                manifest_path.chmod(0o600)
                authorizations[product][scope_id] = authorization
            comparisons = parent / "comparisons"
            comparisons.mkdir(mode=0o700)
            comparison_path = comparisons / f"{module._safe_slug(scope_id)}.json"
            comparison_path.write_text("{}\n")
            comparison_path.chmod(0o600)

            def load_manifest(path):
                return manifests[path.parent.parent.name]

            def normalize(request, *, write=True):
                self.assertFalse(write)
                return manifests[request.product]

            with mock.patch(
                "asterion.dci.reproduction.load_comparison_report",
                return_value=comparison,
            ), mock.patch(
                "asterion.dci.reproduction.load_run_manifest",
                side_effect=load_manifest,
            ), mock.patch.object(
                module, "normalize_full_scope_manifest", side_effect=normalize,
            ):
                report = module._write_full_execution_report(
                    parent, profile,
                    {"profile_sha256": profile_sha, "agent_maximum": 100, "judge_maximum": 100},
                    module.FullRunResult(100, 100, True), authorizations,
                )
                with mock.patch.object(
                    module, "_full_preflight",
                    return_value=(profile, {"profile_sha256": profile_sha, "agent_maximum": 100, "judge_maximum": 100}),
                ):
                    self.assertEqual(
                        module._run_inspect_full(SimpleNamespace(report=report), ROOT, io.StringIO()),
                        0,
                    )
                    comparison_path.chmod(0o644)
                    with self.assertRaisesRegex(ValueError, "permissions"):
                        module._run_inspect_full(
                            SimpleNamespace(report=report), ROOT, io.StringIO()
                        )
                    comparison_path.chmod(0o600)
                    real_comparison = comparisons / "real-comparison.json"
                    comparison_path.rename(real_comparison)
                    comparison_path.symlink_to(real_comparison)
                    with self.assertRaisesRegex(ValueError, "symlink"):
                        module._run_inspect_full(
                            SimpleNamespace(report=report), ROOT, io.StringIO()
                        )
                    comparison_path.unlink()
                    real_comparison.rename(comparison_path)
                    mutated = authorizations["asterion-dci"][scope_id].output_root / "af340-run-manifest.json"
                    mutated.chmod(0o644)
                    with self.assertRaisesRegex(ValueError, "permissions"):
                        module._run_inspect_full(
                            SimpleNamespace(report=report), ROOT, io.StringIO()
                        )
                    mutated.chmod(0o600)
                    mutated.write_text('{"mutated":true}\n')
                    mutated.chmod(0o600)
                    with self.assertRaisesRegex(ValueError, "native-tree"):
                        module._run_inspect_full(
                            SimpleNamespace(report=report), ROOT, io.StringIO()
                        )

                    missing_baseline = SimpleNamespace(
                        **{**comparison.__dict__, "baseline": None,
                           "baseline_run_sha256": None}
                    )
                    mutated.write_text("{}\n")
                    mutated.chmod(0o600)
                    values = json.loads(report.read_text())
                    for evidence in values["scope_evidence"]:
                        native_root = parent / evidence["root_ref"]
                        evidence["tree_sha256"] = module._private_tree_sha256(native_root)
                        if evidence["product"] == "asterion-dci":
                            manifest_file = native_root / "af340-run-manifest.json"
                            evidence["manifest_sha256"] = __import__("hashlib").sha256(
                                manifest_file.read_bytes()
                            ).hexdigest()
                    unsigned = dict(values)
                    unsigned.pop("report_sha256")
                    values["report_sha256"] = module._canonical_sha256(unsigned)
                    report.write_text(json.dumps(values) + "\n")
                    report.chmod(0o600)
                    with mock.patch(
                        "asterion.dci.reproduction.load_comparison_report",
                        return_value=missing_baseline,
                    ), self.assertRaisesRegex(ValueError, "baseline"):
                        module._run_inspect_full(
                            SimpleNamespace(report=report), ROOT, io.StringIO()
                        )


if __name__ == "__main__":
    unittest.main()
