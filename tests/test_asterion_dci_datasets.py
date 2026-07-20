from __future__ import annotations

import json
import tempfile
import unittest
import unicodedata
from pathlib import Path

from asterion.dci.datasets import (
    BENCHMARK_PROMPT_CONTRACT,
    BENCHMARK_PROMPT_CONTRACT_SHA256,
    DatasetError,
    build_benchmark_prompt,
    build_ir_prompt,
    build_qa_prompt,
    load_benchmark_rows,
    load_benchmark_rows_bytes,
    load_beir_benchmark_rows_bytes,
    load_bright_benchmark_rows_bytes,
    portable_query_id_key,
    read_jsonl,
    validate_beir_corpus,
)


class PaperBeirDatasetTests(unittest.TestCase):
    def test_empty_source_answer_normalizes_to_strict_ir_rows(self) -> None:
        payload = (
            b'{"query_id":"q-1","query":"find","answer":"","gold_ids":["a.txt","b.txt"]}\n'
            b'{"query_id":"q-2","query":"find more","answer":"","gold_ids":["c.txt"]}\n'
        )
        rows = load_beir_benchmark_rows_bytes(payload, expected_count=2)
        self.assertEqual(tuple(row.query_id for row in rows), ("q-1", "q-2"))
        self.assertEqual(rows[0].gold_ids, ("a.txt", "b.txt"))
        self.assertIsNone(rows[0].answer)

    def test_malformed_beir_rows_and_source_count_fail_closed(self) -> None:
        invalid = (
            b'not-json\n',
            b'{"query_id":"q","query":"x","answer":"nonempty","gold_ids":["a.txt"]}\n',
            b'{"query_id":"q","query":"x","gold_ids":["a.txt"]}\n',
            b'{"query_id":"q","query":"x","answer":"","gold_ids":["a.txt"],"grade":1}\n',
            b'{"query_id":"q","query":"x","answer":"","gold_ids":["a.txt","a.txt"]}\n',
            b'{"query_id":"q","query":"x","answer":"","gold_ids":["../a.txt"]}\n',
            b'{"query_id":"q","query":"x","answer":"","gold_ids":["nested/a.txt"]}\n',
            b'{"query_id":"q","query":"x","answer":"","gold_ids":["a"]}\n',
            b'{"query_id":"q","query":"x","query":"y","answer":"","gold_ids":["a.txt"]}\n',
        )
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaisesRegex(
                DatasetError, "BEIR"
            ):
                load_beir_benchmark_rows_bytes(payload)
        valid = b'{"query_id":"q","query":"x","answer":"","gold_ids":["a.txt"]}\n'
        with self.assertRaisesRegex(DatasetError, "source count"):
            load_beir_benchmark_rows_bytes(valid, expected_count=2)

    def test_beir_query_id_collisions_and_count_types_fail_closed(self) -> None:
        collision = (
            b'{"query_id":"Q-01","query":"x","answer":"","gold_ids":["a.txt"]}\n'
            b'{"query_id":"q-1","query":"y","answer":"","gold_ids":["b.txt"]}\n'
        )
        with self.assertRaisesRegex(DatasetError, "query ID"):
            load_beir_benchmark_rows_bytes(collision)
        for count in (0, -1, True, 1.0, "1"):
            with self.subTest(count=count), self.assertRaisesRegex(
                DatasetError, "source count"
            ):
                load_beir_benchmark_rows_bytes(b"{}\n", expected_count=count)  # type: ignore[arg-type]

    def test_beir_gold_ids_use_portable_collision_identity(self) -> None:
        collisions = (("A.txt", "a.txt"), ("doc-1.txt", "doc-01.txt"), ("Ａ.txt", "A.txt"))
        for left, right in collisions:
            payload = (
                json.dumps(
                    {
                        "query_id": "q",
                        "query": "x",
                        "answer": "",
                        "gold_ids": [left, right],
                    }
                )
                + "\n"
            ).encode()
            with self.subTest(left=left, right=right), self.assertRaisesRegex(
                DatasetError, "BEIR gold document"
            ):
                load_beir_benchmark_rows_bytes(payload)

    def test_beir_corpus_preflight_rejects_symlinks_and_missing_gold(self) -> None:
        payload = b'{"query_id":"q","query":"x","answer":"","gold_ids":["a.txt"]}\n'
        rows = load_beir_benchmark_rows_bytes(payload)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            corpus = root / "corpus"
            corpus.mkdir()
            (corpus / "a.txt").write_text("document")
            validate_beir_corpus(corpus, rows)

            (corpus / "a.txt").unlink()
            with self.assertRaisesRegex(DatasetError, "BEIR corpus"):
                validate_beir_corpus(corpus, rows)
            target = root / "target"
            target.mkdir()
            (target / "a.txt").write_text("document")
            corpus.rmdir()
            corpus.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(DatasetError, "BEIR corpus"):
                validate_beir_corpus(corpus, rows)


