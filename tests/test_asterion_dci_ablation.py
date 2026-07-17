from __future__ import annotations

import copy
import dataclasses
import hashlib
import io
import importlib
import json
import unittest
from importlib import resources
from unittest import mock


EXPECTED_ROWS = tuple(
    sorted(
        (
            *(f"bounded.context.level{level}" for level in range(5)),
            "bounded.corpus.base",
            "bounded.corpus.base-plus-one",
            "bounded.corpus.base-plus-two",
            "bounded.tools.read-bash",
            "bounded.tools.read-grep",
            *(f"paper.context.level{level}" for level in range(5)),
            "paper.corpus.100000",
            "paper.corpus.200000",
            "paper.corpus.400000",
            "paper.tools.read-bash",
            "paper.tools.read-grep",
        )
    )
)


def ablation_module(test: unittest.TestCase):
    try:
        return importlib.import_module("asterion.dci.ablation")
    except ModuleNotFoundError:
        test.fail("asterion.dci.ablation is not implemented")


class PaperAblationMatrixTests(unittest.TestCase):
    def test_exact_non_cartesian_matrix_is_sorted_unique_and_immutable(self) -> None:
        module = ablation_module(self)

        self.assertEqual(module.paper_ablation_row_ids(), EXPECTED_ROWS)
        self.assertEqual(len(set(EXPECTED_ROWS)), 20)
        self.assertEqual(
            len(
                {
                    module.resolve_paper_ablation_row(row_id).identity_sha256
                    for row_id in EXPECTED_ROWS
                }
            ),
            20,
        )
        self.assertEqual(
            {module.resolve_paper_ablation_row(row_id).ablation_kind for row_id in EXPECTED_ROWS},
            {"context", "corpus", "tools"},
        )
        for row_id in EXPECTED_ROWS:
            row = module.resolve_paper_ablation_row(row_id)
            self.assertEqual(row.row_id, row_id)
            self.assertFalse(row.executable_default)
            self.assertIn(row.cost_class, {"paper-full", "bounded-tiny"})
            self.assertRegex(row.identity_sha256, r"^[0-9a-f]{64}$")
            with self.assertRaises(dataclasses.FrozenInstanceError):
                row.max_turns = 1

        with self.assertRaisesRegex(ValueError, "ablation row is invalid"):
            module.resolve_paper_ablation_row("unknown")

    def test_paper_rows_bind_exact_query_scopes_and_unreported_fineweb_truth(self) -> None:
        module = ablation_module(self)

        for level in range(5):
            row = module.resolve_paper_ablation_row(f"paper.context.level{level}")
            self.assertEqual(row.query_scope_id, "browsecomp-plus.context-ablation.random100")
            self.assertEqual(row.context_profile, f"level{level}")
            self.assertEqual(row.execution_class, "paper-full")

        for suffix, expected_tools in (
            ("read-grep", ("read", "grep")),
            ("read-bash", ("read", "bash")),
        ):
            row = module.resolve_paper_ablation_row(f"paper.tools.{suffix}")
            self.assertEqual(row.query_scope_id, "browsecomp-plus.analysis.n100")
            self.assertEqual(row.tools, expected_tools)
            self.assertEqual(row.context_profile, "level4")
        self.assertNotIn(
            "bash", module.resolve_paper_ablation_row("paper.tools.read-grep").tools
        )

        for target in (100_000, 200_000, 400_000):
            row = module.resolve_paper_ablation_row(f"paper.corpus.{target}")
            self.assertEqual(row.query_scope_id, "browsecomp-plus.analysis.n100")
            self.assertEqual(row.fineweb_source, "HuggingFaceFW/fineweb")
            self.assertEqual(row.fineweb_target_count, target)
            self.assertEqual(row.fineweb_selection_status, "paper-unreported")
            self.assertIsNone(row.fineweb_revision)
            self.assertIsNone(row.fineweb_selection_seed)
            self.assertIsNone(row.fineweb_selection_algorithm)
            self.assertIsNone(row.fineweb_selected_ids_sha256)

    def test_bounded_rows_bind_hash_verified_tiny_fixtures(self) -> None:
        module = ablation_module(self)
        package = resources.files("asterion.dci.resources")

        for suffix, expected_count in (
            ("base", 1),
            ("base-plus-one", 2),
            ("base-plus-two", 3),
        ):
            row = module.resolve_paper_ablation_row(f"bounded.corpus.{suffix}")
            manifest = module.resolve_bounded_corpus_manifest(row.corpus_manifest_id)
            self.assertEqual(len(manifest.documents), expected_count)
            self.assertEqual(manifest.identity_sha256, row.corpus_manifest_sha256)
            for document in manifest.documents:
                raw = package.joinpath(document.resource).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), document.sha256)

        for level in range(5):
            row = module.resolve_paper_ablation_row(f"bounded.context.level{level}")
            self.assertEqual(row.query_fixture_id, "browsecomp-plus.tiny/v1")
            self.assertEqual(row.context_profile, f"level{level}")
            self.assertEqual(row.execution_class, "bounded-fixture")

    def test_execution_gate_requires_one_explicit_bounded_row_and_authorization(self) -> None:
        module = ablation_module(self)

        for authorized in (False, True):
            with self.subTest(authorized=authorized), self.assertRaisesRegex(
                ValueError, "not executable in AF-320"
            ):
                module.require_af320_executable_ablation(
                    "paper.context.level0", benchmark_authorized=authorized
                )
        with self.assertRaisesRegex(ValueError, "authorization is required"):
            module.require_af320_executable_ablation(
                "bounded.context.level0", benchmark_authorized=False
            )
        row = module.require_af320_executable_ablation(
            "bounded.context.level0", benchmark_authorized=True
        )
        self.assertEqual(row.row_id, "bounded.context.level0")

    def test_validate_list_and_render_are_deterministic_and_non_executing(self) -> None:
        module = ablation_module(self)

        first = module.render_paper_ablation_matrix()
        self.assertEqual(first, module.render_paper_ablation_matrix())
        payload = json.loads(first)
        self.assertEqual(tuple(item["row_id"] for item in payload["rows"]), EXPECTED_ROWS)
        self.assertEqual(module.validate_paper_ablation_matrix(), len(EXPECTED_ROWS))
        self.assertEqual(
            module.paper_ablation_matrix_sha256(), module.canonical_sha256(payload)
        )
        self.assertEqual(
            module.render_paper_ablation_command("paper.corpus.100000"),
            "# NON-EXECUTABLE paper-full row: paper.corpus.100000",
        )
        command = module.render_paper_ablation_command("bounded.tools.read-grep")
        self.assertEqual(
            command,
            "asterion-dci benchmark --ablation-row bounded.tools.read-grep",
        )
        self.assertNotIn("--profile", command)
        self.assertNotIn("provider", command)

    def test_schema_and_runtime_reject_unknown_fields_duplicates_and_drift(self) -> None:
        module = ablation_module(self)
        package = resources.files("asterion.dci.resources")
        matrix = json.loads(
            package.joinpath("paper-ablation-matrix.json").read_text(encoding="utf-8")
        )
        schema = json.loads(
            package.joinpath("paper-ablation.schema.json").read_text(encoding="utf-8")
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["row"]["additionalProperties"])
        self.assertEqual(set(schema["$defs"]["row"]["required"]), set(matrix["rows"][0]))

        original_loader = module._load_json_resource
        mutations = []
        unknown = copy.deepcopy(matrix)
        unknown["rows"][0]["hidden_provider_default"] = "sentinel"
        mutations.append(unknown)
        duplicate = copy.deepcopy(matrix)
        duplicate["rows"][1]["row_id"] = duplicate["rows"][0]["row_id"]
        mutations.append(duplicate)
        unsorted = copy.deepcopy(matrix)
        unsorted["rows"][0], unsorted["rows"][1] = unsorted["rows"][1], unsorted["rows"][0]
        mutations.append(unsorted)

        for mutation in mutations:
            def fake_loader(name: str, *, mutation=mutation):
                if name == "paper-ablation-matrix.json":
                    return mutation
                return original_loader(name)

            with self.subTest(kind=tuple(mutation)), mock.patch.object(
                module, "_load_json_resource", side_effect=fake_loader
            ):
                module._matrix.cache_clear()
                with self.assertRaisesRegex(RuntimeError, "ablation contract is invalid"):
                    module.paper_ablation_row_ids()
        module._matrix.cache_clear()

        changed_schema = copy.deepcopy(schema)
        changed_schema["$defs"]["row"]["properties"]["tools"] = {
            "type": "array"
        }

        def schema_loader(name: str):
            if name == "paper-ablation.schema.json":
                return changed_schema
            return original_loader(name)

        with mock.patch.object(
            module, "_load_json_resource", side_effect=schema_loader
        ):
            module._matrix.cache_clear()
            with self.assertRaisesRegex(RuntimeError, "ablation contract is invalid"):
                module.paper_ablation_row_ids()
        module._matrix.cache_clear()


