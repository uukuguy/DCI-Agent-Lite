#!/usr/bin/env python3
"""Record one DCI climb cycle into append-only evidence and current state."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import yaml


LEGACY_DIMENSIONS = (
    "immutable_resolution",
    "repeat_validation",
    "dirty_checkout_safety",
    "override_compatibility",
)


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
    if not isinstance(per_task, dict):
        raise RuntimeError("local-eval.json per_task must be an object")
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
    session_path = args.state_dir / "session-state.json"
    session_state = json.loads(session_path.read_text())
    session_id = session_state["session"]
    work_package_id = hypothesis.get("work_package_id")
    acceptance_kind = (
        "executor"
        if work_package_id == "AF-050"
        else "package"
        if work_package_id is not None
        else "setup-policy"
    )
    decision_reason = f"deterministic local {acceptance_kind} acceptance"
    existing_result = next(
        (result for result in hypothesis["results"] if result["run"] == args.run_id),
        None,
    )
    if existing_result is not None:
        if (
            existing_result.get("local") != total
            or existing_result.get("local_per_task") != per_task
        ):
            raise RuntimeError(
                f"Existing hypothesis result for {args.run_id} conflicts with local evaluation"
            )
    else:
        hypothesis["status"] = status
        hypothesis["results"].append(
            {
                "session": session_id,
                "cycle": args.cycle,
                "run": args.run_id,
                "local": total,
                "local_per_task": per_task,
                "online": None,
                "verdict": verdict,
                "decision_reason": decision_reason,
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
            "session": session_id,
            "hypothesis_id": args.hypothesis_id,
            "paradigm": hypothesis["parent_paradigm"],
            "pushed_at": timestamp,
            "local_score": total,
            **{dimension: per_task.get(dimension, "") for dimension in LEGACY_DIMENSIONS},
            "push_decision": "PUSH",
            "decision_reason": decision_reason,
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
    journal_text += (
        f"- {now:%H:%M} {args.hypothesis_id} {verdict}; "
        f"{acceptance_kind} acceptance recorded.\n"
    )
    args.journal.write_text(journal_text)

    print(json.dumps({"hypothesis": args.hypothesis_id, "verdict": verdict, "next": next_hypothesis}))


if __name__ == "__main__":
    main()
