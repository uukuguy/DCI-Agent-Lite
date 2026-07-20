"""Body-free, versioned evidence for AF-340 reproduction comparisons."""

from __future__ import annotations

import json
import math
import os
import random
import re
import stat
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from asterion.dci.experiment_profiles import ExperimentProfile, resolve_experiment_profile
from asterion.dci.paper_benchmarks import (
    canonical_sha256,
    paper_benchmark_inventory_sha256,
    paper_experiment_scopes_sha256,
    resolve_paper_benchmark,
    resolve_paper_experiment_scope,
)

RUN_MANIFEST_SCHEMA = "dci.reproduction-run-manifest/v1"
QUERY_EVIDENCE_SCHEMA = "dci.reproduction-query-evidence/v1"
_SCHEMA_RESOURCE = "reproduction-result.schema.json"
_TARGET_RESOURCE = "reproduction-targets.json"
_TARGET_SCHEMA_RESOURCE = "reproduction-target.schema.json"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PUBLIC_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_FAILURE_CLASS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EXCLUSION_REASON = re.compile(
    r"^dci\.reproduction-exclusion/[a-z0-9][a-z0-9-]*/v[1-9][0-9]*$"
)
_STATUSES = frozenset({"completed", "failed", "cancelled", "timed_out", "missing"})
_PRODUCTS = frozenset({"original-dci", "asterion-dci"})
_QUERY_FIELDS = frozenset(
    {
        "schema",
        "query_id",
        "dataset_id",
        "scope_id",
        "status",
        "judge_verdict",
        "ndcg_at_10",
        "evidence_sha256",
        "failure_class",
        "exclusion_reason",
        "agent_operations",
        "judge_operations",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    }
)
_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "product",
        "profile_id",
        "profile_identity_sha256",
        "runtime_id",
        "effective_config_identity_sha256",
        "paper_benchmark_inventory_sha256",
        "paper_experiment_scopes_sha256",
        "scope_ids",
        "queries",
        "aggregates",
        "identity_sha256",
    }
)
_AGGREGATE_FIELDS = frozenset(
    {
        "query_count",
        "completed_count",
        "failure_count",
        "excluded_count",
        "accuracy",
        "mean_ndcg_at_10",
        "agent_operations",
        "judge_operations",
        "input_tokens",
        "output_tokens",
        "cost_usd",
    }
)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _canonical_sha256(value: Mapping[str, object]) -> str:
    json.dumps(value, ensure_ascii=False, allow_nan=False)
    return canonical_sha256(value)


def _require_digest(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"DCI reproduction {field} is invalid")
    return value


def _require_public_id(value: object, *, field: str) -> str:
    if type(value) is not str or _PUBLIC_ID.fullmatch(value) is None:
        raise ValueError(f"DCI reproduction {field} is invalid")
    return value


def _require_count(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"DCI reproduction {field} is invalid")
    return value


