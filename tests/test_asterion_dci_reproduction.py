from __future__ import annotations

import json
import math
import stat
import tempfile
import unittest
from dataclasses import FrozenInstanceError, fields, replace
from importlib import resources
from pathlib import Path
from types import MappingProxyType

from asterion.dci.cli import main
from asterion.dci import reproduction as reproduction_module
from asterion.dci.experiment_profiles import (
    experiment_profile_sha256,
    resolve_experiment_profile,
)
from asterion.dci.reproduction import (
    COMPARISON_SCHEMA,
    ESTIMATOR_NAME,
    ESTIMATOR_RESAMPLES,
    RUN_MANIFEST_SCHEMA,
    reproduction_metric_contract_sha256,
    QueryEvidence,
    OperationCounts,
    TokenCounts,
    ConfidenceInterval,
    EstimatorEvidence,
    MetricComparison,
    compare_reproduction_runs,
    load_run_manifest,
    write_comparison_report,
)


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64
_SHA_E = "e" * 64


def _query(
    query_id: str,
    *,
    status: str = "completed",
    verdict: bool | None = True,
    ndcg: float | None = None,
    failure_class: str | None = None,
    exclusion_reason: str | None = None,
    agent_operations: int = 1,
    judge_operations: int = 1,
    input_tokens: int = 10,
    cached_input_tokens: int = 2,
    output_tokens: int = 3,
    cost_usd: float = 0.01,
    evidence_sha256: str = _SHA_C,
) -> dict[str, object]:
    return {
        "query_id": query_id,
        "status": status,
        "judge_verdict": verdict,
        "ndcg_at_10": ndcg,
        "failure_class": failure_class,
        "exclusion_reason": exclusion_reason,
        "evidence_sha256": evidence_sha256,
        "operations": {
            "agent": agent_operations,
            "judge": judge_operations,
        },
        "tokens": {
            "input": input_tokens,
            "cached_input": cached_input_tokens,
            "output": output_tokens,
        },
        "cost_usd": cost_usd,
    }


def _aggregates(
    queries: list[dict[str, object]], metric_identities: list[str]
) -> dict[str, object]:
    included = [
        row
        for row in queries
        if row["exclusion_reason"] is None or row["status"] != "completed"
    ]
    completed = [row for row in included if row["status"] == "completed"]
    verdicts = [
        1.0 if row["judge_verdict"] is True else 0.0
        for row in included
    ] if "llm-answer-correctness" in metric_identities else []
    ndcgs = [
        float(row["ndcg_at_10"] or 0.0)
        for row in included
    ] if "ndcg@10-binary-deduplicated" in metric_identities else []
    input_tokens = sum(int(row["tokens"]["input"]) for row in queries)  # type: ignore[index]
    cached_tokens = sum(
        int(row["tokens"]["cached_input"]) for row in queries  # type: ignore[index]
    )
    output_tokens = sum(int(row["tokens"]["output"]) for row in queries)  # type: ignore[index]
    return {
        "query_count": len(queries),
        "included_count": len(included),
        "excluded_count": len(queries) - len(included),
        "completed_count": len(completed),
        "failed_count": sum(row["status"] == "failed" for row in included),
        "cancelled_count": sum(row["status"] == "cancelled" for row in included),
        "timed_out_count": sum(row["status"] == "timed_out" for row in included),
        "missing_count": sum(row["status"] == "missing" for row in included),
        "accuracy": sum(verdicts) / len(verdicts) if verdicts else None,
        "mean_ndcg_at_10": sum(ndcgs) / len(ndcgs) if ndcgs else None,
        "agent_operations": sum(
            int(row["operations"]["agent"]) for row in queries  # type: ignore[index]
        ),
        "judge_operations": sum(
            int(row["operations"]["judge"]) for row in queries  # type: ignore[index]
        ),
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + cached_tokens + output_tokens,
        "cost_usd": sum(float(row["cost_usd"]) for row in queries),
    }


