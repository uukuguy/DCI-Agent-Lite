"""Body-free, versioned evidence for AF-340 reproduction comparisons."""

from __future__ import annotations

import json
import math
import os
import re
import stat
from dataclasses import dataclass
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


def _validate_schema_resource() -> None:
    try:
        value = json.loads(
            resources.files("asterion.dci.resources")
            .joinpath(_SCHEMA_RESOURCE)
            .read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise RuntimeError("DCI reproduction schema is invalid") from error
    if (
        type(value) is not dict
        or value.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or value.get("$id") != RUN_MANIFEST_SCHEMA
        or value.get("additionalProperties") is not False
        or set(value.get("required", ())) != _MANIFEST_FIELDS
        or set(value.get("properties", ())) != _MANIFEST_FIELDS
        or set(value.get("$defs", ())) != {"query", "aggregates"}
    ):
        raise RuntimeError("DCI reproduction schema is invalid")


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
