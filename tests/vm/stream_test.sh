#!/usr/bin/env bash
# stream_test.sh: exercise stdout, stderr, silence, and exit code.
# Usage: ./stream_test.sh [--lines N] [--sleep S] [--silent T] [--exit CODE]
# Defaults: N=10, S=0.5s between lines, T=0 (no silence), CODE=0

set -euo pipefail

LINES=10
SLEEP=0.5
SILENT=0
EXIT_CODE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lines)   LINES="${2:-10}"; shift 2 ;;
    --sleep)   SLEEP="${2:-0.5}"; shift 2 ;;
    --silent)  SILENT="${2:-0}"; shift 2 ;;
    --exit)    EXIT_CODE="${2:-0}"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

echo "[info] starting stream_test with LINES=$LINES SLEEP=${SLEEP}s SILENT=${SILENT}s EXIT=$EXIT_CODE"

for i in $(seq 1 "$LINES"); do
  echo "stdout line $i"
  if (( i % 3 == 0 )); then
    echo "stderr blip at i=$i" >&2
  fi
  sleep "$SLEEP"
done

if (( SILENT > 0 )); then
  echo "[info] entering intentional silence for ${SILENT}s"
  # No output during this sleep → should tick your inactivity timer
  sleep "$SILENT"
  echo "[info] silence over"
fi

echo "[info] finishing with exit code $EXIT_CODE"
exit "$EXIT_CODE"
