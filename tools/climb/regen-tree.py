#!/usr/bin/env python3
"""Deterministically render the DCI climb resume summary."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "docs/status/climb"


def load_json(name: str, default: object) -> object:
    path = STATE / name
    return json.loads(path.read_text()) if path.exists() else default


def main() -> None:
    hypotheses = yaml.safe_load((STATE / "hypotheses.yaml").read_text())["hypotheses"]
    with (STATE / "runs.csv").open(newline="") as handle:
        runs = list(csv.DictReader(handle))
    session = load_json("session-state.json", {})
    calibration = load_json("calibration.json", {"paradigms": {}})
    tree = {
        "run_count": len(runs),
        "session": session,
        "active": [h for h in hypotheses if h["status"] in {"pending", "in-flight"}],
        "confirmed": [h for h in hypotheses if h["status"] == "confirmed"],
        "falsified": [h for h in hypotheses if h["status"] == "falsified"],
        "runs": runs,
        "calibration": calibration,
    }
    (STATE / "research-tree.json").write_text(json.dumps(tree, indent=2) + "\n")

    lines = [
        "# Research Tree — DCI climb",
        "",
        f"> Deterministic summary generated from tracked state ({len(runs)} runs).",
        "> Do not edit directly; run `python3 tools/climb/regen-tree.py`.",
        "",
        "## In-flight / session state",
        "",
        f"- Phase: {session.get('phase', 'unknown')}",
        f"- Last cycle: {session.get('last_cycle', 0)}",
        f"- Next hypothesis: {session.get('next_hypothesis', 'none')}",
        f"- In flight: {session.get('in_flight') or 'none'}",
        f"- Next action: {session.get('next_action', 'none')}",
        "",
        "## Active hypotheses",
        "",
    ]
    for hypothesis in sorted(tree["active"], key=lambda item: -item["ranking"]):
        lines.append(
            f"- **{hypothesis['id']}** ({hypothesis['status']}, rank {hypothesis['ranking']:.2f}): "
            f"{hypothesis['description']}"
        )
    lines.extend(["", "## Run ladder", "", "| run | hypothesis | local | verdict |", "|---|---|---:|---|"])
    for run in runs:
        lines.append(
            f"| {run['run_id']} | {run['hypothesis_id']} | {run['local_score'] or '—'} | "
            f"{run['verdict'] or 'pending'} |"
        )
    lines.extend(["", "## Negative cache", ""])
    for route in session.get("falsified_routes", []):
        lines.append(f"- {route}")
    (STATE / "research-tree.md").write_text("\n".join(lines) + "\n")
    print(f"[regen-tree] wrote {STATE / 'research-tree.md'}")


if __name__ == "__main__":
    main()
