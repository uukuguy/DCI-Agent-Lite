"""Body-free reproduction manifests and deterministic statistical comparison."""

from __future__ import annotations

import json
import math
import os
import random
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from asterion.dci.experiment_profiles import (
    ExperimentProfile,
    experiment_profile_sha256,
)
from asterion.dci.paper_benchmarks import canonical_sha256

RUN_MANIFEST_SCHEMA = "dci.reproduction-run/v1"
COMPARISON_SCHEMA = "dci.reproduction-comparison/v1"
RESULT_SCHEMA = "dci.reproduction-results/v1"
ESTIMATOR_NAME = "paired-bootstrap-percentile/v1"
ESTIMATOR_SEED = 340_007
ESTIMATOR_RESAMPLES = 10_000

_SHA256 = re.compile(r"[0-9a-f]{64}")
_PUBLIC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+@-]*")
_VERSIONED_REASON = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*/v[1-9][0-9]*")
_STATUSES = ("completed", "failed", "cancelled", "timed_out", "missing")
_ACCURACY_METRIC = "llm-answer-correctness"
_NDCG_METRIC = "ndcg@10-binary-deduplicated"
_METRIC_IDENTITIES = {_ACCURACY_METRIC, _NDCG_METRIC}
_MANIFEST_KEYS = {
    "schema",
    "run_id",
    "profile_id",
    "profile_sha256",
    "runtime",
    "dataset_id",
    "selection_id",
    "selection_sha256",
    "effective_config_sha256",
    "metric_identities",
    "queries",
    "aggregates",
    "identity_sha256",
}
_QUERY_KEYS = {
    "query_id",
    "status",
    "judge_verdict",
    "ndcg_at_10",
    "failure_class",
    "exclusion_reason",
    "evidence_sha256",
    "operations",
    "tokens",
    "cost_usd",
}
_AGGREGATE_KEYS = {
    "query_count",
    "included_count",
    "excluded_count",
    "completed_count",
    "failed_count",
    "cancelled_count",
    "timed_out_count",
    "missing_count",
    "accuracy",
    "mean_ndcg_at_10",
    "agent_operations",
    "judge_operations",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
}
_FORBIDDEN_KEY_PARTS = (
    "answer",
    "prompt",
    "credential",
    "secret",
    "api_key",
    "authorization",
    "tool_body",
    "request_body",
    "response_body",
    "private_path",
)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("DCI reproduction manifest contains a duplicate key")
        value[key] = item
    return value


def _require_exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"DCI reproduction {label} schema is invalid")
    return value


def _require_public_id(value: object, label: str) -> str:
    if type(value) is not str or _PUBLIC_ID.fullmatch(value) is None:
        raise ValueError(f"DCI reproduction {label} is invalid")
    return value


def _require_sha256(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"DCI reproduction {label} is invalid")
    return value


def _require_count(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"DCI reproduction {label} is invalid")
    return value


def _require_finite(value: object, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"DCI reproduction {label} is invalid")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise ValueError(f"DCI reproduction {label} is invalid")
    return result


def _require_optional_unit(value: object, label: str) -> float | None:
    if value is None:
        return None
    result = _require_finite(value, label, minimum=0.0)
    if result > 1.0:
        raise ValueError(f"DCI reproduction {label} is invalid")
    return result


def _reject_body_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in _FORBIDDEN_KEY_PARTS):
                raise ValueError("DCI reproduction evidence is not body-free")
            _reject_body_fields(item)
    elif isinstance(value, list):
        for item in value:
            _reject_body_fields(item)


@dataclass(frozen=True, slots=True)
class OperationCounts:
    agent: int
    judge: int

    def __post_init__(self) -> None:
        _require_count(self.agent, "agent operation count")
        _require_count(self.judge, "Judge operation count")

    def to_dict(self) -> dict[str, int]:
        return {"agent": self.agent, "judge": self.judge}


@dataclass(frozen=True, slots=True)
class TokenCounts:
    input: int
    cached_input: int
    output: int

    def __post_init__(self) -> None:
        _require_count(self.input, "input token count")
        _require_count(self.cached_input, "cached input token count")
        _require_count(self.output, "output token count")

    def to_dict(self) -> dict[str, int]:
        return {
            "input": self.input,
            "cached_input": self.cached_input,
            "output": self.output,
        }


