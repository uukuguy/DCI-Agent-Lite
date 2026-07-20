"""Immutable experiment profiles and explicit AF-340 full-run authorization."""

from __future__ import annotations

import json
import math
import os
import stat
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any

from asterion.dci.paper_benchmarks import (
    canonical_sha256,
    paper_benchmark_ids,
    paper_benchmark_inventory_sha256,
    paper_experiment_scope_ids,
    paper_experiment_scopes_sha256,
    resolve_paper_benchmark,
    resolve_paper_experiment_scope,
)

EXPERIMENT_PROFILE_SCHEMA = "dci.experiment-profile/v1"
EXPERIMENT_AUTHORIZATION_SCHEMA = "asterion.dci.paper-full-authorization/v1"
_EXPERIMENT_PROFILE_RESOURCES = "experiment-profiles.json"
_EXPERIMENT_PROFILE_SCHEMA_RESOURCE = "experiment-profile.schema.json"
_AUTHORIZATION_FILE = "paper-full-authorization.json"
_AUTHORIZATION_FIELDS = (
    "schema",
    "profile_id",
    "profile_identity_sha256",
    "paper_scope_ids",
    "paper_benchmark_inventory_sha256",
    "paper_experiment_scopes_sha256",
    "estimated_budget_usd",
    "invocation_authorized",
)
_EXPECTED_PROFILE_IDS = (
    "current-default/pi",
    "current-default/claude-subscription",
    "current-default/claude-minimax",
    "paper-reference/pi",
    "paper-reference/claude-code",
)
_AF340_RUNTIME_LEVELS = {"level0", "level1", "level2", "level3", "level4"}
_AF340_REASONING = {"low", "medium", "high", "default"}
_PROFILE_FIELDS = {
    "profile_id",
    "profile_family",
    "runtime_id",
    "runtime_provider",
    "runtime_model",
    "runtime_model_from_invocation",
    "runtime_authentication_mode",
    "reasoning",
    "tools",
    "max_turns",
    "runtime_context_level",
    "judge_contract",
    "judge_api",
    "dataset_scope_ids",
    "comparison_targets",
    "paper_seed_policy",
    "paper_scope_dataset_ids",
    "executable_if_authorized",
}


@dataclass(frozen=True, slots=True)
class ExperimentProfile:
    profile_id: str
    profile_family: str
    runtime_id: str
    runtime_provider: str | None
    runtime_model: str | None
    runtime_model_from_invocation: bool
    runtime_authentication_mode: str
    reasoning: str
    tools: str
    max_turns: int
    runtime_context_level: str | None
    judge_contract: str
    judge_api: str
    paper_scope_ids: tuple[str, ...]
    comparison_targets: tuple[tuple[str, float], ...]
    paper_seed_policy: str
    paper_scope_dataset_ids: tuple[str, ...]
    executable_if_authorized: bool
    identity_sha256: str

    def to_mapping(self) -> dict[str, object]:
        scope_contracts = []
        for scope_id in self.paper_scope_ids:
            scope = resolve_paper_experiment_scope(scope_id)
            dataset = resolve_paper_benchmark(scope.dataset_id)
            scope_contracts.append(
                {
                    "scope_id": scope.scope_id,
                    "scope_identity_sha256": scope.identity_sha256,
                    "dataset_id": dataset.dataset_id,
                    "dataset_identity_sha256": dataset.identity_sha256,
                    "selection_count": scope.selection_count,
                    "selection_seed_status": scope.selection_seed_status,
                    "selection_algorithm": scope.selection_algorithm,
                    "selected_ids_sha256": scope.selected_ids_sha256,
                    "corpus_path": dataset.corpus_path,
                    "metric": dataset.metric,
                    "aggregation": "mean-over-selected-queries/v1",
                }
            )
        return {
            "profile_id": self.profile_id,
            "profile_family": self.profile_family,
            "runtime_id": self.runtime_id,
            "runtime_provider": self.runtime_provider,
            "runtime_model": self.runtime_model,
            "runtime_model_from_invocation": self.runtime_model_from_invocation,
            "runtime_authentication_mode": self.runtime_authentication_mode,
            "reasoning": self.reasoning,
            "tools": self.tools,
            "max_turns": self.max_turns,
            "runtime_context_level": self.runtime_context_level,
            "judge_contract": self.judge_contract,
            "judge_api": self.judge_api,
            "dataset_scope_ids": list(self.paper_scope_ids),
            "comparison_targets": dict(self.comparison_targets),
            "paper_seed_policy": self.paper_seed_policy,
            "paper_scope_dataset_ids": list(self.paper_scope_dataset_ids),
            "paper_benchmark_inventory_sha256": paper_benchmark_inventory_sha256(),
            "paper_experiment_scopes_sha256": paper_experiment_scopes_sha256(),
            "scope_contracts": scope_contracts,
            "executable_if_authorized": self.executable_if_authorized,
        }