class PaperBrightDatasetTests(unittest.TestCase):
    @staticmethod
    def _row(query_id: object = 0) -> dict[str, object]:
        return {
            "query": "find documents",
            "reasoning": "source rationale",
            "id": "0",
            "excluded_ids": ["N/A"],
            "gold_ids_long": ["topic/document.txt"],
            "gold_ids": ["topic/document_0.txt", "topic/document_1.txt"],
            "query_id": query_id,
            "answer": "source answer",
        }

    def test_normalizes_exact_source_rows_and_integer_query_ids(self) -> None:
        payload = (
            json.dumps(self._row())
            + "\n"
            + json.dumps(self._row("earth_science_1") | {"id": "1"})
            + "\n"
        ).encode()

        first, second = load_bright_benchmark_rows_bytes(payload, expected_count=2)

        self.assertEqual(first.query_id, "0")
        self.assertEqual(second.query_id, "earth_science_1")
        self.assertEqual(
            first.gold_ids,
            ("topic/document_0.txt", "topic/document_1.txt"),
        )
        self.assertIsNone(first.answer)
        self.assertEqual(
            first.as_dict(),
            {
                "query_id": "0",
                "query": "find documents",
                "gold_ids": ["topic/document_0.txt", "topic/document_1.txt"],
            },
        )
        with self.assertRaises(DatasetError):
            load_benchmark_rows_bytes(payload)

    def test_rejects_source_shape_field_type_count_and_id_collisions(self) -> None:
        invalid_rows = []
        for field, replacement in (
            ("query", ""),
            ("reasoning", None),
            ("id", 0),
            ("excluded_ids", []),
            ("gold_ids_long", [""]),
            ("gold_ids", [1]),
            ("query_id", True),
            ("query_id", 1.0),
            ("answer", ""),
        ):
            invalid_rows.append(self._row() | {field: replacement})
        missing = self._row()
        missing.pop("reasoning")
        invalid_rows.extend((missing, self._row() | {"unknown": "field"}))

        for row in invalid_rows:
            with self.subTest(row=row), self.assertRaises(DatasetError):
                load_bright_benchmark_rows_bytes((json.dumps(row) + "\n").encode())

        collision = (
            json.dumps(self._row(1)) + "\n" + json.dumps(self._row("1")) + "\n"
        ).encode()
        with self.assertRaisesRegex(DatasetError, "query ID"):
            load_bright_benchmark_rows_bytes(collision)

        valid = (json.dumps(self._row()) + "\n").encode()
        for count in (0, -1, True, 1.0, "1", 2):
            with self.subTest(count=count), self.assertRaises(DatasetError):
                load_bright_benchmark_rows_bytes(valid, expected_count=count)  # type: ignore[arg-type]