@dataclass(frozen=True, slots=True)
class QueryEvidence:
    query_id: str
    status: str
    judge_verdict: bool | None
    ndcg_at_10: float | None
    failure_class: str | None
    exclusion_reason: str | None
    evidence_sha256: str
    operations: OperationCounts
    tokens: TokenCounts
    cost_usd: float

    def __post_init__(self) -> None:
        _require_public_id(self.query_id, "query ID")
        if self.status not in _STATUSES:
            raise ValueError("DCI reproduction query status is invalid")
        if self.judge_verdict is not None and type(self.judge_verdict) is not bool:
            raise ValueError("DCI reproduction Judge verdict is invalid")
        _require_optional_unit(self.ndcg_at_10, "NDCG@10")
        if self.failure_class is not None and (
            type(self.failure_class) is not str
            or _VERSIONED_REASON.fullmatch(self.failure_class) is None
        ):
            raise ValueError("DCI reproduction failure class is invalid")
        if self.exclusion_reason is not None and (
            type(self.exclusion_reason) is not str
            or _VERSIONED_REASON.fullmatch(self.exclusion_reason) is None
        ):
            raise ValueError("DCI reproduction exclusion reason is invalid")
        if self.status == "completed":
            if self.failure_class is not None:
                raise ValueError("DCI completed query cannot contain a failure class")
            if (
                self.exclusion_reason is None
                and self.judge_verdict is None
                and self.ndcg_at_10 is None
            ):
                raise ValueError("DCI completed query has no metric evidence")
        elif (
            self.failure_class is None
            or self.judge_verdict is not None
            or self.ndcg_at_10 is not None
        ):
            raise ValueError("DCI non-completed query evidence is invalid")
        _require_sha256(self.evidence_sha256, "evidence digest")
        if type(self.operations) is not OperationCounts or type(self.tokens) is not TokenCounts:
            raise ValueError("DCI reproduction query totals are invalid")
        _require_finite(self.cost_usd, "cost", minimum=0.0)

    @classmethod
    def from_mapping(cls, value: object) -> "QueryEvidence":
        row = _require_exact_mapping(value, _QUERY_KEYS, "query")
        query_id = _require_public_id(row["query_id"], "query ID")
        status = row["status"]
        if type(status) is not str or status not in _STATUSES:
            raise ValueError("DCI reproduction query status is invalid")
        verdict = row["judge_verdict"]
        if verdict is not None and type(verdict) is not bool:
            raise ValueError("DCI reproduction Judge verdict is invalid")
        ndcg = _require_optional_unit(row["ndcg_at_10"], "NDCG@10")
        failure = row["failure_class"]
        exclusion = row["exclusion_reason"]
        if failure is not None and (
            type(failure) is not str or _VERSIONED_REASON.fullmatch(failure) is None
        ):
            raise ValueError("DCI reproduction failure class is invalid")
        if exclusion is not None and (
            type(exclusion) is not str
            or _VERSIONED_REASON.fullmatch(exclusion) is None
        ):
            raise ValueError("DCI reproduction exclusion reason is invalid")
        if status == "completed":
            if failure is not None:
                raise ValueError("DCI completed query cannot contain a failure class")
            if exclusion is None and verdict is None and ndcg is None:
                raise ValueError("DCI completed query has no metric evidence")
        elif failure is None or verdict is not None or ndcg is not None:
            raise ValueError("DCI non-completed query evidence is invalid")
        operations = _require_exact_mapping(
            row["operations"], {"agent", "judge"}, "operation totals"
        )
        tokens = _require_exact_mapping(
            row["tokens"], {"input", "cached_input", "output"}, "token totals"
        )
        return cls(
            query_id=query_id,
            status=status,
            judge_verdict=verdict,
            ndcg_at_10=ndcg,
            failure_class=failure,
            exclusion_reason=exclusion,
            evidence_sha256=_require_sha256(row["evidence_sha256"], "evidence digest"),
            operations=OperationCounts(
                agent=_require_count(operations["agent"], "agent operation count"),
                judge=_require_count(operations["judge"], "Judge operation count"),
            ),
            tokens=TokenCounts(
                input=_require_count(tokens["input"], "input token count"),
                cached_input=_require_count(
                    tokens["cached_input"], "cached input token count"
                ),
                output=_require_count(tokens["output"], "output token count"),
            ),
            cost_usd=_require_finite(row["cost_usd"], "cost", minimum=0.0),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "query_id": self.query_id,
            "status": self.status,
            "judge_verdict": self.judge_verdict,
            "ndcg_at_10": self.ndcg_at_10,
            "failure_class": self.failure_class,
            "exclusion_reason": self.exclusion_reason,
            "evidence_sha256": self.evidence_sha256,
            "operations": self.operations.to_dict(),
            "tokens": self.tokens.to_dict(),
            "cost_usd": self.cost_usd,
        }


