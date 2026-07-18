#!/usr/bin/env python3
"""
Run one BrowseComp-style prompt against pi in RPC mode.

This variant is optimized for experiments:
- stream assistant text live
- optionally print tool boundaries to stderr
- append every raw RPC event to `events.jsonl`
- rewrite `state.json` after each event for real-time inspection
- rewrite `conversation.json` after each event for a cleaner transcript
- save the final answer to `final.txt`
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dci.benchmark.judge import (
    DEFAULT_JUDGE_CACHED_INPUT_PRICE_PER_1M,
    DEFAULT_JUDGE_INPUT_PRICE_PER_1M,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_JUDGE_OUTPUT_PRICE_PER_1M,
    JudgeConfig,
    judge_answer_sync,
    judge_request_fingerprint,
)
from dci.config import (
    ConfigLayers,
    OriginalRuntimeConfig,
    resolve_original_runtime,
    resolve_pi_paths,
)
from dci.effective_config import OriginalEffectiveConfig
from dci.framework.adapters.pi import PiProtocolAdapter, map_pi_capabilities
from dci.framework.protocol import (
    MAX_DEADLINE_MS,
    PROTOCOL_VERSION,
    validate_event_stream,
    validate_run_request,
)


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_RUNS_DIR = REPO_ROOT / "outputs" / "runs"
DEFAULT_EVAL_JUDGE_MODEL = DEFAULT_JUDGE_MODEL
DEFAULT_EVAL_INPUT_PRICE_PER_1M = DEFAULT_JUDGE_INPUT_PRICE_PER_1M
DEFAULT_EVAL_CACHED_INPUT_PRICE_PER_1M = DEFAULT_JUDGE_CACHED_INPUT_PRICE_PER_1M
DEFAULT_EVAL_OUTPUT_PRICE_PER_1M = DEFAULT_JUDGE_OUTPUT_PRICE_PER_1M
DEFAULT_RPC_TIMEOUT_SECONDS = 3600.0
_RPC_STDOUT_EOF = object()


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def _node_bin() -> str:
    """Return path to node >=20, preferring nvm-installed versions over the system default."""
    nvm_dir = Path(os.environ.get("NVM_DIR", Path.home() / ".nvm"))
    versions_dir = nvm_dir / "versions" / "node"
    if versions_dir.is_dir():
        candidates = sorted(
            (d for d in versions_dir.iterdir() if d.name.startswith("v")),
            key=lambda d: tuple(int(x) for x in d.name.lstrip("v").split(".")),
            reverse=True,
        )
        for candidate in candidates:
            major = int(candidate.name.lstrip("v").split(".")[0])
            node = candidate / "bin" / "node"
            if major >= 20 and node.exists():
                return str(node)
    return "node"


def _node_env(base: dict) -> dict:
    """Return a copy of *base* with PATH prepended to include the node >=20 bin dir."""
    node = _node_bin()
    if node == "node":
        return base
    env = base.copy()
    bin_dir = str(Path(node).parent)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    return env


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def read_text_if_exists(path: Optional[Path]) -> Optional[str]:
    if not path:
        return None
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def resolve_repo_relative_path(path: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    if path.is_absolute():
        return path.resolve()

    cwd_candidate = path.resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    return (REPO_ROOT / path).resolve()


def read_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def is_directory_empty(path: Path) -> bool:
    if not path.exists():
        return True
    return not any(path.iterdir())


def build_default_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return DEFAULT_RUNS_DIR / stamp


def clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def sanitize_path_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "item"


def count_text_stats(text: str) -> Dict[str, int]:
    return {
        "chars": len(text),
        "lines": text.count("\n") + (1 if text else 0),
    }


def parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def seconds_between(start: Optional[str], end: Optional[str]) -> Optional[float]:
    start_dt = parse_iso8601(start)
    end_dt = parse_iso8601(end)
    if start_dt is None or end_dt is None:
        return None
    return max(0.0, (end_dt - start_dt).total_seconds())


def expand_extra_args(values: List[str]) -> List[str]:
    expanded: List[str] = []
    for value in values:
        parts = shlex.split(value)
        if parts:
            expanded.extend(parts)
    return expanded


def ensure_built_pi_cli(package_dir: Path) -> Path:
    dist_cli = package_dir / "dist" / "cli.js"
    if dist_cli.exists():
        return dist_cli

    pi_repo_root = package_dir.parents[1]
    sys.stderr.write("[setup] dist/cli.js not found, running `npm run build` at monorepo root\n")
    sys.stderr.flush()
    subprocess.run(
        ["npm", "run", "build"],
        cwd=str(pi_repo_root),
        env=_node_env(os.environ.copy()),
        check=True,
    )
    if not dist_cli.exists():
        raise RuntimeError(f"Build completed but CLI was not found at {dist_cli}")
    return dist_cli


def build_pi_command(
    *,
    package_dir: Path,
    mode: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    tools: Optional[str],
    no_session: bool,
    system_prompt_file: Optional[Path],
    append_system_prompt_file: Optional[Path],
    extra_args: List[str],
    messages: Optional[List[str]] = None,
) -> List[str]:
    dist_cli = ensure_built_pi_cli(package_dir)
    cmd = [_node_bin(), str(dist_cli)]
    if mode:
        cmd.extend(["--mode", mode])

    if provider:
        cmd.extend(["--provider", provider])
    if model:
        cmd.extend(["--model", model])
    if tools:
        cmd.extend(["--tools", tools])
    if system_prompt_file:
        cmd.extend(["--system-prompt", str(system_prompt_file)])
    if append_system_prompt_file:
        cmd.extend(["--append-system-prompt", str(append_system_prompt_file)])
    if no_session:
        cmd.append("--no-session")
    cmd.extend(extra_args)
    if messages:
        cmd.extend(messages)
    return cmd


def load_eval_answer(
    *,
    eval_answer: Optional[str],
    eval_answer_file: Optional[Path],
) -> Optional[str]:
    if eval_answer_file:
        return eval_answer_file.read_text(encoding="utf-8").strip()
    if eval_answer:
        return eval_answer.strip()
    return None


def maybe_reuse_existing_eval(
    *,
    eval_result_path: Path,
    judge_config: JudgeConfig,
    question: str,
    gold_answer: str,
    predicted_answer: str,
) -> Optional[Dict[str, Any]]:
    existing = read_json_if_exists(eval_result_path)
    if not existing:
        return None
    current_fingerprint = judge_request_fingerprint(
        config=judge_config,
        question=question,
        gold_answer=gold_answer,
        predicted_answer=predicted_answer,
    )
    if existing.get("judge_request_fingerprint") != current_fingerprint:
        return None
    if not isinstance(existing.get("is_correct"), bool):
        return None
    return existing


def evaluate_run_output(
    *,
    output_dir: Path,
    question: str,
    gold_answer: str,
    predicted_answer: str,
    judge_config: JudgeConfig,
) -> Dict[str, Any]:
    eval_result_path = output_dir / "eval_result.json"

    def persist_eval_summary(eval_result: Dict[str, Any]) -> None:
        state_path = output_dir / "state.json"
        state = read_json_if_exists(state_path)
        if state is None:
            return
        state["evaluation"] = {
            "judge_model": eval_result.get("judge_model"),
            "judge_base_url": eval_result.get("judge_base_url"),
            "judge_api": eval_result.get("judge_api"),
            "judged_at": eval_result.get("judged_at"),
            "is_correct": eval_result.get("is_correct"),
            "normalized_prediction": eval_result.get("normalized_prediction"),
            "reason": eval_result.get("reason"),
            "cost_estimate_usd": eval_result.get("cost_estimate_usd"),
        }
        write_json(state_path, state)

    reusable = maybe_reuse_existing_eval(
        eval_result_path=eval_result_path,
        judge_config=judge_config,
        question=question,
        gold_answer=gold_answer,
        predicted_answer=predicted_answer,
    )
    if reusable is not None:
        persist_eval_summary(reusable)
        return reusable

    eval_result = judge_answer_sync(
        config=judge_config,
        question=question,
        gold_answer=gold_answer,
        predicted_answer=predicted_answer,
    )
    write_json(eval_result_path, eval_result)
    persist_eval_summary(eval_result)
    return eval_result


def collect_pi_source_provenance(
    *,
    package_dir: Path,
    lock_file: Path,
    revision_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Describe the Git source backing a Pi coding-agent package."""

    def git_output(*args: str) -> Optional[str]:
        result = subprocess.run(
            ["git", "-C", str(package_dir), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    lock_revision = None
    if lock_file.is_file():
        candidate = lock_file.read_text(encoding="utf-8").strip()
        if candidate:
            lock_revision = candidate

    repo_dir = git_output("rev-parse", "--show-toplevel")
    commit = git_output("rev-parse", "HEAD") if repo_dir else None
    status = git_output("status", "--porcelain") if repo_dir else None
    origin_url = git_output("remote", "get-url", "origin") if repo_dir else None
    expected_revision = revision_override or lock_revision
    expected_revision_source = "DCI_PI_REVISION" if revision_override else "pi-revision.txt"
    return {
        "managed_git_checkout": repo_dir is not None,
        "repo_dir": repo_dir,
        "origin_url": origin_url,
        "commit": commit,
        "dirty": bool(status) if status is not None else None,
        "lock_file": str(lock_file),
        "lock_revision": lock_revision,
        "lock_match": commit == lock_revision if commit and lock_revision else None,
        "expected_revision": expected_revision,
        "expected_revision_source": expected_revision_source,
        "expected_match": (
            commit == expected_revision if commit and expected_revision else None
        ),
    }


def format_pi_source_warning(provenance: Dict[str, Any]) -> Optional[str]:
    """Return a non-blocking pre-run warning for an expected revision mismatch."""

    if provenance.get("expected_match") is not False:
        return None
    return (
        "Pi source warning: actual commit "
        f"{provenance.get('commit')} does not match expected revision "
        f"{provenance.get('expected_revision')} from "
        f"{provenance.get('expected_revision_source')}; continuing with recorded provenance."
    )


def emit_pi_source_warning(recorder: Any, *, stream: Any = sys.stderr) -> Optional[str]:
    """Emit and persist a non-blocking source mismatch warning."""

    warning = format_pi_source_warning(recorder.pi_source)
    if warning is None:
        return None
    recorder.add_note(warning)
    print(f"[runner] WARNING: {warning}", file=stream)
    return warning


class ConversationFeatures:
    def __init__(
        self,
        *,
        clear_tool_results: bool,
        clear_tool_results_keep_last: int,
        externalize_tool_results: bool,
        strip_thinking: bool,
        strip_usage: bool,
    ) -> None:
        self.clear_tool_results = clear_tool_results
        self.clear_tool_results_keep_last = clear_tool_results_keep_last
        self.externalize_tool_results = externalize_tool_results
        self.strip_thinking = strip_thinking
        self.strip_usage = strip_usage

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "ConversationFeatures":
        keep_last = int(args.conversation_clear_tool_results_keep_last)
        if keep_last < 0:
            raise RuntimeError("--conversation-clear-tool-results-keep-last must be >= 0")
        return cls(
            clear_tool_results=bool(args.conversation_clear_tool_results),
            clear_tool_results_keep_last=keep_last,
            externalize_tool_results=bool(args.conversation_externalize_tool_results),
            strip_thinking=bool(args.conversation_strip_thinking),
            strip_usage=bool(args.conversation_strip_usage),
        )

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "ConversationFeatures":
        data = payload or {}
        return cls(
            clear_tool_results=bool(data.get("clear_tool_results", False)),
            clear_tool_results_keep_last=int(data.get("clear_tool_results_keep_last", 3)),
            externalize_tool_results=bool(data.get("externalize_tool_results", False)),
            strip_thinking=bool(data.get("strip_thinking", False)),
            strip_usage=bool(data.get("strip_usage", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clear_tool_results": self.clear_tool_results,
            "clear_tool_results_keep_last": self.clear_tool_results_keep_last,
            "externalize_tool_results": self.externalize_tool_results,
            "strip_thinking": self.strip_thinking,
            "strip_usage": self.strip_usage,
        }

    def enabled_feature_names(self) -> List[str]:
        names: List[str] = []
        if self.clear_tool_results:
            names.append("clear_tool_results")
        if self.externalize_tool_results:
            names.append("externalize_tool_results")
        if self.strip_thinking:
            names.append("strip_thinking")
        if self.strip_usage:
            names.append("strip_usage")
        return names


class RunRecorder:
    def __init__(
        self,
        *,
        output_dir: Path,
        question: str,
        package_dir: Path,
        agent_dir: Path,
        cwd: Path,
        provider: Optional[str],
        model: Optional[str],
        tools: Optional[str],
        max_turns: Optional[int],
        rpc_timeout_seconds: Optional[float],
        system_prompt_file: Optional[Path],
        append_system_prompt_file: Optional[Path],
        conversation_features: ConversationFeatures,
        keep_session: bool,
        resume: bool,
    ) -> None:
        self.output_dir = output_dir
        self.resume = resume
        self.conversation_features = conversation_features
        self.pi_source = collect_pi_source_provenance(
            package_dir=package_dir,
            lock_file=REPO_ROOT / "pi-revision.txt",
            revision_override=os.environ.get("DCI_PI_REVISION") or None,
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._pending_tool_call_starts: Dict[str, str] = {}
        self._completed_tool_call_timings: Dict[str, Dict[str, Any]] = {}

        self.events_path = self.output_dir / "events.jsonl"
        self.state_path = self.output_dir / "state.json"
        self.conversation_full_path = self.output_dir / "conversation_full.json"
        self.conversation_path = self.output_dir / "conversation.json"
        self.latest_model_context_path = self.output_dir / "latest_model_context.json"
        self.final_path = self.output_dir / "final.txt"
        self.stderr_path = self.output_dir / "stderr.txt"
        self.question_path = self.output_dir / "question.txt"
        self.tool_results_dir = self.output_dir / "tool_results"
        self.protocol_dir = self.output_dir / "protocol"
        self._protocol_events: List[Dict[str, Any]] = []

        if resume:
            self.state = self._load_existing_state()
            self.conversation_full = self._load_existing_conversation_full()
            self.latest_model_context = self._load_existing_latest_model_context()
            self._validate_resume_inputs(
                question=question,
                package_dir=package_dir,
                agent_dir=agent_dir,
                cwd=cwd,
                provider=provider,
                model=model,
                tools=tools,
                max_turns=max_turns,
                system_prompt_file=system_prompt_file,
                append_system_prompt_file=append_system_prompt_file,
                conversation_features=conversation_features,
                keep_session=keep_session,
            )
            self.question_path.write_text(question + "\n", encoding="utf-8")
            self.state["status"] = "running"
            self.state["finished_at"] = None
            self.state["error"] = None
            self.state["keep_session"] = keep_session
            self.state["rpc_timeout_seconds"] = rpc_timeout_seconds
            self.state["conversation_features"] = self.conversation_features.to_dict()
            self.state["resume_count"] = int(self.state.get("resume_count", 0)) + 1
            self.conversation_full["status"] = "running"
            self.conversation_full["finished_at"] = None
            self.conversation_full["error"] = None
            self.conversation_full["keep_session"] = keep_session
            self.conversation_full["rpc_timeout_seconds"] = rpc_timeout_seconds
            self.conversation_full["conversation_features"] = self.conversation_features.to_dict()
            self.conversation_full["pending_message"] = None
            self.conversation_full["final_text"] = None
            self.latest_model_context["status"] = "running"
            self.latest_model_context["finished_at"] = None
            self.latest_model_context["error"] = None
            self.latest_model_context["rpc_timeout_seconds"] = rpc_timeout_seconds
            self.latest_model_context["runtime_context_management"] = self.latest_model_context.get(
                "runtime_context_management"
            )
            self.add_note("Resumed run in existing output directory.")
            if not keep_session:
                self.add_note(
                    "Resume is reusing the artifact directory only; agent session continuity is not preserved without --keep-session."
                )
        else:
            self.question_path.write_text(question + "\n", encoding="utf-8")
            self.state = {
                "started_at": utc_now(),
                "finished_at": None,
                "status": "running",
                "question": question,
                "package_dir": str(package_dir),
                "agent_dir": str(agent_dir),
                "cwd": str(cwd),
                "provider": provider,
                "model": model,
                "tools": tools,
                "max_turns": max_turns,
                "rpc_timeout_seconds": rpc_timeout_seconds,
                "system_prompt_file": str(system_prompt_file) if system_prompt_file else None,
                "append_system_prompt_file": str(append_system_prompt_file) if append_system_prompt_file else None,
                "conversation_features": self.conversation_features.to_dict(),
                "keep_session": keep_session,
                "resume_count": 0,
                "event_count": 0,
                "turn_count": 0,
                "assistant_text": "",
                "last_event_type": None,
                "messages": [],
                "tool_calls": [],
                "notes": [],
                "paths": {
                    "output_dir": str(self.output_dir),
                    "events_jsonl": str(self.events_path),
                    "state_json": str(self.state_path),
                    "conversation_full_json": str(self.conversation_full_path),
                    "conversation_json": str(self.conversation_path),
                    "latest_model_context_json": str(self.latest_model_context_path),
                    "final_txt": str(self.final_path),
                    "eval_result_json": str(self.output_dir / "eval_result.json"),
                    "stderr_txt": str(self.stderr_path),
                    "question_txt": str(self.question_path),
                    "tool_results_dir": str(self.tool_results_dir),
                },
            }
            self.conversation_full = {
                "started_at": self.state["started_at"],
                "finished_at": None,
                "status": "running",
                "question": question,
                "cwd": str(cwd),
                "provider": provider,
                "model": model,
                "tools": tools,
                "max_turns": max_turns,
                "rpc_timeout_seconds": rpc_timeout_seconds,
                "system_prompt_file": str(system_prompt_file) if system_prompt_file else None,
                "append_system_prompt_file": str(append_system_prompt_file) if append_system_prompt_file else None,
                "conversation_features": self.conversation_features.to_dict(),
                "keep_session": keep_session,
                "messages": [],
                "pending_message": None,
                "final_text": None,
            }
            self._init_conversation(
                system_prompt_file=system_prompt_file,
                append_system_prompt_file=append_system_prompt_file,
            )
            self.latest_model_context = {
                "started_at": self.state["started_at"],
                "finished_at": None,
                "status": "running",
                "question": question,
                "cwd": str(cwd),
                "provider": provider,
                "model": model,
                "tools": tools,
                "max_turns": max_turns,
                "rpc_timeout_seconds": rpc_timeout_seconds,
                "conversation_features": self.conversation_features.to_dict(),
                "runtime_context_management": None,
                "request_count": 0,
                "latest": None,
                "error": None,
            }
        self.state["pi_source"] = self.pi_source
        self.conversation_full["pi_source"] = self.pi_source
        self.latest_model_context["pi_source"] = self.pi_source
        self._init_protocol_attempt(
            question=question,
            tools=tools,
            rpc_timeout_seconds=rpc_timeout_seconds,
        )
        self._restore_tool_call_timing_state()
        self._write_artifacts()

    def _init_protocol_attempt(
        self,
        *,
        question: str,
        tools: Optional[str],
        rpc_timeout_seconds: Optional[float],
    ) -> None:
        attempt = int(self.state.get("resume_count", 0)) + 1
        attempt_stem = f"attempt-{attempt:04d}"
        run_id = f"{sanitize_path_component(self.output_dir.name)}-{attempt_stem}"
        self.protocol_dir.mkdir(parents=True, exist_ok=True)
        self.protocol_request_path = self.protocol_dir / f"{attempt_stem}.request.json"
        self.protocol_events_path = self.protocol_dir / f"{attempt_stem}.events.jsonl"
        self.protocol_events_path.write_text("", encoding="utf-8")
        capabilities = map_pi_capabilities(tools)
        request: Dict[str, Any] = {
            "protocol": PROTOCOL_VERSION,
            "run_id": run_id,
            "input": {"text": question},
            "requested_capabilities": capabilities,
        }
        if (
            rpc_timeout_seconds is not None
            and rpc_timeout_seconds > 0
            and rpc_timeout_seconds * 1000 <= MAX_DEADLINE_MS
        ):
            request["deadline_ms"] = max(1, int(round(rpc_timeout_seconds * 1000)))
        validate_run_request(request)
        write_json(self.protocol_request_path, request)
        self._protocol_adapter = PiProtocolAdapter(
            run_id=run_id,
            capabilities=capabilities,
            emit=self._emit_protocol_event,
        )
        self._protocol_adapter.start()
        self.state["protocol"] = {
            "version": PROTOCOL_VERSION,
            "run_id": run_id,
            "attempt": attempt,
            "request_json": str(self.protocol_request_path),
            "events_jsonl": str(self.protocol_events_path),
        }

    def _emit_protocol_event(self, event: Dict[str, object]) -> None:
        cloned = clone_json(event)
        self._protocol_events.append(cloned)
        with self.protocol_events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(cloned, ensure_ascii=False) + "\n")

    def _finalize_protocol_attempt(self, status: str) -> None:
        if self._protocol_adapter.terminal:
            return
        if status == "completed":
            artifact: Optional[Dict[str, object]] = None
            if self.final_path.exists():
                artifact = {
                    "artifact_id": "final-answer",
                    "kind": "answer",
                    "media_type": "text/plain",
                    "uri": self.final_path.name,
                    "sha256": hashlib.sha256(self.final_path.read_bytes()).hexdigest(),
                }
            self._protocol_adapter.complete(artifact=artifact)
        else:
            self._protocol_adapter.fail()
        validate_event_stream(self._protocol_events)

    def _restore_tool_call_timing_state(self) -> None:
        self._pending_tool_call_starts = {}
        self._completed_tool_call_timings = {}
        for entry in self.state.get("tool_calls", []):
            tool_call_id = entry.get("toolCallId")
            if not isinstance(tool_call_id, str) or not tool_call_id:
                continue
            event_type = entry.get("event")
            recorded_at = entry.get("recorded_at")
            if event_type == "tool_execution_start" and isinstance(recorded_at, str):
                self._pending_tool_call_starts[tool_call_id] = recorded_at
            elif event_type == "tool_execution_end":
                timing = self._build_tool_execution_metadata(
                    tool_call_id=tool_call_id,
                    started_at=entry.get("started_at"),
                    finished_at=entry.get("finished_at") or recorded_at,
                )
                if timing is not None:
                    self._completed_tool_call_timings[tool_call_id] = timing
                self._pending_tool_call_starts.pop(tool_call_id, None)
        self._refresh_existing_tool_message_annotations()

    def _build_tool_execution_metadata(
        self,
        *,
        tool_call_id: str,
        started_at: Optional[str],
        finished_at: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(started_at, str) or not isinstance(finished_at, str):
            return None
        duration_seconds = seconds_between(started_at, finished_at)
        if duration_seconds is None:
            return None
        return {
            "tool_call_id": tool_call_id,
            "status": "completed",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
            "duration_ms": int(round(duration_seconds * 1000)),
        }

    def _annotate_tool_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        if message.get("role") != "toolResult":
            return message
        tool_call_id = message.get("toolCallId")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            return message
        timing = self._completed_tool_call_timings.get(tool_call_id)
        if timing is not None:
            message["tool_execution"] = clone_json(timing)
        return message

    def _annotate_messages_with_tool_timing(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        annotated: List[Dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                annotated.append(message)
                continue
            annotated.append(self._annotate_tool_message(clone_json(message)))
        return annotated

    def _refresh_existing_tool_message_annotations(self) -> None:
        messages = self.conversation_full.get("messages")
        if isinstance(messages, list):
            self.conversation_full["messages"] = self._annotate_messages_with_tool_timing(messages)
        pending_message = self.conversation_full.get("pending_message")
        if isinstance(pending_message, dict):
            self.conversation_full["pending_message"] = self._annotate_tool_message(clone_json(pending_message))
        latest = self.latest_model_context.get("latest")
        if isinstance(latest, dict):
            latest_messages = latest.get("messages")
            if isinstance(latest_messages, list):
                latest["messages"] = self._annotate_messages_with_tool_timing(latest_messages)

    def _load_existing_state(self) -> Dict[str, Any]:
        state = read_json_if_exists(self.state_path)
        if state is None:
            raise RuntimeError(f"Cannot resume: missing {self.state_path}")
        return state

    def _load_existing_conversation_full(self) -> Dict[str, Any]:
        conversation = read_json_if_exists(self.conversation_full_path)
        if conversation is None:
            conversation = read_json_if_exists(self.conversation_path)
        if conversation is None:
            raise RuntimeError(f"Cannot resume: missing {self.conversation_full_path} and {self.conversation_path}")
        return conversation

    def _load_existing_latest_model_context(self) -> Dict[str, Any]:
        context = read_json_if_exists(self.latest_model_context_path)
        if context is None:
            context = {
                "started_at": self.state.get("started_at"),
                "finished_at": None,
                "status": self.state.get("status", "running"),
                "question": self.state.get("question"),
                "cwd": self.state.get("cwd"),
                "provider": self.state.get("provider"),
                "model": self.state.get("model"),
                "tools": self.state.get("tools"),
                "max_turns": self.state.get("max_turns"),
                "rpc_timeout_seconds": self.state.get("rpc_timeout_seconds"),
                "conversation_features": self.conversation_features.to_dict(),
                "runtime_context_management": None,
                "request_count": 0,
                "latest": None,
                "error": None,
            }
        return context

    def _normalize_path_str(self, path: Optional[Path]) -> Optional[str]:
        return str(path) if path else None

    def _infer_keep_session(self, state: Dict[str, Any]) -> Optional[bool]:
        if isinstance(state.get("keep_session"), bool):
            return bool(state["keep_session"])
        command = state.get("command")
        if isinstance(command, list):
            return "--no-session" not in command
        return None

    def _validate_resume_inputs(
        self,
        *,
        question: str,
        package_dir: Path,
        agent_dir: Path,
        cwd: Path,
        provider: Optional[str],
        model: Optional[str],
        tools: Optional[str],
        max_turns: Optional[int],
        system_prompt_file: Optional[Path],
        append_system_prompt_file: Optional[Path],
        conversation_features: ConversationFeatures,
        keep_session: bool,
    ) -> None:
        status = self.state.get("status")
        if status == "completed":
            raise RuntimeError(f"Cannot resume completed run in {self.output_dir}")

        comparisons = {
            "question": (self.state.get("question"), question),
            "package_dir": (self.state.get("package_dir"), str(package_dir)),
            "agent_dir": (self.state.get("agent_dir"), str(agent_dir)),
            "cwd": (self.state.get("cwd"), str(cwd)),
            "provider": (self.state.get("provider"), provider),
            "model": (self.state.get("model"), model),
            "tools": (self.state.get("tools"), tools),
            "max_turns": (self.state.get("max_turns"), max_turns),
            "system_prompt_file": (self.state.get("system_prompt_file"), self._normalize_path_str(system_prompt_file)),
            "append_system_prompt_file": (
                self.state.get("append_system_prompt_file"),
                self._normalize_path_str(append_system_prompt_file),
            ),
            "conversation_features": (
                ConversationFeatures.from_dict(self.state.get("conversation_features")).to_dict(),
                conversation_features.to_dict(),
            ),
        }
        mismatches = [
            f"{name}: existing={existing!r} new={new!r}"
            for name, (existing, new) in comparisons.items()
            if existing != new
        ]
        if mismatches:
            mismatch_text = "\n".join(mismatches)
            raise RuntimeError(f"Cannot resume with different run settings:\n{mismatch_text}")

        previous_keep_session = self._infer_keep_session(self.state)
        if previous_keep_session is not None and previous_keep_session != keep_session:
            raise RuntimeError(
                "Cannot resume with a different session mode. Match the previous run's --keep-session setting."
            )

    def _normalize_message(self, message: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not message:
            return None
        normalized = clone_json(message)
        normalized = self._annotate_tool_message(normalized)

        if normalized.get("role") == "assistant":
            if self.conversation_features.strip_thinking:
                normalized["content"] = [
                    part for part in normalized.get("content", []) if part.get("type") != "thinking"
                ]
            if self.conversation_features.strip_usage:
                normalized.pop("usage", None)

        return normalized

    def _write_artifacts(self) -> None:
        write_json(self.state_path, self.state)
        write_json(self.conversation_full_path, self.conversation_full)
        conversation = self._build_processed_conversation()
        write_json(self.conversation_path, conversation)
        write_json(self.latest_model_context_path, self.latest_model_context)

    def _build_processed_conversation(self) -> Dict[str, Any]:
        conversation = clone_json(self.conversation_full)
        self._apply_conversation_features(conversation)
        return conversation

    def _apply_conversation_features(self, conversation: Dict[str, Any]) -> None:
        messages = conversation.get("messages", [])
        if not isinstance(messages, list):
            return

        if self.conversation_features.externalize_tool_results:
            for message in messages:
                if message.get("role") == "toolResult":
                    self._externalize_tool_result_message(message)

        if self.conversation_features.clear_tool_results:
            self._clear_old_tool_result_messages(messages)

    def _get_tool_result_context(self, message: Dict[str, Any]) -> Dict[str, Any]:
        context_management = message.setdefault("context_management", {})
        tool_result_context = context_management.setdefault("tool_result", {})
        return tool_result_context

    def _collect_tool_result_text(self, message: Dict[str, Any]) -> str:
        texts: List[str] = []
        for part in message.get("content", []):
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
        return "\n\n".join(texts)

    def _build_tool_result_stats(self, message: Dict[str, Any]) -> Dict[str, int]:
        stats = count_text_stats(self._collect_tool_result_text(message))
        stats["content_blocks"] = len(message.get("content", []))
        return stats

    def _build_tool_result_file_name(self, message: Dict[str, Any]) -> str:
        tool_call_id = message.get("toolCallId")
        if isinstance(tool_call_id, str) and tool_call_id:
            stem = sanitize_path_component(tool_call_id)
        else:
            stem = f"event-{self.state.get('event_count', 0)}"
        return f"{stem}.json"

    def _externalize_tool_result_message(self, message: Dict[str, Any]) -> None:
        context = self._get_tool_result_context(message)
        if context.get("externalized"):
            return

        self.tool_results_dir.mkdir(parents=True, exist_ok=True)
        rel_path = Path("tool_results") / self._build_tool_result_file_name(message)
        abs_path = self.output_dir / rel_path
        payload = {
            "saved_at": utc_now(),
            "message": clone_json(message),
        }
        write_json(abs_path, payload)

        context["externalized"] = {
            "path": str(rel_path),
            "saved_at": payload["saved_at"],
            "stats": self._build_tool_result_stats(message),
        }

    def _clear_old_tool_result_messages(self, messages: List[Dict[str, Any]]) -> None:
        keep_last = self.conversation_features.clear_tool_results_keep_last
        tool_result_indexes = [
            index for index, message in enumerate(messages) if message.get("role") == "toolResult"
        ]
        keep_indexes = set(tool_result_indexes[-keep_last:] if keep_last else [])

        for index in tool_result_indexes:
            if index in keep_indexes:
                continue
            self._clear_tool_result_message(messages[index])

    def _clear_tool_result_message(self, message: Dict[str, Any]) -> None:
        context = self._get_tool_result_context(message)
        if context.get("status") == "cleared":
            return

        stats = context.get("externalized", {}).get("stats") or self._build_tool_result_stats(message)
        context["status"] = "cleared"
        context["stats"] = stats
        context["cleared_at"] = utc_now()
        context["keep_last"] = self.conversation_features.clear_tool_results_keep_last

        summary_lines = [
            "[tool result cleared from conversation context]",
            f"tool={message.get('toolName', 'unknown')}",
            f"chars={stats.get('chars', 0)}",
            f"lines={stats.get('lines', 0)}",
        ]
        externalized_path = context.get("externalized", {}).get("path")
        if externalized_path:
            summary_lines.append(f"full_output={externalized_path}")

        message["content"] = [{"type": "text", "text": "\n".join(summary_lines)}]

    def _set_pending_message(self, message: Optional[Dict[str, Any]]) -> None:
        self.conversation_full["pending_message"] = self._normalize_message(message)

    def _append_conversation_message(self, message: Optional[Dict[str, Any]]) -> None:
        normalized = self._normalize_message(message)
        if normalized:
            self.conversation_full["messages"].append(normalized)

    def _init_conversation(
        self,
        *,
        system_prompt_file: Optional[Path],
        append_system_prompt_file: Optional[Path],
    ) -> None:
        base_prompt = read_text_if_exists(system_prompt_file)
        append_prompt = read_text_if_exists(append_system_prompt_file)

        if base_prompt is None and append_prompt is None:
            return

        parts = [part.strip("\n") for part in [base_prompt, append_prompt] if part]
        system_text = "\n\n".join(parts)
        self.conversation_full["messages"].append(
            {
                "role": "system",
                "content": [{"type": "text", "text": system_text}],
                "sources": {
                    "system_prompt_file": str(system_prompt_file) if system_prompt_file else None,
                    "append_system_prompt_file": str(append_system_prompt_file) if append_system_prompt_file else None,
                },
            }
        )

    def set_command(self, command: List[str]) -> None:
        self.state["command"] = command
        self._write_artifacts()

    def add_note(self, note: str) -> None:
        self.state["notes"].append({"timestamp": utc_now(), "text": note})
        self._write_artifacts()

    def append_stderr(self, text: str) -> None:
        if not text:
            return
        with self.stderr_path.open("a", encoding="utf-8") as f:
            f.write(text)

    def record_event(self, event: Dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

        self._protocol_adapter.consume(event)

        recorded_at = utc_now()
        self.state["event_count"] += 1
        self.state["last_event_type"] = event.get("type")

        event_type = event.get("type")
        if event_type == "turn_start":
            self.state["turn_count"] += 1
        elif event_type in {"message_start", "message_end"}:
            self.state["messages"].append(
                {
                    "event": event_type,
                    "message": event.get("message"),
                }
            )
            if event_type == "message_start":
                self._set_pending_message(event.get("message"))
            else:
                self._append_conversation_message(event.get("message"))
                self._set_pending_message(None)
        elif event_type == "message_update":
            assistant_event = event.get("assistantMessageEvent", {})
            if assistant_event.get("type") == "text_delta":
                self.state["assistant_text"] += assistant_event.get("delta", "")
            if assistant_event.get("partial"):
                self._set_pending_message(assistant_event.get("partial"))
        elif event_type in {"tool_execution_start", "tool_execution_end"}:
            tool_call_id = event.get("toolCallId")
            started_at: Optional[str] = None
            finished_at: Optional[str] = None
            duration_seconds: Optional[float] = None

            if isinstance(tool_call_id, str) and tool_call_id:
                if event_type == "tool_execution_start":
                    self._pending_tool_call_starts[tool_call_id] = recorded_at
                    started_at = recorded_at
                else:
                    started_at = self._pending_tool_call_starts.pop(tool_call_id, None)
                    finished_at = recorded_at
                    timing = self._build_tool_execution_metadata(
                        tool_call_id=tool_call_id,
                        started_at=started_at,
                        finished_at=finished_at,
                    )
                    if timing is not None:
                        self._completed_tool_call_timings[tool_call_id] = timing
                        duration_seconds = timing["duration_seconds"]
            self.state["tool_calls"].append(
                {
                    "recorded_at": recorded_at,
                    "event": event_type,
                    "toolCallId": tool_call_id,
                    "toolName": event.get("toolName"),
                    "args": event.get("args"),
                    "isError": event.get("isError"),
                    "result": event.get("result"),
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_seconds": duration_seconds,
                }
            )
        elif event_type == "provider_request_context":
            self._record_latest_model_context(event)

        self._write_artifacts()

    def _record_latest_model_context(self, event: Dict[str, Any]) -> None:
        latest_messages = event.get("messages")
        latest_payload = event.get("payload")
        request_index = event.get("requestIndex")
        runtime_context_management = event.get("runtimeContextManagement")
        annotated_messages = (
            self._annotate_messages_with_tool_timing(latest_messages)
            if isinstance(latest_messages, list)
            else []
        )
        self.latest_model_context["request_count"] = max(
            int(self.latest_model_context.get("request_count", 0)),
            int(request_index) if isinstance(request_index, int) else int(self.latest_model_context.get("request_count", 0)),
        )
        self.latest_model_context["runtime_context_management"] = (
            clone_json(runtime_context_management) if runtime_context_management is not None else None
        )
        self.latest_model_context["latest"] = {
            "captured_at": utc_now(),
            "request_index": request_index,
            "model": event.get("model"),
            "runtime_context_management": (
                clone_json(runtime_context_management) if runtime_context_management is not None else None
            ),
            "message_count": len(annotated_messages),
            "messages": annotated_messages,
            "payload": clone_json(latest_payload),
        }

    def finalize(self, *, status: str, final_text: str = "", error: Optional[str] = None, stderr_text: str = "") -> None:
        self.state["status"] = status
        self.state["finished_at"] = utc_now()
        self.state["assistant_text"] = final_text or self.state.get("assistant_text", "")
        if error:
            self.state["error"] = error

        if self.state["assistant_text"]:
            self.final_path.write_text(self.state["assistant_text"] + ("\n" if not self.state["assistant_text"].endswith("\n") else ""), encoding="utf-8")
        if stderr_text:
            if self.resume and self.stderr_path.exists():
                existing_stderr = self.stderr_path.read_text(encoding="utf-8")
                combined = existing_stderr + ("\n" if existing_stderr and not existing_stderr.endswith("\n") else "") + stderr_text
                self.stderr_path.write_text(combined, encoding="utf-8")
            else:
                self.stderr_path.write_text(stderr_text, encoding="utf-8")

        self.conversation_full["status"] = status
        self.conversation_full["finished_at"] = self.state["finished_at"]
        if error:
            self.conversation_full["error"] = error
        self.conversation_full["final_text"] = self.state["assistant_text"]
        self.conversation_full["pending_message"] = None
        self.latest_model_context["status"] = status
        self.latest_model_context["finished_at"] = self.state["finished_at"]
        if error:
            self.latest_model_context["error"] = error

        self._finalize_protocol_attempt(status)
        self._write_artifacts()


class PiRpcClient:
    def __init__(
        self,
        *,
        package_dir: Path,
        cwd: Path,
        agent_dir: Path,
        provider: Optional[str],
        model: Optional[str],
        tools: Optional[str],
        no_session: bool,
        show_tools: bool,
        system_prompt_file: Optional[Path],
        append_system_prompt_file: Optional[Path],
        extra_args: List[str],
    ) -> None:
        self.package_dir = package_dir
        self.cwd = cwd
        self.agent_dir = agent_dir
        self.provider = provider
        self.model = model
        self.tools = tools
        self.no_session = no_session
        self.show_tools = show_tools
        self.system_prompt_file = system_prompt_file
        self.append_system_prompt_file = append_system_prompt_file
        self.extra_args = extra_args
        self.proc: Optional[subprocess.Popen[bytes]] = None
        self.command: Optional[List[str]] = None
        self.stderr_chunks: List[str] = []
        self._stderr_thread: Optional[threading.Thread] = None
        self._stdout_thread: Optional[threading.Thread] = None
        self._stdout_queue: queue.Queue[object] = queue.Queue()
        self._request_id = 0

    def _ensure_built_cli(self) -> Path:
        return ensure_built_pi_cli(self.package_dir)

    def _build_command(self) -> List[str]:
        self._ensure_built_cli()
        return build_pi_command(
            package_dir=self.package_dir,
            mode="rpc",
            provider=self.provider,
            model=self.model,
            tools=self.tools,
            no_session=self.no_session,
            system_prompt_file=self.system_prompt_file,
            append_system_prompt_file=self.append_system_prompt_file,
            extra_args=self.extra_args,
        )

    def start(self) -> None:
        if self.proc is not None:
            raise RuntimeError("RPC client already started")

        env = _node_env(os.environ.copy())
        env["PI_CODING_AGENT_DIR"] = str(self.agent_dir)
        self.command = self._build_command()
        self.proc = subprocess.Popen(
            self.command,
            cwd=str(self.cwd),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self._stdout_queue = queue.Queue()
        self._stdout_thread = threading.Thread(target=self._drain_stdout, daemon=True)
        self._stdout_thread.start()
        assert self.proc.stderr is not None
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

    def _drain_stdout(self) -> None:
        assert self.proc is not None
        assert self.proc.stdout is not None
        try:
            for raw in self.proc.stdout:
                if raw.endswith(b"\n"):
                    raw = raw[:-1]
                if raw.endswith(b"\r"):
                    raw = raw[:-1]
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    excerpt = raw[:240].decode("utf-8", errors="replace")
                    self._stdout_queue.put(RuntimeError(f"Invalid JSONL from RPC process: {excerpt!r}"))
                    return
                if not isinstance(payload, dict):
                    self._stdout_queue.put(RuntimeError(f"RPC process emitted a non-object JSON value: {payload!r}"))
                    return
                self._stdout_queue.put(payload)
        finally:
            self._stdout_queue.put(_RPC_STDOUT_EOF)

    def _drain_stderr(self) -> None:
        assert self.proc is not None
        assert self.proc.stderr is not None
        for raw in self.proc.stderr:
            self.stderr_chunks.append(raw.decode("utf-8", errors="replace"))

    def stop(self) -> None:
        if self.proc is None:
            return
        proc = self.proc
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        finally:
            if self._stdout_thread is not None:
                self._stdout_thread.join(timeout=1)
            if self._stderr_thread is not None:
                self._stderr_thread.join(timeout=1)
            self._stdout_thread = None
            self._stderr_thread = None
            self.proc = None

    def _next_id(self) -> str:
        self._request_id += 1
        return f"py-{self._request_id}"

    def _send(self, payload: Dict[str, Any]) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("RPC client is not running")
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        self.proc.stdin.write(line.encode("utf-8"))
        self.proc.stdin.flush()

    def _read_json_line(self, *, timeout_seconds: Optional[float] = None) -> Dict[str, Any]:
        if self.proc is None:
            raise RuntimeError("RPC client is not running")
        try:
            if timeout_seconds is None:
                item = self._stdout_queue.get()
            else:
                item = self._stdout_queue.get(timeout=max(0.0, timeout_seconds))
        except queue.Empty as exc:
            raise TimeoutError("Timed out waiting for an RPC event") from exc

        if item is _RPC_STDOUT_EOF:
            stderr_text = self.get_stderr().strip()
            returncode = self.proc.poll()
            raise RuntimeError(f"RPC process exited unexpectedly (returncode={returncode}). stderr:\n{stderr_text}")
        if isinstance(item, BaseException):
            raise item
        if not isinstance(item, dict):
            raise RuntimeError(f"Unexpected RPC queue item: {item!r}")
        return item

    def probe_protocol(self, *, timeout_seconds: float = 10) -> Dict[str, Any]:
        """Validate the model-free RPC ``get_state`` contract."""

        request_id = self._next_id()
        self._send({"id": request_id, "type": "get_state"})
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(
                    f"Pi RPC protocol probe timed out after {timeout_seconds:g} seconds"
                )
            try:
                response = self._read_json_line(timeout_seconds=remaining)
            except TimeoutError as exc:
                raise RuntimeError(
                    f"Pi RPC protocol probe timed out after {timeout_seconds:g} seconds"
                ) from exc
            if response.get("type") != "response" or response.get("id") != request_id:
                continue
            if response.get("command") != "get_state":
                raise RuntimeError(
                    "Pi RPC protocol mismatch: get_state response has command "
                    f"{response.get('command')!r}"
                )
            if response.get("success") is not True:
                raise RuntimeError(
                    "Pi RPC get_state failed: "
                    f"{response.get('error', 'unknown protocol error')}"
                )
            state = response.get("data")
            if not isinstance(state, dict):
                raise RuntimeError("Pi RPC protocol mismatch: get_state data is not an object")
            expected_types = {
                "isStreaming": bool,
                "isCompacting": bool,
                "messageCount": int,
                "pendingMessageCount": int,
            }
            for field, expected_type in expected_types.items():
                value = state.get(field)
                if not isinstance(value, expected_type) or (
                    expected_type is int and isinstance(value, bool)
                ):
                    raise RuntimeError(
                        "Pi RPC protocol mismatch: get_state field "
                        f"{field!r} must be {expected_type.__name__}"
                    )
            return state

    def prompt_and_wait(
        self,
        message: str,
        *,
        recorder: Optional[RunRecorder] = None,
        max_turns: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
    ) -> str:
        request_id = self._next_id()
        self._send({"id": request_id, "type": "prompt", "message": message})

        auxiliary_ids: set[str] = set()
        text_parts: List[str] = []
        prompt_ack = False
        seen_turns = 0
        sent_turn_limit_abort = False
        agent_settled = False
        deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None and timeout_seconds > 0 else None

        while True:
            remaining = None if deadline is None else deadline - time.monotonic()
            try:
                event = self._read_json_line(timeout_seconds=remaining)
            except TimeoutError as exc:
                abort_id = self._next_id()
                try:
                    self._send({"id": abort_id, "type": "abort"})
                except (BrokenPipeError, RuntimeError):
                    pass
                raise RuntimeError(f"RPC prompt timed out after {timeout_seconds:g} seconds") from exc
            if recorder:
                recorder.record_event(event)

            event_type = event.get("type")

            if event_type == "response":
                response_id = event.get("id")
                if response_id == request_id:
                    if not event.get("success", False):
                        raise RuntimeError(f"RPC prompt failed: {event.get('error', 'unknown error')}")
                    prompt_ack = True
                elif response_id in auxiliary_ids:
                    pass
                continue

            if event_type == "agent_start":
                text_parts = []
                continue

            if event_type == "turn_start":
                seen_turns += 1
                if max_turns is not None and seen_turns > max_turns and not sent_turn_limit_abort:
                    abort_id = self._next_id()
                    auxiliary_ids.add(abort_id)
                    self._send({"id": abort_id, "type": "abort"})
                    sent_turn_limit_abort = True
                    note = f"Reached max_turns={max_turns}; sent RPC abort before turn {seen_turns}."
                    if recorder:
                        recorder.add_note(note)
                    sys.stderr.write(f"\n[runner] {note}\n")
                    sys.stderr.flush()
                continue

            if event_type == "message_update":
                assistant_event = event.get("assistantMessageEvent", {})
                if assistant_event.get("type") == "text_delta":
                    delta = assistant_event.get("delta", "")
                    text_parts.append(delta)
                    sys.stdout.write(delta)
                    sys.stdout.flush()
                continue

            if event_type == "tool_execution_start" and self.show_tools:
                sys.stderr.write(f"\n[tool:start] {event.get('toolName', 'unknown')}\n")
                sys.stderr.flush()
                continue

            if event_type == "tool_execution_end" and self.show_tools:
                tool_name = event.get("toolName", "unknown")
                is_error = "yes" if event.get("isError") else "no"
                sys.stderr.write(f"\n[tool:end] {tool_name} error={is_error}\n")
                sys.stderr.flush()
                continue

            if event_type == "agent_end":
                if not prompt_ack:
                    raise RuntimeError("Received agent_end before prompt acknowledgement")
                if "willRetry" not in event:
                    break
                continue

            if event_type == "agent_settled":
                if not prompt_ack:
                    raise RuntimeError("Received agent_settled before prompt acknowledgement")
                agent_settled = True
                break

        if agent_settled:
            probe_timeout_seconds = 10.0
            if deadline is not None:
                probe_timeout_seconds = deadline - time.monotonic()
                if probe_timeout_seconds <= 0:
                    raise RuntimeError(
                        f"RPC prompt timed out after {timeout_seconds:g} seconds"
                    )
            state = self.probe_protocol(timeout_seconds=probe_timeout_seconds)
            if (
                state["isStreaming"]
                or state["isCompacting"]
                or state["pendingMessageCount"] != 0
            ):
                raise RuntimeError(
                    "Pi RPC agent_settled postcondition failed: session is not idle"
                )

        return "".join(text_parts)

    def get_stderr(self) -> str:
        return "".join(self.stderr_chunks)


def parse_args() -> argparse.Namespace:
    pi_paths = resolve_pi_paths(REPO_ROOT)
    parser = argparse.ArgumentParser(
        description=(
            "Run one benchmark-style question against pi-coding-agent via RPC. "
            "Suitable as a starting point for BrowseComp Plus experiments."
        )
    )
    parser.add_argument("question", nargs="*", help="Question text. If omitted, reads from --question-file or stdin.")
    parser.add_argument(
        "--runtime",
        help="Agent runtime. Original DCI supports exactly 'pi'. Default: pi.",
    )
    parser.add_argument(
        "--terminal",
        action="store_true",
        help=(
            "Launch pi in its interactive terminal UI instead of the RPC artifact runner. "
            "Positional question text or --question-file is forwarded as the initial message."
        ),
    )
    parser.add_argument("--question-file", type=Path, help="Read the question from a UTF-8 text file.")
    parser.add_argument(
        "--provider",
        help="Provider passed to pi. Overrides DCI_PROVIDER and the Pi default.",
    )
    parser.add_argument(
        "--model",
        help="Model id or pattern passed to pi. Overrides DCI_MODEL and the Pi default.",
    )
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=pi_paths.package_dir,
        help=(
            "Path to Pi's built `packages/coding-agent` directory. Defaults to the path "
            "derived from DCI_PI_DIR (preferring ./pi, then legacy ./pi-mono)."
        ),
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=REPO_ROOT,
        help="Working directory for the agent subprocess. Defaults to the DCI repo root.",
    )
    parser.add_argument(
        "--agent-dir",
        type=Path,
        default=pi_paths.agent_dir,
        help="Pi agent config directory. Defaults to DCI_PI_AGENT_DIR or <DCI_PI_DIR>/.pi/agent.",
    )
    parser.add_argument(
        "--tools",
        help="Comma-separated built-in tools. Overrides DCI_TOOLS and the Pi default.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        help="Client-side cap on agent turns. The runner sends an RPC abort before turn N+1 starts.",
    )
    parser.add_argument(
        "--pi-thinking-level",
        choices=["", "off", "minimal", "low", "medium", "high", "xhigh"],
        help="Pi thinking/reasoning level forwarded as --thinking <level>.",
    )
    parser.add_argument(
        "--runtime-context-level",
        help="Optional Pi context-management profile, such as level0 through level4.",
    )
    parser.add_argument(
        "--rpc-timeout-seconds",
        type=non_negative_float,
        help=(
            "Wall-clock deadline for one RPC prompt. Overrides DCI_RPC_TIMEOUT_SECONDS "
            f"or {DEFAULT_RPC_TIMEOUT_SECONDS:g}; set to 0 to disable."
        ),
    )
    parser.add_argument(
        "--system-prompt-file",
        type=Path,
        help=(
            "Optional text file passed to pi via --system-prompt. "
            "Relative paths are resolved against the current directory first, then the DCI repo root. "
            "By default, pi uses its own dynamically generated system prompt."
        ),
    )
    parser.add_argument(
        "--append-system-prompt-file",
        type=Path,
        help=(
            "Optional text file passed to pi via --append-system-prompt. "
            "Relative paths are resolved against the current directory first, then the DCI repo root."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory to store events.jsonl, state.json, conversation_full.json, conversation.json, "
            "latest_model_context.json, final.txt, and stderr.txt. Default: outputs/runs/<timestamp>"
        ),
    )
    parser.add_argument(
        "--conversation-clear-tool-results",
        action="store_true",
        help=(
            "Compact conversation.json by replacing older toolResult payloads with placeholders "
            "while keeping recent tool results inline."
        ),
    )
    parser.add_argument(
        "--conversation-clear-tool-results-keep-last",
        type=int,
        default=3,
        help="When --conversation-clear-tool-results is enabled, keep the last N toolResult messages inline. Default: 3",
    )
    parser.add_argument(
        "--conversation-externalize-tool-results",
        action="store_true",
        help="Write each toolResult message to output_dir/tool_results/*.json and add a pointer from conversation.json.",
    )
    parser.add_argument(
        "--conversation-strip-thinking",
        action="store_true",
        help="Remove assistant thinking blocks from conversation.json.",
    )
    parser.add_argument(
        "--conversation-strip-usage",
        action="store_true",
        help="Remove assistant usage metadata from conversation.json.",
    )
    parser.add_argument(
        "--resume",
        nargs="?",
        const="__USE_OUTPUT_DIR__",
        help=(
            "Resume in an existing output directory. "
            "Pass a directory explicitly, or use --resume with --output-dir to resume that directory. "
            "If the directory does not exist or is empty, the runner prints a warning and starts a new run there."
        ),
    )
    parser.add_argument(
        "--keep-session",
        action="store_true",
        help="Persist session history instead of running with --no-session.",
    )
    parser.add_argument(
        "--show-tools",
        action="store_true",
        help="Print tool start/end events to stderr while the agent runs.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help=(
            "Extra CLI arg or quoted arg string forwarded to pi. "
            'Examples: --extra-arg="--context-management-level level3" or '
            "--extra-arg=--model --extra-arg=claude-sonnet-4-20250514"
        ),
    )
    parser.add_argument(
        "--eval-answer",
        help=(
            "Optional gold answer. If provided, the runner grades final.txt with the configured "
            "OpenAI-compatible judge and writes eval_result.json."
        ),
    )
    parser.add_argument(
        "--eval-answer-file",
        type=Path,
        help="Optional UTF-8 text file containing the gold answer for evaluation.",
    )
    parser.add_argument(
        "--eval-judge-base-url",
        help=(
            "OpenAI-compatible judge API base URL. "
            "Overrides DCI_EVAL_JUDGE_BASE_URL from .env."
        ),
    )
    parser.add_argument(
        "--eval-judge-api",
        help=(
            "Judge protocol: responses or chat-completions. "
            "Overrides DCI_EVAL_JUDGE_API from .env."
        ),
    )
    parser.add_argument(
        "--eval-judge-model",
        help=(
            "Judge model. Overrides DCI_EVAL_JUDGE_MODEL from .env. "
            f"Built-in default: {DEFAULT_EVAL_JUDGE_MODEL}"
        ),
    )
    parser.add_argument(
        "--eval-judge-api-key-env",
        help=(
            "Environment variable containing the judge API key. Overrides "
            "DCI_EVAL_JUDGE_API_KEY_ENV; direct DCI_EVAL_JUDGE_API_KEY takes precedence."
        ),
    )
    parser.add_argument(
        "--eval-judge-timeout-seconds",
        type=int,
        help="Judge HTTP timeout. Overrides DCI_EVAL_JUDGE_TIMEOUT_SECONDS; built-in default: 120",
    )
    parser.add_argument(
        "--eval-judge-input-price-per-1m",
        type=float,
        help=(
            "Judge input token price per 1M tokens. Overrides "
            f"DCI_EVAL_JUDGE_INPUT_PRICE_PER_1M; built-in default: {DEFAULT_EVAL_INPUT_PRICE_PER_1M}"
        ),
    )
    parser.add_argument(
        "--eval-judge-cached-input-price-per-1m",
        type=float,
        help=(
            "Judge cached-input token price per 1M tokens. Overrides "
            "DCI_EVAL_JUDGE_CACHED_INPUT_PRICE_PER_1M; built-in default: "
            f"{DEFAULT_EVAL_CACHED_INPUT_PRICE_PER_1M}"
        ),
    )
    parser.add_argument(
        "--eval-judge-output-price-per-1m",
        type=float,
        help=(
            "Judge output token price per 1M tokens. Overrides "
            f"DCI_EVAL_JUDGE_OUTPUT_PRICE_PER_1M; built-in default: {DEFAULT_EVAL_OUTPUT_PRICE_PER_1M}"
        ),
    )
    return parser.parse_args()


def load_judge_config_from_args(args: argparse.Namespace) -> JudgeConfig:
    return JudgeConfig.from_env(
        base_url=args.eval_judge_base_url,
        api=args.eval_judge_api,
        model=args.eval_judge_model,
        api_key_env=args.eval_judge_api_key_env,
        timeout_seconds=args.eval_judge_timeout_seconds,
        input_price_per_1m=args.eval_judge_input_price_per_1m,
        cached_input_price_per_1m=args.eval_judge_cached_input_price_per_1m,
        output_price_per_1m=args.eval_judge_output_price_per_1m,
    )


def resolve_runtime_args(
    args: argparse.Namespace, layers: ConfigLayers
) -> OriginalRuntimeConfig:
    args.max_turns_explicit = args.max_turns is not None
    resolved = resolve_original_runtime(
        {
            "runtime": args.runtime,
            "provider": args.provider,
            "model": args.model,
            "tools": args.tools,
            "max_turns": args.max_turns,
            "timeout_seconds": args.rpc_timeout_seconds,
            "thinking_level": args.pi_thinking_level,
            "context_profile": args.runtime_context_level,
        },
        layers,
    )
    args.runtime = resolved.runtime
    args.provider = resolved.provider
    args.model = resolved.model
    args.tools = resolved.tools
    args.max_turns = resolved.max_turns
    args.rpc_timeout_seconds = resolved.timeout_seconds
    args.pi_thinking_level = resolved.thinking_level
    args.runtime_context_level = resolved.context_profile
    return resolved


def effective_config_for_run(
    *,
    runtime: OriginalRuntimeConfig,
    args: argparse.Namespace,
    judge_config: Optional[JudgeConfig],
) -> dict[str, object]:
    judge: dict[str, object] = {}
    if judge_config is not None:
        judge = {
            "endpoint": judge_config.endpoint,
            "api": judge_config.api,
            "model": judge_config.model,
            "thinking": judge_config.effective_thinking,
            "json_mode": judge_config.json_mode,
        }
    return OriginalEffectiveConfig(
        runtime=runtime,
        context={
            "profile": runtime.context_profile,
            "implementation_sha256": None,
        },
        judge=judge,
        experiment={
            "dataset": None,
            "selection": "single-query",
            "corpus": args.cwd.name,
            "metric": "judge-correctness" if judge_config is not None else None,
            "execution_class": "single",
        },
    ).to_public_dict()


def write_effective_config(path: Path, payload: dict[str, object]) -> None:
    write_json(path, payload)
    path.chmod(0o600)


def resolved_pi_extra_args(args: argparse.Namespace) -> List[str]:
    extra_args = expand_extra_args(args.extra_arg)
    if args.pi_thinking_level:
        extra_args.extend(["--thinking", args.pi_thinking_level])
    if args.runtime_context_level:
        extra_args.extend(["--context-management-level", args.runtime_context_level])
    return extra_args


def load_question(args: argparse.Namespace, *, resume_dir: Optional[Path]) -> str:
    if args.question_file:
        return args.question_file.read_text(encoding="utf-8").strip()
    if args.question:
        return " ".join(args.question).strip()
    if resume_dir:
        resume_question = read_text_if_exists(resume_dir / "question.txt")
        if resume_question is not None:
            return resume_question.strip()
        state = read_json_if_exists(resume_dir / "state.json")
        if state and isinstance(state.get("question"), str):
            return state["question"].strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    return ""


def resolve_output_dir(args: argparse.Namespace) -> tuple[Path, bool]:
    output_dir = args.output_dir.resolve() if args.output_dir else None
    resume_dir: Optional[Path] = None

    if args.resume is not None:
        if args.resume == "__USE_OUTPUT_DIR__":
            if output_dir is None:
                raise RuntimeError("--resume without a directory requires --output-dir")
            resume_dir = output_dir
        else:
            resume_dir = Path(args.resume).resolve()
            if output_dir is not None and output_dir != resume_dir:
                raise RuntimeError("--resume DIR and --output-dir must point to the same directory")

    resolved_dir = resume_dir or output_dir or build_default_output_dir().resolve()
    return resolved_dir, resume_dir is not None


def normalize_resume_mode(output_dir: Path, resume_requested: bool) -> tuple[bool, Optional[str]]:
    if not resume_requested:
        return False, None
    if not output_dir.exists():
        return (
            False,
            f"[runner] --resume requested but directory does not exist; creating a new run instead: {output_dir}",
        )
    if is_directory_empty(output_dir):
        return (
            False,
            f"[runner] --resume requested but directory is empty; creating a new run instead: {output_dir}",
        )
    return True, None


def terminal_initial_messages(args: argparse.Namespace) -> List[str]:
    if args.question_file:
        message = args.question_file.read_text(encoding="utf-8").strip()
        return [message] if message else []
    if args.question:
        message = " ".join(args.question).strip()
        return [message] if message else []
    return []


def validate_terminal_mode_args(args: argparse.Namespace) -> Optional[str]:
    incompatible: List[str] = []
    if args.output_dir is not None:
        incompatible.append("--output-dir")
    if args.resume is not None:
        incompatible.append("--resume")
    if getattr(args, "max_turns_explicit", args.max_turns is not None):
        incompatible.append("--max-turns")
    if args.show_tools:
        incompatible.append("--show-tools")
    if args.conversation_clear_tool_results:
        incompatible.append("--conversation-clear-tool-results")
    if args.conversation_externalize_tool_results:
        incompatible.append("--conversation-externalize-tool-results")
    if args.conversation_strip_thinking:
        incompatible.append("--conversation-strip-thinking")
    if args.conversation_strip_usage:
        incompatible.append("--conversation-strip-usage")
    if args.eval_answer is not None:
        incompatible.append("--eval-answer")
    if args.eval_answer_file is not None:
        incompatible.append("--eval-answer-file")

    if incompatible:
        return "--terminal cannot be combined with runner-only options: " + ", ".join(incompatible)
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return "--terminal requires an interactive stdin/stdout TTY"
    return None


def run_terminal_mode(args: argparse.Namespace) -> int:
    error = validate_terminal_mode_args(args)
    if error:
        print(error, file=sys.stderr)
        return 2

    system_prompt_file = resolve_repo_relative_path(args.system_prompt_file)
    append_system_prompt_file = resolve_repo_relative_path(args.append_system_prompt_file)
    env = _node_env(os.environ.copy())
    env["PI_CODING_AGENT_DIR"] = str(args.agent_dir.resolve())
    cmd = build_pi_command(
        package_dir=args.package_dir.resolve(),
        mode=None,
        provider=args.provider,
        model=args.model,
        tools=args.tools,
        no_session=False,
        system_prompt_file=system_prompt_file,
        append_system_prompt_file=append_system_prompt_file,
        extra_args=resolved_pi_extra_args(args),
        messages=terminal_initial_messages(args),
    )
    completed = subprocess.run(
        cmd,
        cwd=str(args.cwd.resolve()),
        env=env,
        check=False,
    )
    return completed.returncode


def main() -> int:
    layers = ConfigLayers.from_repo(REPO_ROOT)
    layers.materialize(os.environ)
    args = parse_args()
    try:
        runtime_config = resolve_runtime_args(args, layers)
    except ValueError as exc:
        print(f"Invalid runtime configuration: {exc}", file=sys.stderr)
        return 2
    if args.terminal:
        try:
            return run_terminal_mode(args)
        except Exception as exc:
            print(f"Terminal run failed: {exc}", file=sys.stderr)
            return 1

    if args.eval_answer and args.eval_answer_file:
        print("Use at most one of --eval-answer and --eval-answer-file.", file=sys.stderr)
        return 2
    eval_answer = load_eval_answer(
        eval_answer=args.eval_answer,
        eval_answer_file=args.eval_answer_file.resolve() if args.eval_answer_file else None,
    )
    judge_config: Optional[JudgeConfig] = None
    if eval_answer is not None:
        try:
            judge_config = load_judge_config_from_args(args)
        except ValueError as exc:
            print(f"Invalid judge configuration: {exc}", file=sys.stderr)
            return 2
    try:
        conversation_features = ConversationFeatures.from_args(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        output_dir, resume = resolve_output_dir(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    resume, resume_warning = normalize_resume_mode(output_dir, resume)
    if resume_warning:
        print(resume_warning, file=sys.stderr)

    question = load_question(args, resume_dir=output_dir if resume else None)
    if not question:
        print("No question provided. Use positional text, --question-file, or stdin.", file=sys.stderr)
        return 2

    system_prompt_file = resolve_repo_relative_path(args.system_prompt_file)
    append_system_prompt_file = resolve_repo_relative_path(args.append_system_prompt_file)
    if not resume:
        if output_dir.exists() and not is_directory_empty(output_dir):
            print(
                f"Refusing to reuse non-empty output directory without --resume: {output_dir}",
                file=sys.stderr,
            )
            return 2

    existing_state = read_json_if_exists(output_dir / "state.json") if resume else None
    output_dir.mkdir(parents=True, exist_ok=True)
    write_effective_config(
        output_dir / "effective-config.json",
        effective_config_for_run(
            runtime=runtime_config,
            args=args,
            judge_config=judge_config,
        ),
    )
    if resume and eval_answer is not None and existing_state and existing_state.get("status") == "completed":
        predicted_answer = (
            read_text_if_exists(output_dir / "final.txt")
            or existing_state.get("assistant_text")
            or ""
        ).strip()
        try:
            eval_result = evaluate_run_output(
                output_dir=output_dir,
                question=question,
                gold_answer=eval_answer,
                predicted_answer=predicted_answer,
                judge_config=judge_config,
            )
        except Exception as exc:
            print(f"Evaluation failed: {exc}", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "output_dir": str(output_dir),
                    "is_correct": eval_result.get("is_correct"),
                    "normalized_prediction": eval_result.get("normalized_prediction"),
                    "reason": eval_result.get("reason"),
                    "eval_result_json": str(output_dir / "eval_result.json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    try:
        recorder = RunRecorder(
            output_dir=output_dir,
            question=question,
            package_dir=args.package_dir.resolve(),
            agent_dir=args.agent_dir.resolve(),
            cwd=args.cwd.resolve(),
            provider=args.provider,
            model=args.model,
            tools=args.tools,
            max_turns=args.max_turns,
            rpc_timeout_seconds=args.rpc_timeout_seconds,
            system_prompt_file=system_prompt_file,
            append_system_prompt_file=append_system_prompt_file,
            conversation_features=conversation_features,
            keep_session=args.keep_session,
            resume=resume,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    emit_pi_source_warning(recorder)

    client = PiRpcClient(
        package_dir=args.package_dir.resolve(),
        cwd=args.cwd.resolve(),
        agent_dir=args.agent_dir.resolve(),
        provider=args.provider,
        model=args.model,
        tools=args.tools,
        no_session=not args.keep_session,
        show_tools=args.show_tools,
        system_prompt_file=system_prompt_file,
        append_system_prompt_file=append_system_prompt_file,
        extra_args=resolved_pi_extra_args(args),
    )

    try:
        client.start()
        if client.command:
            recorder.set_command(client.command)
        sys.stderr.write(f"[runner] saving run artifacts under {output_dir}\n")
        sys.stderr.flush()

        final_text = client.prompt_and_wait(
            question,
            recorder=recorder,
            max_turns=args.max_turns,
            timeout_seconds=args.rpc_timeout_seconds,
        )
        if not final_text.endswith("\n"):
            sys.stdout.write("\n")
        recorder.finalize(status="completed", final_text=final_text, stderr_text=client.get_stderr())
        if eval_answer is not None:
            eval_result = evaluate_run_output(
                output_dir=output_dir,
                question=question,
                gold_answer=eval_answer,
                predicted_answer=final_text.strip(),
                judge_config=judge_config,
            )
            print(
                json.dumps(
                    {
                        "output_dir": str(output_dir),
                        "is_correct": eval_result.get("is_correct"),
                        "normalized_prediction": eval_result.get("normalized_prediction"),
                        "reason": eval_result.get("reason"),
                        "eval_result_json": str(output_dir / "eval_result.json"),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 0
    except Exception as exc:
        stderr_text = client.get_stderr().strip()
        recorder.finalize(status="failed", error=str(exc), stderr_text=stderr_text)
        print(f"RPC run failed: {exc}", file=sys.stderr)
        if stderr_text:
            print("\n[agent stderr]", file=sys.stderr)
            print(stderr_text, file=sys.stderr)
        return 1
    finally:
        client.stop()


if __name__ == "__main__":
    raise SystemExit(main())
