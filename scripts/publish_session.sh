#!/usr/bin/env bash
# publish_session.sh — Generate an HTML session artifact and push to GitHub.
# Vercel auto-deploys on push.
#
# Usage:
#   publish_session.sh --title "Title" --agent "agent_id" \
#                      --body-md /path/to/summary.md \
#                      [--type session|diagram|brainstorm|design] \
#                      [--tags "tag1,tag2"]

set -euo pipefail

REPO="${PNA_SESSIONS_REPO:-$HOME/dev/projects/pna-sessions}"
SCRIPT_DIR="$REPO/scripts"

FILENAME=$(python3 "$SCRIPT_DIR/generate_session.py" "$@")

if [ -z "$FILENAME" ]; then
  echo "ERROR: generate_session.py produced no output" >&2
  exit 1
fi

echo "Generated: sessions/$FILENAME"

cd "$REPO"
git add "sessions/$FILENAME" manifest.json
git commit -m "session: $FILENAME"
git push origin main

echo "Pushed. Vercel will deploy in ~30s."
echo "URL: https://pna-sessions.vercel.app/sessions/${FILENAME%.html}"