@dataclass(frozen=True, slots=True)
class RunAggregates:
    query_count: int
    included_count: int
    excluded_count: int
    completed_count: int
    failed_count: int
    cancelled_count: int
    timed_out_count: int
    missing_count: int
    accuracy: float | None
    mean_ndcg_at_10: float | None
    agent_operations: int
    judge_operations: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float

    def to_dict(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in (
                "query_count",
                "included_count",
                "excluded_count",
                "completed_count",
                "failed_count",
                "cancelled_count",
                "timed_out_count",
                "missing_count",
                "accuracy",
                "mean_ndcg_at_10",
                "agent_operations",
                "judge_operations",
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "total_tokens",
                "cost_usd",
            )
        }


def _computed_aggregates(
    queries: tuple[QueryEvidence, ...], metric_identities: tuple[str, ...]
) -> RunAggregates:
    included = tuple(row for row in queries if row.exclusion_reason is None)
    has_accuracy = _ACCURACY_METRIC in metric_identities
    has_ndcg = _NDCG_METRIC in metric_identities
    accuracy_values = (
        tuple(
            1.0 if row.status == "completed" and row.judge_verdict is True else 0.0
            for row in included
        )
        if has_accuracy
        else ()
    )
    ndcg_values = (
        tuple(
            row.ndcg_at_10
            if row.status == "completed" and row.ndcg_at_10 is not None
            else 0.0
            for row in included
        )
        if has_ndcg
        else ()
    )
    input_tokens = sum(row.tokens.input for row in queries)
    cached_input_tokens = sum(row.tokens.cached_input for row in queries)
    output_tokens = sum(row.tokens.output for row in queries)
    return RunAggregates(
        query_count=len(queries),
        included_count=len(included),
        excluded_count=len(queries) - len(included),
        completed_count=sum(row.status == "completed" for row in included),
        failed_count=sum(row.status == "failed" for row in included),
        cancelled_count=sum(row.status == "cancelled" for row in included),
        timed_out_count=sum(row.status == "timed_out" for row in included),
        missing_count=sum(row.status == "missing" for row in included),
        accuracy=(sum(accuracy_values) / len(accuracy_values) if accuracy_values else None),
        mean_ndcg_at_10=(sum(ndcg_values) / len(ndcg_values) if ndcg_values else None),
        agent_operations=sum(row.operations.agent for row in queries),
        judge_operations=sum(row.operations.judge for row in queries),
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + cached_input_tokens + output_tokens,
        cost_usd=sum(row.cost_usd for row in queries),
    )