@dataclass(frozen=True, slots=True)
class FullExecutionAuthorization:
    """Explicit full execution authorization for AF-340."""

    profile_id: str
    output_root: Path
    estimated_budget_usd: float
    invocation_authorized: bool


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate key")
        value[key] = item
    return value


def _load_json_resource(name: str) -> dict[str, Any]:
    try:
        raw = resources.files("asterion.dci.resources").joinpath(name).read_text(
            encoding="utf-8"
        )
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError) as error:
        raise RuntimeError("DCI experiment profile contract is invalid") from error
    if type(value) is not dict:
        raise RuntimeError("DCI experiment profile contract is invalid")
    return value


def _require_string(value: object, *, name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"DCI experiment profile {name} is invalid")
    return value


def _validate_positive_int(value: object, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"DCI experiment profile {name} is invalid")
    return value


def _validate_safe_float(value: object, *, name: str) -> float:
    if type(value) is bool:
        raise ValueError(f"DCI experiment profile {name} is invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"DCI experiment profile {name} is invalid") from error
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"DCI experiment profile {name} is invalid")
    return parsed


def _check_no_symlink(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError("DCI paper full output root is invalid")


def _normalize_output_root(value: object) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise ValueError("DCI paper full output root is invalid")
    output = Path(os.path.abspath(os.path.normpath(str(value))))
    _check_no_symlink(output)
    return output


def _validate_profile_schema() -> dict[str, Any]:
    schema = _load_json_resource(_EXPERIMENT_PROFILE_SCHEMA_RESOURCE)
    try:
        profile = schema["$defs"]["profile"]
        required = profile["required"]
        properties = profile["properties"]
        collection = schema["properties"]["profiles"]
    except (KeyError, TypeError):
        raise RuntimeError("DCI experiment profile contract is invalid") from None
    if (
        set(schema)
        != {
            "$schema",
            "$id",
            "type",
            "additionalProperties",
            "required",
            "properties",
            "$defs",
        }
        or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("$id") != EXPERIMENT_PROFILE_SCHEMA
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or schema.get("required") != ["schema", "profiles"]
        or schema.get("properties", {}).get("schema")
        != {"const": EXPERIMENT_PROFILE_SCHEMA}
        or collection
        != {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {"$ref": "#/$defs/profile"},
        }
        or set(schema.get("$defs", {})) != {"profile"}
        or set(profile) != {"type", "additionalProperties", "required", "properties"}
        or profile.get("type") != "object"
        or profile.get("additionalProperties") is not False
        or type(required) is not list
        or set(required) != _PROFILE_FIELDS
        or type(properties) is not dict
        or set(properties) != _PROFILE_FIELDS
    ):
        raise RuntimeError("DCI experiment profile contract is invalid")
    return schema


@lru_cache(maxsize=1)
def _profiles() -> dict[str, ExperimentProfile]:
    _validate_profile_schema()
    payload = _load_json_resource(_EXPERIMENT_PROFILE_RESOURCES)
    profiles = payload.get("profiles")
    if (
        set(payload) != {"schema", "profiles"}
        or payload.get("schema") != EXPERIMENT_PROFILE_SCHEMA
        or type(profiles) is not list
        or len(profiles) != 5
    ):
        raise RuntimeError("DCI experiment profile contract is invalid")

    expected_scope_ids = paper_experiment_scope_ids()
    expected_scope_set = set(expected_scope_ids)
    expected_dataset_ids = tuple(paper_benchmark_ids())
    parsed: dict[str, ExperimentProfile] = {}

    for item in profiles:
        if type(item) is not dict:
            raise RuntimeError("DCI experiment profile contract is invalid")
        if set(item) != _PROFILE_FIELDS:
            raise RuntimeError("DCI experiment profile contract is invalid")

        profile_id = _require_string(item.get("profile_id"), name="profile_id")
        if profile_id not in _EXPECTED_PROFILE_IDS:
            raise RuntimeError("DCI experiment profile contract is invalid")
        if profile_id in parsed:
            raise RuntimeError("DCI experiment profile contract is invalid")

        profile_family = _require_string(item.get("profile_family"), name="profile_family")
        if profile_family not in {"current-default", "paper-reference"}:
            raise RuntimeError("DCI experiment profile contract is invalid")

        runtime_id = _require_string(item.get("runtime_id"), name="runtime_id")
        if runtime_id not in {"pi", "claude-code"}:
            raise RuntimeError("DCI experiment profile contract is invalid")

        runtime_provider = item.get("runtime_provider")
        if runtime_provider is not None and (
            type(runtime_provider) is not str or not runtime_provider
        ):
            raise RuntimeError("DCI experiment profile contract is invalid")

        runtime_model = item.get("runtime_model")
        if runtime_model is not None and (type(runtime_model) is not str or not runtime_model):
            raise RuntimeError("DCI experiment profile contract is invalid")

        runtime_model_from_invocation = item.get("runtime_model_from_invocation")
        if type(runtime_model_from_invocation) is not bool:
            raise RuntimeError("DCI experiment profile contract is invalid")

        runtime_authentication_mode = _require_string(
            item.get("runtime_authentication_mode"),
            name="runtime_authentication_mode",
        )
        if runtime_authentication_mode not in {
            "provider",
            "subscription",
            "minimax-coding-plan",
            "native",
        }:
            raise RuntimeError("DCI experiment profile contract is invalid")

        if runtime_id == "pi":
            if (
                runtime_authentication_mode != "provider"
                or runtime_provider != "openai-codex"
                or runtime_model_from_invocation
                or runtime_model is None
            ):
                raise RuntimeError("DCI experiment profile contract is invalid")
        else:
            if runtime_authentication_mode == "subscription":
                if runtime_provider is not None or runtime_model is not None:
                    raise RuntimeError("DCI experiment profile contract is invalid")
                if runtime_model_from_invocation:
                    raise RuntimeError("DCI experiment profile contract is invalid")
            elif runtime_authentication_mode == "minimax-coding-plan":
                if (
                    runtime_provider != "minimax"
                    or runtime_model != "MiniMax-M3"
                    or runtime_model_from_invocation
                ):
                    raise RuntimeError("DCI experiment profile contract is invalid")
            elif runtime_authentication_mode == "native":
                if (
                    runtime_provider not in {"anthropic", "minimax"}
                    or runtime_model is None
                    or runtime_model_from_invocation
                ):
                    raise RuntimeError("DCI experiment profile contract is invalid")

        reasoning = _require_string(item.get("reasoning"), name="reasoning")
        if reasoning not in _AF340_REASONING:
            raise RuntimeError("DCI experiment profile contract is invalid")

        tools = _require_string(item.get("tools"), name="tools")
        if "," not in tools:
            raise RuntimeError("DCI experiment profile contract is invalid")

        max_turns = _validate_positive_int(item.get("max_turns"), name="max_turns")
        if max_turns < 1:
            raise RuntimeError("DCI experiment profile contract is invalid")

        runtime_context_level = item.get("runtime_context_level")
        if runtime_context_level is not None:
            if (
                type(runtime_context_level) is not str
                or runtime_context_level not in _AF340_RUNTIME_LEVELS
            ):
                raise RuntimeError("DCI experiment profile contract is invalid")

        judge_contract = _require_string(item.get("judge_contract"), name="judge_contract")
        if not judge_contract.startswith("dci.paper-answer-judge/"):
            raise RuntimeError("DCI experiment profile contract is invalid")
        judge_api = _require_string(item.get("judge_api"), name="judge_api")
        if judge_api not in {"chat-completions", "responses"}:
            raise RuntimeError("DCI experiment profile contract is invalid")

        dataset_scope_ids = item.get("dataset_scope_ids")
        if (
            type(dataset_scope_ids) is not list
            or len(dataset_scope_ids) != 16
            or tuple(dataset_scope_ids) != expected_scope_ids
        ):
            raise RuntimeError("DCI experiment profile contract is invalid")
        for scope_id in dataset_scope_ids:
            if (
                type(scope_id) is not str
                or scope_id not in expected_scope_set
                or not scope_id
            ):
                raise RuntimeError("DCI experiment profile contract is invalid")
            resolve_paper_experiment_scope(scope_id)

        comparison_targets = item.get("comparison_targets")
        if (
            type(comparison_targets) is not dict
            or set(comparison_targets)
            != {"qa_accuracy_drop_margin", "ir_ndcg_drop_margin"}
        ):
            raise RuntimeError("DCI experiment profile contract is invalid")
        qa_accuracy_drop_margin = _validate_safe_float(
            comparison_targets.get("qa_accuracy_drop_margin"),
            name="qa_accuracy_drop_margin",
        )
        ir_ndcg_drop_margin = _validate_safe_float(
            comparison_targets.get("ir_ndcg_drop_margin"), name="ir_ndcg_drop_margin"
        )

        paper_seed_policy = _require_string(
            item.get("paper_seed_policy"), name="paper_seed_policy"
        )
        if paper_seed_policy not in {"explicit", "paper-unreported-preserved"}:
            raise RuntimeError("DCI experiment profile contract is invalid")

        dataset_scope_dataset_ids = item.get("paper_scope_dataset_ids")
        if (
            type(dataset_scope_dataset_ids) is not list
            or len(dataset_scope_dataset_ids) != 13
            or tuple(dataset_scope_dataset_ids) != expected_dataset_ids
        ):
            raise RuntimeError("DCI experiment profile contract is invalid")

        executable_if_authorized = item.get("executable_if_authorized")
        if executable_if_authorized is not True:
            raise RuntimeError("DCI experiment profile contract is invalid")
        if type(executable_if_authorized) is not bool:
            raise RuntimeError("DCI experiment profile contract is invalid")

        profile = ExperimentProfile(
            profile_id=profile_id,
            profile_family=profile_family,
            runtime_id=runtime_id,
            runtime_provider=runtime_provider,
            runtime_model=runtime_model,
            runtime_model_from_invocation=runtime_model_from_invocation,
            runtime_authentication_mode=runtime_authentication_mode,
            reasoning=reasoning,
            tools=tools,
            max_turns=max_turns,
            runtime_context_level=runtime_context_level,
            judge_contract=judge_contract,
            judge_api=judge_api,
            paper_scope_ids=tuple(dataset_scope_ids),
            comparison_targets=(
                ("qa_accuracy_drop_margin", qa_accuracy_drop_margin),
                ("ir_ndcg_drop_margin", ir_ndcg_drop_margin),
            ),
            paper_seed_policy=paper_seed_policy,
            paper_scope_dataset_ids=tuple(dataset_scope_dataset_ids),
            executable_if_authorized=executable_if_authorized,
            identity_sha256="",
        )
        parsed[profile_id] = ExperimentProfile(
            **{
                field: getattr(profile, field)
                for field in profile.__slots__
                if field != "identity_sha256"
            },
            identity_sha256=canonical_sha256(profile.to_mapping()),
        )

    for profile_id in _EXPECTED_PROFILE_IDS:
        if profile_id not in parsed:
            raise RuntimeError("DCI experiment profile contract is invalid")
    # keep canonical identity order by IDs
    return MappingProxyType({key: parsed[key] for key in _EXPECTED_PROFILE_IDS})


def experiment_profile_ids() -> tuple[str, ...]:
    return tuple(_profiles().keys())


def resolve_experiment_profile(profile_id: object) -> ExperimentProfile:
    if type(profile_id) is not str:
        raise ValueError("DCI experiment profile is invalid")
    profiles = _profiles()
    if profile_id not in profiles:
        raise ValueError("DCI experiment profile is invalid")
    return profiles[profile_id]


def experiment_profile_sha256(profile_id: object) -> str:
    return resolve_experiment_profile(profile_id).identity_sha256


def experiment_profile_schema_sha256() -> str:
    return canonical_sha256(_validate_profile_schema())


def experiment_profiles_sha256() -> str:
    return canonical_sha256(
        {
            "schema": EXPERIMENT_PROFILE_SCHEMA,
            "profiles": [
                {
                    "profile_id": profile.profile_id,
                    "identity_sha256": profile.identity_sha256,
                }
                for profile in map(_profiles().__getitem__, experiment_profile_ids())
            ],
        }
    )


def _safe_float(value: object) -> float:
    if type(value) is bool:
        raise ValueError("DCI paper full authorization record is invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("DCI paper full authorization record is invalid") from error
    if not math.isfinite(parsed):
        raise ValueError("DCI paper full authorization record is invalid")
    return parsed


def _collect_authorization_payload(
    profile: ExperimentProfile, budget_usd: float
) -> dict[str, object]:
    return {
        "schema": EXPERIMENT_AUTHORIZATION_SCHEMA,
        "profile_id": profile.profile_id,
        "profile_identity_sha256": profile.identity_sha256,
        "paper_scope_ids": list(profile.paper_scope_ids),
        "paper_benchmark_inventory_sha256": paper_benchmark_inventory_sha256(),
        "paper_experiment_scopes_sha256": paper_experiment_scopes_sha256(),
        "estimated_budget_usd": budget_usd,
        "invocation_authorized": True,
    }

def _load_authorization_record(root: Path) -> dict[str, object]:
    path = root / _AUTHORIZATION_FILE
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > 2_097_152
    ):
        raise ValueError("DCI paper full authorization cache is invalid")
    try:
        raw = path.read_text(encoding="utf-8")
        record = json.loads(raw, object_pairs_hook=_unique_object)
    except (OSError, ValueError) as error:
        raise ValueError("DCI paper full authorization cache is invalid") from error
    if (
        type(record) is not dict
        or set(record) != set(_AUTHORIZATION_FIELDS)
        or record.get("schema") != EXPERIMENT_AUTHORIZATION_SCHEMA
        or type(record.get("profile_id")) is not str
        or type(record.get("profile_identity_sha256")) is not str
        or type(record.get("paper_scope_ids")) is not list
        or type(record.get("paper_benchmark_inventory_sha256")) is not str
        or type(record.get("paper_experiment_scopes_sha256")) is not str
        or type(record.get("estimated_budget_usd")) not in {int, float}
        or type(record.get("invocation_authorized")) is not bool
    ):
        raise ValueError("DCI paper full authorization cache is invalid")
    return record


def _prepare_output_root(path: Path) -> Path:
    path = _normalize_output_root(path)
    if path.exists():
        raise ValueError("DCI paper full output root is invalid")
    path.mkdir(parents=True, mode=0o700)
    path.chmod(0o700)
    return path


def authorize_full_execution(
    profile_id: str,
    output_root: Path,
    estimated_budget_usd: float,
    invocation_authorized: bool,
) -> FullExecutionAuthorization:
    if invocation_authorized is not True:
        raise ValueError("DCI paper full execution is not authorized")

    profile = resolve_experiment_profile(profile_id)
    budget = _validate_safe_float(estimated_budget_usd, name="estimated_budget_usd")
    output = _prepare_output_root(output_root)
    payload = _collect_authorization_payload(profile, budget)

    cache = output / _AUTHORIZATION_FILE
    descriptor = os.open(cache, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")

    return FullExecutionAuthorization(
        profile_id=profile.profile_id,
        output_root=output,
        estimated_budget_usd=budget,
        invocation_authorized=True,
    )


def validate_full_execution_authorization(
    authorization: object,
    *,
    scope_id: str,
) -> FullExecutionAuthorization:
    """Validate one invocation-bound authorization against its private record."""

    if type(authorization) is not FullExecutionAuthorization:
        raise ValueError("DCI paper full execution authorization is invalid")
    if authorization.invocation_authorized is not True:
        raise ValueError("DCI paper full execution authorization is invalid")
    profile = resolve_experiment_profile(authorization.profile_id)
    if scope_id not in profile.paper_scope_ids:
        raise ValueError("DCI paper full execution authorization is invalid")
    budget = _validate_safe_float(
        authorization.estimated_budget_usd,
        name="estimated_budget_usd",
    )
    output = _normalize_output_root(authorization.output_root)
    try:
        output_metadata = output.lstat()
        record_path = output / _AUTHORIZATION_FILE
        record_metadata = record_path.lstat()
    except OSError as error:
        raise ValueError("DCI paper full execution authorization is invalid") from error
    if (
        output != authorization.output_root
        or output.is_symlink()
        or not stat.S_ISDIR(output_metadata.st_mode)
        or stat.S_IMODE(output_metadata.st_mode) != 0o700
        or record_path.is_symlink()
        or not stat.S_ISREG(record_metadata.st_mode)
        or stat.S_IMODE(record_metadata.st_mode) != 0o600
    ):
        raise ValueError("DCI paper full execution authorization is invalid")
    record = _load_authorization_record(output)
    expected = _collect_authorization_payload(profile, budget)
    if record != expected:
        raise ValueError("DCI paper full execution authorization is invalid")
    return authorization


def full_execution_authorization_identity(
    authorization: object,
    *,
    scope_id: str,
) -> dict[str, object]:
    """Return the path-free authorization identity included in batch fingerprints."""

    validated = validate_full_execution_authorization(
        authorization,
        scope_id=scope_id,
    )
    profile = resolve_experiment_profile(validated.profile_id)
    return {
        "schema": EXPERIMENT_AUTHORIZATION_SCHEMA,
        "profile_id": profile.profile_id,
        "profile_identity_sha256": profile.identity_sha256,
        "experiment_profiles_sha256": experiment_profiles_sha256(),
        "paper_benchmark_inventory_sha256": paper_benchmark_inventory_sha256(),
        "paper_experiment_scopes_sha256": paper_experiment_scopes_sha256(),
        "estimated_budget_usd": validated.estimated_budget_usd,
    }
