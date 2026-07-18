"""Immutable AF-340 experiment identities and full-execution authorization."""

from __future__ import annotations

import json
import math
import os
import re
import stat
from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from asterion.dci.paper_benchmarks import (
    canonical_sha256,
    paper_benchmark_inventory_sha256,
    paper_experiment_scope_ids,
    paper_experiment_scopes_sha256,
    resolve_paper_experiment_scope,
)

EXPERIMENT_PROFILE_SCHEMA = "dci.experiment-profiles/v1"
_PROFILE_IDS = (
    "current-default/pi",
    "current-default/claude-subscription",
    "current-default/claude-minimax",
    "paper-reference/pi",
    "paper-reference/claude-code",
)
_PUBLIC_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]*")
_EXPECTED_PROFILE_SEMANTICS = {
    "current-default/pi": ("pi", "openai-codex", "gpt-5.6-luna", "saved-auth-or-provider-key", None, "read,bash", 100, "deepseek-v4-flash"),
    "current-default/claude-subscription": ("claude-code", None, None, "local-subscription", None, "read,grep", 100, "deepseek-v4-flash"),
    "current-default/claude-minimax": ("claude-code", None, None, "invocation-minimax-coding-plan", None, "read,grep", 100, "deepseek-v4-flash"),
    "paper-reference/pi": ("pi", "openai", "gpt-5.4-nano", "saved-auth-or-provider-key", "high", "read,bash", 300, "gpt-4.1"),
    "paper-reference/claude-code": ("claude-code", None, "claude-sonnet-4-6", "local-subscription", "medium", "read,grep", 300, "gpt-4.1"),
}
_CURRENT_JUDGE = {
    "base_url": "https://api.deepseek.com/v1", "api": "chat-completions",
    "model": "deepseek-v4-flash", "thinking": False, "json_object": True,
    "prompt_contract": "dci.answer-judge/v1",
}
_PAPER_JUDGE = {
    "base_url": "https://api.openai.com/v1", "api": "responses",
    "model": "gpt-4.1", "thinking": False, "json_object": True,
    "prompt_contract": "dci.paper-answer-judge/gpt-4.1/v1",
}


@dataclass(frozen=True, slots=True)
class ExperimentProfile:
    profile_id: str
    runtime: str
    provider: str | None
    model: str | None
    authentication_mode: str
    reasoning: str | None
    tools: str
    max_turns: int
    context_profile: str
    judge: Mapping[str, object]
    dataset_inventory_sha256: str
    experiment_scopes_sha256: str
    scope_ids: tuple[str, ...]
    selected_ids_sha256: tuple[str, ...]
    paper_unreported_scope_ids: tuple[str, ...]
    corpus_identity: str
    metric_identities: tuple[str, ...]
    aggregation_identity: str
    comparison: Mapping[str, object]

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "runtime": self.runtime,
            "provider": self.provider,
            "model": self.model,
            "authentication_mode": self.authentication_mode,
            "reasoning": self.reasoning,
            "tools": self.tools,
            "max_turns": self.max_turns,
            "context_profile": self.context_profile,
            "judge": dict(self.judge),
            "dataset_inventory_sha256": self.dataset_inventory_sha256,
            "experiment_scopes_sha256": self.experiment_scopes_sha256,
            "scope_ids": list(self.scope_ids),
            "selected_ids_sha256": list(self.selected_ids_sha256),
            "paper_unreported_scope_ids": list(self.paper_unreported_scope_ids),
            "corpus_identity": self.corpus_identity,
            "metric_identities": list(self.metric_identities),
            "aggregation_identity": self.aggregation_identity,
            "comparison": dict(self.comparison),
        }


@dataclass(frozen=True, slots=True)
class FullExecutionAuthorization:
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