class PaperAblationCommandTests(unittest.TestCase):
    def test_validate_list_and_render_commands_are_model_free(self) -> None:
        try:
            from asterion.dci.cli import main
        except ImportError:
            self.fail("asterion-dci ablation commands are not implemented")

        stdout = io.StringIO()
        self.assertEqual(main(["ablation", "validate"], stdout=stdout), 0)
        validation = json.loads(stdout.getvalue())
        self.assertEqual(validation["rows"], 20)
        self.assertRegex(validation["matrix_sha256"], r"^[0-9a-f]{64}$")

        stdout = io.StringIO()
        self.assertEqual(
            main(
                ["ablation", "list", "--execution-class", "bounded-fixture"],
                stdout=stdout,
            ),
            0,
        )
        listing = json.loads(stdout.getvalue())
        self.assertEqual(len(listing["rows"]), 10)
        self.assertTrue(
            all(row["execution_class"] == "bounded-fixture" for row in listing["rows"])
        )

        stdout = io.StringIO()
        self.assertEqual(
            main(
                ["ablation", "render", "bounded.tools.read-grep"],
                stdout=stdout,
            ),
            0,
        )
        self.assertEqual(
            stdout.getvalue(),
            "asterion-dci benchmark --ablation-row bounded.tools.read-grep\n",
        )

    def test_ablation_command_failures_are_body_free(self) -> None:
        from asterion.dci.cli import main

        stderr = io.StringIO()
        self.assertEqual(
            main(
                ["ablation", "render", "sentinel-secret-row"], stderr=stderr
            ),
            2,
        )
        self.assertEqual(stderr.getvalue(), "DCI ablation command failed\n")
        self.assertNotIn("sentinel", stderr.getvalue())

if __name__ == "__main__":
    unittest.main()
