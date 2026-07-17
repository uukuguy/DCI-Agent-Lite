#!/usr/bin/env python3
"""Bind one validated AF-320 paper benchmark report to terminal Climb state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asterion.dci.artifacts import bind_paper_benchmark_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--pi-dir", type=Path, required=True)
    parser.add_argument(
        "--state-dir", type=Path, default=Path("docs/status/climb")
    )
    parser.add_argument("--hypothesis-id", default="AF-320-H-004")
    args = parser.parse_args(argv)
    digest = bind_paper_benchmark_evidence(
        args.report,
        state_dir=args.state_dir,
        pi_dir=args.pi_dir,
        hypothesis_id=args.hypothesis_id,
    )
    print(
        json.dumps(
            {"hypothesis": args.hypothesis_id, "evidence_sha256": digest},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
