from __future__ import annotations

import json
import unittest
from unittest import mock

from asterion.dci.analysis import (
    aggregate_results,
    compute_detailed_analysis,
    gather_query_metrics,
    write_analysis_artifacts,
)
from asterion.dci.export import DciExportError, export_resolution_summary
from asterion.dci.trajectory_resolution import TrajectoryResolutionError


def _resolution(
    *, localization: float, matched: int, retained: float | None = 0.5
) -> dict[str, object]:
    return {
        "schema": "dci.trajectory-resolution-summary/v1",
        "identity_sha256": "a" * 64,
        "dataset_id": "fixture.qa",
        "query_id": "q-1",
        "metrics": {
            "coverage": {"any": 1.0, "mean": 0.5, "all": 0.0},
            "localization": {
                "value": localization,
                "matched_gold_count": matched,
                "unavailable_reason": None,
            },
            "retained_coverage": {
                "value": retained,
                "unavailable_reason": (
                    None if retained is not None else "final-context-unavailable"
                ),
            },
        },
        "counts": {
            "gold_documents": matched * 2,
            "surfaced_gold_documents": matched,
            "tool_observations": 1,
            "alignments": matched,
        },
    }


def _metric(summary: dict[str, object], query_id: str) -> dict[str, object]:
    summary = json.loads(json.dumps(summary))
    summary["query_id"] = query_id
    return gather_query_metrics(
        row={"query_id": query_id, "query": "question", "answer": "answer"},
        state={"status": "completed", "messages": [], "tool_calls": []},
        latest_model_context={},
        final_text="answer",
        resolution_summary=summary,
    )


class PaperResolutionAnalysisTests(unittest.TestCase):
    def test_query_metrics_reject_unvalidated_resolution_fields(self) -> None:
        summary = _resolution(localization=0.5, matched=1)
        summary["body"] = "SECRET BODY"

        with self.assertRaises(ValueError):
            _metric(summary, "q-1")

    def test_analysis_tolerates_no_resolution_and_rejects_malformed_metrics(self) -> None:
        no_resolution = gather_query_metrics(
            row={"query_id": "q-1", "query": "question", "answer": "answer"},
            state={"status": "completed", "messages": [], "tool_calls": []},
            latest_model_context={},
            final_text="answer",
        )
        self.assertEqual(no_resolution["resolution_status"], "not-available")

        malformed = _resolution(localization=0.5, matched=1)
        malformed["metrics"] = []
        with self.assertRaises(ValueError):
            _metric(malformed, "q-1")

    def test_query_summary_jsonl_markdown_and_micro_aggregate_are_deterministic(self) -> None:
        first = _metric(_resolution(localization=0.5, matched=2), "q-1")
        second = _metric(
            _resolution(localization=1.0, matched=1, retained=None), "q-2"
        )

        summary = aggregate_results((first, second))
        analysis = compute_detailed_analysis(
            results=(first, second),
            rows=(
                {"query_id": "q-1", "query": "question", "answer": "answer"},
                {"query_id": "q-2", "query": "question", "answer": "answer"},
            ),
            summary=summary,
        )
        artifacts = write_analysis_artifacts(
            results=(first, second),
            rows=(
                {"query_id": "q-1", "query": "question", "answer": "answer"},
                {"query_id": "q-2", "query": "question", "answer": "answer"},
            ),
            summary=summary,
            include_figures=False,
        )

        self.assertEqual(summary["resolution"]["coverage"]["mean"], 0.5)
        self.assertAlmostEqual(summary["resolution"]["localization"], 2.0 / 3.0)
        self.assertEqual(summary["resolution"]["matched_gold_count"], 3)
        self.assertEqual(summary["resolution"]["retained_coverage"], 0.5)
        row = analysis["per_query_metrics"][0]
        self.assertEqual(row["resolution_status"], "available")
        self.assertEqual(row["coverage_any"], 1.0)
        self.assertEqual(row["localization"], 0.5)
        self.assertEqual(row["retained_coverage"], 0.5)
        jsonl = [json.loads(line) for line in artifacts["analysis.jsonl"].splitlines()]
        self.assertEqual(jsonl[1]["localization_matched_gold_count"], 1)
        self.assertIn("## Paper Resolution", artifacts["analysis.md"].decode())

    def test_resolution_figure_is_emitted_only_when_resolution_is_available(self) -> None:
        result = _metric(_resolution(localization=0.5, matched=1), "q-1")
        rows = ({"query_id": "q-1", "query": "question", "answer": "answer"},)
        artifacts = write_analysis_artifacts(
            results=(result,),
            rows=rows,
            summary=aggregate_results((result,)),
            include_figures=True,
        )
        self.assertIn("analysis_figures/resolution_metrics.png", artifacts)
        self.assertIn(
            "analysis_figures/resolution_metrics.png",
            artifacts["analysis.md"].decode(),
        )

    def test_export_uses_strict_body_free_projection_and_safe_failure(self) -> None:
        summary = _resolution(localization=0.5, matched=1)
        with mock.patch(
            "asterion.dci.trajectory_resolution.analyze_trajectory_resolution",
            return_value={"private": "SECRET BODY"},
        ), mock.patch(
            "asterion.dci.trajectory_resolution.public_resolution_projection",
            return_value=summary,
        ):
            exported = export_resolution_summary(
                run_dir=mock.sentinel.run_dir,
                attempt=1,
                corpus_dir=mock.sentinel.corpus_dir,
                gold_manifest_path=mock.sentinel.manifest,
                segment_characters=8,
            )
        self.assertEqual(exported, summary)
        self.assertNotIn("SECRET BODY", json.dumps(exported))

        with mock.patch(
            "asterion.dci.trajectory_resolution.analyze_trajectory_resolution",
            side_effect=TrajectoryResolutionError("SECRET BODY"),
        ), self.assertRaises(DciExportError):
            export_resolution_summary(
                run_dir=mock.sentinel.run_dir,
                attempt=1,
                corpus_dir=mock.sentinel.corpus_dir,
                gold_manifest_path=mock.sentinel.manifest,
                segment_characters=8,
            )


if __name__ == "__main__":
    unittest.main()