def _require_float(
    value: object, *, field: str, maximum: float | None = None
) -> float:
    if type(value) is bool:
        raise ValueError(f"DCI reproduction {field} is invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"DCI reproduction {field} is invalid") from error
    if not math.isfinite(parsed) or parsed < 0 or (
        maximum is not None and parsed > maximum
    ):
        raise ValueError(f"DCI reproduction {field} is invalid")
    return parsed


def _load_mapping_resource(name: str, *, kind: str) -> dict[str, object]:
    try:
        value = json.loads(
            resources.files("asterion.dci.resources")
            .joinpath(name)
            .read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise RuntimeError(f"DCI reproduction {kind} is invalid") from error
    if type(value) is not dict:
        raise RuntimeError(f"DCI reproduction {kind} is invalid")
    return value


def _validate_schema_resource() -> dict[str, object]:
    value = _load_mapping_resource(_SCHEMA_RESOURCE, kind="schema")
    if (
        value.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or value.get("$id") != RUN_MANIFEST_SCHEMA
        or value.get("additionalProperties") is not False
        or set(value.get("required", ())) != _MANIFEST_FIELDS
        or set(value.get("properties", ())) != _MANIFEST_FIELDS
        or set(value.get("$defs", ())) != {"query", "aggregates"}
    ):
        raise RuntimeError("DCI reproduction schema is invalid")
    return value


@dataclass(frozen=True, slots=True)
class ReproductionTarget:
    """One primary-source result target without query or answer bodies."""

    target_id: str
    profile_id: str
    source_id: str
    source_url: str
    agentic_search_accuracy: float
    qa_accuracy: float
    ir_ndcg_at_10: float
    dataset_targets: Mapping[str, float]
    identity_sha256: str

    def __post_init__(self) -> None:
        if self.target_id != "paper.2605.05242v1/dci-agent-cc/main":
            raise ValueError("DCI reproduction target ID is invalid")
        if self.profile_id != "paper-reference/claude-code":
            raise ValueError("DCI reproduction target profile is invalid")
        if self.source_id != "arxiv:2605.05242v1" or self.source_url != (
            "https://arxiv.org/pdf/2605.05242v1"
        ):
            raise ValueError("DCI reproduction target source is invalid")
        for field in (
            "agentic_search_accuracy",
            "qa_accuracy",
            "ir_ndcg_at_10",
        ):
            object.__setattr__(
                self,
                field,
                _require_float(getattr(self, field), field=field, maximum=1.0),
            )
        expected_datasets = {
            "beir.arguana",
            "beir.scifact",
            "bright.biology",
            "bright.earth-science",
            "bright.economics",
            "bright.robotics",
            "browsecomp-plus",
            "qa.2wikimultihopqa",
            "qa.bamboogle",
            "qa.hotpotqa",
            "qa.musique",
            "qa.nq",
            "qa.triviaqa",
        }
        if set(self.dataset_targets) != expected_datasets:
            raise ValueError("DCI reproduction target dataset set is invalid")
        normalized_targets = {
            dataset_id: _require_float(
                value, field="dataset target", maximum=1.0
            )
            for dataset_id, value in sorted(self.dataset_targets.items())
        }
        object.__setattr__(
            self, "dataset_targets", MappingProxyType(normalized_targets)
        )
        mapping = self.to_mapping()
        identity = mapping.pop("identity_sha256")
        if identity != _canonical_sha256(mapping):
            raise ValueError("DCI reproduction target identity drifted")

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "dci.reproduction-target/v1",
            "target_id": self.target_id,
            "profile_id": self.profile_id,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "agentic_search_accuracy": self.agentic_search_accuracy,
            "qa_accuracy": self.qa_accuracy,
            "ir_ndcg_at_10": self.ir_ndcg_at_10,
            "dataset_targets": dict(self.dataset_targets),
            "identity_sha256": self.identity_sha256,
        }


@lru_cache(maxsize=1)
def _reproduction_targets() -> Mapping[str, ReproductionTarget]:
    schema = _load_mapping_resource(_TARGET_SCHEMA_RESOURCE, kind="target registry")
    payload = _load_mapping_resource(_TARGET_RESOURCE, kind="target registry")
    if (
        type(schema) is not dict
        or schema.get("$id") != "dci.reproduction-target/v1"
        or schema.get("additionalProperties") is not False
        or type(payload) is not dict
        or set(payload) != {"schema", "targets"}
        or payload.get("schema") != "dci.reproduction-target/v1"
        or type(payload.get("targets")) is not list
        or len(payload["targets"]) != 1
    ):
        raise RuntimeError("DCI reproduction target registry is invalid")
    parsed: dict[str, ReproductionTarget] = {}
    for item in payload["targets"]:
        if type(item) is not dict or set(item) != {
            "target_id",
            "profile_id",
            "source_id",
            "source_url",
            "agentic_search_accuracy",
            "qa_accuracy",
            "ir_ndcg_at_10",
            "dataset_targets",
        }:
            raise RuntimeError("DCI reproduction target registry is invalid")
        base = {"schema": "dci.reproduction-target/v1", **item}
        try:
            target = ReproductionTarget(
                target_id=item["target_id"],
                profile_id=item["profile_id"],
                source_id=item["source_id"],
                source_url=item["source_url"],
                agentic_search_accuracy=item["agentic_search_accuracy"],
                qa_accuracy=item["qa_accuracy"],
                ir_ndcg_at_10=item["ir_ndcg_at_10"],
                dataset_targets=item["dataset_targets"],
                identity_sha256=_canonical_sha256(base),
            )
        except (TypeError, ValueError) as error:
            raise RuntimeError("DCI reproduction target registry is invalid") from error
        if target.profile_id in parsed:
            raise RuntimeError("DCI reproduction target registry is invalid")
        parsed[target.profile_id] = target
    return MappingProxyType(parsed)


def resolve_reproduction_target(profile_id: str) -> ReproductionTarget | None:
    """Resolve the published target for a profile, if the paper reports one."""

    resolve_experiment_profile(profile_id)
    return _reproduction_targets().get(profile_id)


def reproduction_result_schema_sha256() -> str:
    """Return the canonical identity of the installed result schema."""

    return _canonical_sha256(_validate_schema_resource())


def reproduction_target_schema_sha256() -> str:
    """Return the canonical identity of the installed target schema."""

    schema = _load_mapping_resource(_TARGET_SCHEMA_RESOURCE, kind="target schema")
    if schema.get("$id") != "dci.reproduction-target/v1":
        raise RuntimeError("DCI reproduction target schema is invalid")
    return _canonical_sha256(schema)


def reproduction_targets_sha256() -> str:
    """Return the canonical identity of the validated target registry."""

    targets = _reproduction_targets()
    return _canonical_sha256(
        {
            "schema": "dci.reproduction-target/v1",
            "targets": [
                {
                    "profile_id": target.profile_id,
                    "identity_sha256": target.identity_sha256,
                }
                for target in targets.values()
            ],
        }
    )


@dataclass(frozen=True, slots=True)
class QueryEvidence:
    """One immutable, body-free query outcome."""

    query_id: str
    dataset_id: str
    scope_id: str
    status: str
    judge_verdict: bool | None
    ndcg_at_10: float | None
    evidence_sha256: str | None
    failure_class: str | None
    exclusion_reason: str | None
    agent_operations: int
    judge_operations: int
    input_tokens: int
    output_tokens: int
    cost_usd: float

    def __post_init__(self) -> None:
        _require_public_id(self.query_id, field="query_id")
        _require_public_id(self.dataset_id, field="dataset_id")
        _require_public_id(self.scope_id, field="scope_id")
        if self.status not in _STATUSES:
            raise ValueError("DCI reproduction status is invalid")
        scope = resolve_paper_experiment_scope(self.scope_id)
        if scope.dataset_id != self.dataset_id:
            raise ValueError("DCI reproduction dataset identity drifted")
        dataset = resolve_paper_benchmark(self.dataset_id)
        if self.status == "completed":
            if self.failure_class is not None or self.exclusion_reason is not None:
                raise ValueError("DCI reproduction completed row is invalid")
            if dataset.mode == "qa":
                if type(self.judge_verdict) is not bool or self.ndcg_at_10 is not None:
                    raise ValueError("DCI reproduction QA metric is invalid")
            elif dataset.mode == "ir":
                if self.judge_verdict is not None or self.ndcg_at_10 is None:
                    raise ValueError("DCI reproduction IR metric is invalid")
            else:
                raise ValueError("DCI reproduction dataset mode is invalid")
        else:
            if self.judge_verdict is not None or self.ndcg_at_10 is not None:
                raise ValueError("DCI reproduction failure metric is invalid")
            if (
                type(self.failure_class) is not str
                or _FAILURE_CLASS.fullmatch(self.failure_class) is None
            ):
                raise ValueError("DCI reproduction failure class is invalid")
        if self.ndcg_at_10 is not None:
            object.__setattr__(
                self,
                "ndcg_at_10",
                _require_float(self.ndcg_at_10, field="ndcg_at_10", maximum=1.0),
            )
        if self.status == "missing":
            if self.evidence_sha256 is not None:
                raise ValueError("DCI reproduction missing evidence is invalid")
        else:
            _require_digest(self.evidence_sha256, field="evidence_sha256")
        if self.exclusion_reason is not None and (
            type(self.exclusion_reason) is not str
            or _EXCLUSION_REASON.fullmatch(self.exclusion_reason) is None
        ):
            raise ValueError("DCI reproduction exclusion reason is invalid")
        for field in (
            "agent_operations",
            "judge_operations",
            "input_tokens",
            "output_tokens",
        ):
            _require_count(getattr(self, field), field=field)
        object.__setattr__(
            self, "cost_usd", _require_float(self.cost_usd, field="cost_usd")
        )
        if self.status == "missing" and any(
            (
                self.agent_operations,
                self.judge_operations,
                self.input_tokens,
                self.output_tokens,
                self.cost_usd,
            )
        ):
            raise ValueError("DCI reproduction missing row counters are invalid")

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": QUERY_EVIDENCE_SCHEMA,
            "query_id": self.query_id,
            "dataset_id": self.dataset_id,
            "scope_id": self.scope_id,
            "status": self.status,
            "judge_verdict": self.judge_verdict,
            "ndcg_at_10": self.ndcg_at_10,
            "evidence_sha256": self.evidence_sha256,
            "failure_class": self.failure_class,
            "exclusion_reason": self.exclusion_reason,
            "agent_operations": self.agent_operations,
            "judge_operations": self.judge_operations,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
        }

    @classmethod
    def from_mapping(cls, value: object) -> QueryEvidence:
        if type(value) is not dict or set(value) != _QUERY_FIELDS:
            raise ValueError("DCI reproduction query evidence is invalid")
        if value.get("schema") != QUERY_EVIDENCE_SCHEMA:
            raise ValueError("DCI reproduction query evidence is invalid")
        return cls(
            query_id=value["query_id"],
            dataset_id=value["dataset_id"],
            scope_id=value["scope_id"],
            status=value["status"],
            judge_verdict=value["judge_verdict"],
            ndcg_at_10=value["ndcg_at_10"],
            evidence_sha256=value["evidence_sha256"],
            failure_class=value["failure_class"],
            exclusion_reason=value["exclusion_reason"],
            agent_operations=value["agent_operations"],
            judge_operations=value["judge_operations"],
            input_tokens=value["input_tokens"],
            output_tokens=value["output_tokens"],
            cost_usd=value["cost_usd"],
        )


