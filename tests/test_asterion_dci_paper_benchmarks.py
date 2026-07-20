from __future__ import annotations

import copy
import hashlib
import importlib
import json
import unittest
from importlib import resources
from pathlib import Path
from unittest import mock


EXPECTED_DATASETS = (
    "beir.arguana",
    "beir.scifact",
    "bright.biology",
    "bright.earth-science",
    "bright.economics",
    "bright.robotics",
    "browsecomp-plus",
    "qa.2wikimultihopqa",
    "qa.bamboogle",
    "qa.hotpotqa",
    "qa.musique",
    "qa.nq",
    "qa.triviaqa",
)

EXPECTED_SCOPES = (
    "beir.arguana.main.random50",
    "beir.scifact.main.random50",
    "bright.biology.main.full",
    "bright.earth-science.main.full",
    "bright.economics.main.full",
    "bright.robotics.main.full",
    "browsecomp-plus.analysis.n100",
    "browsecomp-plus.appendix-a1.random50",
    "browsecomp-plus.context-ablation.random100",
    "browsecomp-plus.main.all830",
    "qa.2wikimultihopqa.main.random50",
    "qa.bamboogle.main.full",
    "qa.hotpotqa.main.random50",
    "qa.musique.main.random50",
    "qa.nq.main.random50",
    "qa.triviaqa.main.random50",
)


def paper_module(test: unittest.TestCase):
    try:
        return importlib.import_module("asterion.dci.paper_benchmarks")
    except ModuleNotFoundError:
        test.fail("asterion.dci.paper_benchmarks is not implemented")


