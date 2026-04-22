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
        def clean(s, limit):
            """Truncate and collapse whitespace so the value stays on one JSON line."""
            if s is None:
                return ""
            s = str(s)[:limit]
            # Collapse newlines/tabs to spaces so json.dumps produces a single-line string
            return s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")

        result_full = row["result"] or ""
        task = {
            "id": row["id"],
            "title": clean(row["title"], 120),
            "prompt": clean(row["prompt"], 800),
            "assigned_agent": row["assigned_agent"],
            "status": row["status"],
            "priority": row["priority"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            # Preview only — full result lives in pna-sessions
            "result": clean(result_full, 600) + ("…" if len(result_full) > 600 else ""),
            "result_length": len(result_full),
            "error": clean(row["error"], 400),
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

    # Match the ENTIRE line starting with window.__KANBAN_DATA__ (handles any JSON value, not just {})
    pattern = re.compile(r"^window\.__KANBAN_DATA__\s*=\s*.*$", re.MULTILINE)
    new_source, n = pattern.subn(replacement, source, count=1)

    if n == 0:
        print(
            "[export_kanban] Error: could not find 'window.__KANBAN_DATA__' line in kanban.html.",
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
