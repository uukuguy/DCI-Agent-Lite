#!/usr/bin/env bash
set -euo pipefail

echo "ERROR: DCI dependency-policy climb has no external leaderboard; local acceptance is ground truth." >&2
exit 2
