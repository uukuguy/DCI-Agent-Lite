#!/usr/bin/env python3
"""Apply the DCI local acceptance decision gate."""

from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-eval-json", required=True)
    args = parser.parse_args()
    with open(args.local_eval_json) as handle:
        score = float(json.load(handle)["total"])
    if score < 1:
        decision, reason = "SKIP", "disaster: no policy dimension passed"
    else:
        decision, reason = "PUSH", "cheap deterministic local acceptance"
    print(json.dumps({"decision": decision, "reason": reason, "local_total": score}))


if __name__ == "__main__":
    main()
