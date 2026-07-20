from __future__ import annotations

import json
import io
import os
import stat
import tempfile
import unittest
from pathlib import Path

from asterion.dci.cli import main
from asterion.dci.experiment_profiles import resolve_experiment_profile
from asterion.dci.paper_benchmarks import (
    resolve_paper_benchmark,
    resolve_paper_experiment_scope,
)
from asterion.dci.reproduction import (
    QueryEvidence,
    RunManifest,
    compare_reproduction_runs,
    load_run_manifest,
    resolve_reproduction_target,
)


_SHA_A = "a" * 64
_SHA_B = "b" * 64


def _query(
    query_id: str,
    *,
    status: str = "completed",
    judge_verdict: bool | None = True,
    failure_class: str | None = None,
    exclusion_reason: str | None = None,
) -> QueryEvidence:
    profile = resolve_experiment_profile("current-default/pi")
    scope_id = next(
        scope_id
        for scope_id in profile.paper_scope_ids
        if resolve_paper_benchmark(
            resolve_paper_experiment_scope(scope_id).dataset_id
        ).mode
        == "qa"
    )
    scope = resolve_paper_experiment_scope(scope_id)
    return QueryEvidence(
        query_id=query_id,
        dataset_id=scope.dataset_id,
        scope_id=scope_id,
        status=status,
        judge_verdict=judge_verdict,
        ndcg_at_10=None,
        evidence_sha256=None if status == "missing" else _SHA_A,
        failure_class=failure_class,
        exclusion_reason=exclusion_reason,
        agent_operations=1 if status != "missing" else 0,
        judge_operations=1 if status == "completed" else 0,
        input_tokens=10 if status != "missing" else 0,
        output_tokens=5 if status != "missing" else 0,
        cost_usd=0.25 if status != "missing" else 0.0,
    )


def _ir_query(query_id: str, ndcg_at_10: float) -> QueryEvidence:
    profile = resolve_experiment_profile("current-default/pi")
    scope_id = next(
        scope_id
        for scope_id in profile.paper_scope_ids
        if resolve_paper_benchmark(
            resolve_paper_experiment_scope(scope_id).dataset_id
        ).mode
        == "ir"
    )
    scope = resolve_paper_experiment_scope(scope_id)
    return QueryEvidence(
        query_id=query_id,
        dataset_id=scope.dataset_id,
        scope_id=scope_id,
        status="completed",
        judge_verdict=None,
        ndcg_at_10=ndcg_at_10,
        evidence_sha256=_SHA_A,
        failure_class=None,
        exclusion_reason=None,
        agent_operations=1,
        judge_operations=0,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.25,
    )


def _manifest_for(
    product: str,
    *queries: QueryEvidence,
    profile_id: str = "current-default/pi",
) -> RunManifest:
    profile = resolve_experiment_profile(profile_id)
    return RunManifest.create(
        product=product,
        profile=profile,
        effective_config_identity_sha256=_SHA_B,
        scope_ids=tuple(sorted({query.scope_id for query in queries})),
        queries=queries,
    )


def _manifest(*queries: QueryEvidence) -> RunManifest:
    return _manifest_for("original-dci", *(queries or (_query("q-1"),)))