class PaperBenchmarkInventoryTests(unittest.TestCase):
    def test_exact_thirteen_dataset_inventory_is_closed_and_sorted(self) -> None:
        module = paper_module(self)

        self.assertEqual(module.paper_benchmark_ids(), EXPECTED_DATASETS)
        self.assertEqual(len(set(module.paper_benchmark_ids())), 13)
        for dataset_id in EXPECTED_DATASETS:
            dataset = module.resolve_paper_benchmark(dataset_id)
            self.assertEqual(dataset.dataset_id, dataset_id)
            self.assertEqual(dataset.execution_class, "paper-full")
            self.assertIn(dataset.mode, {"qa", "ir"})
            self.assertTrue(dataset.identity_sha256)
            self.assertRegex(dataset.identity_sha256, r"^[0-9a-f]{64}$")

    def test_beir_source_counts_and_judge_contracts_are_explicit(self) -> None:
        module = paper_module(self)

        arguana = module.resolve_paper_benchmark("beir.arguana")
        scifact = module.resolve_paper_benchmark("beir.scifact")
        self.assertEqual((arguana.source_split, arguana.source_count), ("test", 1406))
        self.assertEqual((scifact.source_split, scifact.source_count), ("test", 300))
        self.assertEqual(arguana.metric, "ndcg@10-binary-deduplicated")
        self.assertEqual(scifact.metric, "ndcg@10-binary-deduplicated")
        self.assertIsNone(arguana.judge_contract)
        self.assertIsNone(scifact.judge_contract)

        for dataset_id in (
            "browsecomp-plus",
            "qa.2wikimultihopqa",
            "qa.bamboogle",
            "qa.hotpotqa",
            "qa.musique",
            "qa.nq",
            "qa.triviaqa",
        ):
            with self.subTest(dataset_id=dataset_id):
                dataset = module.resolve_paper_benchmark(dataset_id)
                self.assertEqual(dataset.metric, "llm-answer-correctness")
                self.assertEqual(
                    dataset.judge_contract,
                    "dci.paper-answer-judge/gpt-4.1/v1",
                )

    def test_every_source_split_count_is_explicit(self) -> None:
        module = paper_module(self)
        expected = {
            "beir.arguana": 1406,
            "beir.scifact": 300,
            "bright.biology": 103,
            "bright.earth-science": 116,
            "bright.economics": 103,
            "bright.robotics": 101,
            "browsecomp-plus": 830,
            "qa.2wikimultihopqa": 12576,
            "qa.bamboogle": 125,
            "qa.hotpotqa": 7405,
            "qa.musique": 2417,
            "qa.nq": 3610,
            "qa.triviaqa": 11313,
        }
        self.assertEqual(
            {key: module.resolve_paper_benchmark(key).source_count for key in expected},
            expected,
        )

    def test_unknown_ids_and_aliases_fail_closed(self) -> None:
        module = paper_module(self)

        for value in (None, "", "NQ", "nq", "qa_nq", " qa.nq", "qa.nq ", True):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "paper benchmark"
            ):
                module.resolve_paper_benchmark(value)

    def test_every_bound_profile_maps_to_a_non_executable_paper_scope(self) -> None:
        module = paper_module(self)
        bound = {
            dataset.batch_profile
            for dataset_id in EXPECTED_DATASETS
            if (dataset := module.resolve_paper_benchmark(dataset_id)).batch_profile
            is not None
        }
        self.assertEqual(len(bound), 12)
        for profile in bound:
            with self.subTest(profile=profile):
                scope_id = module.paper_scope_for_profile(profile)
                self.assertIn(scope_id, EXPECTED_SCOPES)
                with self.assertRaisesRegex(
                    ValueError, "not executable without explicit AF-340 authorization"
                ):
                    module.require_af320_executable_scope(scope_id)
        self.assertIsNone(module.paper_scope_for_profile("qa.bamboogle"))
        self.assertIsNone(module.paper_scope_for_profile(None))

    def test_packaged_inventory_and_schema_are_closed(self) -> None:
        module = paper_module(self)
        package = resources.files("asterion.dci.resources")
        inventory = json.loads(
            package.joinpath("paper-benchmarks.json").read_text(encoding="utf-8")
        )
        schema = json.loads(
            package.joinpath("paper-benchmark.schema.json").read_text(encoding="utf-8")
        )

        self.assertEqual(inventory["schema"], "dci.paper-benchmark-inventory/v1")
        self.assertEqual(tuple(item["dataset_id"] for item in inventory["datasets"]), EXPECTED_DATASETS)
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["dataset"]["additionalProperties"])
        self.assertEqual(
            set(schema["$defs"]["dataset"]["required"]),
            set(inventory["datasets"][0]),
        )
        self.assertEqual(
            module.paper_benchmark_inventory_sha256(),
            module.canonical_sha256(inventory),
        )

    def test_inventory_references_real_profiles_launchers_and_fixture_registry(self) -> None:
        package = resources.files("asterion.dci.resources")
        inventory = json.loads(
            package.joinpath("paper-benchmarks.json").read_text(encoding="utf-8")
        )
        profiles = json.loads(
            package.joinpath("batch-profiles.json").read_text(encoding="utf-8")
        )["profiles"]
        fixtures = {
            item["fixture_id"]: item
            for item in json.loads(
                package.joinpath("paper-bounded-fixtures.json").read_text(
                    encoding="utf-8"
                )
            )["fixtures"]
        }
        for item in inventory["datasets"]:
            with self.subTest(dataset_id=item["dataset_id"]):
                if item["batch_profile"] is not None:
                    profile = profiles[item["batch_profile"]]
                    self.assertEqual(profile["dataset"], item["dataset_path"])
                    self.assertEqual(profile["corpus"], item["corpus_path"])
                    self.assertEqual(profile["mode"], item["mode"])
                    self.assertTrue(Path(item["launcher"]).is_file())
                self.assertEqual(
                    fixtures[item["bounded_fixture"]],
                    {
                        "fixture_id": item["bounded_fixture"],
                        "dataset_id": item["dataset_id"],
                        "mode": item["mode"],
                        "artifact_id": f"{item['mode']}/v1",
                        "execution_class": "bounded-fixture",
                    },
                )

        fixture_payload = json.loads(
            package.joinpath("paper-bounded-fixtures.json").read_text(encoding="utf-8")
        )
        for artifact in fixture_payload["artifacts"].values():
            for resource_field, digest_field in (
                ("dataset_resource", "dataset_sha256"),
                ("corpus_document_resource", "corpus_document_sha256"),
            ):
                raw = package.joinpath(artifact[resource_field]).read_bytes()
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(), artifact[digest_field]
                )

        bamboogle = next(
            item for item in inventory["datasets"] if item["dataset_id"] == "qa.bamboogle"
        )
        self.assertEqual(bamboogle["source_count"], 125)
        self.assertIsNone(bamboogle["batch_profile"])
        self.assertIsNone(bamboogle["launcher"])
        self.assertNotEqual(
            bamboogle["dataset_path"], profiles["qa.bamboogle"]["dataset"]
        )

    def test_packaged_schema_semantics_cannot_drift_from_runtime(self) -> None:
        module = paper_module(self)
        original_loader = module._load_json_resource
        mutations = (
            ("paper-benchmark.schema.json", "dataset", "mode", {"type": "string"}),
            (
                "paper-experiment-scope.schema.json",
                "scope",
                "selection_seed_status",
                {"type": "string"},
            ),
        )
        for name, definition, field, replacement in mutations:
            schema = copy.deepcopy(original_loader(name))
            schema["$defs"][definition]["properties"][field] = replacement

            def fake_loader(resource_name, *, schema=schema, name=name):
                if resource_name == name:
                    return schema
                return original_loader(resource_name)

            with self.subTest(name=name, field=field), mock.patch.object(
                module, "_load_json_resource", side_effect=fake_loader
            ):
                module._benchmarks.cache_clear()
                module._scopes.cache_clear()
                with self.assertRaisesRegex(RuntimeError, "contract is invalid"):
                    if definition == "dataset":
                        module.paper_benchmark_ids()
                    else:
                        module.paper_experiment_scope_ids()
        module._benchmarks.cache_clear()
        module._scopes.cache_clear()

    def test_semantic_inventory_mutations_fail_loader_validation(self) -> None:
        module = paper_module(self)
        package = resources.files("asterion.dci.resources")
        original_payload = json.loads(
            package.joinpath("paper-benchmarks.json").read_text(encoding="utf-8")
        )
        original_loader = module._load_resource
        mutations = (
            ("metric", "unknown"),
            ("gold_field", "gold_ids"),
            ("judge_contract", None),
            ("family", "ir"),
            ("dataset_path", "../escape.jsonl"),
            ("batch_profile", "missing.profile"),
            ("bounded_fixture", "missing.fixture/v1"),
            ("launcher", "../escape.sh"),
            ("source_count", None),
        )
        for field, value in mutations:
            payload = copy.deepcopy(original_payload)
            target = next(
                item for item in payload["datasets"] if item["dataset_id"] == "qa.nq"
            )
            target[field] = value

            def fake_loader(name, schema, collection, *, payload=payload):
                if name == "paper-benchmarks.json":
                    return payload
                return original_loader(name, schema, collection)

            with self.subTest(field=field), mock.patch.object(
                module, "_load_resource", side_effect=fake_loader
            ):
                module._benchmarks.cache_clear()
                with self.assertRaisesRegex(RuntimeError, "contract is invalid"):
                    module.paper_benchmark_ids()
        module._benchmarks.cache_clear()