def _manifest(
    queries: list[dict[str, object]],
    *,
    profile_id: str = "current-default/pi",
    runtime: str = "pi",
    dataset_id: str | None = None,
    selection_id: str | None = None,
    selection_sha256: str = _SHA_A,
    effective_config_sha256: str = _SHA_B,
    product: str = "asterion-dci",
    run_id: str | None = None,
) -> dict[str, object]:
    queries = sorted(queries, key=lambda row: str(row["query_id"]))
    if any(row["ndcg_at_10"] is not None for row in queries):
        metric_identities = ["ndcg@10-binary-deduplicated"]
    else:
        metric_identities = ["llm-answer-correctness"]
    dataset_id = dataset_id or (
        "beir.arguana"
        if metric_identities == ["ndcg@10-binary-deduplicated"]
        else "qa.bamboogle"
    )
    selection_id = selection_id or f"{dataset_id}.fixture.all"
    value: dict[str, object] = {
        "schema": RUN_MANIFEST_SCHEMA,
        "run_id": run_id or (
            "run.original/v1" if product == "original-dci" else "run.asterion/v1"
        ),
        "product": product,
        "implementation_sha256": _SHA_D if product == "original-dci" else _SHA_E,
        "profile_id": profile_id,
        "profile_sha256": experiment_profile_sha256(profile_id),
        "runtime": runtime,
        "dataset_id": dataset_id,
        "selection_id": selection_id,
        "selection_sha256": selection_sha256,
        "effective_config_sha256": effective_config_sha256,
        "product_effective_config_sha256": (
            _SHA_D if product == "original-dci" else _SHA_E
        ),
        "metric_contract_sha256": reproduction_metric_contract_sha256(profile_id),
        "metric_identities": metric_identities,
        "queries": queries,
        "aggregates": _aggregates(queries, metric_identities),
    }
    from asterion.dci.paper_benchmarks import canonical_sha256

    value["identity_sha256"] = canonical_sha256(value)
    return value


def _source_manifest(
    queries: list[dict[str, object]], **kwargs: object
) -> dict[str, object]:
    return _manifest(queries, product="original-dci", **kwargs)  # type: ignore[arg-type]


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _rehash(value: dict[str, object]) -> None:
    from asterion.dci.paper_benchmarks import canonical_sha256

    value["identity_sha256"] = canonical_sha256(
        {key: item for key, item in value.items() if key != "identity_sha256"}
    )


def _forge_report_metrics(report, metrics: dict[str, MetricComparison]):
    """Build a self-hashed report without invoking its constructor validation."""

    forged = object.__new__(type(report))
    for field in fields(report):
        object.__setattr__(
            forged,
            field.name,
            MappingProxyType(dict(metrics))
            if field.name == "metrics"
            else getattr(report, field.name),
        )
    from asterion.dci.paper_benchmarks import canonical_sha256

    object.__setattr__(forged, "identity_sha256", canonical_sha256(forged._unsigned_dict()))
    return forged


def _forge_report(report, **changes: object):
    forged = object.__new__(type(report))
    for field in fields(report):
        value = changes.get(field.name, getattr(report, field.name))
        if field.name == "metrics":
            value = MappingProxyType(dict(value))  # type: ignore[arg-type]
        object.__setattr__(forged, field.name, value)
    from asterion.dci.paper_benchmarks import canonical_sha256

    object.__setattr__(forged, "identity_sha256", canonical_sha256(forged._unsigned_dict()))
    return forged


