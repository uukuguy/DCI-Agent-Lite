#!/usr/bin/env python3
"""Run a model-free Pi RPC protocol compatibility probe."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from dci.benchmark.pi_rpc_runner import PiRpcClient  # noqa: E402
from dci.config import load_project_env, resolve_pi_paths  # noqa: E402


def parse_args() -> argparse.Namespace:
    load_project_env(REPO_ROOT)
    pi_paths = resolve_pi_paths(REPO_ROOT)
    parser = argparse.ArgumentParser(
        description="Run a model-free Pi RPC get_state compatibility check."
    )
    parser.add_argument("--timeout-seconds", type=float, default=10)
    parser.add_argument("--package-dir", type=Path, default=pi_paths.package_dir)
    parser.add_argument("--agent-dir", type=Path, default=pi_paths.agent_dir)
    parser.add_argument("--cwd", type=Path, default=REPO_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = PiRpcClient(
        package_dir=args.package_dir.resolve(),
        cwd=args.cwd.resolve(),
        agent_dir=args.agent_dir.resolve(),
        provider=os.environ.get("DCI_PROVIDER"),
        model=os.environ.get("DCI_MODEL"),
        tools=None,
        no_session=True,
        show_tools=False,
        system_prompt_file=None,
        append_system_prompt_file=None,
        extra_args=["--no-approve"],
    )
    try:
        client.start()
        state = client.probe_protocol(timeout_seconds=args.timeout_seconds)
    except (RuntimeError, TimeoutError) as exc:
        print(f"Pi RPC protocol check failed: {exc}", file=sys.stderr)
        return 1
    finally:
        client.stop()

    print(
        json.dumps(
            {
                "ok": True,
                "command": "get_state",
                "is_streaming": state["isStreaming"],
                "is_compacting": state["isCompacting"],
                "message_count": state["messageCount"],
                "pending_message_count": state["pendingMessageCount"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