class ReproductionManifestValidationTests(unittest.TestCase):
    def test_rejects_duplicate_and_missing_query_ids(self) -> None:
        with self.assertRaises(ValueError):
            _manifest(_query("q-1"), _query("q-1"))

        value = _manifest().to_mapping()
        del value["queries"][0]["query_id"]
        with self.assertRaises(ValueError):
            RunManifest.from_mapping(value)

    def test_rejects_profile_effective_config_and_aggregate_drift(self) -> None:
        value = _manifest().to_mapping()
        mutations = (
            ("profile_identity_sha256", _SHA_A),
            ("effective_config_identity_sha256", "not-a-digest"),
            ("paper_experiment_scopes_sha256", _SHA_A),
        )
        for field, replacement in mutations:
            with self.subTest(field=field):
                changed = json.loads(json.dumps(value))
                changed[field] = replacement
                with self.assertRaises(ValueError):
                    RunManifest.from_mapping(changed)

        changed = json.loads(json.dumps(value))
        changed["queries"][0]["dataset_id"] = "paper.qa.nq"
        with self.assertRaises(ValueError):
            RunManifest.from_mapping(changed)

        changed = json.loads(json.dumps(value))
        changed["aggregates"]["accuracy"] = 0.0
        with self.assertRaises(ValueError):
            RunManifest.from_mapping(changed)

    def test_preserves_noncompleted_rows_and_versioned_exclusions(self) -> None:
        rows = (
            _query("q-completed"),
            _query("q-failed", status="failed", judge_verdict=None, failure_class="runtime-failed"),
            _query("q-cancelled", status="cancelled", judge_verdict=None, failure_class="cancelled"),
            _query("q-timed-out", status="timed_out", judge_verdict=None, failure_class="deadline"),
            _query("q-missing", status="missing", judge_verdict=None, failure_class="missing-evidence"),
            _query(
                "q-excluded",
                status="failed",
                judge_verdict=None,
                failure_class="selection-mismatch",
                exclusion_reason="dci.reproduction-exclusion/not-in-matched-selection/v1",
            ),
        )
        manifest = _manifest(*rows)
        self.assertEqual(
            tuple(row.status for row in manifest.queries),
            ("cancelled", "completed", "failed", "failed", "missing", "timed_out"),
        )
        self.assertEqual(manifest.aggregates["failure_count"], 4)
        self.assertEqual(manifest.aggregates["excluded_count"], 1)

        changed = manifest.to_mapping()
        excluded = next(row for row in changed["queries"] if row["query_id"] == "q-excluded")
        excluded["exclusion_reason"] = "informal-reason"
        with self.assertRaises(ValueError):
            RunManifest.from_mapping(changed)

    def test_rejects_bodies_credentials_and_private_paths(self) -> None:
        value = _manifest().to_mapping()
        for field in ("prompt", "answer", "tool_output", "api_key"):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(value))
                changed["queries"][0][field] = "sentinel-secret"
                with self.assertRaises(ValueError):
                    RunManifest.from_mapping(changed)

        changed = json.loads(json.dumps(value))
        changed["queries"][0]["failure_class"] = "/private/sentinel-secret"
        with self.assertRaises(ValueError):
            RunManifest.from_mapping(changed)

    def test_load_run_manifest_rejects_duplicate_json_keys_and_preserves_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = root / "manifest.json"
            manifest = _manifest()
            path.write_text(json.dumps(manifest.to_mapping()))
            loaded = load_run_manifest(path)
            self.assertEqual(loaded, manifest)

            path.write_text('{"schema":"first","schema":"second"}')
            with self.assertRaises(ValueError):
                load_run_manifest(path)