def _aggregate(queries: Sequence[QueryEvidence]) -> dict[str, int | float | None]:
    included = tuple(row for row in queries if row.exclusion_reason is None)
    qa_rows = tuple(
        row
        for row in included
        if resolve_paper_benchmark(row.dataset_id).mode == "qa"
    )
    ir_rows = tuple(
        row
        for row in included
        if resolve_paper_benchmark(row.dataset_id).mode == "ir"
    )
    accuracy = (
        sum(row.judge_verdict is True for row in qa_rows) / len(qa_rows)
        if qa_rows
        else None
    )
    mean_ndcg = (
        sum(row.ndcg_at_10 or 0.0 for row in ir_rows) / len(ir_rows)
        if ir_rows
        else None
    )
    return {
        "query_count": len(queries),
        "completed_count": sum(row.status == "completed" for row in included),
        "failure_count": sum(row.status != "completed" for row in included),
        "excluded_count": len(queries) - len(included),
        "accuracy": accuracy,
        "mean_ndcg_at_10": mean_ndcg,
        "agent_operations": sum(row.agent_operations for row in queries),
        "judge_operations": sum(row.judge_operations for row in queries),
        "input_tokens": sum(row.input_tokens for row in queries),
        "output_tokens": sum(row.output_tokens for row in queries),
        "cost_usd": sum(row.cost_usd for row in queries),
    }