@lru_cache(maxsize=1)
def _profiles() -> Mapping[str, ExperimentProfile]:
    try:
        package = resources.files("asterion.dci.resources")
        payload = json.loads(package.joinpath("experiment-profiles.json").read_text(), object_pairs_hook=_unique_object)
        schema = json.loads(package.joinpath("experiment-profile.schema.json").read_text(), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError):
        raise RuntimeError("DCI experiment profile contract is invalid") from None
    if (type(payload) is not dict or set(payload) != {"schema", "profiles"}
            or payload.get("schema") != EXPERIMENT_PROFILE_SCHEMA
            or type(payload.get("profiles")) is not list
            or type(schema) is not dict or schema.get("$id") != EXPERIMENT_PROFILE_SCHEMA
            or schema.get("additionalProperties") is not False):
        raise RuntimeError("DCI experiment profile contract is invalid")

    scope_ids = paper_experiment_scope_ids()
    selected = tuple(resolve_paper_experiment_scope(scope_id).selected_ids_sha256 for scope_id in scope_ids)
    unreported = tuple(scope_id for scope_id in scope_ids if resolve_paper_experiment_scope(scope_id).selection_seed_status == "paper-unreported")
    fields = {"profile_id", "runtime", "provider", "model", "authentication_mode", "reasoning", "tools", "max_turns", "context_profile", "judge", "dataset_inventory_sha256", "experiment_scopes_sha256", "scope_ids", "selected_ids_sha256", "paper_unreported_scope_ids", "corpus_identity", "metric_identities", "aggregation_identity", "comparison"}
    parsed: dict[str, ExperimentProfile] = {}
    for item in payload["profiles"]:
        if type(item) is not dict or set(item) != fields:
            raise RuntimeError("DCI experiment profile contract is invalid")
        profile_id, judge = item["profile_id"], item["judge"]
        if (type(profile_id) is not str or profile_id in parsed or type(judge) is not dict
                or item["dataset_inventory_sha256"] != paper_benchmark_inventory_sha256()
                or item["experiment_scopes_sha256"] != paper_experiment_scopes_sha256()
                or item["scope_ids"] != list(scope_ids)
                or item["selected_ids_sha256"] != list(selected)
                or item["paper_unreported_scope_ids"] != list(unreported)
                or type(item["max_turns"]) is not int or item["max_turns"] <= 0
                or item["context_profile"] != "level3"):
            raise RuntimeError("DCI experiment profile contract is invalid")
        parsed[profile_id] = ExperimentProfile(
            profile_id=profile_id, runtime=item["runtime"], provider=item["provider"], model=item["model"],
            authentication_mode=item["authentication_mode"], reasoning=item["reasoning"], tools=item["tools"],
            max_turns=item["max_turns"], context_profile=item["context_profile"], judge=MappingProxyType(dict(judge)),
            dataset_inventory_sha256=item["dataset_inventory_sha256"], experiment_scopes_sha256=item["experiment_scopes_sha256"],
            scope_ids=scope_ids, selected_ids_sha256=selected, paper_unreported_scope_ids=unreported,
            corpus_identity=item["corpus_identity"], metric_identities=tuple(item["metric_identities"]),
            aggregation_identity=item["aggregation_identity"], comparison=MappingProxyType(dict(item["comparison"])),
        )
    if tuple(parsed) != _PROFILE_IDS:
        raise RuntimeError("DCI experiment profile contract is invalid")
    for name, expected in _EXPECTED_PROFILE_SEMANTICS.items():
        profile = parsed[name]
        actual = (
            profile.runtime, profile.provider, profile.model,
            profile.authentication_mode, profile.reasoning, profile.tools,
            profile.max_turns, profile.judge.get("model"),
        )
        if actual != expected:
            raise RuntimeError("DCI experiment profile contract is invalid")
        expected_judge = _PAPER_JUDGE if name.startswith("paper-reference/") else _CURRENT_JUDGE
        if (
            dict(profile.judge) != expected_judge
            or profile.corpus_identity != "dci.paper-corpora/af-320-v1"
            or profile.metric_identities
            != ("llm-answer-correctness", "ndcg@10-binary-deduplicated")
            or profile.aggregation_identity
            != "dci.paper-aggregation/query-preserving/v1"
        ):
            raise RuntimeError("DCI experiment profile contract is invalid")
    return MappingProxyType(parsed)


def experiment_profile_ids() -> tuple[str, ...]:
    return tuple(_profiles())


def resolve_experiment_profile(profile_id: object, *, invocation_provider: str | None = None, invocation_model: str | None = None) -> ExperimentProfile:
    if type(profile_id) is not str or profile_id not in _profiles():
        raise ValueError("DCI experiment profile is invalid")
    profile = _profiles()[profile_id]
    if profile_id != "current-default/claude-minimax":
        if invocation_provider is not None or invocation_model is not None:
            raise ValueError("DCI experiment profile invocation identity is invalid")
        return profile
    if invocation_provider not in {"minimax", "minimax-cn"} or type(invocation_model) is not str or _PUBLIC_IDENTITY.fullmatch(invocation_model) is None:
        raise ValueError("DCI MiniMax invocation identity is required")
    return replace(profile, provider=invocation_provider, model=invocation_model)


def experiment_profile_sha256(profile_id: str, *, invocation_provider: str | None = None, invocation_model: str | None = None) -> str:
    profile = resolve_experiment_profile(profile_id, invocation_provider=invocation_provider, invocation_model=invocation_model)
    return canonical_sha256(profile.to_canonical_dict())


def _fresh_private_output_root(output_root: Path) -> Path:
    requested = Path(os.path.abspath(os.path.normpath(Path(output_root).expanduser())))
    if requested.is_symlink():
        raise ValueError("DCI full output root must not be a symlink")
    absolute = requested.parent.resolve() / requested.name
    if absolute.exists():
        raise ValueError("DCI full output root must be fresh")
    absolute.mkdir(parents=True, mode=0o700)
    absolute.chmod(0o700)
    if stat.S_IMODE(absolute.stat().st_mode) != 0o700:
        raise ValueError("DCI full output root must be private")
    return absolute


def authorize_full_execution(profile_id: str, output_root: Path, estimated_budget_usd: float, invocation_authorized: bool, *, invocation_provider: str | None = None, invocation_model: str | None = None, preflight_scope_ids: Sequence[str] | None = None, preflight_selected_ids_sha256: Sequence[str] | None = None, cache_only: bool = False) -> FullExecutionAuthorization:
    profile = resolve_experiment_profile(profile_id, invocation_provider=invocation_provider, invocation_model=invocation_model)
    if invocation_authorized is not True:
        raise ValueError("DCI full execution requires invocation authorization")
    if isinstance(estimated_budget_usd, bool) or not isinstance(estimated_budget_usd, (int, float)) or not math.isfinite(float(estimated_budget_usd)) or float(estimated_budget_usd) < 0:
        raise ValueError("DCI full execution budget is invalid")
    if cache_only:
        raise ValueError("DCI full execution cannot be authorized by cache evidence")
    if preflight_scope_ids is not None and tuple(preflight_scope_ids) != profile.scope_ids:
        raise ValueError("DCI full execution preflight scope mismatch")
    if preflight_selected_ids_sha256 is not None and tuple(preflight_selected_ids_sha256) != profile.selected_ids_sha256:
        raise ValueError("DCI full execution preflight selection mismatch")
    private_root = _fresh_private_output_root(output_root)
    return FullExecutionAuthorization(profile.profile_id, private_root, float(estimated_budget_usd), True)