class ReproductionComparisonTests(unittest.TestCase):
    def test_accuracy_margin_uses_deterministic_paired_bootstrap(self) -> None:
        baseline_rows = tuple(_query(f"qa-{index:04d}") for index in range(2500))
        passing_rows = tuple(
            _query(f"qa-{index:04d}", judge_verdict=index >= 100)
            for index in range(2500)
        )
        failing_rows = tuple(
            _query(f"qa-{index:04d}", judge_verdict=index >= 150)
            for index in range(2500)
        )
        profile = resolve_experiment_profile("current-default/pi")
        baseline = _manifest_for("original-dci", *baseline_rows)

        passing = compare_reproduction_runs(
            baseline,
            _manifest_for("asterion-dci", *passing_rows),
            profile,
        )
        failing = compare_reproduction_runs(
            baseline,
            _manifest_for("asterion-dci", *failing_rows),
            profile,
        )

        self.assertAlmostEqual(passing.accuracy["delta"], -0.04)
        self.assertGreaterEqual(passing.accuracy["lower_bound"], -0.05)
        self.assertTrue(passing.accuracy["passes"])
        self.assertTrue(passing.accepted)
        self.assertAlmostEqual(failing.accuracy["delta"], -0.06)
        self.assertLess(failing.accuracy["lower_bound"], -0.05)
        self.assertFalse(failing.accuracy["passes"])
        self.assertFalse(failing.accepted)

    def test_ndcg_margin_uses_deterministic_paired_bootstrap(self) -> None:
        baseline_rows = tuple(_ir_query(f"ir-{index:02d}", 0.5) for index in range(20))
        passing_rows = tuple(_ir_query(f"ir-{index:02d}", 0.481) for index in range(20))
        failing_rows = tuple(_ir_query(f"ir-{index:02d}", 0.479) for index in range(20))
        profile = resolve_experiment_profile("current-default/pi")
        baseline = _manifest_for("original-dci", *baseline_rows)

        passing = compare_reproduction_runs(
            baseline,
            _manifest_for("asterion-dci", *passing_rows),
            profile,
        )
        failing = compare_reproduction_runs(
            baseline,
            _manifest_for("asterion-dci", *failing_rows),
            profile,
        )

        self.assertAlmostEqual(passing.ndcg_at_10["delta"], -0.019)
        self.assertGreaterEqual(passing.ndcg_at_10["lower_bound"], -0.02)
        self.assertTrue(passing.ndcg_at_10["passes"])
        self.assertAlmostEqual(failing.ndcg_at_10["delta"], -0.021)
        self.assertLess(failing.ndcg_at_10["lower_bound"], -0.02)
        self.assertFalse(failing.ndcg_at_10["passes"])

    def test_report_binds_estimator_seed_pairs_exclusions_and_costs(self) -> None:
        included = _query("q-included")
        missing = _query(
            "q-missing",
            status="missing",
            judge_verdict=None,
            failure_class="missing-evidence",
        )
        excluded = _query(
            "q-excluded",
            status="failed",
            judge_verdict=None,
            failure_class="selection-mismatch",
            exclusion_reason="dci.reproduction-exclusion/not-in-matched-selection/v1",
        )
        profile = resolve_experiment_profile("current-default/pi")
        report = compare_reproduction_runs(
            _manifest_for("original-dci", included, missing, excluded),
            _manifest_for("asterion-dci", included, missing, excluded),
            profile,
        )

        self.assertEqual(report.estimator["name"], "paired-bootstrap-percentile/v1")
        self.assertEqual(report.estimator["seed"], 340)
        self.assertEqual(report.estimator["resamples"], 10_000)
        self.assertRegex(report.estimator["query_set_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(report.estimator["accuracy_sample_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(report.retained_pair_ids, ("q-included", "q-missing"))
        self.assertEqual(report.excluded_query_ids, ("q-excluded",))
        self.assertEqual(len(report.pairs), 2)
        self.assertEqual(report.completion["baseline_rate"], 0.5)
        self.assertEqual(report.completion["candidate_failure_rate"], 0.5)
        self.assertEqual(report.totals["candidate"]["agent_operations"], 2)
        self.assertEqual(report.totals["candidate"]["cost_usd"], 0.5)
        with self.assertRaises(TypeError):
            report.pairs[0]["baseline"]["status"] = "failed"
        repeated = compare_reproduction_runs(
            _manifest_for("original-dci", included, missing, excluded),
            _manifest_for("asterion-dci", included, missing, excluded),
            profile,
        )
        self.assertEqual(
            json.dumps(report.to_mapping(), sort_keys=True).encode(),
            json.dumps(repeated.to_mapping(), sort_keys=True).encode(),
        )

    def test_claude_uses_target_comparison_without_manufactured_pairs(self) -> None:
        profile = resolve_experiment_profile("paper-reference/claude-code")
        candidate = _manifest_for(
            "asterion-dci",
            _query("q-target"),
            _ir_query("ir-target", 0.5),
            profile_id=profile.profile_id,
        )

        report = compare_reproduction_runs(None, candidate, profile)
        target = resolve_reproduction_target(profile.profile_id)

        self.assertEqual(report.comparison_kind, "target-comparison")
        self.assertIsNone(report.accepted)
        self.assertEqual(report.pairs, ())
        self.assertEqual(report.retained_pair_ids, ())
        self.assertEqual(len(report.target_rows), 2)
        self.assertEqual(
            report.estimator["name"], "single-run-bootstrap-percentile/v1"
        )
        self.assertEqual(report.estimator["resamples"], 10_000)
        self.assertEqual(report.accuracy["candidate_mean"], 1.0)
        self.assertEqual(report.ndcg_at_10["candidate_mean"], 0.5)
        self.assertEqual(report.target_identity["profile_id"], profile.profile_id)
        self.assertEqual(
            report.target_identity["profile_identity_sha256"], profile.identity_sha256
        )
        self.assertEqual(report.target_identity["target_id"], target.target_id)
        self.assertEqual(
            report.target_identity["target_identity_sha256"], target.identity_sha256
        )
        self.assertEqual(target.agentic_search_accuracy, 0.8)
        self.assertEqual(target.qa_accuracy, 0.83)
        self.assertEqual(target.ir_ndcg_at_10, 0.685)
        self.assertEqual(
            dict(target.dataset_targets),
            {
                "beir.arguana": 0.853,
                "beir.scifact": 0.757,
                "bright.biology": 0.771,
                "bright.earth-science": 0.69,
                "bright.economics": 0.468,
                "bright.robotics": 0.568,
                "browsecomp-plus": 0.8,
                "qa.2wikimultihopqa": 0.82,
                "qa.bamboogle": 0.8,
                "qa.hotpotqa": 0.88,
                "qa.musique": 0.74,
                "qa.nq": 0.78,
                "qa.triviaqa": 0.96,
            },
        )
        self.assertNotIn("source-parity", json.dumps(report.to_mapping()))

    def test_cli_writes_private_report_and_returns_nonzero_for_failed_acceptance(self) -> None:
        profile = resolve_experiment_profile("current-default/pi")
        baseline = _manifest_for("original-dci", _query("q-cli"))
        passing = _manifest_for("asterion-dci", _query("q-cli"))
        failing = _manifest_for(
            "asterion-dci", _query("q-cli", judge_verdict=False)
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            os.chmod(root, 0o700)
            baseline_path = root / "baseline.json"
            passing_path = root / "passing.json"
            failing_path = root / "failing.json"
            baseline_path.write_text(json.dumps(baseline.to_mapping()))
            passing_path.write_text(json.dumps(passing.to_mapping()))
            failing_path.write_text(json.dumps(failing.to_mapping()))

            passing_report = root / "passing-report.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(
                main(
                    [
                        "paper",
                        "compare",
                        "--baseline",
                        str(baseline_path),
                        "--candidate",
                        str(passing_path),
                        "--profile",
                        profile.profile_id,
                        "--output",
                        str(passing_report),
                    ],
                    stdout=stdout,
                    stderr=stderr,
                ),
                0,
            )
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("acceptance=pass", stdout.getvalue())
            self.assertEqual(stat.S_IMODE(passing_report.stat().st_mode), 0o600)

            stdout = io.StringIO()
            stderr = io.StringIO()
            self.assertEqual(
                main(
                    [
                        "paper",
                        "compare",
                        "--baseline",
                        str(baseline_path),
                        "--candidate",
                        str(failing_path),
                        "--profile",
                        profile.profile_id,
                        "--output",
                        str(root / "failing-report.json"),
                    ],
                    stdout=stdout,
                    stderr=stderr,
                ),
                1,
            )
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("acceptance=fail", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
