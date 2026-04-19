#!/usr/bin/env python3
"""
update_manifest.py — Upserts an entry in manifest.json at the repo root.

Usage:
  python3 update_manifest.py \
    --type session \
    --title "Session title" \
    --agent "principal_architect" \
    --path "sessions/2026-04-19-123456.html" \
    [--tags "tag1,tag2"]
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MANIFEST = REPO_ROOT / "manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True,
                        choices=["session", "diagram", "brainstorm", "design"])
    parser.add_argument("--title", required=True)
    parser.add_argument("--agent", default="main")
    parser.add_argument("--path", required=True, help="Relative path from repo root")
    parser.add_argument("--date", default="", help="ISO date, defaults to today")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        from datetime import datetime, timezone
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    entries = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []

    # Deduplicate by path
    entries = [e for e in entries if e.get("path") != args.path]

    entries.append({
        "type": args.type,
        "title": args.title,
        "date": date_str,
        "agent": args.agent,
        "path": args.path,
        "tags": tags,
    })

    MANIFEST.write_text(json.dumps(entries, indent=2))
    print(f"manifest.json updated: {len(entries)} entries", file=sys.stderr)


if __name__ == "__main__":
    main()
