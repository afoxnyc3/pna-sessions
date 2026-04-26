#!/bin/bash
# refresh.sh — Auto-refresh backlog, kanban, and tracing pages and push to GitHub.
# Installed as a launchd agent running every 30 minutes.
# GitHub push triggers Vercel auto-deploy (~30s).

set -euo pipefail

REPO="$HOME/dev/projects/pna-sessions"
LOG_PREFIX="[pna-refresh $(date '+%Y-%m-%d %H:%M:%S')]"

cd "$REPO"

echo "$LOG_PREFIX Starting refresh"

# Run all four export scripts (each injects data into its HTML in-place,
# except sync_library which writes library_data.json consumed by library.html).
python3 scripts/export_backlog.py || echo "$LOG_PREFIX WARNING: export_backlog.py failed"
python3 scripts/export_kanban.py  || echo "$LOG_PREFIX WARNING: export_kanban.py failed"
python3 scripts/export_trace.py   || echo "$LOG_PREFIX WARNING: export_trace.py failed"
python3 scripts/sync_library.py   || echo "$LOG_PREFIX WARNING: sync_library.py failed"

# Only commit and push if something actually changed
if git diff --quiet backlog.html kanban.html tracing.html library_data.json; then
  echo "$LOG_PREFIX No changes — skipping push"
  exit 0
fi

git add backlog.html kanban.html tracing.html library_data.json
git commit -m "data: auto-refresh $(date '+%Y-%m-%d %H:%M')"

# Auth via gh token
if command -v gh &>/dev/null; then
  TOKEN=$(gh auth token 2>/dev/null || echo "")
  if [[ -n "$TOKEN" ]]; then
    REPO_PATH=$(git remote get-url origin | sed 's|.*github.com[:/]||' | sed 's|\.git$||' | sed 's|https://[^@]*@github.com/||')
    git remote set-url origin "https://${TOKEN}@github.com/${REPO_PATH}.git"
  fi
fi

git push origin main
echo "$LOG_PREFIX Pushed — Vercel deploying"