@dataclass(frozen=True, slots=True)
class RunManifest:
    """One exact reproduction run or scope result."""

    product: str
    profile_id: str
    profile_identity_sha256: str
    runtime_id: str
    effective_config_identity_sha256: str
    paper_benchmark_inventory_sha256: str
    paper_experiment_scopes_sha256: str
    scope_ids: tuple[str, ...]
    queries: tuple[QueryEvidence, ...]
    aggregates: Mapping[str, int | float | None]
    identity_sha256: str

    def __post_init__(self) -> None:
        if self.product not in _PRODUCTS:
            raise ValueError("DCI reproduction product is invalid")
        profile = resolve_experiment_profile(self.profile_id)
        if self.profile_identity_sha256 != profile.identity_sha256:
            raise ValueError("DCI reproduction profile identity drifted")
        if self.runtime_id != profile.runtime_id:
            raise ValueError("DCI reproduction runtime identity drifted")
        _require_digest(
            self.effective_config_identity_sha256,
            field="effective_config_identity_sha256",
        )
        if self.paper_benchmark_inventory_sha256 != paper_benchmark_inventory_sha256():
            raise ValueError("DCI reproduction benchmark identity drifted")
        if self.paper_experiment_scopes_sha256 != paper_experiment_scopes_sha256():
            raise ValueError("DCI reproduction scope identity drifted")
        if (
            not self.scope_ids
            or tuple(sorted(set(self.scope_ids))) != self.scope_ids
            or not set(self.scope_ids).issubset(profile.paper_scope_ids)
        ):
            raise ValueError("DCI reproduction scope set is invalid")
        if not self.queries or tuple(sorted(self.queries, key=lambda row: row.query_id)) != self.queries:
            raise ValueError("DCI reproduction query order is invalid")
        query_ids = tuple(row.query_id for row in self.queries)
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("DCI reproduction query IDs are invalid")
        if any(row.scope_id not in self.scope_ids for row in self.queries):
            raise ValueError("DCI reproduction query scope drifted")
        expected_aggregates = _aggregate(self.queries)
        if set(self.aggregates) != _AGGREGATE_FIELDS or dict(self.aggregates) != expected_aggregates:
            raise ValueError("DCI reproduction aggregates drifted")
        object.__setattr__(self, "aggregates", MappingProxyType(expected_aggregates))
        mapping = self.to_mapping()
        identity = mapping.pop("identity_sha256")
        if identity != _canonical_sha256(mapping):
            raise ValueError("DCI reproduction manifest identity drifted")

    @classmethod
    def create(
        cls,
        *,
        product: str,
        profile: ExperimentProfile,
        effective_config_identity_sha256: str,
        scope_ids: Sequence[str],
        queries: Sequence[QueryEvidence],
    ) -> RunManifest:
        _validate_schema_resource()
        normalized_scopes = tuple(sorted(scope_ids))
        normalized_queries = tuple(sorted(queries, key=lambda row: row.query_id))
        aggregates = _aggregate(normalized_queries)
        base: dict[str, object] = {
            "schema": RUN_MANIFEST_SCHEMA,
            "product": product,
            "profile_id": profile.profile_id,
            "profile_identity_sha256": profile.identity_sha256,
            "runtime_id": profile.runtime_id,
            "effective_config_identity_sha256": effective_config_identity_sha256,
            "paper_benchmark_inventory_sha256": paper_benchmark_inventory_sha256(),
            "paper_experiment_scopes_sha256": paper_experiment_scopes_sha256(),
            "scope_ids": list(normalized_scopes),
            "queries": [row.to_mapping() for row in normalized_queries],
            "aggregates": aggregates,
        }
        return cls(
            product=product,
            profile_id=profile.profile_id,
            profile_identity_sha256=profile.identity_sha256,
            runtime_id=profile.runtime_id,
            effective_config_identity_sha256=effective_config_identity_sha256,
            paper_benchmark_inventory_sha256=paper_benchmark_inventory_sha256(),
            paper_experiment_scopes_sha256=paper_experiment_scopes_sha256(),
            scope_ids=normalized_scopes,
            queries=normalized_queries,
            aggregates=aggregates,
            identity_sha256=_canonical_sha256(base),
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": RUN_MANIFEST_SCHEMA,
            "product": self.product,
            "profile_id": self.profile_id,
            "profile_identity_sha256": self.profile_identity_sha256,
            "runtime_id": self.runtime_id,
            "effective_config_identity_sha256": self.effective_config_identity_sha256,
            "paper_benchmark_inventory_sha256": self.paper_benchmark_inventory_sha256,
            "paper_experiment_scopes_sha256": self.paper_experiment_scopes_sha256,
            "scope_ids": list(self.scope_ids),
            "queries": [row.to_mapping() for row in self.queries],
            "aggregates": dict(self.aggregates),
            "identity_sha256": self.identity_sha256,
        }

    @classmethod
    def from_mapping(cls, value: object) -> RunManifest:
        _validate_schema_resource()
        if type(value) is not dict or set(value) != _MANIFEST_FIELDS:
            raise ValueError("DCI reproduction run manifest is invalid")
        if value.get("schema") != RUN_MANIFEST_SCHEMA:
            raise ValueError("DCI reproduction run manifest is invalid")
        scope_ids = value.get("scope_ids")
        queries = value.get("queries")
        aggregates = value.get("aggregates")
        if type(scope_ids) is not list or type(queries) is not list or type(aggregates) is not dict:
            raise ValueError("DCI reproduction run manifest is invalid")
        return cls(
            product=value["product"],
            profile_id=value["profile_id"],
            profile_identity_sha256=value["profile_identity_sha256"],
            runtime_id=value["runtime_id"],
            effective_config_identity_sha256=value["effective_config_identity_sha256"],
            paper_benchmark_inventory_sha256=value[
                "paper_benchmark_inventory_sha256"
            ],
            paper_experiment_scopes_sha256=value["paper_experiment_scopes_sha256"],
            scope_ids=tuple(scope_ids),
            queries=tuple(QueryEvidence.from_mapping(row) for row in queries),
            aggregates=aggregates,
            identity_sha256=value["identity_sha256"],
        )


