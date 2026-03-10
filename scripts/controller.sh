#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/.openclaw/workspace/tripwiki}"
cd "$REPO_DIR"

# Simple controller: if there are unchecked cities in BACKLOG, open next batch as TODO marker file.
# NOTE: actual subagent spawning is handled by OpenClaw agent session, not from cron.
# Cron job runs to surface a reminder commit and keep repo state consistent.

if [ ! -f BACKLOG.md ]; then
  echo "BACKLOG.md missing" >&2
  exit 1
fi

NEXT=$(grep -nE '^\- \[ \] ' BACKLOG.md | head -n 1 | sed -E 's/^([0-9]+):\- \[ \] (.+)$/\2/') || true

if [ -z "${NEXT:-}" ]; then
  echo "No pending cities." >&2
  exit 0
fi

STAMP=$(date -u +%F)
mkdir -p controller
OUT="controller/next-city-${STAMP}.txt"
echo "NEXT_CITY=${NEXT}" > "$OUT"

git add "$OUT" || true
if git diff --cached --quiet; then
  exit 0
fi

git commit -m "chore: controller tick (next=${NEXT})" || true
# Push if possible
if git remote -v | grep -q origin; then
  git push || true
fi
