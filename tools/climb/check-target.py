#!/usr/bin/env python3
"""Report whether the optional deterministic local climb target is met."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "docs/status/climb"


def main() -> None:
    target_text = (STATE / "session-target.md").read_text()
    match = re.search(r"target_value:\s*([0-9.]+)", target_text)
    if not match:
        print(json.dumps({"has_target": False, "met": False, "reason": "best-effort mode"}))
        return
    target = float(match.group(1))
    with (STATE / "runs.csv").open(newline="") as handle:
        scores = [float(row["local_score"]) for row in csv.DictReader(handle) if row["local_score"]]
    current = max(scores, default=None)
    met = current is not None and current >= target
    print(json.dumps({"has_target": True, "met": met, "current": current, "target": target}))
    if met:
        raise SystemExit(10)


if __name__ == "__main__":
    main()
