#!/usr/bin/env python3
"""Independently rebind retained AF-330 Claude evidence without printing bodies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asterion.dci.dual_runtime_verification import (
    DciDualRuntimeVerificationError,
    verify_restricted_claude_binding,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify_restricted_claude_binding(
            repo_root=args.repo_root,
            run_dir=args.run_dir,
            corpus_dir=args.corpus_dir,
            report_path=args.report,
            record_path=args.record,
        )
    except DciDualRuntimeVerificationError:
        print("AF-330 Claude evidence verification failed", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
