#!/usr/bin/env bash
# publish_session.sh — Generate an HTML session page and push to GitHub.
# Vercel auto-deploys from the GitHub repo on push.
#
# Usage:
#   publish_session.sh --title "Session title" --agent "agent_id" \
#                      --body-md /path/to/summary.md [--tags "tag1,tag2"]
#
# Env vars (optional):
#   PNA_SESSIONS_REPO  — absolute path to pna-sessions repo
#                        default: ~/dev/projects/pna-sessions

set -euo pipefail

REPO="${PNA_SESSIONS_REPO:-$HOME/dev/projects/pna-sessions}"
SCRIPT_DIR="$REPO/scripts"

# Pass all args through to the Python generator
FILENAME=$(python3 "$SCRIPT_DIR/generate_session.py" "$@")

if [ -z "$FILENAME" ]; then
  echo "ERROR: generate_session.py produced no output" >&2
  exit 1
fi

echo "Generated: sessions/$FILENAME"

# Commit and push
cd "$REPO"
git add "sessions/$FILENAME" sessions/index.json
git commit -m "session: $FILENAME"
git push origin main

echo "Pushed. Vercel will deploy in ~30s."
echo "URL: https://pna-sessions.vercel.app/sessions/${FILENAME%.html}"