class ReproductionManifestTests(unittest.TestCase):
    def _load_value(self, value: dict[str, object]):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            _write(path, value)
            return load_run_manifest(path)

    def test_manifest_is_frozen_stably_ordered_and_body_free(self) -> None:
        value = _manifest([_query("q-1"), _query("q-2")])
        manifest = self._load_value(value)

        self.assertEqual([row.query_id for row in manifest.queries], ["q-1", "q-2"])
        self.assertIsInstance(manifest.queries[0], QueryEvidence)
        with self.assertRaises(FrozenInstanceError):
            manifest.run_id = "changed"  # type: ignore[misc]
        with self.assertRaises(ValueError):
            replace(manifest, dataset_id="")
        self.assertNotIn('"answer":', json.dumps(manifest.to_dict()))

    def test_direct_query_evidence_construction_is_strict(self) -> None:
        with self.assertRaises(ValueError):
            QueryEvidence(
                query_id="",
                status="completed",
                judge_verdict=True,
                ndcg_at_10=None,
                failure_class=None,
                exclusion_reason=None,
                evidence_sha256=_SHA_C,
                operations=OperationCounts(agent=1, judge=1),
                tokens=TokenCounts(input=1, cached_input=0, output=1),
                cost_usd=0.0,
            )

    def test_manifest_rejects_duplicate_or_missing_query_ids(self) -> None:
        for queries in (
            [_query("q-1"), _query("q-1")],
            [_query("")],
        ):
            with self.subTest(queries=queries), self.assertRaises(ValueError):
                self._load_value(_manifest(queries))

        value = _manifest([_query("q-1"), _query("q-2")])
        value["queries"] = list(reversed(value["queries"]))  # type: ignore[arg-type]
        from asterion.dci.paper_benchmarks import canonical_sha256

        value["identity_sha256"] = canonical_sha256(
            {key: item for key, item in value.items() if key != "identity_sha256"}
        )
        with self.assertRaises(ValueError):
            self._load_value(value)

    def test_manifest_rejects_all_non_completed_rows_without_failure_class(self) -> None:
        for status in ("failed", "cancelled", "timed_out", "missing"):
            row = _query(status, status=status, verdict=None)
            with self.subTest(status=status), self.assertRaises(ValueError):
                self._load_value(_manifest([row]))

            row["failure_class"] = f"runtime.{status}/v1"
            loaded = self._load_value(_manifest([row]))
            self.assertEqual(loaded.aggregates.accuracy, 0.0)

    def test_manifest_rejects_exclusion_without_versioned_reason(self) -> None:
        row = _query("q-1", verdict=None, exclusion_reason="not applicable")
        with self.assertRaises(ValueError):
            self._load_value(_manifest([row]))
        row["exclusion_reason"] = "metric.not-applicable/v1"
        self.assertEqual(self._load_value(_manifest([row])).aggregates.excluded_count, 1)

    def test_manifest_rejects_unknown_body_or_credential_fields_at_any_depth(self) -> None:
        for field in ("answer", "prompt_body", "api_key", "credential", "tool_body"):
            value = _manifest([_query("q-1")])
            value["queries"][0][field] = "SECRET"  # type: ignore[index]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self._load_value(value)

        value = _manifest([_query("q-1")])
        value["unexpected"] = "field"
        with self.assertRaises(ValueError):
            self._load_value(value)

    def test_manifest_rejects_non_finite_or_inconsistent_aggregates(self) -> None:
        for bad in (math.nan, math.inf, -math.inf):
            value = _manifest([_query("q-1")])
            value["queries"][0]["cost_usd"] = bad  # type: ignore[index]
            _rehash(value)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self._load_value(value)

        value = _manifest([_query("q-1")])
        value["aggregates"]["completed_count"] = 0  # type: ignore[index]
        _rehash(value)
        with self.assertRaises(ValueError):
            self._load_value(value)

    def test_manifest_rejects_invalid_exact_digests(self) -> None:
        for field in (
            "profile_sha256",
            "selection_sha256",
            "effective_config_sha256",
        ):
            value = _manifest([_query("q-1")])
            value[field] = "not-a-sha256"
            _rehash(value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self._load_value(value)

    def test_manifest_schema_binds_product_and_independent_provenance(self) -> None:
        schema = json.loads(
            resources.files("asterion.dci.resources")
            .joinpath("reproduction-result.schema.json")
            .read_text(encoding="utf-8")
        )
        required = set(schema["$defs"]["run_manifest"]["required"])
        self.assertTrue(
            {
                "product",
                "implementation_sha256",
                "product_effective_config_sha256",
            }.issubset(required)
        )

    def test_manifest_rejects_runtime_profile_mismatch(self) -> None:
        value = _manifest(
            [_query("q-1")],
            profile_id="paper-reference/claude-code",
            runtime="pi",
        )
        with self.assertRaises(ValueError):
            self._load_value(value)

    def test_manifest_requires_each_declared_metric_on_completed_rows(self) -> None:
        value = _manifest([_query("q-1", verdict=None, ndcg=0.5)])
        value["metric_identities"] = ["llm-answer-correctness"]
        _rehash(value)
        with self.assertRaises(ValueError):
            self._load_value(value)

    def test_comparison_rejects_identity_drift(self) -> None:
        baseline = self._load_value(_source_manifest([_query("q-1")]))
        drifts = {
            "dataset_id": "qa.other.main",
            "selection_id": "qa.fixture.other",
            "selection_sha256": _SHA_C,
            "effective_config_sha256": _SHA_C,
            "profile_id": "paper-reference/pi",
        }
        for key, value in drifts.items():
            candidate_value = _manifest([_query("q-1")])
            if key == "profile_id":
                candidate_value = _manifest(
                    [_query("q-1")], profile_id=str(value)
                )
            else:
                candidate_value[key] = value
                from asterion.dci.paper_benchmarks import canonical_sha256

                candidate_value["identity_sha256"] = canonical_sha256(
                    {k: v for k, v in candidate_value.items() if k != "identity_sha256"}
                )
            candidate = self._load_value(candidate_value)
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare_reproduction_runs(
                    baseline, candidate, resolve_experiment_profile("current-default/pi")
                )


class ReproductionStatisticsTests(unittest.TestCase):
    def _loaded(self, value: dict[str, object]):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            _write(path, value)
            return load_run_manifest(path)

    def _accuracy_report(self, *, count: int, regressions: int):
        baseline_rows = [_query(f"q-{index:04d}") for index in range(count)]
        candidate_rows = [
            _query(f"q-{index:04d}", verdict=index >= regressions)
            for index in range(count)
        ]
        return compare_reproduction_runs(
            self._loaded(_source_manifest(baseline_rows)),
            self._loaded(_manifest(candidate_rows)),
            resolve_experiment_profile("current-default/pi"),
        )

    def _ndcg_report(self, delta: float):
        baseline = _source_manifest(
            [_query(f"q-{i}", verdict=None, ndcg=0.5) for i in range(20)]
        )
        candidate = _manifest(
            [_query(f"q-{i}", verdict=None, ndcg=0.5 + delta) for i in range(20)]
        )
        return compare_reproduction_runs(
            self._loaded(baseline),
            self._loaded(candidate),
            resolve_experiment_profile("current-default/pi"),
        )

    def _forged_metric_reports(self):
        report = self._accuracy_report(count=20, regressions=0)
        metric = report.metrics["accuracy"]
        drifted_values = MetricComparison(
            baseline=0.5,
            candidate=0.5,
            delta=0.0,
            confidence_interval=metric.confidence_interval,
            margin=metric.margin,
            accepted=metric.accepted,
            estimator=metric.estimator,
        )
        drifted_sample = replace(
            metric,
            estimator=replace(metric.estimator, sample_sha256=_SHA_A),
        )
        drifted_interval = replace(
            metric,
            confidence_interval=ConfidenceInterval(lower=-0.01, upper=0.01),
        )
        return {
            "point-values": _forge_report_metrics(
                report, {"accuracy": drifted_values}
            ),
            "sample-digest": _forge_report_metrics(
                report, {"accuracy": drifted_sample}
            ),
            "bootstrap-interval": _forge_report_metrics(
                report, {"accuracy": drifted_interval}
            ),
        }

    def _assert_report_forgery_rejected_everywhere(self, forged) -> None:
        with self.assertRaises(ValueError):
            replace(forged, identity_sha256=forged.identity_sha256)
        with self.assertRaises(ValueError):
            forged.to_dict()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            serialized = {
                **forged._unsigned_dict(),
                "identity_sha256": forged.identity_sha256,
            }
            source = root / "forged.json"
            _write(source, serialized)
            with self.assertRaises(ValueError):
                reproduction_module.load_comparison_report(source)
            private = root / "private"
            private.mkdir(mode=0o700)
            output = private / "report.json"
            with self.assertRaises(ValueError):
                write_comparison_report(output, forged)
            self.assertFalse(output.exists())

    def test_accuracy_minus_point_zero_four_passes_and_is_deterministic(self) -> None:
        report = self._accuracy_report(count=2_500, regressions=100)
        metric = report.metrics["accuracy"]
        self.assertAlmostEqual(metric.delta, -0.04)
        self.assertGreaterEqual(metric.confidence_interval.lower, -0.05)
        self.assertTrue(metric.accepted)
        self.assertTrue(report.accepted)
        self.assertEqual(metric.estimator.name, ESTIMATOR_NAME)
        self.assertEqual(metric.estimator.resamples, ESTIMATOR_RESAMPLES)
        self.assertEqual(len(metric.estimator.query_set_sha256), 64)
        self.assertEqual(report.to_json_bytes(), report.to_json_bytes())

    def test_accuracy_minus_point_zero_six_fails(self) -> None:
        report = self._accuracy_report(count=2_500, regressions=150)
        metric = report.metrics["accuracy"]
        self.assertAlmostEqual(metric.delta, -0.06)
        self.assertLess(metric.confidence_interval.lower, -0.05)
        self.assertFalse(metric.accepted)
        self.assertFalse(report.accepted)

    def test_all_failed_rows_contribute_zero_to_declared_metric(self) -> None:
        rows = [
            _query(
                "q-1",
                status="failed",
                verdict=None,
                failure_class="runtime.failed/v1",
            )
        ]
        baseline = self._loaded(_source_manifest(rows))
        candidate = self._loaded(_manifest(rows))
        report = compare_reproduction_runs(
            baseline,
            candidate,
            resolve_experiment_profile("current-default/pi"),
        )
        self.assertEqual(report.metrics["accuracy"].candidate, 0.0)

    def test_ndcg_threshold_fixtures_use_lower_confidence_bound(self) -> None:
        passing = self._ndcg_report(-0.019)
        failing = self._ndcg_report(-0.021)
        self.assertAlmostEqual(passing.metrics["ndcg_at_10"].delta, -0.019)
        self.assertAlmostEqual(
            passing.metrics["ndcg_at_10"].confidence_interval.lower, -0.019
        )
        self.assertTrue(passing.metrics["ndcg_at_10"].accepted)
        self.assertAlmostEqual(failing.metrics["ndcg_at_10"].delta, -0.021)
        self.assertFalse(failing.metrics["ndcg_at_10"].accepted)

    def test_report_preserves_pairs_exclusions_rates_and_totals(self) -> None:
        baseline_rows = [
            _query("q-1"),
            _query("q-2", verdict=None, exclusion_reason="metric.not-applicable/v1"),
            _query(
                "q-3",
                status="timed_out",
                verdict=None,
                failure_class="runtime.timeout/v1",
                judge_operations=0,
            ),
        ]
        candidate_rows = [
            _query("q-1", input_tokens=20, cost_usd=0.02),
            _query(
                "q-2", verdict=None, exclusion_reason="metric.not-applicable/v1"
            ),
            _query(
                "q-3",
                status="failed",
                verdict=None,
                failure_class="runtime.failed/v1",
                judge_operations=0,
            ),
        ]
        report = compare_reproduction_runs(
            self._loaded(_source_manifest(baseline_rows)),
            self._loaded(_manifest(candidate_rows)),
            resolve_experiment_profile("current-default/pi"),
        )
        self.assertEqual(report.pair_ids, ("q-1", "q-3"))
        self.assertEqual(report.exclusion_ids, ("q-2",))
        self.assertAlmostEqual(report.candidate.completion_rate, 0.5)
        self.assertAlmostEqual(report.candidate.failure_rate, 0.5)
        self.assertEqual(report.candidate.agent_operations, 3)
        self.assertEqual(report.candidate.judge_operations, 2)
        self.assertEqual(report.candidate.input_tokens, 40)
        self.assertEqual(report.candidate.total_tokens, 55)
        self.assertAlmostEqual(report.candidate.cost_usd, 0.04)

    def test_report_retains_complete_body_free_pair_and_exclusion_evidence(self) -> None:
        baseline_rows = [
            _query("q-1", verdict=True, ndcg=None),
            _query("q-2", verdict=None, exclusion_reason="metric.not-applicable/v1"),
        ]
        candidate_rows = [
            _query("q-1", verdict=False, ndcg=None),
            _query("q-2", verdict=None, exclusion_reason="metric.not-applicable/v1"),
        ]
        report = compare_reproduction_runs(
            self._loaded(_source_manifest(baseline_rows)),
            self._loaded(_manifest(candidate_rows)),
            resolve_experiment_profile("current-default/pi"),
        )
        payload = report.to_dict()
        pair = payload["pairs"][0]
        self.assertEqual(
            set(pair), {"query_id", "baseline", "candidate"}
        )
        self.assertEqual(
            set(pair["baseline"]),
            {"status", "judge_verdict", "ndcg_at_10", "evidence_sha256"},
        )
        exclusion = payload["exclusions"][0]
        self.assertEqual(exclusion["query_id"], "q-2")
        self.assertEqual(
            exclusion["baseline"]["exclusion_reason"],
            "metric.not-applicable/v1",
        )
        self.assertNotIn('"answer":', json.dumps(payload))

    def test_estimator_sample_digest_binds_values_status_and_evidence(self) -> None:
        baseline = self._loaded(
            _source_manifest([_query("q-1"), _query("q-2")])
        )
        first = self._loaded(
            _manifest([_query("q-1", verdict=False), _query("q-2")])
        )
        second = self._loaded(_manifest([_query("q-1"), _query("q-2")]))
        first_report = compare_reproduction_runs(
            baseline, first, resolve_experiment_profile("current-default/pi")
        )
        second_report = compare_reproduction_runs(
            baseline, second, resolve_experiment_profile("current-default/pi")
        )
        self.assertNotEqual(
            first_report.metrics["accuracy"].estimator.sample_sha256,
            second_report.metrics["accuracy"].estimator.sample_sha256,
        )
        evidence_variant = self._loaded(
            _manifest(
                [
                    _query("q-1", verdict=False, evidence_sha256=_SHA_D),
                    _query("q-2"),
                ]
            )
        )
        status_variant = self._loaded(
            _manifest(
                [
                    _query(
                        "q-1",
                        status="failed",
                        verdict=None,
                        failure_class="runtime.failed/v1",
                    ),
                    _query("q-2"),
                ]
            )
        )
        evidence_report = compare_reproduction_runs(
            baseline,
            evidence_variant,
            resolve_experiment_profile("current-default/pi"),
        )
        status_report = compare_reproduction_runs(
            baseline,
            status_variant,
            resolve_experiment_profile("current-default/pi"),
        )
        self.assertEqual(
            first_report.metrics["accuracy"].delta,
            evidence_report.metrics["accuracy"].delta,
        )
        self.assertEqual(
            first_report.metrics["accuracy"].delta,
            status_report.metrics["accuracy"].delta,
        )
        self.assertNotEqual(
            first_report.metrics["accuracy"].estimator.sample_sha256,
            evidence_report.metrics["accuracy"].estimator.sample_sha256,
        )
        self.assertNotEqual(
            first_report.metrics["accuracy"].estimator.sample_sha256,
            status_report.metrics["accuracy"].estimator.sample_sha256,
        )

    def test_constructor_rejects_self_hashed_cross_field_metric_forgery(self) -> None:
        for drift, forged in self._forged_metric_reports().items():
            with self.subTest(drift=drift), self.assertRaises(ValueError):
                replace(
                    forged,
                    metrics=dict(forged.metrics),
                    identity_sha256=forged.identity_sha256,
                )

    def test_load_rejects_self_hashed_cross_field_metric_forgery(self) -> None:
        loader = getattr(reproduction_module, "load_comparison_report", None)
        self.assertIsNotNone(loader)
        for drift, forged in self._forged_metric_reports().items():
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "forged-report.json"
                _write(
                    path,
                    {**forged._unsigned_dict(), "identity_sha256": forged.identity_sha256},
                )
                with self.assertRaises(ValueError):
                    loader(path)

    def test_load_comparison_report_round_trips_valid_report(self) -> None:
        report = self._accuracy_report(count=20, regressions=0)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_bytes(report.to_json_bytes())
            loaded = reproduction_module.load_comparison_report(path)
        self.assertEqual(loaded.to_json_bytes(), report.to_json_bytes())

    def test_report_binds_required_metric_identities_and_rejects_deletion(self) -> None:
        report = self._accuracy_report(count=20, regressions=0)
        self.assertEqual(report.metric_identities, ("llm-answer-correctness",))
        forged = _forge_report(
            report,
            metric_identities=(),
            metrics={},
            accepted=True,
        )
        self._assert_report_forgery_rejected_everywhere(forged)

    def test_report_replays_full_exclusion_contract(self) -> None:
        rows = [
            _query("q-1"),
            _query("q-2", verdict=None, exclusion_reason="metric.not-applicable/v1"),
        ]
        report = compare_reproduction_runs(
            self._loaded(_source_manifest(rows)),
            self._loaded(_manifest(rows)),
            resolve_experiment_profile("current-default/pi"),
        )
        exclusion = report.exclusions[0]
        variants = {
            "asymmetric": replace(
                exclusion,
                candidate=replace(
                    exclusion.candidate, exclusion_reason="metric.other/v1"
                ),
            ),
            "unallowed": replace(
                exclusion,
                baseline=replace(
                    exclusion.baseline, exclusion_reason="metric.other/v1"
                ),
                candidate=replace(
                    exclusion.candidate, exclusion_reason="metric.other/v1"
                ),
            ),
            "noncompleted": replace(
                exclusion,
                baseline=replace(exclusion.baseline, status="failed"),
                candidate=replace(exclusion.candidate, status="failed"),
            ),
        }
        for drift, forged_exclusion in variants.items():
            with self.subTest(drift=drift):
                self._assert_report_forgery_rejected_everywhere(
                    _forge_report(report, exclusions=(forged_exclusion,))
                )

    def test_target_report_binds_exact_profile_target_and_runtime(self) -> None:
        profile = resolve_experiment_profile("paper-reference/claude-code")
        report = compare_reproduction_runs(
            None,
            self._loaded(
                _manifest(
                    [_query("q-1")],
                    profile_id=profile.profile_id,
                    runtime="claude-code",
                )
            ),
            profile,
        )
        self.assertEqual(report.runtime, "claude-code")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target-report.json"
            path.write_bytes(report.to_json_bytes())
            self.assertEqual(
                reproduction_module.load_comparison_report(path).to_json_bytes(),
                report.to_json_bytes(),
            )
        variants = {
            "wrong-target": _forge_report(report, target_identity="DCI-Agent-Lite"),
            "wrong-profile-digest": _forge_report(report, profile_sha256=_SHA_A),
            "wrong-runtime": _forge_report(report, runtime="pi"),
        }
        for drift, forged in variants.items():
            with self.subTest(drift=drift):
                self._assert_report_forgery_rejected_everywhere(forged)

    def test_serialization_rejects_self_hashed_cross_field_metric_forgery(self) -> None:
        for drift, forged in self._forged_metric_reports().items():
            with self.subTest(drift=drift), self.assertRaises(ValueError):
                forged.to_dict()
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary) / "private"
                parent.mkdir(mode=0o700)
                path = parent / "report.json"
                with self.assertRaises(ValueError):
                    write_comparison_report(path, forged)
                self.assertFalse(path.exists())

    def test_source_parity_rejects_self_comparison(self) -> None:
        manifest = self._loaded(_manifest([_query("q-1")]))
        with self.assertRaises(ValueError):
            compare_reproduction_runs(
                manifest,
                manifest,
                resolve_experiment_profile("current-default/pi"),
            )

    def test_source_parity_binds_roles_and_shared_normalized_experiment(self) -> None:
        source = self._loaded(_source_manifest([_query("q-1")]))
        asterion = self._loaded(_manifest([_query("q-1")]))
        report = compare_reproduction_runs(
            source, asterion, resolve_experiment_profile("current-default/pi")
        )
        self.assertEqual(report.baseline_product, "original-dci")
        self.assertEqual(report.candidate_product, "asterion-dci")
        self.assertEqual(report.effective_config_sha256, _SHA_B)
        self.assertNotEqual(
            report.baseline_product_effective_config_sha256,
            report.candidate_product_effective_config_sha256,
        )
        with self.assertRaises(ValueError):
            compare_reproduction_runs(
                asterion, source, resolve_experiment_profile("current-default/pi")
            )

    def test_exclusions_are_symmetric_allowlisted_and_cannot_hide_failures(self) -> None:
        baseline_rows = [
            _query("q-1"),
            _query("q-2", verdict=None, exclusion_reason="metric.not-applicable/v1"),
        ]
        asymmetric_candidate = [_query("q-1"), _query("q-2")]
        with self.assertRaises(ValueError):
            compare_reproduction_runs(
                self._loaded(_source_manifest(baseline_rows)),
                self._loaded(_manifest(asymmetric_candidate)),
                resolve_experiment_profile("current-default/pi"),
            )

        disallowed = [
            _query("q-1"),
            _query("q-2", verdict=None, exclusion_reason="metric.arbitrary/v1"),
        ]
        with self.assertRaises(ValueError):
            compare_reproduction_runs(
                self._loaded(_source_manifest(disallowed)),
                self._loaded(_manifest(disallowed)),
                resolve_experiment_profile("current-default/pi"),
            )

        hidden_failure = [
            _query("q-1"),
            _query(
                "q-2",
                status="failed",
                verdict=None,
                failure_class="runtime.failed/v1",
                exclusion_reason="metric.not-applicable/v1",
            ),
        ]
        hidden_source = self._loaded(_source_manifest(hidden_failure))
        self.assertEqual(hidden_source.aggregates.failed_count, 1)
        self.assertEqual(hidden_source.aggregates.excluded_count, 0)
        with self.assertRaises(ValueError):
            compare_reproduction_runs(
                hidden_source,
                self._loaded(_manifest(hidden_failure)),
                resolve_experiment_profile("current-default/pi"),
            )

    def test_all_public_report_values_validate_and_copy_mutable_mappings(self) -> None:
        report = self._accuracy_report(count=20, regressions=0)
        with self.assertRaises(ValueError):
            replace(report, comparison_kind="arbitrary")
        with self.assertRaises(ValueError):
            replace(report, accepted=not report.accepted)
        with self.assertRaises(ValueError):
            replace(report.candidate, completion_rate=2.0)
        with self.assertRaises(ValueError):
            ConfidenceInterval(lower=1.0, upper=0.0)
        with self.assertRaises(ValueError):
            EstimatorEvidence(
                name="arbitrary",
                seed=1,
                resamples=1,
                sample_sha256=_SHA_A,
            )

        source = dict(report.metrics)
        copied = replace(report, metrics=source)
        source.clear()
        self.assertTrue(copied.metrics)
        self.assertIsInstance(copied.metrics, type(MappingProxyType({})))

        forged = object.__new__(ConfidenceInterval)
        object.__setattr__(forged, "lower", math.nan)
        object.__setattr__(forged, "upper", 0.0)
        with self.assertRaises(ValueError):
            forged.to_dict()

    def test_claude_is_target_comparison_and_rejects_source_baseline(self) -> None:
        profile = resolve_experiment_profile("paper-reference/claude-code")
        candidate = self._loaded(
            _manifest(
                [_query("q-1")],
                profile_id=profile.profile_id,
                runtime="claude-code",
            )
        )
        report = compare_reproduction_runs(None, candidate, profile)
        self.assertEqual(report.comparison_kind, "target-comparison")
        self.assertEqual(report.target_identity, "DCI-Agent-CC")
        self.assertEqual(report.pair_ids, ())
        self.assertNotIn("source-parity", json.dumps(report.to_dict()))
        with self.assertRaises(ValueError):
            replace(report, baseline_product="original-dci")
        with self.assertRaises(ValueError):
            compare_reproduction_runs(candidate, candidate, profile)