def _parse_aggregates(value: object) -> RunAggregates:
    item = _require_exact_mapping(value, _AGGREGATE_KEYS, "aggregate")
    return RunAggregates(
        query_count=_require_count(item["query_count"], "query count"),
        included_count=_require_count(item["included_count"], "included count"),
        excluded_count=_require_count(item["excluded_count"], "excluded count"),
        completed_count=_require_count(item["completed_count"], "completed count"),
        failed_count=_require_count(item["failed_count"], "failed count"),
        cancelled_count=_require_count(item["cancelled_count"], "cancelled count"),
        timed_out_count=_require_count(item["timed_out_count"], "timed-out count"),
        missing_count=_require_count(item["missing_count"], "missing count"),
        accuracy=_require_optional_unit(item["accuracy"], "accuracy"),
        mean_ndcg_at_10=_require_optional_unit(
            item["mean_ndcg_at_10"], "mean NDCG@10"
        ),
        agent_operations=_require_count(item["agent_operations"], "agent operations"),
        judge_operations=_require_count(item["judge_operations"], "Judge operations"),
        input_tokens=_require_count(item["input_tokens"], "input tokens"),
        cached_input_tokens=_require_count(
            item["cached_input_tokens"], "cached input tokens"
        ),
        output_tokens=_require_count(item["output_tokens"], "output tokens"),
        total_tokens=_require_count(item["total_tokens"], "total tokens"),
        cost_usd=_require_finite(item["cost_usd"], "aggregate cost", minimum=0.0),
    )


def _same_aggregates(left: RunAggregates, right: RunAggregates) -> bool:
    for name in _AGGREGATE_KEYS:
        a, b = getattr(left, name), getattr(right, name)
        if isinstance(a, float) or isinstance(b, float):
            if a is None or b is None or not math.isclose(float(a), float(b), abs_tol=1e-12):
                return a is b
        elif a != b:
            return False
    return True


