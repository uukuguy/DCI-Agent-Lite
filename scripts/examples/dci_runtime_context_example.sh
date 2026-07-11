#!/usr/bin/env bash

# Auto-load .env from repo root if present
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  while [ "$REPO_ROOT" != "/" ] && [ ! -d "$REPO_ROOT/.git" ]; do
    REPO_ROOT="$(dirname "$REPO_ROOT")"
  done
fi
if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

set -euo pipefail

: "${DCI_PROVIDER:?Set DCI_PROVIDER in .env (for example: anthropic)}"
: "${DCI_MODEL:?Set DCI_MODEL in .env (for example: claude-sonnet-4-20250514)}"

level="${1:-high}"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
QUESTION="Read the files in the current directory. Do not use web search. Use rg instead of grep when searching. Question: In the Bonang Matheba interview where the third-to-last question asks about the origin of the name given to her by radio listeners, what is the interviewer's first name? Answer with just the first name and one supporting file path."

cd "$REPO_ROOT"
uv run dci-agent-lite \
  --package-dir "$REPO_ROOT/pi-mono/packages/coding-agent" \
  --agent-dir "$REPO_ROOT/pi-mono/.pi/agent" \
  --cwd "$REPO_ROOT/corpus/bc_plus_docs" \
  --tools read,bash \
  --max-turns 6 \
  --eval-answer "Adaku" \
  --extra-arg="--thinking $level" \
  "$QUESTION"
