#!/usr/bin/env python3
"""
export_kanban.py

Queries claudeclaw mission_tasks (last 14 days) and injects the data into
kanban.html as window.__KANBAN_DATA__.

Usage:
    python3 scripts/export_kanban.py
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = Path("/Users/alex/dev/claudeclaw/store/claudeclaw.db")
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
KANBAN_HTML = PROJECT_DIR / "kanban.html"


QUERY = """
SELECT
    id,
    title,
    prompt,
    assigned_agent,
    status,
    priority,
    created_at,
    started_at,
    completed_at,
    result,
    error
FROM mission_tasks
WHERE created_at >= strftime('%s', 'now', '-14 days')
ORDER BY priority DESC, created_at DESC
"""


def load_tasks():
    """Load tasks from DB. Returns empty dict of lists if DB is inaccessible."""
    empty = {"queued": [], "running": [], "completed": [], "failed": []}

    if not DB_PATH.exists():
        print(f"[export_kanban] Warning: DB not found at {DB_PATH}, using empty data.", file=sys.stderr)
        return empty

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(QUERY)
        rows = cur.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        print(f"[export_kanban] Warning: DB error ({exc}), using empty data.", file=sys.stderr)
        return empty

    grouped = {"queued": [], "running": [], "completed": [], "failed": []}

    for row in rows:
        task = {
            "id": row["id"],
            "title": row["title"],
            "prompt": row["prompt"],
            "assigned_agent": row["assigned_agent"],
            "status": row["status"],
            "priority": row["priority"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "result": row["result"],
            "error": row["error"],
        }
        status = row["status"] if row["status"] in grouped else "queued"
        grouped[status].append(task)

    return grouped


def inject_into_html(data: dict) -> Path:
    """Replace window.__KANBAN_DATA__ = {} in kanban.html with real data."""
    if not KANBAN_HTML.exists():
        print(f"[export_kanban] Error: {KANBAN_HTML} not found.", file=sys.stderr)
        sys.exit(1)

    source = KANBAN_HTML.read_text(encoding="utf-8")

    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    replacement = f"window.__KANBAN_DATA__ = {json_str}"

    pattern = r"window\.__KANBAN_DATA__\s*=\s*\{[^}]*\}"
    new_source, n = re.subn(pattern, replacement, source, count=1)

    if n == 0:
        print(
            "[export_kanban] Error: could not find 'window.__KANBAN_DATA__ = {}' placeholder in kanban.html.",
            file=sys.stderr,
        )
        sys.exit(1)

    KANBAN_HTML.write_text(new_source, encoding="utf-8")
    return KANBAN_HTML


def main():
    data = load_tasks()

    total = sum(len(v) for v in data.values())
    print(f"[export_kanban] Loaded {total} tasks "
          f"(queued={len(data['queued'])}, running={len(data['running'])}, "
          f"completed={len(data['completed'])}, failed={len(data['failed'])})")

    out_path = inject_into_html(data)
    print(f"[export_kanban] Done -> {out_path}")


if __name__ == "__main__":
    main()
