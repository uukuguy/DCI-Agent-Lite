from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from asterion.dci.experiment_profiles import resolve_experiment_profile
from asterion.dci.paper_benchmarks import (
    resolve_paper_benchmark,
    resolve_paper_experiment_scope,
)
from asterion.dci.reproduction import QueryEvidence, RunManifest, load_run_manifest


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


def _manifest(*queries: QueryEvidence) -> RunManifest:
    profile = resolve_experiment_profile("current-default/pi")
    scope_id = _query("scope-probe").scope_id
    return RunManifest.create(
        product="original-dci",
        profile=profile,
        effective_config_identity_sha256=_SHA_B,
        scope_ids=(scope_id,),
        queries=queries or (_query("q-1"),),
    )


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


if __name__ == "__main__":
    unittest.main()