class AsterionDciDatasetTests(unittest.TestCase):
    def _dataset(self, payload: bytes) -> Path:
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = Path(root.name) / "rows.jsonl"
        path.write_bytes(payload)
        return path

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_read_jsonl(self) -> None:
        path = self._dataset(
            b'\n{"query_id":"q-2","query":"two","answer":"a2"}\n'
            b'  \n{"query_id":"q-1","query":"one","answer":"a1"}\n'
        )
        rows = load_benchmark_rows(path)
        self.assertEqual([row.query_id for row in rows], ["q-2", "q-1"])
        self.assertEqual(read_jsonl(path), rows)
        self.assertIsInstance(rows, tuple)
        with self.assertRaisesRegex((AttributeError, TypeError), ""):
            rows[0].query_id = "changed"  # type: ignore[misc]

    def test_loads_ir_aliases_without_answer_and_preserves_optional_fields(
        self,
    ) -> None:
        path = self._dataset(
            b'{"query_id":"bright-1","query":"find docs","gold_docs":["a.txt","b.txt"]}\n'
            b'{"query_id":"bright-2","query":"find ids","gold_ids":["c.txt"]}\n'
        )
        first, second = load_benchmark_rows(path)
        self.assertEqual(first.gold_docs, ("a.txt", "b.txt"))
        self.assertIsNone(first.answer)
        self.assertEqual(second.gold_ids, ("c.txt",))
        self.assertIsNone(second.answer)

    def test_loads_qa_answer_aliases_and_preserves_source_shape(self) -> None:
        path = self._dataset(
            b'{"query_id":"qa-alias","query":"question","answer":["primary","alias"]}\n'
        )

        row = load_benchmark_rows(path)[0]

        self.assertEqual(row.answer, ("primary", "alias"))
        self.assertEqual(row.as_dict()["answer"], ["primary", "alias"])

    def test_preserves_representative_six_qa_and_four_bright_row_order(self) -> None:
        values = [
            {
                "query_id": f"qa-{index}",
                "query": f"question {index}",
                "answer": f"answer {index}",
            }
            for index in range(6)
        ] + [
            {
                "query_id": f"bright-{index}",
                "query": f"retrieval {index}",
                "gold_docs": [f"document-{index}.txt"],
            }
            for index in range(4)
        ]
        payload = ("\n\n".join(json.dumps(value) for value in values) + "\n").encode()
        rows = load_benchmark_rows(self._dataset(payload))
        self.assertEqual(
            tuple(row.query_id for row in rows),
            tuple(value["query_id"] for value in values),
        )
        self.assertEqual(sum(row.is_ir for row in rows), 4)

    def test_rejects_invalid_utf8_json_duplicate_keys_and_unknown_fields(self) -> None:
        invalid = (
            b"\xff",
            b'{"query_id":"q","query":}\n',
            b'{"query_id":"q","query":"x","query":"y","answer":"a"}\n',
            b'{"query_id":"q","query":"x","answer":"a","api_key":"secret"}\n',
            b"[]\n",
        )
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(DatasetError):
                load_benchmark_rows(self._dataset(payload))

    def test_all_accepted_text_ingress_is_strict_utf8_durable(self) -> None:
        accepted = {
            "query_id": "utf8-row",
            "query": "question\x00\u0085\u2028\u2029",
            "answer": "answer\x01\u2028",
        }
        row = load_benchmark_rows(
            self._dataset((json.dumps(accepted) + "\n").encode("utf-8"))
        )[0]
        json.dumps(row.as_dict(), ensure_ascii=False).encode("utf-8")

        ir = {
            "query_id": "utf8-ir",
            "query": "question\u2029",
            "gold_docs": ["document\x01\u2028.txt"],
        }
        ir_row = load_benchmark_rows(
            self._dataset((json.dumps(ir) + "\n").encode("utf-8"))
        )[0]
        json.dumps(ir_row.as_dict(), ensure_ascii=False).encode("utf-8")

        qa_prompt = build_qa_prompt("question\x00\u2028", Path("/tmp/corpus"))
        ir_prompt = build_ir_prompt(
            "question\u2029", Path("/tmp/corpus"), "hint\x01\u2028"
        )
        qa_prompt.encode("utf-8")
        ir_prompt.encode("utf-8")

    def test_rejects_lone_surrogates_at_every_durable_text_ingress(self) -> None:
        invalid_rows = (
            {"query_id": "q", "query": "bad\ud800", "answer": "a"},
            {"query_id": "q", "query": "q", "answer": "bad\udfff"},
            {"query_id": "q", "query": "q", "gold_docs": ["bad\ud800"]},
            {"query_id": "q", "query": "q", "gold_ids": ["bad\udfff"]},
        )
        for value in invalid_rows:
            with self.subTest(value=repr(value)), self.assertRaises(DatasetError):
                load_benchmark_rows(
                    self._dataset((json.dumps(value) + "\n").encode("utf-8"))
                )
        for prompt in (
            lambda: build_qa_prompt("bad\ud800", Path("/tmp/corpus")),
            lambda: build_ir_prompt("bad\udfff", Path("/tmp/corpus")),
            lambda: build_ir_prompt("q", Path("/tmp/corpus"), "bad\ud800"),
        ):
            with self.assertRaises(DatasetError):
                prompt()

    def test_requires_exact_nonempty_strings_and_mode_specific_gold(self) -> None:
        invalid_objects = [
            {"query_id": True, "query": "q", "answer": "a"},
            {"query_id": 1, "query": "q", "answer": "a"},
            {"query_id": "q", "query": None, "answer": "a"},
            {"query_id": "q", "query": "", "answer": "a"},
            {"query_id": "q", "query": "q", "answer": False},
            {"query_id": "q", "query": "q", "answer": None},
            {"query_id": "q", "query": "q", "answer": []},
            {"query_id": "q", "query": "q", "answer": [""]},
            {"query_id": "q", "query": "q", "answer": ["ok", 1]},
            {"query_id": "q", "query": "q", "answer": {"alias": "a"}},
            {"query_id": "q", "query": "q"},
            {"query_id": "q", "query": "q", "gold_docs": []},
            {"query_id": "q", "query": "q", "gold_ids": [1]},
            {"query_id": "q", "query": "q", "gold_docs": [""]},
            {"query_id": "q", "query": "q", "answer": "a", "gold_docs": ["x"]},
            {"query_id": "q", "query": "q", "gold_docs": ["x"], "gold_ids": ["x"]},
        ]
        for value in invalid_objects:
            payload = (json.dumps(value) + "\n").encode()
            with self.subTest(value=value), self.assertRaises(DatasetError):
                load_benchmark_rows(self._dataset(payload))

    def test_query_ids_use_portable_collision_and_reserved_name_rules(self) -> None:
        collision_groups = [
            ("Alpha", "alpha"),
            ("caf\u00e9", "cafe\u0301"),
            ("query-1", "query-01"),
        ]
        for left, right in collision_groups:
            with self.subTest(left=left, right=right):
                payload = (
                    json.dumps({"query_id": left, "query": "q", "answer": "a"})
                    + "\n"
                    + json.dumps({"query_id": right, "query": "q", "answer": "a"})
                    + "\n"
                ).encode()
                with self.assertRaisesRegex(DatasetError, "query ID"):
                    load_benchmark_rows(self._dataset(payload))
                self.assertEqual(
                    portable_query_id_key(left), portable_query_id_key(right)
                )

        for query_id in (
            "../escape",
            "a/b",
            r"a\b",
            "a\x00b",
            "CON",
            "con.txt",
            "summary.json",
            "results",
            ".inputs",
            "batch-state.json",
            ".asterion-dci-batch.lock",
            ".",
            "..",
            "trail.",
            "trail ",
            "a／b",
            "fullwidth：colon",
            "next\u0085line",
            "joined\u200dword",
            "line\u2028separator",
            "paragraph\u2029separator",
            "surrogate\ud800",
            "noncharacter\ufdd0",
            "plane-noncharacter\U0010ffff",
        ):
            with (
                self.subTest(query_id=query_id),
                self.assertRaisesRegex(DatasetError, "query ID"),
            ):
                portable_query_id_key(query_id)

        for query_id in ("日本語", "emoji-😀", "café", "a b"):
            with self.subTest(printable=query_id):
                self.assertTrue(portable_query_id_key(query_id))

    def test_portable_query_id_rejects_every_disallowed_unicode_scalar_property(
        self,
    ) -> None:
        for codepoint in range(0x110000):
            character = chr(codepoint)
            is_noncharacter = (
                0xFDD0 <= codepoint <= 0xFDEF or codepoint & 0xFFFE == 0xFFFE
            )
            if (
                unicodedata.category(character) in {"Cc", "Cf", "Cs"}
                or codepoint in {0x2028, 0x2029}
                or is_noncharacter
            ):
                with self.assertRaises(DatasetError):
                    portable_query_id_key(f"a{character}b")

    def test_portable_query_id_enforces_cross_platform_component_boundaries(
        self,
    ) -> None:
        accepted = (
            "a" * 255,
            "é" * 127,
            "e\u0301" * 85,
            "😀" * 63,
        )
        rejected = (
            "a" * 256,
            "é" * 128,
            "e\u0301" * 86,
            "😀" * 64,
            "query-" + "9" * 5000,
        )
        for query_id in accepted:
            with self.subTest(accepted=(len(query_id), repr(query_id[:4]))):
                self.assertTrue(portable_query_id_key(query_id))
        for query_id in rejected:
            with self.subTest(rejected=(len(query_id), repr(query_id[:4]))):
                with self.assertRaises(DatasetError):
                    portable_query_id_key(query_id)

    def test_jsonl_uses_physical_newlines_and_reports_physical_line_numbers(
        self,
    ) -> None:
        first = {"query_id": "q-1", "query": "a\u2028b\u2029c", "answer": "x"}
        second = {"query_id": "q-2", "query": "second", "answer": "y"}
        path = self._dataset(
            (
                json.dumps(first, ensure_ascii=False)
                + "\n\n"
                + json.dumps(second)
                + "\n"
            ).encode()
        )
        rows = load_benchmark_rows(path)
        self.assertEqual(rows[0].query, "a\u2028b\u2029c")
        self.assertEqual([row.query_id for row in rows], ["q-1", "q-2"])

        invalid = self._dataset(b'{"query_id":"q","query":"x","answer":"a"}\n\n{bad}\n')
        with self.assertRaisesRegex(DatasetError, "line 3"):
            load_benchmark_rows(invalid)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_build_benchmark_prompt(
        self,
    ) -> None:
        corpus = Path("/tmp/corpus")
        expected = (
            "Answer the following question. The answer is contained in the corpus directory at @/tmp/corpus. "
            "**Do Not use web search!** Use ripgrep (rg) instead of grep for fast searching. "
            "After using tools, always finish with a non-empty textual final answer.\n\n"
            "QUESTION:\nWhat?\n"
        )
        self.assertEqual(build_benchmark_prompt("What?", corpus), expected)
        self.assertEqual(build_qa_prompt("What?", corpus), expected)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_build_ir_prompt(
        self,
    ) -> None:
        prompt = build_ir_prompt(
            "Where?", Path("/tmp/corpus"), "one directory per topic"
        )
        self.assertEqual(
            prompt,
            "You are a careful research assistant. Answer the question below using ONLY documents in @/tmp/corpus.\n"
            "Do not use online search or any external tools beyond Grep and Bash.\n\n"
            "Question:\nWhere?\n\n"
            "CORPUS STRUCTURE:\none directory per topic\n\n"
            "SEARCH STRATEGY (follow exactly):\n"
            "1. Use Grep/Bash ONLY — do NOT use the Agent tool, spawn subagents, or browse the web.\n"
            "2. Run multiple Grep/Bash searches IN PARALLEL within a single response to save time.\n"
            "3. Use diverse, targeted keywords to maximize recall before drawing conclusions.\n"
            "4. After each round, reflect on gaps and launch follow-up searches to cover missing angles.\n"
            "5. Do NOT stop after finding a few documents — exhaust all plausible search angles.\n\n"
            "RETRIEVAL INSTRUCTIONS:\n"
            "- Both recall AND precision matter equally — the output is evaluated with NDCG, which penalizes both missing relevant documents and including irrelevant ones.\n"
            "- Find EVERY document that is genuinely relevant. Missing a gold document hurts recall.\n"
            "- Read each candidate document carefully before including it. Including an irrelevant document hurts precision.\n"
            "- A document is relevant only if it directly addresses the question or provides essential supporting evidence for the answer. Do NOT include tangential or loosely related documents.\n\n"
            "RANKING INSTRUCTIONS:\n"
            "- Rank the final list by relevance: the most directly useful document for answering the question goes first. Ranking quality affects NDCG score.\n\n"
            "Your response MUST follow this exact format:\n"
            "Relevant Documents (ranked by relevance, most relevant first; maximum 20):\n"
            "1. {corpus}/path/to/doc1.txt\n"
            "2. {corpus}/path/to/doc2.txt\n"
            "3. {corpus}/path/to/doc3.txt\n"
            "(use full relative paths from the working directory; list at most 20 documents; omit any document that is not directly relevant)\n\n"
            "Explanation: {step-by-step reasoning with inline citations, e.g. [{corpus}/relative_path]}\n"
            "Exact Answer: {concise final answer only}\n"
            "Confidence: {0–100%; use below 50% if evidence is weak, ambiguous, or missing}\n",
        )

    def test_prompt_corpus_identity_and_hint_branch_are_source_compatible(self) -> None:
        from asterion.dci.pi_rpc import FINAL_ANSWER_RECOVERY_PROMPT
        from dci.benchmark.pi_rpc_runner import (
            FINAL_ANSWER_RECOVERY_PROMPT as source_final_answer_recovery_prompt,
        )
        from scripts.bcplus_eval.run_bcplus_eval import (
            BENCHMARK_PROMPT_CONTRACT as source_prompt_contract,
            BENCHMARK_PROMPT_CONTRACT_SHA256 as source_prompt_contract_sha256,
            build_benchmark_prompt as source_qa_prompt,
            build_ir_prompt as source_ir_prompt,
        )

        corpus = Path("/tmp/corpus with space")
        qa = build_qa_prompt("Q", corpus)
        self.assertIn("@/tmp/corpus with space. ", qa)
        self.assertEqual(qa, source_qa_prompt("Q", corpus))
        self.assertEqual(
            build_ir_prompt("Q", corpus, ""), source_ir_prompt("Q", corpus, "")
        )
        self.assertEqual(
            build_ir_prompt("Q", corpus, "   "), source_ir_prompt("Q", corpus, "   ")
        )
        self.assertEqual(BENCHMARK_PROMPT_CONTRACT, source_prompt_contract)
        self.assertEqual(
            FINAL_ANSWER_RECOVERY_PROMPT, source_final_answer_recovery_prompt
        )
        self.assertEqual(
            BENCHMARK_PROMPT_CONTRACT_SHA256, source_prompt_contract_sha256
        )
        for unsafe in (
            "bad\npath",
            "bad\rpath",
            "bad\u0085path",
            "bad\u200dpath",
            "bad\u2028path",
            "bad\u2029path",
            "bad\ud800path",
            "bad\ufdd0path",
            "bad\U0010ffffpath",
        ):
            with self.subTest(unsafe=repr(unsafe)), self.assertRaises(DatasetError):
                build_qa_prompt("Q", Path(unsafe))


if __name__ == "__main__":
    unittest.main()