class PaperExperimentScopeTests(unittest.TestCase):
    def test_exact_experiment_scopes_preserve_browsecomp_distinctions(self) -> None:
        module = paper_module(self)

        self.assertEqual(module.paper_experiment_scope_ids(), EXPECTED_SCOPES)
        expected = {
            "browsecomp-plus.main.all830": ("all", 830),
            "browsecomp-plus.analysis.n100": ("deterministic-sample", 100),
            "browsecomp-plus.context-ablation.random100": ("random-sample", 100),
            "browsecomp-plus.appendix-a1.random50": ("random-sample", 50),
        }
        identities = set()
        for scope_id, selection in expected.items():
            with self.subTest(scope_id=scope_id):
                scope = module.resolve_paper_experiment_scope(scope_id)
                self.assertEqual((scope.selection_mode, scope.selection_count), selection)
                self.assertRegex(scope.selected_ids_sha256, r"^[0-9a-f]{64}$")
                identities.add(scope.identity_sha256)
                if selection[0] == "all":
                    self.assertIsNone(scope.selection_seed)
                else:
                    self.assertIsInstance(scope.selection_seed, int)
                    self.assertTrue(scope.selection_algorithm)
        self.assertEqual(len(identities), 4)

    def test_every_sampled_scope_binds_seed_algorithm_and_selected_ids(self) -> None:
        module = paper_module(self)

        for scope_id in EXPECTED_SCOPES:
            scope = module.resolve_paper_experiment_scope(scope_id)
            self.assertEqual(scope.execution_class, "paper-full")
            self.assertRegex(scope.selected_ids_sha256, r"^[0-9a-f]{64}$")
            if scope.selection_seed_status == "asterion-defined":
                with self.subTest(scope_id=scope_id):
                    self.assertIsInstance(scope.selection_seed, int)
                    self.assertTrue(scope.selection_algorithm)
            elif scope.selection_seed_status == "paper-unreported":
                self.assertIsNone(scope.selection_seed)
                self.assertEqual(
                    scope.selection_algorithm, "published-selected-id-manifest/v1"
                )
                selected = module.published_scope_selected_ids(scope_id)
                self.assertEqual(len(selected), scope.selection_count)
                self.assertEqual(module.canonical_sha256(selected), scope.selected_ids_sha256)
            else:
                self.assertEqual(scope.selection_seed_status, "not-applicable")
                self.assertIsNone(scope.selection_seed)
            self.assertIn(scope.dataset_id, EXPECTED_DATASETS)

    def test_scope_resource_is_packaged_closed_and_digest_bound(self) -> None:
        module = paper_module(self)
        package = resources.files("asterion.dci.resources")
        scopes = json.loads(
            package.joinpath("paper-experiment-scopes.json").read_text(encoding="utf-8")
        )
        schema = json.loads(
            package.joinpath("paper-experiment-scope.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(scopes["schema"], "dci.paper-experiment-scopes/v1")
        self.assertEqual(tuple(item["scope_id"] for item in scopes["scopes"]), EXPECTED_SCOPES)
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["scope"]["additionalProperties"])
        self.assertEqual(
            module.paper_experiment_scopes_sha256(),
            module.canonical_sha256(scopes),
        )

    def test_scope_aliases_fail_closed(self) -> None:
        module = paper_module(self)

        for value in (None, "", "browsecomp", "browsecomp-plus.main", True):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "experiment scope"
            ):
                module.resolve_paper_experiment_scope(value)

    def test_browsecomp_scope_manifests_recompute_from_all_830_ids(self) -> None:
        module = paper_module(self)
        rows = [
            json.loads(line)
            for line in Path("data/bcplus_qa.jsonl").read_text().splitlines()
            if line
        ]
        source_ids = tuple(str(row["query_id"]) for row in rows)

        expected_counts = {
            "browsecomp-plus.main.all830": 830,
            "browsecomp-plus.analysis.n100": 100,
            "browsecomp-plus.context-ablation.random100": 100,
            "browsecomp-plus.appendix-a1.random50": 50,
        }
        selected_sets = {}
        for scope_id, count in expected_counts.items():
            with self.subTest(scope_id=scope_id):
                selected = module.select_and_verify_scope_ids(scope_id, source_ids)
                self.assertEqual(len(selected), count)
                self.assertEqual(selected, tuple(sorted(selected)))
                selected_sets[scope_id] = selected
        self.assertNotEqual(
            selected_sets["browsecomp-plus.analysis.n100"],
            selected_sets["browsecomp-plus.context-ablation.random100"],
        )

    def test_manifest_mismatch_duplicates_and_paper_execution_fail_closed(self) -> None:
        module = paper_module(self)

        with self.assertRaisesRegex(ValueError, "selected-ID manifest"):
            module.select_and_verify_scope_ids(
                "browsecomp-plus.appendix-a1.random50", ("wrong",) * 830
            )
        with self.assertRaisesRegex(ValueError, "selected-ID manifest"):
            module.select_and_verify_scope_ids(
                "browsecomp-plus.appendix-a1.random50", tuple(str(i) for i in range(49))
            )
        with self.assertRaisesRegex(ValueError, "not executable without explicit AF-340 authorization"):
            module.require_af320_executable_scope(
                "browsecomp-plus.appendix-a1.random50"
            )

    def test_published_random50_manifests_verify_against_full_source_ids(self) -> None:
        module = paper_module(self)
        sources = {
            "qa.2wikimultihopqa.main.random50": ("dev", 12576),
            "qa.hotpotqa.main.random50": ("dev", 7405),
            "qa.musique.main.random50": ("dev", 2417),
            "qa.nq.main.random50": ("test", 3610),
            "qa.triviaqa.main.random50": ("test", 11313),
        }
        for scope_id, (prefix, count) in sources.items():
            with self.subTest(scope_id=scope_id):
                source_ids = tuple(f"{prefix}_{index}" for index in range(count))
                self.assertEqual(
                    module.select_and_verify_scope_ids(scope_id, source_ids),
                    module.published_scope_selected_ids(scope_id),
                )

        bamboogle_ids = tuple(f"test_{index}" for index in range(125))
        self.assertEqual(
            len(
                module.select_and_verify_scope_ids(
                    "qa.bamboogle.main.full", bamboogle_ids
                )
            ),
            125,
        )

    def test_semantic_scope_mutations_fail_loader_validation(self) -> None:
        module = paper_module(self)
        package = resources.files("asterion.dci.resources")
        original_payload = json.loads(
            package.joinpath("paper-experiment-scopes.json").read_text(
                encoding="utf-8"
            )
        )
        original_loader = module._load_resource
        mutations = (
            ("selection_seed", 0),
            ("selection_seed_status", "reported"),
            ("selection_algorithm", "unknown/v1"),
            ("selection_count", 51),
            ("dataset_id", "missing"),
            ("execution_class", "bounded-fixture"),
        )
        for field, value in mutations:
            payload = copy.deepcopy(original_payload)
            target = next(
                item
                for item in payload["scopes"]
                if item["scope_id"] == "qa.nq.main.random50"
            )
            target[field] = value

            def fake_loader(name, schema, collection, *, payload=payload):
                if name == "paper-experiment-scopes.json":
                    return payload
                return original_loader(name, schema, collection)

            with self.subTest(field=field), mock.patch.object(
                module, "_load_resource", side_effect=fake_loader
            ):
                module._scopes.cache_clear()
                with self.assertRaisesRegex(RuntimeError, "contract is invalid"):
                    module.paper_experiment_scope_ids()
        module._scopes.cache_clear()


if __name__ == "__main__":
    unittest.main()
