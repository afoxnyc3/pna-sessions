#!/usr/bin/env python3
"""
add_to_manifest.py — Register an existing artifact in manifest.json.

Usage:
  python3 add_to_manifest.py \
    --path "diagrams/foo.html" \
    --title "Title" \
    --agent "principal_architect" \
    --type diagram \
    [--tags "tag1,tag2"]
    [--date "2026-04-19"]
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MANIFEST_FILE = REPO_ROOT / "manifest.json"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--agent", default="main")
    parser.add_argument("--type", default="diagram",
                        choices=["session", "diagram", "brainstorm", "design"])
    parser.add_argument("--tags", default="")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    manifest = json.loads(MANIFEST_FILE.read_text()) if MANIFEST_FILE.exists() else []
    
    # Avoid duplicates
    if any(e["path"] == args.path for e in manifest):
        print(f"Already in manifest: {args.path}")
        return

    manifest.append({
        "path": args.path,
        "date": date_str,
        "title": args.title,
        "agent": args.agent,
        "tags": tags,
        "type": args.type,
    })
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
    print(f"Added: {args.path}")

if __name__ == "__main__":
    main()
