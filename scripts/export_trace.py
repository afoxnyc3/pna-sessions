#!/usr/bin/env python3
"""
export_trace.py
Export agent session token/cost tracing data from claudeclaw.db into tracing.html.

Usage:
    python3 scripts/export_trace.py
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / "dev" / "claudeclaw" / "store" / "claudeclaw.db"
SCRIPT_DIR = Path(__file__).parent
HTML_PATH = SCRIPT_DIR.parent / "tracing.html"

MISSIONS_QUERY = """
  SELECT
    id,
    title,
    assigned_agent,
    status,
    priority,
    substr(result, 1, 200)   AS result_preview,
    error,
    created_at,
    started_at,
    completed_at,
    CASE
      WHEN completed_at IS NOT NULL AND started_at IS NOT NULL
        THEN completed_at - started_at
      ELSE NULL
    END AS duration_secs
  FROM mission_tasks
  WHERE status IN ('completed', 'failed', 'queued', 'running')
  ORDER BY COALESCE(completed_at, created_at) DESC
  LIMIT 60
"""


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
            COUNT(*)                                       AS turns,
            MAX(tu.context_tokens)                        AS peak_context,
            SUM(tu.output_tokens)                         AS total_output,
            ROUND(SUM(tu.cost_usd), 4)                    AS total_cost,
            SUM(tu.did_compact)                           AS compactions,
            MIN(tu.created_at)                            AS session_start,
            MAX(tu.created_at)                            AS session_end,
            (MAX(tu.created_at) - MIN(tu.created_at))    AS duration_secs
        FROM token_usage tu
        GROUP BY tu.session_id
        ORDER BY session_start DESC
        LIMIT 50
    """

    join_query = """
        SELECT
            tu.session_id,
            COUNT(*)                                       AS turns,
            MAX(tu.context_tokens)                        AS peak_context,
            SUM(tu.output_tokens)                         AS total_output,
            ROUND(SUM(tu.cost_usd), 4)                    AS total_cost,
            SUM(tu.did_compact)                           AS compactions,
            MIN(tu.created_at)                            AS session_start,
            MAX(tu.created_at)                            AS session_end,
            (MAX(tu.created_at) - MIN(tu.created_at))    AS duration_secs,
            s.agent_id                                    AS agent_id
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

    clean = []
    for r in rows:
        dur = r.get("duration_secs")
        clean.append({
            "session_id":    r.get("session_id") or "",
            "turns":         int(r.get("turns") or 0),
            "peak_context":  int(r.get("peak_context") or 0),
            "total_output":  int(r.get("total_output") or 0),
            "total_cost":    float(r.get("total_cost") or 0.0),
            "compactions":   int(r.get("compactions") or 0),
            "session_start": int(r.get("session_start") or 0),
            "session_end":   int(r.get("session_end") or 0),
            "duration_secs": int(dur) if dur is not None else None,
            "agent_id":      r.get("agent_id") or None,
        })
    return clean


def get_missions(db_path: Path) -> list[dict]:
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    except Exception as exc:
        print(f"[warn] Could not open DB for missions: {exc}", file=sys.stderr)
        return []

    # Check table exists
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='mission_tasks'"
        )
        if cur.fetchone() is None:
            conn.close()
            return []
    except Exception:
        conn.close()
        return []

    rows = []
    try:
        cur = conn.execute(MISSIONS_QUERY)
        rows = [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        print(f"[warn] Missions query failed: {exc}", file=sys.stderr)

    conn.close()

    clean = []
    for r in rows:
        dur = r.get("duration_secs")
        clean.append({
            "id":             r.get("id") or "",
            "title":          r.get("title") or "",
            "assigned_agent": r.get("assigned_agent") or None,
            "status":         r.get("status") or "queued",
            "priority":       int(r.get("priority") or 0),
            "result_preview": r.get("result_preview") or None,
            "error":          r.get("error") or None,
            "created_at":     int(r.get("created_at") or 0),
            "started_at":     int(r.get("started_at")) if r.get("started_at") else None,
            "completed_at":   int(r.get("completed_at")) if r.get("completed_at") else None,
            "duration_secs":  int(dur) if dur is not None else None,
        })
    return clean


def _replace_window_var(source: str, var_name: str, json_blob: str) -> str:
    """Replace window.__VAR__ = [...] with new JSON.

    Handles both the initial empty placeholder and previously-injected data.
    The closing ] of a json.dumps(indent=2) array is always at column 0 on its
    own line, so we anchor with ^] in MULTILINE mode to avoid false matches
    against ] characters inside string values.
    """
    placeholder = f"window.__{var_name}__ = []"
    replacement = f"window.__{var_name}__ = {json_blob}"

    # Fast path: empty placeholder still in source
    if placeholder in source:
        return source.replace(placeholder, replacement, 1)

    # Fallback: replace previously-injected data block
    pattern = re.compile(
        r"window\.__" + re.escape(var_name) + r"__\s*=\s*\[.*?^\]",
        re.DOTALL | re.MULTILINE,
    )
    updated, count = pattern.subn(replacement, source, count=1)
    if count == 0:
        print(
            f"[error] Could not locate window.__{var_name}__ in tracing.html",
            file=sys.stderr,
        )
        sys.exit(1)
    return updated


def inject(html_path: Path, sessions: list[dict], missions: list[dict]) -> None:
    if not html_path.exists():
        print(f"[error] tracing.html not found at {html_path}", file=sys.stderr)
        sys.exit(1)

    source = html_path.read_text(encoding="utf-8")

    source = _replace_window_var(source, "TRACE_DATA", json.dumps(sessions, indent=2))
    source = _replace_window_var(source, "MISSION_DATA", json.dumps(missions, indent=2))

    html_path.write_text(source, encoding="utf-8")


def main() -> None:
    print(f"Reading DB: {DB_PATH}")

    sessions = get_sessions(DB_PATH)
    print(f"Found {len(sessions)} sessions")

    missions = get_missions(DB_PATH)
    print(f"Found {len(missions)} missions")

    print(f"Injecting into: {HTML_PATH}")
    inject(HTML_PATH, sessions, missions)

    print(f"Done -> {HTML_PATH.resolve()}")


if __name__ == "__main__":
    main()
