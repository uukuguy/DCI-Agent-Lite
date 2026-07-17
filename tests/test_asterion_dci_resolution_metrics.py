from __future__ import annotations

import math
import unittest

from asterion.dci.resolution_metrics import (
    CoverageMetrics,
    DocumentLocalization,
    GoldDocumentSet,
    LocalizationAggregate,
    LocalizationUnavailableReason,
    ResolutionMetricError,
    SurfacedGoldSet,
    aggregate_dataset_localization,
    aggregate_query_coverage,
    best_document_localization,
    compute_query_coverage,
    compute_retained_coverage,
    coverage_all,
    coverage_any,
    coverage_mean,
    gold_document_set,
    localization_candidate_score,
    normalize_segment_count,
    query_localization,
    surfaced_gold_set,
)


class ResolutionCoverageTests(unittest.TestCase):
    def test_any_mean_all_match_hand_computed_multi_gold_values(self) -> None:
        gold = gold_document_set(("a.txt", "b.txt", "c.txt"))

        none = compute_query_coverage(gold, surfaced_gold_set(gold, ()))
        one = compute_query_coverage(gold, surfaced_gold_set(gold, ("b.txt",)))
        all_gold = compute_query_coverage(
            gold, surfaced_gold_set(gold, ("a.txt", "b.txt", "c.txt"))
        )

        self.assertEqual((none.any, none.mean, none.all), (0.0, 0.0, 0.0))
        self.assertEqual((one.any, one.mean, one.all), (1.0, 1.0 / 3.0, 0.0))
        self.assertEqual((all_gold.any, all_gold.mean, all_gold.all), (1.0, 1.0, 1.0))
        surfaced_one = surfaced_gold_set(gold, ("b.txt",))
        self.assertEqual(coverage_any(gold, surfaced_one), 1.0)
        self.assertEqual(coverage_mean(gold, surfaced_one), 1.0 / 3.0)
        self.assertEqual(coverage_all(gold, surfaced_one), 0.0)

    def test_gold_and_surfaced_sets_reject_empty_duplicate_and_foreign_ids(self) -> None:
        for values in ((), ("",), ("a", "a"), (True,)):
            with self.subTest(values=values), self.assertRaises(ResolutionMetricError):
                gold_document_set(values)  # type: ignore[arg-type]
        gold = gold_document_set(("a", "b"))
        for values in (("a", "a"), ("foreign",), (1,)):
            with self.subTest(values=values), self.assertRaises(ResolutionMetricError):
                surfaced_gold_set(gold, values)  # type: ignore[arg-type]

    def test_query_coverage_aggregation_is_arithmetic_per_query(self) -> None:
        first_gold = gold_document_set(("a",))
        second_gold = gold_document_set(("b", "c", "d"))
        aggregate = aggregate_query_coverage(
            (
                compute_query_coverage(
                    first_gold, surfaced_gold_set(first_gold, ("a",))
                ),
                compute_query_coverage(
                    second_gold, surfaced_gold_set(second_gold, ("b",))
                ),
            )
        )

        self.assertEqual(aggregate.any, 1.0)
        self.assertAlmostEqual(aggregate.mean, 2.0 / 3.0)
        self.assertEqual(aggregate.all, 0.5)
        with self.assertRaises(ResolutionMetricError):
            aggregate_query_coverage(())
        for forged in (
            (math.nan, 0.0, 0.0),
            (1.1, 0.0, 0.0),
            (True, 0.0, 0.0),
        ):
            with self.subTest(forged=forged), self.assertRaises(ResolutionMetricError):
                CoverageMetrics(*forged)  # type: ignore[arg-type]
        with self.assertRaises(ResolutionMetricError):
            CoverageMetrics(0.0, 1.0, 1.0)
        forged_high = object.__new__(CoverageMetrics)
        forged_low = object.__new__(CoverageMetrics)
        for target, values in ((forged_high, (2.0, 2.0, 2.0)), (forged_low, (0.0, 0.0, 0.0))):
            object.__setattr__(target, "any", values[0])
            object.__setattr__(target, "mean", values[1])
            object.__setattr__(target, "all", values[2])
        with self.assertRaises(ResolutionMetricError):
            aggregate_query_coverage((forged_high, forged_low))

    def test_forged_set_internals_are_revalidated_by_coverage_consumers(self) -> None:
        forged_gold = object.__new__(GoldDocumentSet)
        object.__setattr__(forged_gold, "ids", ("a", "a"))
        forged_surfaced = object.__new__(SurfacedGoldSet)
        object.__setattr__(forged_surfaced, "ids", ("a", "a"))

        with self.assertRaises(ResolutionMetricError):
            compute_query_coverage(forged_gold, forged_surfaced)
        with self.assertRaises(ResolutionMetricError):
            compute_retained_coverage(forged_gold, forged_surfaced)
        with self.assertRaises(ResolutionMetricError):
            surfaced_gold_set(forged_gold, ("a",))

    def test_retained_coverage_is_separate_and_missing_context_is_unavailable(self) -> None:
        gold = gold_document_set(("a", "b"))
        unavailable = compute_retained_coverage(gold, None)
        retained = compute_retained_coverage(gold, surfaced_gold_set(gold, ("a",)))

        self.assertIsNone(unavailable.value)
        self.assertEqual(
            unavailable.unavailable_reason,
            LocalizationUnavailableReason.FINAL_CONTEXT_UNAVAILABLE,
        )
        self.assertEqual(retained.value, 0.5)
        self.assertIsNone(retained.unavailable_reason)