def load_run_manifest(path: Path | str | os.PathLike[str]) -> RunManifest:
    """Load one strict manifest without following a symlink or exposing bodies."""

    manifest_path = Path(path)
    try:
        metadata = manifest_path.lstat()
        if manifest_path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("DCI reproduction manifest path is invalid")
        value = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("DCI reproduction manifest is invalid") from error
    return RunManifest.from_mapping(value)


def _safe_query_projection(row: QueryEvidence) -> dict[str, object]:
    return {
        "query_id": row.query_id,
        "dataset_id": row.dataset_id,
        "scope_id": row.scope_id,
        "status": row.status,
        "judge_verdict": row.judge_verdict,
        "ndcg_at_10": row.ndcg_at_10,
        "evidence_sha256": row.evidence_sha256,
        "failure_class": row.failure_class,
        "exclusion_reason": row.exclusion_reason,
    }


def _totals(manifest: RunManifest) -> dict[str, int | float]:
    return {
        field: manifest.aggregates[field]
        for field in (
            "agent_operations",
            "judge_operations",
            "input_tokens",
            "output_tokens",
            "cost_usd",
        )
    }


def _completion_rates(queries: Sequence[QueryEvidence]) -> tuple[float, float]:
    if not queries:
        return 0.0, 0.0
    completion = sum(row.status == "completed" for row in queries) / len(queries)
    return completion, 1.0 - completion


def _sample_sha256(
    query_ids: Sequence[str], baseline: Sequence[float], candidate: Sequence[float]
) -> str:
    return canonical_sha256(
        {
            "query_ids": list(query_ids),
            "baseline": list(baseline),
            "candidate": list(candidate),
        }
    )


def _bootstrap_metric(
    *,
    query_ids: Sequence[str],
    baseline: Sequence[float],
    candidate: Sequence[float],
    margin: float,
    seed: int,
    resamples: int,
) -> dict[str, int | float | bool | str]:
    if not query_ids or len(query_ids) != len(baseline) or len(baseline) != len(candidate):
        raise ValueError("DCI reproduction comparison sample is invalid")
    differences = tuple(
        candidate_value - baseline_value
        for baseline_value, candidate_value in zip(baseline, candidate, strict=True)
    )
    point_delta = sum(differences) / len(differences)
    rng = random.Random(seed)
    bootstrapped = [
        sum(rng.choices(differences, k=len(differences))) / len(differences)
        for _ in range(resamples)
    ]
    bootstrapped.sort()
    lower = bootstrapped[int((resamples - 1) * 0.025)]
    upper = bootstrapped[int((resamples - 1) * 0.975)]
    return {
        "pair_count": len(query_ids),
        "baseline_mean": sum(baseline) / len(baseline),
        "candidate_mean": sum(candidate) / len(candidate),
        "delta": point_delta,
        "lower_bound": lower,
        "upper_bound": upper,
        "margin": margin,
        "passes": lower >= -margin,
        "sample_sha256": _sample_sha256(query_ids, baseline, candidate),
    }


