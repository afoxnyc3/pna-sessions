#!/usr/bin/env bash
# publish_md.sh — Bundle one or more markdown files into a single styled
# HTML and hand it to publish.sh.
#
# Usage:
#   publish_md.sh \
#     --title "Title" \
#     --type session|diagram|brainstorm|design \
#     --agent "agent_id" \
#     [--tags "tag1,tag2"] \
#     [--intro "/path/to/intro.md"] \
#     <md_file> [<md_file> ...]
#
# Each <md_file> can optionally be prefixed with "Header::" to add a
# top-level section header before its content. Example:
#   "SPEC::./SPEC.md"
#
# Renders with pandoc using the same compact serif style as existing
# session/design pages, then calls publish.sh which copies the HTML
# into the right MC subfolder, updates manifest.json, and commits.

set -euo pipefail

REPO="${PNA_SESSIONS_REPO:-$HOME/dev/projects/pna-sessions}"
PUBLISH="$REPO/scripts/publish.sh"

TITLE="" TYPE="design" AGENT="main" TAGS="" INTRO=""
FILES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title) TITLE="$2"; shift 2 ;;
    --type)  TYPE="$2";  shift 2 ;;
    --agent) AGENT="$2"; shift 2 ;;
    --tags)  TAGS="$2";  shift 2 ;;
    --intro) INTRO="$2"; shift 2 ;;
    --) shift; FILES+=("$@"); break ;;
    -*) echo "Unknown flag: $1" >&2; exit 1 ;;
    *) FILES+=("$1"); shift ;;
  esac
done

if [[ -z "$TITLE" || ${#FILES[@]} -eq 0 ]]; then
  echo "ERROR: --title and at least one markdown file are required" >&2
  exit 1
fi

# ── Build a temporary combined markdown ────────────────────────────────────
TMP_MD=$(mktemp -t pna_md.XXXXXX.md)
trap 'rm -f "$TMP_MD" "$TMP_HTML"' EXIT

{
  echo "% $TITLE"
  echo "% $AGENT"
  echo "% $(date '+%Y-%m-%d')"
  echo
  if [[ -n "$INTRO" && -f "$INTRO" ]]; then
    cat "$INTRO"
    echo
    echo
  fi
  for entry in "${FILES[@]}"; do
    if [[ "$entry" == *"::"* ]]; then
      header="${entry%%::*}"
      path="${entry##*::}"
    else
      header=""
      path="$entry"
    fi
    if [[ ! -f "$path" ]]; then
      echo "WARNING: skipping missing file: $path" >&2
      continue
    fi
    if [[ -n "$header" ]]; then
      echo
      echo "---"
      echo
      echo "# $header"
      echo
      echo "*Source: \`$path\`*"
      echo
    fi
    cat "$path"
    echo
    echo
  done
} > "$TMP_MD"

# ── Pandoc render with compact serif style (matches existing artifacts) ───
TMP_HTML=$(mktemp -t pna_md.XXXXXX.html)

PANDOC_CSS='body { max-width: 920px; margin: 2.5rem auto; padding: 0 1.25rem; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif; color: #1a1a1a; line-height: 1.65; font-size: 16px; background: #fafafa; }
h1 { font-size: 2rem; margin-top: 0; color: #0a0a0a; border-bottom: 2px solid #eaeaea; padding-bottom: 0.6rem; }
h2 { font-size: 1.4rem; margin-top: 2.2rem; color: #0a0a0a; border-bottom: 1px solid #f0f0f0; padding-bottom: 0.35rem; }
h3 { font-size: 1.1rem; margin-top: 1.6rem; color: #222; }
h4 { font-size: 1rem;   margin-top: 1.4rem; color: #333; }
p, li { color: #1f1f1f; }
em { color: #555; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.9em; }
code { background: #f0f0f0; padding: 0.08em 0.35em; border-radius: 3px; }
pre { background: #f4f4f4; padding: 1rem; border-radius: 6px; overflow-x: auto; border: 1px solid #e5e5e5; }
pre code { background: transparent; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0 1.5rem; font-size: 0.93em; }
th, td { border: 1px solid #e0e0e0; padding: 0.55rem 0.75rem; text-align: left; vertical-align: top; }
th { background: #f0f0f0; font-weight: 600; }
tr:nth-child(even) td { background: #fcfcfc; }
a { color: #0a66c2; text-decoration: none; }
a:hover { text-decoration: underline; }
blockquote { border-left: 3px solid #ccc; padding-left: 1rem; color: #555; margin: 1rem 0; }
hr { border: none; border-top: 1px solid #d8d8d8; margin: 2.5rem 0; }
.footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #eaeaea; font-size: 0.85em; color: #777; }'

pandoc "$TMP_MD" \
  --from markdown+yaml_metadata_block+pipe_tables+task_lists+raw_html \
  --to html5 \
  --standalone \
  --metadata "title=$TITLE" \
  --css /dev/stdin \
  --no-highlight \
  -o "$TMP_HTML" <<< "$PANDOC_CSS" 2>&1 || {
    # Pandoc may not accept --css /dev/stdin on all platforms; fall back to embedded style
    pandoc "$TMP_MD" \
      --from markdown+yaml_metadata_block+pipe_tables+task_lists+raw_html \
      --to html5 \
      --standalone \
      --metadata "title=$TITLE" \
      --no-highlight \
      -H <(printf '<style>%s</style>' "$PANDOC_CSS") \
      -o "$TMP_HTML"
  }

# ── Hand to publish.sh ─────────────────────────────────────────────────────
ARGS=(--file "$TMP_HTML" --title "$TITLE" --type "$TYPE" --agent "$AGENT")
if [[ -n "$TAGS" ]]; then
  ARGS+=(--tags "$TAGS")
fi

"$PUBLISH" "${ARGS[@]}"
