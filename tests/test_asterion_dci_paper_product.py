from __future__ import annotations

import io
import json
import unittest
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import mock

from asterion.dci.cli import main


class PaperBenchmarkCliTests(unittest.TestCase):
    def test_one_explicit_bounded_ablation_maps_to_packaged_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory, mock.patch(
            "asterion.dci.cli.run_benchmark"
        ) as benchmark:
            root = Path(temporary_directory)
            benchmark.return_value = type(
                "Result", (), {"output_root": root / "out", "counts": {"total": 1}}
            )()
            self.assertEqual(
                main(
                    [
                        "benchmark",
                        "--ablation-row",
                        "bounded.tools.read-grep",
                        "--output-root",
                        "out",
                        "--provider",
                        "fixture-provider",
                        "--model",
                        "fixture-model",
                    ],
                    repo_root=root,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                ),
                0,
            )

        request = benchmark.call_args.args[0]
        self.assertEqual(request.dataset.name, "qa.jsonl")
        self.assertEqual(request.corpus.name, "base")
        self.assertEqual(request.cwd, request.corpus)
        self.assertEqual(request.runtime_options.tools, "read,grep")
        self.assertEqual(request.runtime_options.runtime_context_level, "level4")
        self.assertEqual(request.max_turns, 8)
        self.assertEqual(request.ablation_row, "bounded.tools.read-grep")
        self.assertTrue(request.conversation_features.externalize_tool_results)
        self.assertEqual(request.resolution_registry.name, "qa-registry.json")
        self.assertEqual(request.resolution_segment_characters, 4096)

    def test_ablation_execution_rejects_paper_and_conflicting_inputs_before_runtime(self) -> None:
        cases = (
            [
                "benchmark",
                "--ablation-row",
                "paper.context.level0",
                "--output-root",
                "out",
            ],
            [
                "benchmark",
                "--ablation-row",
                "bounded.context.level0",
                "--output-root",
                "out",
                "--extra-arg=--sentinel-secret-override",
            ],
            [
                "benchmark",
                "--ablation-row",
                "bounded.context.level0",
                "--dataset",
                "sentinel-secret-dataset",
                "--output-root",
                "out",
            ],
        )
        with mock.patch("asterion.dci.cli.load_asterion_dci_env") as load_env, mock.patch(
            "asterion.dci.cli.run_benchmark"
        ) as benchmark:
            for argv in cases:
                with self.subTest(argv=argv):
                    stderr = io.StringIO()
                    self.assertEqual(main(argv, stderr=stderr), 2)
                    self.assertEqual(stderr.getvalue(), "DCI benchmark failed\n")
                    self.assertNotIn("sentinel", stderr.getvalue())
        load_env.assert_not_called()
        benchmark.assert_not_called()

    def test_paper_description_is_body_free_and_digest_bound(self) -> None:
        stdout = io.StringIO()
        self.assertEqual(main(["paper", "describe"], stdout=stdout), 0)
        value = json.loads(stdout.getvalue())

        self.assertEqual(value["schema"], "dci.paper-product-contract/v1")
        self.assertEqual(len(value["dataset_ids"]), 13)
        self.assertEqual(len(value["experiment_scope_ids"]), 16)
        self.assertEqual(len(value["experiment_profile_ids"]), 5)
        self.assertTrue(value["paper_full_requires_invocation_authorization"])
        self.assertEqual(len(value["ablation_row_ids"]), 20)
        self.assertEqual(value["context_profiles"], [f"level{i}" for i in range(5)])
        self.assertEqual(
            value["resolution_metrics"],
            ["coverage_any", "coverage_mean", "coverage_all", "localization", "retained_coverage"],
        )
        for field in (
            "benchmark_inventory_sha256",
            "experiment_scopes_sha256",
            "ablation_matrix_sha256",
        ):
            self.assertRegex(value[field], r"^[0-9a-f]{64}$")
        rendered = json.dumps(value)
        for forbidden in ("query", "answer", "snippet", "tool_output", "api_key"):
            self.assertNotIn(f'"{forbidden}"', rendered)

    def test_paper_verification_defaults_to_zero_external_operations(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        self.assertEqual(
            main(["paper", "verify"], stdout=stdout, stderr=stderr),
            0,
            stderr.getvalue(),
        )
        self.assertIn("Agent operations: 0", stdout.getvalue())
        self.assertIn("Judge operations: 0", stdout.getvalue())
        self.assertIn("Planned external operations: 3", stdout.getvalue())
        self.assertIn("Full dataset ran: no", stdout.getvalue())

    def test_resolution_export_cli_reanalyzes_authoritative_inputs(self) -> None:
        projection = {
            "schema": "dci.trajectory-resolution-summary/v1",
            "query_id": "opaque-query-id",
        }
        with mock.patch(
            "asterion.dci.cli.export_resolution_summary", return_value=projection
        ) as export:
            stdout = io.StringIO()
            self.assertEqual(
                main(
                    [
                        "export",
                        "resolution",
                        "--run-dir",
                        "run",
                        "--attempt",
                        "2",
                        "--corpus-dir",
                        "corpus",
                        "--gold-manifest",
                        "gold.json",
                        "--segment-characters",
                        "4096",
                    ],
                    stdout=stdout,
                ),
                0,
            )
        self.assertEqual(json.loads(stdout.getvalue()), projection)
        self.assertEqual(export.call_args.kwargs["attempt"], 2)
        self.assertEqual(export.call_args.kwargs["segment_characters"], 4096)
        self.assertEqual(export.call_args.kwargs["run_dir"], Path("run"))

    def test_paper_and_export_failures_are_body_free(self) -> None:
        for argv, expected in (
            (["paper", "unknown-secret"], "DCI paper command failed\n"),
            (
                [
                    "export",
                    "resolution",
                    "--run-dir",
                    "sentinel-secret-run",
                    "--attempt",
                    "0",
                    "--corpus-dir",
                    "corpus",
                    "--gold-manifest",
                    "gold.json",
                    "--segment-characters",
                    "1",
                ],
                "DCI export failed\n",
            ),
        ):
            with self.subTest(argv=argv):
                stderr = io.StringIO()
                self.assertEqual(main(argv, stderr=stderr), 2)
                self.assertEqual(stderr.getvalue(), expected)
                self.assertNotIn("sentinel", stderr.getvalue())


class PaperBenchmarkProductParityTests(unittest.TestCase):
    def test_ablation_axis_identity_prevents_equivalent_configuration_cache_collision(self) -> None:
        from asterion.dci.ablation import bounded_ablation_input_paths
        from asterion.dci.artifacts import DciConversationFeatures
        from asterion.dci.benchmark import BenchmarkRequest, _prepare
        from asterion.dci.config import DciRuntimeOptions
        from asterion.dci.judge import JudgeConfig

        from asterion.dci.ablation import bounded_ablation_resolution_registry_path

        dataset, corpus = bounded_ablation_input_paths("bounded.context.level4")
        request = BenchmarkRequest(
            dataset=dataset,
            output_root=Path("unused-output"),
            cwd=corpus,
            judge_config=JudgeConfig(),
            runtime_options=DciRuntimeOptions(
                provider="fixture-provider",
                model="fixture-model",
                tools="read,bash",
                runtime_context_level="level4",
            ),
            corpus=corpus,
            max_turns=8,
            conversation_features=DciConversationFeatures(
                externalize_tool_results=True
            ),
            ablation_row="bounded.context.level4",
            resolution_registry=bounded_ablation_resolution_registry_path(),
            resolution_segment_characters=4096,
        )
        first = _prepare(request)[2]
        second = _prepare(
            replace(request, ablation_row="bounded.tools.read-bash")
        )[2]

        self.assertNotEqual(first["ablation"], second["ablation"])
        self.assertNotEqual(first["run_fingerprint"], second["run_fingerprint"])
        self.assertNotEqual(first["batch_fingerprint"], second["batch_fingerprint"])

        legacy = _prepare(replace(request, ablation_row=None))[2]
        self.assertNotIn("ablation", legacy)

    def test_operator_docs_expose_safe_complete_commands_and_boundaries(self) -> None:
        root = Path(__file__).resolve().parents[1]
        values = {
            "reference": (root / "asterion/docs/guides/asterion-dci-complete-reference.md").read_text(),
            "validation": (root / "asterion/docs/verification/asterion-dci-validation-guide.md").read_text(),
            "readme": (root / "README.md").read_text(),
            "env": (root / ".env.template").read_text(),
        }
        for name, value in values.items():
            with self.subTest(name=name):
                self.assertIn("ablation", value)
        self.assertIn("asterion-dci paper describe", values["reference"])
        self.assertIn("export resolution", values["reference"])
        self.assertIn("paper-full", values["readme"])
        self.assertIn("no environment default", values["env"])

    def test_verification_description_exposes_the_same_paper_contract(self) -> None:
        from asterion.dci.verification import (
            DCI_PRODUCT_DESCRIPTION,
            paper_product_contract,
        )

        contract = paper_product_contract()
        self.assertEqual(
            tuple(function.function_id for function in DCI_PRODUCT_DESCRIPTION.functions),
            (
                "ablation",
                "benchmark",
                "evaluate",
                "export",
                "installed-application",
                "paper-contracts",
                "research",
                "resume",
                "terminal",
            ),
        )
        self.assertEqual(contract["ablation_matrix_sha256"], contract["resources"]["paper-ablation-matrix.json"])
        self.assertEqual(contract["benchmark_inventory_sha256"], contract["resources"]["paper-benchmarks.json"])
        self.assertEqual(contract["experiment_scopes_sha256"], contract["resources"]["paper-experiment-scopes.json"])


if __name__ == "__main__":
    unittest.main()