def _bootstrap_single_metric(
    *,
    query_ids: Sequence[str],
    values: Sequence[float],
    seed: int,
    resamples: int,
) -> dict[str, int | float | str]:
    if not query_ids or len(query_ids) != len(values):
        raise ValueError("DCI reproduction target sample is invalid")
    rng = random.Random(seed)
    bootstrapped = [
        sum(rng.choices(values, k=len(values))) / len(values)
        for _ in range(resamples)
    ]
    bootstrapped.sort()
    return {
        "sample_count": len(query_ids),
        "candidate_mean": sum(values) / len(values),
        "lower_bound": bootstrapped[int((resamples - 1) * 0.025)],
        "upper_bound": bootstrapped[int((resamples - 1) * 0.975)],
        "sample_sha256": canonical_sha256(
            {"query_ids": list(query_ids), "candidate": list(values)}
        ),
    }


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    """Versioned result of a paired Pi or unpaired Claude comparison."""

    comparison_kind: str
    profile_id: str
    profile_identity_sha256: str
    baseline_manifest_identity_sha256: str | None
    candidate_manifest_identity_sha256: str
    estimator: Mapping[str, object]
    accuracy: Mapping[str, object] | None
    ndcg_at_10: Mapping[str, object] | None
    completion: Mapping[str, float]
    totals: Mapping[str, Mapping[str, int | float]]
    retained_pair_ids: tuple[str, ...]
    excluded_query_ids: tuple[str, ...]
    pairs: tuple[Mapping[str, object], ...]
    target_rows: tuple[Mapping[str, object], ...]
    target_identity: Mapping[str, object] | None
    accepted: bool | None
    identity_sha256: str

    def __post_init__(self) -> None:
        if self.comparison_kind not in {"paired-noninferiority", "target-comparison"}:
            raise ValueError("DCI reproduction comparison kind is invalid")
        profile = resolve_experiment_profile(self.profile_id)
        if self.profile_identity_sha256 != profile.identity_sha256:
            raise ValueError("DCI reproduction comparison profile drifted")
        if self.comparison_kind == "paired-noninferiority":
            if (
                self.baseline_manifest_identity_sha256 is None
                or self.target_identity is not None
                or self.target_rows
                or type(self.accepted) is not bool
            ):
                raise ValueError("DCI reproduction paired comparison is invalid")
        elif (
            self.baseline_manifest_identity_sha256 is not None
            or self.pairs
            or self.retained_pair_ids
            or self.target_identity is None
            or self.accepted is not None
        ):
            raise ValueError("DCI reproduction target comparison is invalid")
        for digest in (
            self.candidate_manifest_identity_sha256,
            self.identity_sha256,
            *(
                (self.baseline_manifest_identity_sha256,)
                if self.baseline_manifest_identity_sha256 is not None
                else ()
            ),
        ):
            _require_digest(digest, field="comparison identity")
        mapping = self.to_mapping()
        identity = mapping.pop("identity_sha256")
        if identity != _canonical_sha256(mapping):
            raise ValueError("DCI reproduction comparison identity drifted")

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "dci.reproduction-comparison/v1",
            "comparison_kind": self.comparison_kind,
            "profile_id": self.profile_id,
            "profile_identity_sha256": self.profile_identity_sha256,
            "baseline_manifest_identity_sha256": self.baseline_manifest_identity_sha256,
            "candidate_manifest_identity_sha256": self.candidate_manifest_identity_sha256,
            "estimator": dict(self.estimator),
            "accuracy": None if self.accuracy is None else dict(self.accuracy),
            "ndcg_at_10": None if self.ndcg_at_10 is None else dict(self.ndcg_at_10),
            "completion": dict(self.completion),
            "totals": {
                name: dict(values) for name, values in self.totals.items()
            },
            "retained_pair_ids": list(self.retained_pair_ids),
            "excluded_query_ids": list(self.excluded_query_ids),
            "pairs": [
                {
                    "query_id": pair["query_id"],
                    "dataset_id": pair["dataset_id"],
                    "scope_id": pair["scope_id"],
                    "baseline": dict(pair["baseline"]),
                    "candidate": dict(pair["candidate"]),
                }
                for pair in self.pairs
            ],
            "target_rows": [dict(row) for row in self.target_rows],
            "target_identity": (
                None if self.target_identity is None else dict(self.target_identity)
            ),
            "accepted": self.accepted,
            "identity_sha256": self.identity_sha256,
        }


def _comparison_report(**values: object) -> ComparisonReport:
    base = {
        "schema": "dci.reproduction-comparison/v1",
        **values,
    }
    return ComparisonReport(
        comparison_kind=values["comparison_kind"],
        profile_id=values["profile_id"],
        profile_identity_sha256=values["profile_identity_sha256"],
        baseline_manifest_identity_sha256=values[
            "baseline_manifest_identity_sha256"
        ],
        candidate_manifest_identity_sha256=values[
            "candidate_manifest_identity_sha256"
        ],
        estimator=MappingProxyType(dict(values["estimator"])),
        accuracy=(
            None
            if values["accuracy"] is None
            else MappingProxyType(dict(values["accuracy"]))
        ),
        ndcg_at_10=(
            None
            if values["ndcg_at_10"] is None
            else MappingProxyType(dict(values["ndcg_at_10"]))
        ),
        completion=MappingProxyType(dict(values["completion"])),
        totals=MappingProxyType(
            {
                name: MappingProxyType(dict(total))
                for name, total in values["totals"].items()
            }
        ),
        retained_pair_ids=tuple(values["retained_pair_ids"]),
        excluded_query_ids=tuple(values["excluded_query_ids"]),
        pairs=tuple(
            MappingProxyType(
                {
                    **dict(pair),
                    "baseline": MappingProxyType(dict(pair["baseline"])),
                    "candidate": MappingProxyType(dict(pair["candidate"])),
                }
            )
            for pair in values["pairs"]
        ),
        target_rows=tuple(
            MappingProxyType(dict(row)) for row in values["target_rows"]
        ),
        target_identity=(
            None
            if values["target_identity"] is None
            else MappingProxyType(dict(values["target_identity"]))
        ),
        accepted=values["accepted"],
        identity_sha256=_canonical_sha256(base),
    )


