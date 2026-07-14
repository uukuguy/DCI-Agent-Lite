from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from asterion.dci.datasets import (
    DatasetError,
    build_benchmark_prompt,
    build_ir_prompt,
    build_qa_prompt,
    load_benchmark_rows,
    portable_query_id_key,
    read_jsonl,
)


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
            b'{"query_id":"bright-2","query":"find ids","gold_ids":["c.txt"],"answer":"optional"}\n'
        )
        first, second = load_benchmark_rows(path)
        self.assertEqual(first.gold_docs, ("a.txt", "b.txt"))
        self.assertIsNone(first.answer)
        self.assertEqual(second.gold_ids, ("c.txt",))
        self.assertEqual(second.answer, "optional")

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

    def test_requires_exact_nonempty_strings_and_mode_specific_gold(self) -> None:
        invalid_objects = [
            {"query_id": True, "query": "q", "answer": "a"},
            {"query_id": 1, "query": "q", "answer": "a"},
            {"query_id": "q", "query": None, "answer": "a"},
            {"query_id": "q", "query": "", "answer": "a"},
            {"query_id": "q", "query": "q", "answer": False},
            {"query_id": "q", "query": "q", "answer": None},
            {"query_id": "q", "query": "q"},
            {"query_id": "q", "query": "q", "gold_docs": []},
            {"query_id": "q", "query": "q", "gold_ids": [1]},
            {"query_id": "q", "query": "q", "gold_docs": [""]},
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
            ".",
            "..",
            "trail.",
            "trail ",
            "a／b",
            "fullwidth：colon",
        ):
            with (
                self.subTest(query_id=query_id),
                self.assertRaisesRegex(DatasetError, "query ID"),
            ):
                portable_query_id_key(query_id)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_build_benchmark_prompt(
        self,
    ) -> None:
        corpus = Path("/tmp/corpus")
        expected = (
            "Answer the following question. The answer is contained in the corpus directory at @/tmp/corpus. "
            "**Do Not use web search!** Use ripgrep (rg) instead of grep for fast searching.\n\n"
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


if __name__ == "__main__":
    unittest.main()
