#!/usr/bin/env python3
"""
export_trace.py
Export agent session token/cost tracing data from claudeclaw.db into tracing.html.

Usage:
    python3 scripts/export_trace.py
"""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / "dev" / "claudeclaw" / "store" / "claudeclaw.db"
SCRIPT_DIR = Path(__file__).parent
HTML_PATH = SCRIPT_DIR.parent / "tracing.html"
PLACEHOLDER = "window.__TRACE_DATA__ = []"


def get_sessions(db_path: Path) -> list[dict]:
    if not db_path.exists():
        print(f"[warn] DB not found at {db_path}, using empty dataset.", file=sys.stderr)
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    except Exception as exc:
        print(f"[warn] Could not open DB: {exc}", file=sys.stderr)
        return []

    # Check whether sessions table exists and has agent_id
    has_sessions = False
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        has_sessions = cur.fetchone() is not None
    except Exception:
        pass

    # Check whether token_usage exists
    try:
        conn.execute("SELECT 1 FROM token_usage LIMIT 1")
    except Exception as exc:
        print(f"[warn] token_usage not accessible: {exc}", file=sys.stderr)
        conn.close()
        return []

    base_query = """
        SELECT
            tu.session_id,
            COUNT(*)                        AS turns,
            MAX(tu.context_tokens)          AS peak_context,
            SUM(tu.output_tokens)           AS total_output,
            ROUND(SUM(tu.cost_usd), 4)      AS total_cost,
            SUM(tu.did_compact)             AS compactions,
            MIN(tu.created_at)              AS session_start,
            MAX(tu.created_at)              AS session_end
        FROM token_usage tu
        GROUP BY tu.session_id
        ORDER BY session_start DESC
        LIMIT 50
    """

    join_query = """
        SELECT
            tu.session_id,
            COUNT(*)                        AS turns,
            MAX(tu.context_tokens)          AS peak_context,
            SUM(tu.output_tokens)           AS total_output,
            ROUND(SUM(tu.cost_usd), 4)      AS total_cost,
            SUM(tu.did_compact)             AS compactions,
            MIN(tu.created_at)              AS session_start,
            MAX(tu.created_at)              AS session_end,
            s.agent_id                      AS agent_id
        FROM token_usage tu
        LEFT JOIN sessions s ON s.session_id = tu.session_id
        GROUP BY tu.session_id
        ORDER BY session_start DESC
        LIMIT 50
    """

    rows = []
    if has_sessions:
        try:
            cur = conn.execute(join_query)
            rows = [dict(r) for r in cur.fetchall()]
        except Exception as exc:
            print(f"[warn] JOIN query failed ({exc}), falling back to base query.", file=sys.stderr)

    if not rows:
        try:
            cur = conn.execute(base_query)
            rows = [dict(r) for r in cur.fetchall()]
            for row in rows:
                row.setdefault("agent_id", None)
        except Exception as exc:
            print(f"[warn] Base query failed: {exc}", file=sys.stderr)

    conn.close()

    # Ensure all fields are JSON-safe
    clean = []
    for r in rows:
        clean.append({
            "session_id":    r.get("session_id") or "",
            "turns":         int(r.get("turns") or 0),
            "peak_context":  int(r.get("peak_context") or 0),
            "total_output":  int(r.get("total_output") or 0),
            "total_cost":    float(r.get("total_cost") or 0.0),
            "compactions":   int(r.get("compactions") or 0),
            "session_start": int(r.get("session_start") or 0),
            "session_end":   int(r.get("session_end") or 0),
            "agent_id":      r.get("agent_id") or None,
        })
    return clean


def inject(html_path: Path, sessions: list[dict]) -> None:
    if not html_path.exists():
        print(f"[error] tracing.html not found at {html_path}", file=sys.stderr)
        sys.exit(1)

    source = html_path.read_text(encoding="utf-8")
    json_blob = json.dumps(sessions, indent=2)
    replacement = f"window.__TRACE_DATA__ = {json_blob}"

    if PLACEHOLDER not in source:
        print(f"[error] Placeholder '{PLACEHOLDER}' not found in tracing.html", file=sys.stderr)
        sys.exit(1)

    updated = source.replace(PLACEHOLDER, replacement, 1)
    html_path.write_text(updated, encoding="utf-8")


def main() -> None:
    print(f"Reading DB: {DB_PATH}")
    sessions = get_sessions(DB_PATH)
    print(f"Found {len(sessions)} sessions")

    print(f"Injecting into: {HTML_PATH}")
    inject(HTML_PATH, sessions)

    print(f"Done → {HTML_PATH.resolve()}")


if __name__ == "__main__":
    main()
