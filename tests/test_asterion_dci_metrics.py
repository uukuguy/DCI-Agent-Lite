from __future__ import annotations

import math
import unittest
from pathlib import Path

from asterion.dci.metrics import (
    MetricError,
    compute_ir_ndcg,
    compute_ndcg_at_k,
    ndcg_at_k,
    normalize_retrieved_path,
    parse_retrieved_docs,
    parse_retrieved_documents,
)


class AsterionDciMetricTests(unittest.TestCase):
    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_parse_retrieved_docs(
        self,
    ) -> None:
        text = (
            "prefix Relevant Documents (ranked):\\n"
            "1. ./corpus/a.txt\\n"
            "2. C:\\corpus\\b.txt\\n"
            "3. ./corpus/a.txt\\n\\nExplanation: done"
        )
        expected = ["./corpus/a.txt", r"C:\corpus\b.txt", "./corpus/a.txt"]
        self.assertEqual(parse_retrieved_docs(text), expected)
        self.assertEqual(parse_retrieved_documents(text), expected)
        self.assertEqual(parse_retrieved_documents("no ranked block"), [])

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_normalize_retrieved_path(
        self,
    ) -> None:
        corpus = Path("/work/corpus")
        cases = {
            "/work/corpus/topic/a.txt": "topic/a.txt",
            r"\work\corpus\topic\a.txt": "topic/a.txt",
            "./topic/a.txt": "a.txt",
            "/elsewhere/topic/a.txt": "a.txt",
            "a.txt": "a.txt",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_retrieved_path(value, corpus), expected)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_compute_ndcg_at_k(
        self,
    ) -> None:
        self.assertEqual(compute_ndcg_at_k(["a"], set(), 10), 0.0)
        self.assertEqual(ndcg_at_k(["a"], {"a"}, 1), 1.0)
        expected = (1 / math.log2(3)) / (1 + 1 / math.log2(3))
        self.assertAlmostEqual(ndcg_at_k(["x", "b"], {"a", "b"}, 2), expected)
        # Source rank semantics count duplicate relevant documents independently.
        self.assertGreater(ndcg_at_k(["a", "a"], {"a"}, 2), 1.0)
        for invalid in (0, -1, True, 1.0, "10"):
            with self.subTest(invalid=invalid), self.assertRaises(MetricError):
                ndcg_at_k(["a"], {"a"}, invalid)  # type: ignore[arg-type]
        with self.assertRaises(MetricError):
            ndcg_at_k("a", {"a"}, 1)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_compute_ir_ndcg(
        self,
    ) -> None:
        final = "Relevant Documents:\n1. q1.txt\n2. /corpus/gold.txt\n3. gold.txt\n\nExplanation: x"
        score = compute_ir_ndcg(
            final,
            {"query_id": "q1", "gold_ids": ["gold.txt"]},
            Path("/corpus"),
            k=10,
        )
        # Self-query is excluded, while source duplicate rank semantics are preserved.
        self.assertGreater(score, 1.0)
        self.assertEqual(
            compute_ir_ndcg("Relevant Documents:\n1. x.txt", {"query_id": "q"}, None),
            0.0,
        )
        with self.assertRaises(MetricError):
            compute_ir_ndcg(final, {"query_id": "q", "gold_docs": [1]}, None)
        with self.assertRaises(MetricError):
            compute_ir_ndcg(
                final,
                {"query_id": "q", "gold_docs": False, "gold_ids": ["gold.txt"]},
                None,
            )


if __name__ == "__main__":
    unittest.main()