@dataclass(frozen=True, slots=True)
class RunManifest:
    run_id: str
    profile_id: str
    profile_sha256: str
    runtime: str
    dataset_id: str
    selection_id: str
    selection_sha256: str
    effective_config_sha256: str
    metric_identities: tuple[str, ...]
    queries: tuple[QueryEvidence, ...]
    aggregates: RunAggregates
    identity_sha256: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.run_id, "run ID"),
            (self.profile_id, "profile ID"),
            (self.runtime, "runtime ID"),
            (self.dataset_id, "dataset ID"),
            (self.selection_id, "selection ID"),
        ):
            _require_public_id(value, label)
        for value, label in (
            (self.profile_sha256, "profile digest"),
            (self.selection_sha256, "selection digest"),
            (self.effective_config_sha256, "effective configuration digest"),
            (self.identity_sha256, "run identity"),
        ):
            _require_sha256(value, label)
        if (
            type(self.metric_identities) is not tuple
            or not self.metric_identities
            or not set(self.metric_identities).issubset(_METRIC_IDENTITIES)
            or len(set(self.metric_identities)) != len(self.metric_identities)
            or type(self.queries) is not tuple
            or not self.queries
            or any(type(row) is not QueryEvidence for row in self.queries)
            or type(self.aggregates) is not RunAggregates
        ):
            raise ValueError("DCI reproduction run manifest values are invalid")
        query_ids = tuple(row.query_id for row in self.queries)
        if query_ids != tuple(sorted(query_ids)) or len(set(query_ids)) != len(query_ids):
            raise ValueError("DCI reproduction query IDs are invalid")
        for row in self.queries:
            if row.status != "completed" or row.exclusion_reason is not None:
                continue
            if _ACCURACY_METRIC in self.metric_identities and row.judge_verdict is None:
                raise ValueError("DCI reproduction declared accuracy evidence is missing")
            if _NDCG_METRIC in self.metric_identities and row.ndcg_at_10 is None:
                raise ValueError("DCI reproduction declared NDCG evidence is missing")
        if not _same_aggregates(
            self.aggregates,
            _computed_aggregates(self.queries, self.metric_identities),
        ):
            raise ValueError("DCI reproduction aggregates are inconsistent")
        unsigned = self.to_dict()
        unsigned.pop("identity_sha256")
        if self.identity_sha256 != canonical_sha256(unsigned):
            raise ValueError("DCI reproduction run identity is invalid")

    @classmethod
    def from_mapping(cls, value: object) -> "RunManifest":
        _reject_body_fields(value)
        item = _require_exact_mapping(value, _MANIFEST_KEYS, "run manifest")
        if item["schema"] != RUN_MANIFEST_SCHEMA:
            raise ValueError("DCI reproduction run schema is invalid")
        supplied_identity = _require_sha256(item["identity_sha256"], "run identity")
        unsigned = {key: data for key, data in item.items() if key != "identity_sha256"}
        if supplied_identity != canonical_sha256(unsigned):
            raise ValueError("DCI reproduction run identity is invalid")
        raw_metrics = item["metric_identities"]
        if (
            type(raw_metrics) is not list
            or not raw_metrics
            or any(type(metric) is not str or _PUBLIC_ID.fullmatch(metric) is None for metric in raw_metrics)
            or len(set(raw_metrics)) != len(raw_metrics)
            or not set(raw_metrics).issubset(_METRIC_IDENTITIES)
        ):
            raise ValueError("DCI reproduction metric identities are invalid")
        raw_queries = item["queries"]
        if type(raw_queries) is not list or not raw_queries:
            raise ValueError("DCI reproduction queries are invalid")
        queries = tuple(QueryEvidence.from_mapping(row) for row in raw_queries)
        query_ids = tuple(row.query_id for row in queries)
        if query_ids != tuple(sorted(query_ids)) or len(set(query_ids)) != len(query_ids):
            raise ValueError("DCI reproduction query IDs are invalid")
        for row in queries:
            if row.status != "completed" or row.exclusion_reason is not None:
                continue
            if _ACCURACY_METRIC in raw_metrics and row.judge_verdict is None:
                raise ValueError("DCI reproduction declared accuracy evidence is missing")
            if _NDCG_METRIC in raw_metrics and row.ndcg_at_10 is None:
                raise ValueError("DCI reproduction declared NDCG evidence is missing")
        aggregates = _parse_aggregates(item["aggregates"])
        expected = _computed_aggregates(queries, tuple(raw_metrics))
        if not _same_aggregates(aggregates, expected):
            raise ValueError("DCI reproduction aggregates are inconsistent")
        return cls(
            run_id=_require_public_id(item["run_id"], "run ID"),
            profile_id=_require_public_id(item["profile_id"], "profile ID"),
            profile_sha256=_require_sha256(item["profile_sha256"], "profile digest"),
            runtime=_require_public_id(item["runtime"], "runtime ID"),
            dataset_id=_require_public_id(item["dataset_id"], "dataset ID"),
            selection_id=_require_public_id(item["selection_id"], "selection ID"),
            selection_sha256=_require_sha256(
                item["selection_sha256"], "selection digest"
            ),
            effective_config_sha256=_require_sha256(
                item["effective_config_sha256"], "effective configuration digest"
            ),
            metric_identities=tuple(raw_metrics),
            queries=queries,
            aggregates=aggregates,
            identity_sha256=supplied_identity,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": RUN_MANIFEST_SCHEMA,
            "run_id": self.run_id,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "runtime": self.runtime,
            "dataset_id": self.dataset_id,
            "selection_id": self.selection_id,
            "selection_sha256": self.selection_sha256,
            "effective_config_sha256": self.effective_config_sha256,
            "metric_identities": list(self.metric_identities),
            "queries": [row.to_dict() for row in self.queries],
            "aggregates": self.aggregates.to_dict(),
            "identity_sha256": self.identity_sha256,
        }


def load_run_manifest(path: Path) -> RunManifest:
    """Load one exact, duplicate-key-free, body-free reproduction manifest."""

    source = Path(path)
    try:
        metadata = source.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("DCI reproduction manifest path is invalid")
        payload = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("DCI reproduction manifest is invalid") from None
    return RunManifest.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    lower: float
    upper: float

    def to_dict(self) -> dict[str, float]:
        return {"lower": self.lower, "upper": self.upper}


@dataclass(frozen=True, slots=True)
class EstimatorEvidence:
    name: str
    seed: int
    resamples: int
    query_set_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "seed": self.seed,
            "resamples": self.resamples,
            "query_set_sha256": self.query_set_sha256,
        }