class ReproductionCliTests(unittest.TestCase):
    def test_compare_writes_private_deterministic_report_and_fails_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            report = root / "private" / "report.json"
            _write(baseline, _source_manifest([_query("q-1")]))
            _write(candidate, _manifest([_query("q-1", verdict=False)]))

            first = main(
                [
                    "paper",
                    "compare",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--profile",
                    "current-default/pi",
                    "--output",
                    str(report),
                ]
            )
            first_bytes = report.read_bytes()
            second = main(
                [
                    "paper",
                    "compare",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--profile",
                    "current-default/pi",
                    "--output",
                    str(report),
                ]
            )
            self.assertNotEqual(first, 0)
            self.assertNotEqual(second, 0)
            self.assertEqual(first_bytes, report.read_bytes())
            self.assertEqual(stat.S_IMODE(report.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(report.stat().st_mode), 0o600)
            self.assertEqual(json.loads(first_bytes)["schema"], COMPARISON_SCHEMA)

    def test_compare_returns_nonzero_on_schema_drift_without_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            report = root / "private" / "report.json"
            value = _manifest([_query("q-1")])
            value["schema"] = "dci.reproduction-run/v999"
            _write(baseline, value)
            _write(candidate, _manifest([_query("q-1")]))
            result = main(
                [
                    "paper",
                    "compare",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--profile",
                    "current-default/pi",
                    "--output",
                    str(report),
                ]
            )
            self.assertNotEqual(result, 0)
            self.assertFalse(report.exists())

    def test_compare_rejects_existing_non_private_parent_without_changing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public_parent = root / "public"
            public_parent.mkdir(mode=0o755)
            os_mode = stat.S_IMODE(public_parent.stat().st_mode)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            _write(baseline, _source_manifest([_query("q-1")]))
            _write(candidate, _manifest([_query("q-1")]))
            result = main(
                [
                    "paper",
                    "compare",
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                    "--profile",
                    "current-default/pi",
                    "--output",
                    str(public_parent / "report.json"),
                ]
            )
            self.assertNotEqual(result, 0)
            self.assertEqual(stat.S_IMODE(public_parent.stat().st_mode), os_mode)


if __name__ == "__main__":
    unittest.main()
