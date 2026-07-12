#!/usr/bin/env python3
"""Record one DCI climb cycle into append-only evidence and current state."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--hypothesis-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--cycle", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evaluation = json.loads((args.run_dir / "local-eval.json").read_text())
    total = int(evaluation["total"])
    per_task = evaluation["per_task"]
    verdict = "confirmed 4/4" if total == 4 else f"falsified {total}/4"
    status = "confirmed" if total == 4 else "falsified"
    now = datetime.now().astimezone()
    timestamp = now.isoformat(timespec="seconds")

    runs_path = args.state_dir / "runs.csv"
    with runs_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        existing_runs = list(reader)
        fieldnames = reader.fieldnames
    if fieldnames is None:
        raise RuntimeError(f"Missing runs.csv header: {runs_path}")
    if any(row["run_id"] == args.run_id for row in existing_runs):
        print(
            json.dumps(
                {
                    "hypothesis": args.hypothesis_id,
                    "run_id": args.run_id,
                    "replayed": True,
                    "action": "no-op",
                }
            )
        )
        return

    hypotheses_path = args.state_dir / "hypotheses.yaml"
    hypothesis_state = yaml.safe_load(hypotheses_path.read_text())
    hypotheses = hypothesis_state["hypotheses"]
    hypothesis = next(item for item in hypotheses if item["id"] == args.hypothesis_id)
    hypothesis["status"] = status
    hypothesis["results"].append(
        {
            "session": "2026-07-12-pi-revision",
            "cycle": args.cycle,
            "run": args.run_id,
            "local": total,
            "local_per_task": per_task,
            "online": None,
            "verdict": verdict,
            "decision_reason": "deterministic local setup-policy acceptance",
        }
    )
    hypotheses_path.write_text(
        yaml.safe_dump(hypothesis_state, sort_keys=False, allow_unicode=True)
    )

    row = {name: "" for name in fieldnames}
    row.update(
        {
            "run_id": args.run_id,
            "cycle": args.cycle,
            "session": "2026-07-12-pi-revision",
            "hypothesis_id": args.hypothesis_id,
            "paradigm": hypothesis["parent_paradigm"],
            "pushed_at": timestamp,
            "local_score": total,
            "immutable_resolution": per_task["immutable_resolution"],
            "repeat_validation": per_task["repeat_validation"],
            "dirty_checkout_safety": per_task["dirty_checkout_safety"],
            "override_compatibility": per_task["override_compatibility"],
            "push_decision": "PUSH",
            "decision_reason": "cheap deterministic local acceptance",
            "verdict": verdict,
            "train_cost_h": "0.01",
            "manifest_path": f"runs/climb/{args.run_id}/manifest.json",
        }
    )
    with runs_path.open("a", newline="") as handle:
        csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n").writerow(row)

    remaining = sorted(
        (item for item in hypotheses if item["status"] == "pending"),
        key=lambda item: -float(item["ranking"]),
    )
    next_hypothesis = remaining[0]["id"] if remaining else None
    session_path = args.state_dir / "session-state.json"
    session_state = json.loads(session_path.read_text())
    session_state.update(
        {
            "phase": "implementation",
            "last_cycle": args.cycle,
            "next_hypothesis": next_hypothesis,
            "in_flight": None,
            "next_action": (
                f"Start {next_hypothesis}." if next_hypothesis else "Trigger Knowledge Layer."
            ),
        }
    )
    session_path.write_text(json.dumps(session_state, indent=2) + "\n")

    date_header = f"## {now:%Y-%m-%d}"
    journal_text = args.journal.read_text()
    if date_header not in journal_text:
        journal_text += f"\n{date_header}\n"
    journal_text += f"- {now:%H:%M} {args.hypothesis_id} {verdict}; setup-policy acceptance recorded.\n"
    args.journal.write_text(journal_text)

    print(json.dumps({"hypothesis": args.hypothesis_id, "verdict": verdict, "next": next_hypothesis}))


if __name__ == "__main__":
    main()