@dataclass(frozen=True, slots=True)
class MetricComparison:
    baseline: float
    candidate: float
    delta: float
    confidence_interval: ConfidenceInterval
    margin: float
    accepted: bool
    estimator: EstimatorEvidence

    def to_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline,
            "candidate": self.candidate,
            "delta": self.delta,
            "confidence_interval": self.confidence_interval.to_dict(),
            "margin": self.margin,
            "accepted": self.accepted,
            "estimator": self.estimator.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ComparisonTotals:
    completion_rate: float
    failure_rate: float
    agent_operations: int
    judge_operations: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float

    @classmethod
    def from_manifest(cls, manifest: RunManifest) -> "ComparisonTotals":
        aggregates = manifest.aggregates
        denominator = aggregates.included_count
        completed = aggregates.completed_count
        return cls(
            completion_rate=completed / denominator if denominator else 0.0,
            failure_rate=(denominator - completed) / denominator if denominator else 0.0,
            agent_operations=aggregates.agent_operations,
            judge_operations=aggregates.judge_operations,
            input_tokens=aggregates.input_tokens,
            cached_input_tokens=aggregates.cached_input_tokens,
            output_tokens=aggregates.output_tokens,
            total_tokens=aggregates.total_tokens,
            cost_usd=aggregates.cost_usd,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "completion_rate": self.completion_rate,
            "failure_rate": self.failure_rate,
            "agent_operations": self.agent_operations,
            "judge_operations": self.judge_operations,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
        }


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    comparison_kind: str
    profile_id: str
    profile_sha256: str
    dataset_id: str
    selection_id: str
    selection_sha256: str
    effective_config_sha256: str
    baseline_run_sha256: str | None
    candidate_run_sha256: str
    target_identity: str | None
    pair_ids: tuple[str, ...]
    exclusion_ids: tuple[str, ...]
    baseline: ComparisonTotals | None
    candidate: ComparisonTotals
    metrics: Mapping[str, MetricComparison]
    accepted: bool | None
    identity_sha256: str

    def _unsigned_dict(self) -> dict[str, object]:
        return {
            "schema": COMPARISON_SCHEMA,
            "comparison_kind": self.comparison_kind,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "dataset_id": self.dataset_id,
            "selection_id": self.selection_id,
            "selection_sha256": self.selection_sha256,
            "effective_config_sha256": self.effective_config_sha256,
            "baseline_run_sha256": self.baseline_run_sha256,
            "candidate_run_sha256": self.candidate_run_sha256,
            "target_identity": self.target_identity,
            "pair_ids": list(self.pair_ids),
            "exclusion_ids": list(self.exclusion_ids),
            "baseline": None if self.baseline is None else self.baseline.to_dict(),
            "candidate": self.candidate.to_dict(),
            "metrics": {name: metric.to_dict() for name, metric in self.metrics.items()},
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._unsigned_dict(), "identity_sha256": self.identity_sha256}

    def to_json_bytes(self) -> bytes:
        return (
            json.dumps(
                self.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")


def _metric_value(row: QueryEvidence, metric: str) -> float:
    if row.status != "completed":
        return 0.0
    if metric == "accuracy":
        return 1.0 if row.judge_verdict is True else 0.0
    return row.ndcg_at_10 if row.ndcg_at_10 is not None else 0.0


def _paired_metric(
    baseline: tuple[QueryEvidence, ...],
    candidate: tuple[QueryEvidence, ...],
    metric: str,
    margin: float,
    query_set_sha256: str,
) -> MetricComparison:
    baseline_values = tuple(_metric_value(row, metric) for row in baseline)
    candidate_values = tuple(_metric_value(row, metric) for row in candidate)
    differences = tuple(
        candidate_value - baseline_value
        for baseline_value, candidate_value in zip(
            baseline_values, candidate_values, strict=True
        )
    )
    count = len(differences)
    if not count:
        raise ValueError("DCI reproduction comparison has no matched queries")
    rng = random.Random(ESTIMATOR_SEED)
    estimates = [
        sum(rng.choices(differences, k=count)) / count
        for _ in range(ESTIMATOR_RESAMPLES)
    ]
    estimates.sort()
    lower = estimates[math.floor(0.025 * (ESTIMATOR_RESAMPLES - 1))]
    upper = estimates[math.ceil(0.975 * (ESTIMATOR_RESAMPLES - 1))]
    baseline_mean = sum(baseline_values) / count
    candidate_mean = sum(candidate_values) / count
    delta = candidate_mean - baseline_mean
    return MetricComparison(
        baseline=baseline_mean,
        candidate=candidate_mean,
        delta=delta,
        confidence_interval=ConfidenceInterval(lower=lower, upper=upper),
        margin=margin,
        accepted=lower >= margin,
        estimator=EstimatorEvidence(
            name=ESTIMATOR_NAME,
            seed=ESTIMATOR_SEED,
            resamples=ESTIMATOR_RESAMPLES,
            query_set_sha256=query_set_sha256,
        ),
    )


def _profile_digest(profile: ExperimentProfile) -> str:
    return experiment_profile_sha256(
        profile.profile_id,
        invocation_provider=profile.provider
        if profile.profile_id == "current-default/claude-minimax"
        else None,
        invocation_model=profile.model
        if profile.profile_id == "current-default/claude-minimax"
        else None,
    )


def compare_reproduction_runs(
    baseline: RunManifest | None,
    candidate: RunManifest,
    profile: ExperimentProfile,
) -> ComparisonReport:
    """Compare exact matched Pi runs or one Claude run against its target identity."""

    profile_digest = _profile_digest(profile)
    if candidate.profile_id != profile.profile_id or candidate.profile_sha256 != profile_digest:
        raise ValueError("DCI reproduction profile identity drifted")
    if candidate.runtime != profile.runtime:
        raise ValueError("DCI reproduction runtime identity drifted")
    if profile.runtime == "claude-code":
        if baseline is not None:
            raise ValueError("DCI Claude reproduction has no source parity baseline")
        target = profile.comparison.get("published_target") or profile.comparison.get(
            "target_identity"
        )
        if type(target) is not str:
            raise ValueError("DCI Claude reproduction target identity is invalid")
        unsigned = {
            "schema": COMPARISON_SCHEMA,
            "comparison_kind": "target-comparison",
            "profile_id": profile.profile_id,
            "profile_sha256": profile_digest,
            "dataset_id": candidate.dataset_id,
            "selection_id": candidate.selection_id,
            "selection_sha256": candidate.selection_sha256,
            "effective_config_sha256": candidate.effective_config_sha256,
            "baseline_run_sha256": None,
            "candidate_run_sha256": candidate.identity_sha256,
            "target_identity": target,
            "pair_ids": [],
            "exclusion_ids": [
                row.query_id for row in candidate.queries if row.exclusion_reason is not None
            ],
            "baseline": None,
            "candidate": ComparisonTotals.from_manifest(candidate).to_dict(),
            "metrics": {},
            "accepted": None,
        }
        return ComparisonReport(
            comparison_kind="target-comparison",
            profile_id=profile.profile_id,
            profile_sha256=profile_digest,
            dataset_id=candidate.dataset_id,
            selection_id=candidate.selection_id,
            selection_sha256=candidate.selection_sha256,
            effective_config_sha256=candidate.effective_config_sha256,
            baseline_run_sha256=None,
            candidate_run_sha256=candidate.identity_sha256,
            target_identity=target,
            pair_ids=(),
            exclusion_ids=tuple(unsigned["exclusion_ids"]),  # type: ignore[arg-type]
            baseline=None,
            candidate=ComparisonTotals.from_manifest(candidate),
            metrics=MappingProxyType({}),
            accepted=None,
            identity_sha256=canonical_sha256(unsigned),
        )
    if baseline is None:
        raise ValueError("DCI Pi reproduction requires a source baseline")
    identity_fields = (
        "profile_id",
        "profile_sha256",
        "runtime",
        "dataset_id",
        "selection_id",
        "selection_sha256",
        "effective_config_sha256",
        "metric_identities",
    )
    if any(getattr(baseline, name) != getattr(candidate, name) for name in identity_fields):
        raise ValueError("DCI reproduction experiment identity drifted")
    if baseline.profile_id != profile.profile_id or baseline.profile_sha256 != profile_digest:
        raise ValueError("DCI reproduction profile identity drifted")
    baseline_by_id = {row.query_id: row for row in baseline.queries}
    candidate_by_id = {row.query_id: row for row in candidate.queries}
    all_ids = tuple(sorted(set(baseline_by_id) | set(candidate_by_id)))
    if set(baseline_by_id) != set(candidate_by_id):
        raise ValueError("DCI reproduction matched query IDs drifted")
    exclusion_ids = tuple(
        query_id
        for query_id in all_ids
        if baseline_by_id[query_id].exclusion_reason is not None
        or candidate_by_id[query_id].exclusion_reason is not None
    )
    pair_ids = tuple(query_id for query_id in all_ids if query_id not in exclusion_ids)
    baseline_pairs = tuple(baseline_by_id[query_id] for query_id in pair_ids)
    candidate_pairs = tuple(candidate_by_id[query_id] for query_id in pair_ids)
    query_set_sha256 = canonical_sha256(
        {
            "dataset_id": baseline.dataset_id,
            "selection_id": baseline.selection_id,
            "selection_sha256": baseline.selection_sha256,
            "pair_ids": list(pair_ids),
            "exclusion_ids": list(exclusion_ids),
        }
    )
    comparison = dict(profile.comparison)
    metrics: dict[str, MetricComparison] = {}
    has_accuracy = _ACCURACY_METRIC in baseline.metric_identities
    has_ndcg = _NDCG_METRIC in baseline.metric_identities
    if has_accuracy:
        metrics["accuracy"] = _paired_metric(
            baseline_pairs,
            candidate_pairs,
            "accuracy",
            _require_finite(comparison.get("accuracy_margin"), "accuracy margin"),
            query_set_sha256,
        )
    if has_ndcg:
        metrics["ndcg_at_10"] = _paired_metric(
            baseline_pairs,
            candidate_pairs,
            "ndcg_at_10",
            _require_finite(comparison.get("ndcg_margin"), "NDCG margin"),
            query_set_sha256,
        )
    if not metrics:
        raise ValueError("DCI reproduction comparison has no metric evidence")
    accepted = all(metric.accepted for metric in metrics.values())
    baseline_totals = ComparisonTotals.from_manifest(baseline)
    candidate_totals = ComparisonTotals.from_manifest(candidate)
    unsigned = {
        "schema": COMPARISON_SCHEMA,
        "comparison_kind": "source-parity",
        "profile_id": profile.profile_id,
        "profile_sha256": profile_digest,
        "dataset_id": candidate.dataset_id,
        "selection_id": candidate.selection_id,
        "selection_sha256": candidate.selection_sha256,
        "effective_config_sha256": candidate.effective_config_sha256,
        "baseline_run_sha256": baseline.identity_sha256,
        "candidate_run_sha256": candidate.identity_sha256,
        "target_identity": None,
        "pair_ids": list(pair_ids),
        "exclusion_ids": list(exclusion_ids),
        "baseline": baseline_totals.to_dict(),
        "candidate": candidate_totals.to_dict(),
        "metrics": {name: metric.to_dict() for name, metric in metrics.items()},
        "accepted": accepted,
    }
    return ComparisonReport(
        comparison_kind="source-parity",
        profile_id=profile.profile_id,
        profile_sha256=profile_digest,
        dataset_id=candidate.dataset_id,
        selection_id=candidate.selection_id,
        selection_sha256=candidate.selection_sha256,
        effective_config_sha256=candidate.effective_config_sha256,
        baseline_run_sha256=baseline.identity_sha256,
        candidate_run_sha256=candidate.identity_sha256,
        target_identity=None,
        pair_ids=pair_ids,
        exclusion_ids=exclusion_ids,
        baseline=baseline_totals,
        candidate=candidate_totals,
        metrics=MappingProxyType(metrics),
        accepted=accepted,
        identity_sha256=canonical_sha256(unsigned),
    )


def write_comparison_report(path: Path, report: ComparisonReport) -> None:
    """Write a deterministic report beneath a private directory."""

    destination = Path(path)
    parent = destination.parent
    if parent.exists():
        metadata = parent.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise ValueError("DCI reproduction report parent is invalid")
    else:
        parent.mkdir(parents=True, mode=0o700)
        os.chmod(parent, 0o700)
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise ValueError("DCI reproduction report path is invalid")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(destination, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(report.to_json_bytes())
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
