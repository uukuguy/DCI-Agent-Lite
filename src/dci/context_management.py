"""Original DCI-owned live context profiles, extension, and model-free hooks."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


CONTRACT_VERSION = "dci.context-profile/v1"
_NAMES = ("level0", "level1", "level2", "level3", "level4")
_EXPECTED = {
    "level0": (None, None, None, None, None),
    "level1": (50_000, None, None, None, None),
    "level2": (20_000, None, None, None, None),
    "level3": (20_000, 240_000, 12, None, None),
    "level4": (20_000, 240_000, 12, 20_000, 3),
}


@dataclass(frozen=True)
class ContextProfile:
    name: str
    tool_result_character_cap: int | None
    compaction_character_trigger: int | None
    retained_turns: int | None
    summary_recent_token_target: int | None
    summary_failure_limit: int | None
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class ContextExtension:
    path: Path
    manifest_path: Path
    version: str
    contract_version: str
    sha256: str


def context_profile_names() -> tuple[str, ...]:
    _profiles()
    return _NAMES


def resolve_context_profile(value: object) -> ContextProfile:
    if not isinstance(value, str) or value not in _NAMES:
        raise ValueError("Original DCI context profile is invalid")
    return _profiles()[value]


def _profiles() -> Mapping[str, ContextProfile]:
    try:
        payload = json.loads(
            resources.files("dci.resources").joinpath("context-profiles.json").read_text(
                encoding="utf-8"
            )
        )
        values = payload["profiles"]
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Original DCI context profile resource is invalid") from exc
    if payload.get("schema") != CONTRACT_VERSION or tuple(values) != _NAMES:
        raise RuntimeError("Original DCI context profile resource is invalid")
    parsed = {}
    for name, expected in _EXPECTED.items():
        value = values[name]
        actual = (
            value.get("tool_result_character_cap"),
            value.get("compaction_character_trigger"),
            value.get("retained_turns"),
            value.get("summary_recent_token_target"),
            value.get("summary_failure_limit"),
        )
        if value.get("profile") != name or value.get("contract_version") != CONTRACT_VERSION or actual != expected:
            raise RuntimeError("Original DCI context profile resource is invalid")
        parsed[name] = ContextProfile(name, *expected)
    return MappingProxyType(parsed)


def resolve_context_extension() -> ContextExtension:
    package = resources.files("dci.resources.pi")
    manifest_path = Path(str(package.joinpath("context-extension-manifest.json")))
    source_path = Path(str(package.joinpath("dci-context-extension.ts")))
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = source_path.read_bytes()
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Original DCI context extension is invalid") from exc
    digest = hashlib.sha256(source).hexdigest()
    if (
        set(manifest) != {"schema", "extension_version", "contract_version", "resource", "byte_length", "sha256"}
        or manifest.get("schema") != "dci.context-extension-manifest/v1"
        or manifest.get("contract_version") != CONTRACT_VERSION
        or manifest.get("resource") != source_path.name
        or manifest.get("byte_length") != len(source)
        or manifest.get("sha256") != digest
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        raise RuntimeError("Original DCI context extension is invalid")
    return ContextExtension(
        path=source_path,
        manifest_path=manifest_path,
        version=manifest["extension_version"],
        contract_version=manifest["contract_version"],
        sha256=digest,
    )


class ModelFreeContextPolicy:
    """Deterministic mirror of the shipped extension's body-free state transitions."""

    def __init__(self, profile: ContextProfile) -> None:
        self.profile = profile
        self.extension = resolve_context_extension()
        self.accumulated_characters = 0
        self.compactions = 0
        self.compaction_pending = False
        self.summary_attempts = 0
        self.summary_successes = 0
        self.consecutive_summary_failures = 0
        self.summary_suppressed = False
        self.telemetry: list[dict[str, object]] = []
        self._emit("startup")

    def _emit(self, event: str) -> None:
        self.telemetry.append({"schema": "dci.context-telemetry/v1", "event": event, **self.public_counters()})

    def tool_result(self, text: str) -> str:
        self.accumulated_characters += len(text)
        trigger = self.profile.compaction_character_trigger
        self.compaction_pending = trigger is not None and self.accumulated_characters > trigger
        self._emit("tool_result")
        cap = self.profile.tool_result_character_cap
        return text if cap is None or len(text) <= cap else text[:cap]

    def compact(self, *, summary_succeeded: bool | None) -> None:
        if not self.compaction_pending:
            raise ValueError("Original DCI compaction is not pending")
        if self.profile.name == "level4" and not self.summary_suppressed:
            if type(summary_succeeded) is not bool:
                raise ValueError("Original DCI summary result is required")
            self.summary_attempts += 1
            if summary_succeeded:
                self.summary_successes += 1
                self.consecutive_summary_failures = 0
            else:
                self.consecutive_summary_failures += 1
                self.summary_suppressed = self.consecutive_summary_failures >= 3
        self.compactions += 1
        self.accumulated_characters = 0
        self.compaction_pending = False
        self._emit("compaction_complete")

    def visible_turn_count(self, turns: int) -> int:
        retained = self.profile.retained_turns
        return turns if retained is None else min(turns, retained)

    def public_counters(self) -> dict[str, object]:
        return {
            "profile": self.profile.name,
            "compactions": self.compactions,
            "summary_attempts": self.summary_attempts,
            "summary_successes": self.summary_successes,
            "summary_suppressed": self.summary_suppressed,
            "extension_sha256": self.extension.sha256,
        }

    def snapshot(self) -> dict[str, object]:
        return {
            **self.public_counters(),
            "accumulated_characters": self.accumulated_characters,
            "compaction_pending": self.compaction_pending,
            "consecutive_summary_failures": self.consecutive_summary_failures,
            "telemetry": list(self.telemetry),
        }

    @classmethod
    def resume(cls, profile: ContextProfile, state: Mapping[str, object]) -> "ModelFreeContextPolicy":
        policy = cls(profile)
        if state.get("profile") != profile.name or state.get("extension_sha256") != policy.extension.sha256:
            raise ValueError("Original DCI context resume evidence is invalid")
        try:
            policy.accumulated_characters = int(state["accumulated_characters"])
            policy.compactions = int(state["compactions"])
            policy.compaction_pending = bool(state["compaction_pending"])
            policy.summary_attempts = int(state["summary_attempts"])
            policy.summary_successes = int(state["summary_successes"])
            policy.consecutive_summary_failures = int(state["consecutive_summary_failures"])
            policy.summary_suppressed = bool(state["summary_suppressed"])
            policy.telemetry = list(state["telemetry"]) + [{"schema": "dci.context-telemetry/v1", "event": "resume", **policy.public_counters()}]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Original DCI context resume evidence is invalid") from exc
        return policy
