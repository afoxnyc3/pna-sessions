#!/usr/bin/env bash
# publish.sh — Publish any HTML artifact to pna-sessions and push to GitHub.
# GitHub Pages auto-serves at https://afoxnyc3.github.io/pna-sessions/
#
# Usage:
#   publish.sh --file /path/to/file.html \
#              --title "Title" \
#              --type session|diagram|brainstorm|design \
#              --agent "agent_id" \
#              [--tags "tag1,tag2"]
#
# Env vars:
#   PNA_SESSIONS_REPO  — absolute path to local pna-sessions clone
#                        default: ~/dev/projects/pna-sessions
#   GH_TOKEN           — GitHub token (falls back to `gh auth token`)

set -euo pipefail

REPO="${PNA_SESSIONS_REPO:-$HOME/dev/projects/pna-sessions}"

# ── Parse args ─────────────────────────────────────────────────────────────
FILE="" TITLE="" TYPE="session" AGENT="main" TAGS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)   FILE="$2";   shift 2 ;;
    --title)  TITLE="$2";  shift 2 ;;
    --type)   TYPE="$2";   shift 2 ;;
    --agent)  AGENT="$2";  shift 2 ;;
    --tags)   TAGS="$2";   shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$FILE" || -z "$TITLE" ]]; then
  echo "ERROR: --file and --title are required" >&2
  exit 1
fi

if [[ ! -f "$FILE" ]]; then
  echo "ERROR: File not found: $FILE" >&2
  exit 1
fi

# ── Validate type ───────────────────────────────────────────────────────────
case "$TYPE" in
  session|diagram|brainstorm|design) ;;
  *) echo "ERROR: --type must be one of: session diagram brainstorm design" >&2; exit 1 ;;
esac

# ── Sync repo ───────────────────────────────────────────────────────────────
cd "$REPO"
git pull origin main --quiet 2>/dev/null || true

# ── Name output file ────────────────────────────────────────────────────────
DATE=$(date +%Y-%m-%d)
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -dc '[:alnum:]-' | cut -c1-60)
OUTFILE="${DATE}-${SLUG}.html"
SUBFOLDER="${TYPE}s"   # sessions, diagrams, brainstorms, designs

mkdir -p "$REPO/$SUBFOLDER"
cp "$FILE" "$REPO/$SUBFOLDER/$OUTFILE"

echo "Copied → $SUBFOLDER/$OUTFILE"

# ── Update manifest.json ────────────────────────────────────────────────────
python3 "$REPO/scripts/update_manifest.py" \
  --type "$TYPE" \
  --title "$TITLE" \
  --agent "$AGENT" \
  --path "$SUBFOLDER/$OUTFILE" \
  --date "$DATE" \
  --tags "$TAGS"

# ── Commit + push ───────────────────────────────────────────────────────────
git add "$SUBFOLDER/$OUTFILE" manifest.json
git commit -m "publish($TYPE): $TITLE [$AGENT]"

# Auth: use gh token if available
if command -v gh &>/dev/null; then
  TOKEN=$(gh auth token 2>/dev/null || echo "")
  if [[ -n "$TOKEN" ]]; then
    REMOTE_URL=$(git remote get-url origin)
    REPO_PATH=$(echo "$REMOTE_URL" | sed 's|.*github.com[:/]||' | sed 's|\.git$||')
    git remote set-url origin "https://${TOKEN}@github.com/${REPO_PATH}.git"
  fi
fi

git push origin main
echo ""
echo "Published: https://afoxnyc3.github.io/pna-sessions/$SUBFOLDER/$OUTFILE"