class ResolutionLocalizationTests(unittest.TestCase):
    def test_segment_boundaries_and_b_equals_one(self) -> None:
        self.assertEqual(normalize_segment_count(1, 100), 1)
        self.assertEqual(normalize_segment_count(100, 100), 1)
        self.assertEqual(normalize_segment_count(101, 100), 2)
        self.assertEqual(localization_candidate_score(1, 100, 100), 1.0)
        self.assertEqual(localization_candidate_score(100, 100, 100), 1.0)
        self.assertEqual(localization_candidate_score(100, 400, 100), 1.0)
        self.assertEqual(localization_candidate_score(400, 400, 100), 0.0)

    def test_per_document_keeps_maximum_and_full_document_fallback(self) -> None:
        best = best_document_localization(
            "a.txt",
            full_document_characters=400,
            candidate_snippet_characters=(300, 100, 100),
            segment_characters=100,
        )
        fallback = best_document_localization(
            "b.txt",
            full_document_characters=400,
            candidate_snippet_characters=(),
            segment_characters=100,
        )

        self.assertEqual(best.document_id, "a.txt")
        self.assertEqual(best.score, 1.0)
        self.assertEqual(fallback.score, 0.0)

    def test_smaller_snippet_never_scores_worse_and_scores_are_bounded(self) -> None:
        for full_length in range(1, 301, 17):
            previous = -1.0
            for snippet_length in range(full_length, 0, -1):
                score = localization_candidate_score(
                    snippet_length, full_length, 13
                )
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 1.0)
                self.assertGreaterEqual(score, previous)
                previous = score

    def test_invalid_lengths_segment_widths_and_nonfinite_values_fail_closed(self) -> None:
        invalid = (0, -1, True, 1.5, math.nan, math.inf)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ResolutionMetricError):
                normalize_segment_count(value, 100)  # type: ignore[arg-type]
            with self.subTest(segment=value), self.assertRaises(ResolutionMetricError):
                normalize_segment_count(1, value)  # type: ignore[arg-type]
        with self.assertRaises(ResolutionMetricError):
            localization_candidate_score(101, 100, 10)

    def test_query_and_dataset_localization_use_surfaced_gold_micro_aggregation(self) -> None:
        first = query_localization(
            (best_document_localization("a", 400, (100,), 100),)
        )
        second = query_localization(
            (
                best_document_localization("b", 400, (), 100),
                best_document_localization("c", 400, (), 100),
            )
        )
        unavailable = query_localization(())
        dataset = aggregate_dataset_localization((first, second, unavailable))

        self.assertEqual(first.value, 1.0)
        self.assertEqual(second.value, 0.0)
        self.assertIsNone(unavailable.value)
        self.assertEqual(
            unavailable.unavailable_reason,
            LocalizationUnavailableReason.NO_SURFACED_GOLD,
        )
        self.assertAlmostEqual(dataset.value or 0.0, 1.0 / 3.0)
        self.assertEqual(dataset.matched_gold_count, 3)

        with self.assertRaises(ResolutionMetricError):
            query_localization(
                (DocumentLocalization("same", 0.5), DocumentLocalization("same", 0.4))
            )
        with self.assertRaises(ResolutionMetricError):
            DocumentLocalization("bad", math.nan)

    def test_forged_query_aggregate_cannot_enter_dataset_micro_average(self) -> None:
        forged = object.__new__(LocalizationAggregate)
        object.__setattr__(forged, "value", 1.0)
        object.__setattr__(forged, "matched_gold_count", 0)
        object.__setattr__(forged, "per_document", ())
        object.__setattr__(forged, "unavailable_reason", None)

        with self.assertRaises(ResolutionMetricError):
            aggregate_dataset_localization((forged,))

        forged_document = object.__new__(DocumentLocalization)
        object.__setattr__(forged_document, "document_id", "bad")
        object.__setattr__(forged_document, "score", 2.0)
        forged_nonempty = object.__new__(LocalizationAggregate)
        object.__setattr__(forged_nonempty, "value", 2.0)
        object.__setattr__(forged_nonempty, "matched_gold_count", 1)
        object.__setattr__(forged_nonempty, "per_document", (forged_document,))
        object.__setattr__(forged_nonempty, "unavailable_reason", None)
        with self.assertRaises(ResolutionMetricError):
            aggregate_dataset_localization((forged_nonempty,))

        duplicate_query = LocalizationAggregate(
            value=0.5,
            matched_gold_count=2,
            per_document=(
                DocumentLocalization("same", 0.5),
                DocumentLocalization("same", 0.5),
            ),
            unavailable_reason=None,
        )
        with self.assertRaises(ResolutionMetricError):
            aggregate_dataset_localization((duplicate_query,))

    def test_zero_dataset_denominator_is_unavailable(self) -> None:
        aggregate = aggregate_dataset_localization((query_localization(()),))

        self.assertIsNone(aggregate.value)
        self.assertEqual(aggregate.matched_gold_count, 0)
        self.assertEqual(
            aggregate.unavailable_reason,
            LocalizationUnavailableReason.NO_DATASET_SURFACED_GOLD,
        )
        with self.assertRaises(ResolutionMetricError):
            aggregate_dataset_localization(())


if __name__ == "__main__":
    unittest.main()