def _validate_candidate(candidate: RunManifest, profile: ExperimentProfile) -> None:
    if (
        candidate.product != "asterion-dci"
        or candidate.profile_id != profile.profile_id
        or candidate.profile_identity_sha256 != profile.identity_sha256
        or candidate.runtime_id != profile.runtime_id
    ):
        raise ValueError("DCI reproduction candidate identity drifted")


def compare_reproduction_runs(
    baseline: RunManifest | None,
    candidate: RunManifest,
    profile: ExperimentProfile,
) -> ComparisonReport:
    """Compare matched Pi rows or label one Claude run as target-comparison."""

    _validate_candidate(candidate, profile)
    if profile.runtime_id == "claude-code":
        if baseline is not None:
            raise ValueError("DCI Claude reproduction has no source baseline")
        included = tuple(
            row for row in candidate.queries if row.exclusion_reason is None
        )
        completion_rate, failure_rate = _completion_rates(included)
        qa_rows = tuple(
            row
            for row in included
            if resolve_paper_benchmark(row.dataset_id).mode == "qa"
        )
        ir_rows = tuple(
            row
            for row in included
            if resolve_paper_benchmark(row.dataset_id).mode == "ir"
        )
        accuracy = (
            _bootstrap_single_metric(
                query_ids=[row.query_id for row in qa_rows],
                values=[float(row.judge_verdict is True) for row in qa_rows],
                seed=340,
                resamples=10_000,
            )
            if qa_rows
            else None
        )
        ndcg = (
            _bootstrap_single_metric(
                query_ids=[row.query_id for row in ir_rows],
                values=[float(row.ndcg_at_10 or 0.0) for row in ir_rows],
                seed=341,
                resamples=10_000,
            )
            if ir_rows
            else None
        )
        published_target = resolve_reproduction_target(profile.profile_id)
        target_identity = {
            "profile_id": profile.profile_id,
            "profile_identity_sha256": profile.identity_sha256,
            "qa_accuracy_drop_margin": dict(profile.comparison_targets)[
                "qa_accuracy_drop_margin"
            ],
            "ir_ndcg_drop_margin": dict(profile.comparison_targets)[
                "ir_ndcg_drop_margin"
            ],
            "published_target_status": (
                "available" if published_target is not None else "not-applicable"
            ),
            "target_id": (
                None if published_target is None else published_target.target_id
            ),
            "target_identity_sha256": (
                None if published_target is None else published_target.identity_sha256
            ),
            "source_id": (
                None if published_target is None else published_target.source_id
            ),
        }
        return _comparison_report(
            comparison_kind="target-comparison",
            profile_id=profile.profile_id,
            profile_identity_sha256=profile.identity_sha256,
            baseline_manifest_identity_sha256=None,
            candidate_manifest_identity_sha256=candidate.identity_sha256,
            estimator={
                "name": "single-run-bootstrap-percentile/v1",
                "seed": 340,
                "resamples": 10_000,
                "query_set_sha256": canonical_sha256(
                    [row.query_id for row in included]
                ),
                "accuracy_sample_sha256": (
                    None if accuracy is None else accuracy["sample_sha256"]
                ),
                "ndcg_sample_sha256": (
                    None if ndcg is None else ndcg["sample_sha256"]
                ),
            },
            accuracy=accuracy,
            ndcg_at_10=ndcg,
            completion={
                "candidate_rate": completion_rate,
                "candidate_failure_rate": failure_rate,
            },
            totals={"candidate": _totals(candidate)},
            retained_pair_ids=(),
            excluded_query_ids=tuple(
                row.query_id
                for row in candidate.queries
                if row.exclusion_reason is not None
            ),
            pairs=(),
            target_rows=tuple(_safe_query_projection(row) for row in included),
            target_identity=target_identity,
            accepted=None,
        )

    if baseline is None:
        raise ValueError("DCI Pi reproduction requires a source baseline")
    if (
        baseline.product != "original-dci"
        or baseline.profile_id != profile.profile_id
        or baseline.profile_identity_sha256 != profile.identity_sha256
        or baseline.runtime_id != "pi"
        or candidate.runtime_id != "pi"
        or baseline.scope_ids != candidate.scope_ids
        or baseline.effective_config_identity_sha256
        != candidate.effective_config_identity_sha256
    ):
        raise ValueError("DCI reproduction baseline identity drifted")
    baseline_by_id = {row.query_id: row for row in baseline.queries}
    candidate_by_id = {row.query_id: row for row in candidate.queries}
    if set(baseline_by_id) != set(candidate_by_id):
        raise ValueError("DCI reproduction query selection drifted")

    retained: list[tuple[QueryEvidence, QueryEvidence]] = []
    excluded_ids: list[str] = []
    for query_id in sorted(baseline_by_id):
        baseline_row = baseline_by_id[query_id]
        candidate_row = candidate_by_id[query_id]
        if (
            baseline_row.dataset_id != candidate_row.dataset_id
            or baseline_row.scope_id != candidate_row.scope_id
            or baseline_row.exclusion_reason != candidate_row.exclusion_reason
        ):
            raise ValueError("DCI reproduction paired row drifted")
        if baseline_row.exclusion_reason is not None:
            excluded_ids.append(query_id)
        else:
            retained.append((baseline_row, candidate_row))
    if not retained:
        raise ValueError("DCI reproduction comparison has no retained pairs")

    qa_pairs = tuple(
        pair
        for pair in retained
        if resolve_paper_benchmark(pair[0].dataset_id).mode == "qa"
    )
    ir_pairs = tuple(
        pair
        for pair in retained
        if resolve_paper_benchmark(pair[0].dataset_id).mode == "ir"
    )
    targets = dict(profile.comparison_targets)
    accuracy = (
        _bootstrap_metric(
            query_ids=[pair[0].query_id for pair in qa_pairs],
            baseline=[float(pair[0].judge_verdict is True) for pair in qa_pairs],
            candidate=[float(pair[1].judge_verdict is True) for pair in qa_pairs],
            margin=targets["qa_accuracy_drop_margin"],
            seed=340,
            resamples=10_000,
        )
        if qa_pairs
        else None
    )
    ndcg = (
        _bootstrap_metric(
            query_ids=[pair[0].query_id for pair in ir_pairs],
            baseline=[float(pair[0].ndcg_at_10 or 0.0) for pair in ir_pairs],
            candidate=[float(pair[1].ndcg_at_10 or 0.0) for pair in ir_pairs],
            margin=targets["ir_ndcg_drop_margin"],
            seed=341,
            resamples=10_000,
        )
        if ir_pairs
        else None
    )
    baseline_completion, baseline_failure = _completion_rates(
        [pair[0] for pair in retained]
    )
    candidate_completion, candidate_failure = _completion_rates(
        [pair[1] for pair in retained]
    )
    accepted = all(
        metric["passes"] for metric in (accuracy, ndcg) if metric is not None
    )
    retained_ids = tuple(pair[0].query_id for pair in retained)
    estimator = {
        "name": "paired-bootstrap-percentile/v1",
        "seed": 340,
        "resamples": 10_000,
        "query_set_sha256": canonical_sha256(list(retained_ids)),
        "accuracy_sample_sha256": (
            None if accuracy is None else accuracy["sample_sha256"]
        ),
        "ndcg_sample_sha256": None if ndcg is None else ndcg["sample_sha256"],
    }
    pairs = tuple(
        {
            "query_id": baseline_row.query_id,
            "dataset_id": baseline_row.dataset_id,
            "scope_id": baseline_row.scope_id,
            "baseline": _safe_query_projection(baseline_row),
            "candidate": _safe_query_projection(candidate_row),
        }
        for baseline_row, candidate_row in retained
    )
    return _comparison_report(
        comparison_kind="paired-noninferiority",
        profile_id=profile.profile_id,
        profile_identity_sha256=profile.identity_sha256,
        baseline_manifest_identity_sha256=baseline.identity_sha256,
        candidate_manifest_identity_sha256=candidate.identity_sha256,
        estimator=estimator,
        accuracy=accuracy,
        ndcg_at_10=ndcg,
        completion={
            "baseline_rate": baseline_completion,
            "baseline_failure_rate": baseline_failure,
            "candidate_rate": candidate_completion,
            "candidate_failure_rate": candidate_failure,
        },
        totals={"baseline": _totals(baseline), "candidate": _totals(candidate)},
        retained_pair_ids=retained_ids,
        excluded_query_ids=tuple(excluded_ids),
        pairs=pairs,
        target_rows=(),
        target_identity=None,
        accepted=accepted,
    )


def write_comparison_report(path: Path, report: ComparisonReport) -> None:
    """Create one exclusive 0600 report below an existing private parent."""

    output = Path(os.path.abspath(os.path.normpath(path)))
    parent = output.parent
    try:
        parent_metadata = parent.lstat()
    except OSError as error:
        raise ValueError("DCI reproduction report parent is invalid") from error
    if (
        parent.is_symlink()
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or stat.S_IMODE(parent_metadata.st_mode) != 0o700
        or output.exists()
        or output.is_symlink()
    ):
        raise ValueError("DCI reproduction report path is invalid")
    raw = (
        json.dumps(report.to_mapping(), sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode()
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
