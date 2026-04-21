#!/usr/bin/env python3
"""
export_backlog.py -- inject mission_tasks data into backlog.html
Usage: python3 scripts/export_backlog.py
"""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
BACKLOG_HTML = os.path.join(PROJECT_DIR, "backlog.html")
DB_PATH = os.path.expanduser("~/dev/claudeclaw/store/claudeclaw.db")


def fetch_tasks():
    if not os.path.exists(DB_PATH):
        print(f"[warn] DB not found at {DB_PATH}, using empty data", file=sys.stderr)
        return []

    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("""
            SELECT id, title, prompt, assigned_agent, status, priority,
                   created_at, started_at, completed_at, error
            FROM mission_tasks
            WHERE status != 'cancelled'
            ORDER BY priority DESC, created_at ASC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        con.close()
        return rows
    except sqlite3.OperationalError as e:
        print(f"[warn] DB query failed: {e}", file=sys.stderr)
        return []


def inject_data(html: str, tasks: list, exported_at: str) -> str:
    # Use a lambda so the replacement string is never interpreted as a regex template.
    data_json = json.dumps(tasks, default=str)

    def replace_data(_m):
        return f"window.__BACKLOG_DATA__ = {data_json};"

    def replace_ts(_m):
        return f'window.__BACKLOG_EXPORTED__ = "{exported_at}";'

    html = re.sub(
        r'window\.__BACKLOG_DATA__\s*=\s*\[.*?\];',
        replace_data,
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r'window\.__BACKLOG_EXPORTED__\s*=\s*"[^"]*";',
        replace_ts,
        html,
    )
    return html


def main():
    if not os.path.exists(BACKLOG_HTML):
        print(f"[error] backlog.html not found at {BACKLOG_HTML}", file=sys.stderr)
        sys.exit(1)

    tasks = fetch_tasks()
    exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with open(BACKLOG_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    html = inject_data(html, tasks, exported_at)

    with open(BACKLOG_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Exported {len(tasks)} task(s) -> {BACKLOG_HTML}")
    print(f"Timestamp: {exported_at}")


if __name__ == "__main__":
    main()
