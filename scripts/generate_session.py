#!/usr/bin/env python3
"""
generate_session.py — Creates a self-contained HTML session summary and
registers it in manifest.json at the repo root.

Usage:
  python3 generate_session.py \
    --title "Title" \
    --agent "principal_architect" \
    --body-md path/to/summary.md \
    [--type session|diagram|brainstorm|design|research|postmortem] \
    [--tags "tag1,tag2"]

Or pipe markdown body via stdin:
  echo "# Summary..." | python3 generate_session.py --title "..." --agent "..."

Output:
  sessions/YYYY-MM-DD-HHMMSS.html  (created)
  manifest.json                    (updated at repo root)
  Prints the filename on stdout.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = REPO_ROOT / "sessions"
MANIFEST_FILE = REPO_ROOT / "manifest.json"


def parse_frontmatter(md: str):
    """Extract YAML-style frontmatter between --- delimiters at top of markdown.
    Returns (dict, remaining_markdown_without_frontmatter).
    """
    lines = md.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, md
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, md
    fm = {}
    for line in lines[1:end_idx]:
        m = re.match(r"^([\w_]+):\s*(.*)", line.strip())
        if m:
            fm[m.group(1)] = m.group(2).strip()
    remaining = "".join(lines[end_idx + 1:])
    return fm, remaining


def md_to_html(md: str) -> str:
    lines = md.splitlines()
    html_lines = []
    in_code = False
    in_ul = False
    in_ol = False
    in_table = False
    table_head_done = False

    def close_lists():
        nonlocal in_ul, in_ol, in_table, table_head_done
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False
        if in_table:
            if not table_head_done:
                html_lines.append("</thead><tbody>")
            html_lines.append("</tbody></table></div>")
            in_table = False
            table_head_done = False

    for line in lines:
        # Code block toggle
        if line.strip().startswith("```"):
            if not in_code:
                lang = line.strip()[3:].strip() or "text"
                close_lists()
                html_lines.append(f'<pre><code class="lang-{lang}">')
                in_code = True
            else:
                html_lines.append("</code></pre>")
                in_code = False
            continue

        if in_code:
            html_lines.append(_esc(line))
            continue

        # Table row (starts and contains |)
        stripped = line.strip()
        if stripped.startswith("|") and "|" in stripped[1:]:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # Separator row: | --- | :---: | etc.
            if cells and all(re.match(r"^:?-+:?$", c) for c in cells if c.strip()):
                if in_table and not table_head_done:
                    html_lines.append("</thead><tbody>")
                    table_head_done = True
                continue
            if not in_table:
                close_lists()
                html_lines.append('<div class="table-wrapper"><table>')
                html_lines.append("<thead><tr>")
                for c in cells:
                    html_lines.append(f"<th>{_inline(c)}</th>")
                html_lines.append("</tr>")
                in_table = True
                table_head_done = False
            else:
                html_lines.append("<tr>")
                for c in cells:
                    html_lines.append(f"<td>{_inline(c)}</td>")
                html_lines.append("</tr>")
            continue

        # Headings
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            close_lists()
            level = len(m.group(1))
            html_lines.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue

        # Horizontal rule
        if re.match(r"^---+$", line.strip()):
            close_lists()
            html_lines.append("<hr>")
            continue

        # Checklist item
        m = re.match(r"^[-*]\s+\[([ x])\]\s+(.*)", line)
        if m:
            checked = " checked" if m.group(1) == "x" else ""
            if not in_ul:
                if in_ol:
                    html_lines.append("</ol>")
                    in_ol = False
                html_lines.append('<ul class="checklist">')
                in_ul = True
            html_lines.append(
                f'<li><input type="checkbox" disabled{checked}> {_inline(m.group(2))}</li>'
            )
            continue

        # Unordered list item
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            if not in_ul:
                if in_ol:
                    html_lines.append("</ol>")
                    in_ol = False
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{_inline(m.group(1))}</li>")
            continue

        # Ordered list item
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            if not in_ol:
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"<li>{_inline(m.group(1))}</li>")
            continue

        # Blank line
        if not line.strip():
            close_lists()
            html_lines.append("")
            continue

        # Paragraph
        close_lists()
        html_lines.append(f"<p>{_inline(line)}</p>")

    close_lists()
    if in_code:
        html_lines.append("</code></pre>")

    return "\n".join(html_lines)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", lambda m: f"<code>{_esc(m.group(1))}</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank">\1</a>', s)
    return s


def _confidence_badge(confidence: str) -> str:
    conf_lower = confidence.lower()
    if conf_lower == "high":
        cls = "confidence-high"
    elif conf_lower == "medium":
        cls = "confidence-medium"
    elif conf_lower == "low":
        cls = "confidence-low"
    else:
        cls = "confidence-unknown"
    return f'<span class="confidence-badge {cls}">{_esc(confidence)}</span>'


def build_html(
    title: str,
    agent: str,
    date_str: str,
    artifact_type: str,
    tags: list,
    body_html: str,
    frontmatter: dict = None,
) -> str:
    if frontmatter is None:
        frontmatter = {}
    tag_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
    type_colors = {
        "session":    "#22c55e",
        "diagram":    "#3b82f6",
        "brainstorm": "#f59e0b",
        "design":     "#a855f7",
        "research":   "#06b6d4",
        "postmortem": "#ef4444",
    }
    type_color = type_colors.get(artifact_type, "#666")

    research_css = ""
    research_meta_html = ""
    research_js = ""
    postmortem_css = ""
    postmortem_meta_html = ""

    if artifact_type == "postmortem":
        postmortem_css = """
    /* ── Postmortem-specific styles ── */
    .pm-meta {
      max-width: 860px; margin: 0 auto;
      padding: 20px 32px 20px;
      display: flex; flex-wrap: wrap; gap: 20px;
      border-bottom: 1px solid var(--border);
    }
    .pm-field { display: flex; flex-direction: column; gap: 4px; min-width: 120px; }
    .pm-label {
      font-size: 9px; text-transform: uppercase; letter-spacing: 0.12em;
      color: var(--muted); font-family: var(--font-mono);
    }
    .pm-value { font-size: 12px; color: var(--text); }
    .severity-badge {
      display: inline-block; font-size: 10px; padding: 2px 8px;
      border-radius: 3px; font-weight: 600; letter-spacing: 0.05em;
      text-transform: uppercase; font-family: var(--font-mono);
    }
    .severity-critical { background: rgba(239,68,68,0.2);  color: #ef4444; }
    .severity-high     { background: rgba(249,115,22,0.2); color: #f97316; }
    .severity-medium   { background: rgba(245,158,11,0.2); color: #f59e0b; }
    .severity-low      { background: rgba(34,197,94,0.15); color: #22c55e; }
    .severity-unknown  { background: rgba(102,102,102,0.2); color: var(--muted); }
    .pm-status-resolved { color: #22c55e; }
    /* Section accent borders */
    article h2 { border-left: 3px solid #ef4444; padding-left: 10px; border-bottom: none; margin-top: 28px; }
    article h3 { color: #aaa; }
    .rca-box {
      background: rgba(239,68,68,0.05); border: 1px solid rgba(239,68,68,0.2);
      border-radius: 6px; padding: 16px 20px; margin: 8px 0 20px;
    }
    .fix-box {
      background: rgba(34,197,94,0.05); border: 1px solid rgba(34,197,94,0.15);
      border-radius: 6px; padding: 16px 20px; margin: 8px 0 20px;
    }
    /* Tables */
    .table-wrapper { overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%; margin: 12px 0 16px; }
    article table { width: 100%; border-collapse: collapse; font-size: 12px; }
    article table th {
      text-align: left; font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted); padding: 8px 10px;
      border-bottom: 1px solid var(--border); white-space: nowrap;
    }
    article table td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
    article table tr:nth-child(even) td { background: var(--surface); }
    @media (max-width: 640px) {
      article { font-size: 15px; padding: 20px 16px; }
      .pm-meta { padding: 16px; gap: 12px; }
      article table td, article table th { font-size: 11px; padding: 6px 8px; }
    }"""

        def _severity_badge(severity: str) -> str:
            sev_lower = severity.lower()
            cls_map = {
                "critical": "severity-critical",
                "high": "severity-high",
                "medium": "severity-medium",
                "low": "severity-low",
            }
            cls = cls_map.get(sev_lower, "severity-unknown")
            return f'<span class="severity-badge {cls}">{_esc(severity)}</span>'

        incident    = _esc(frontmatter.get("incident", title))
        severity    = frontmatter.get("severity", "")
        sev_badge   = _severity_badge(severity) if severity else "&mdash;"
        detected    = _esc(frontmatter.get("detected_at", ""))
        resolved    = _esc(frontmatter.get("resolved_at", ""))
        duration    = _esc(frontmatter.get("duration", ""))
        status      = frontmatter.get("status", "resolved")
        status_cls  = "pm-status-resolved" if status.lower() == "resolved" else ""

        postmortem_meta_html = f"""
  <div class="pm-meta">
    <div class="pm-field">
      <span class="pm-label">Incident</span>
      <span class="pm-value">{incident}</span>
    </div>
    <div class="pm-field">
      <span class="pm-label">Severity</span>
      <span class="pm-value">{sev_badge}</span>
    </div>
    <div class="pm-field">
      <span class="pm-label">Status</span>
      <span class="pm-value {status_cls}">{_esc(status)}</span>
    </div>
    <div class="pm-field">
      <span class="pm-label">Detected</span>
      <span class="pm-value">{detected}</span>
    </div>
    <div class="pm-field">
      <span class="pm-label">Resolved</span>
      <span class="pm-value">{resolved}</span>
    </div>
    <div class="pm-field">
      <span class="pm-label">Duration</span>
      <span class="pm-value">{duration}</span>
    </div>
  </div>"""

    if artifact_type == "research":
        research_css = """
    /* ── Research-specific styles ── */
    .research-meta {
      max-width: 860px; margin: 0 auto;
      padding: 20px 32px 0;
      display: flex; flex-wrap: wrap; gap: 20px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 20px;
    }
    .meta-field { display: flex; flex-direction: column; gap: 4px; min-width: 140px; }
    .meta-label {
      font-size: 9px; text-transform: uppercase; letter-spacing: 0.12em;
      color: var(--muted); font-family: var(--font-mono);
    }
    .meta-value { font-size: 12px; color: var(--text); }
    .confidence-badge {
      display: inline-block; font-size: 10px; padding: 2px 8px;
      border-radius: 3px; font-weight: 600; letter-spacing: 0.05em;
      text-transform: uppercase; font-family: var(--font-mono);
    }
    .confidence-high   { background: rgba(34,197,94,0.15);  color: #22c55e; }
    .confidence-medium { background: rgba(245,158,11,0.15); color: #f59e0b; }
    .confidence-low    { background: rgba(239,68,68,0.15);  color: #ef4444; }
    .confidence-unknown { background: rgba(102,102,102,0.2); color: var(--muted); }
    /* Tables */
    .table-wrapper { overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%; margin: 12px 0 16px; }
    article table { width: 100%; border-collapse: collapse; font-size: 12px; }
    article table th {
      text-align: left; font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted); padding: 8px 10px;
      border-bottom: 1px solid var(--border); white-space: nowrap;
    }
    article table td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
    article table tr:nth-child(even) td { background: var(--surface); }
    article table.table-source td, article table.table-source th { font-size: 11px; }
    /* Section cards */
    .section-executive {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; padding: 16px 20px; margin: 4px 0 20px;
    }
    .section-executive p { font-size: 15px; line-height: 1.8; margin-bottom: 0; }
    .section-executive h2 { margin-top: 0; }
    .section-feynman {
      border-left: 3px solid #06b6d4;
      padding-left: 16px; margin: 4px 0 20px;
    }
    .section-feynman h2 { color: #06b6d4; }
    article ol.insights-list { margin: 8px 0 12px 20px; }
    article ol.insights-list li { margin-bottom: 10px; line-height: 1.65; }
    /* Mobile */
    @media (max-width: 640px) {
      article { font-size: 15px; padding: 20px 16px; }
      .research-meta { padding: 16px 16px 16px; gap: 12px; }
      .meta-field { min-width: 120px; }
      article table.table-source td,
      article table.table-source th { font-size: 11px; padding: 5px 6px; }
      article table td, article table th { padding: 6px 8px; }
    }"""

        query      = _esc(frontmatter.get("query", ""))
        fm_agent   = _esc(frontmatter.get("agent", agent))
        completed  = _esc(frontmatter.get("completed_at", date_str))
        confidence = frontmatter.get("confidence", "")
        conf_badge = _confidence_badge(confidence) if confidence else "&mdash;"

        research_meta_html = f"""
  <div class="research-meta">
    <div class="meta-field">
      <span class="meta-label">Query</span>
      <span class="meta-value">{query}</span>
    </div>
    <div class="meta-field">
      <span class="meta-label">Agent</span>
      <span class="meta-value">{fm_agent}</span>
    </div>
    <div class="meta-field">
      <span class="meta-label">Completed</span>
      <span class="meta-value">{completed}</span>
    </div>
    <div class="meta-field">
      <span class="meta-label">Confidence</span>
      <span class="meta-value">{conf_badge}</span>
    </div>
  </div>"""

        research_js = """
  <script>
    document.addEventListener('DOMContentLoaded', function () {
      // Mark Source Ledger tables (look for table after a heading containing "source")
      document.querySelectorAll('article h2').forEach(function (h) {
        if (h.textContent.trim().toLowerCase().includes('source')) {
          var next = h.nextElementSibling;
          if (next && next.classList.contains('table-wrapper')) {
            var tbl = next.querySelector('table');
            if (tbl) tbl.classList.add('table-source');
          }
        }
      });

      // Wrap sections for visual treatment
      wrapSection('executive summary', 'section-executive');
      wrapSection('feynman bridge', 'section-feynman');

      // Style Actionable Insights ordered list
      document.querySelectorAll('article h2').forEach(function (h) {
        if (h.textContent.trim().toLowerCase().includes('actionable insights')) {
          var next = h.nextElementSibling;
          if (next && next.tagName === 'OL') next.classList.add('insights-list');
        }
      });
    });

    function wrapSection(headingText, wrapClass) {
      var article = document.querySelector('article');
      if (!article) return;
      var target = null;
      article.querySelectorAll('h2').forEach(function (h) {
        if (h.textContent.trim().toLowerCase().includes(headingText)) target = h;
      });
      if (!target) return;
      var wrapper = document.createElement('div');
      wrapper.className = wrapClass;
      target.parentNode.insertBefore(wrapper, target);
      var node = target;
      while (node) {
        var next = node.nextSibling;
        var isNewSection =
          node !== target &&
          node.nodeType === 1 &&
          /^H[1-3]$/.test(node.tagName);
        if (isNewSection) break;
        wrapper.appendChild(node);
        node = next;
      }
    }
  </script>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_esc(title)} — P&amp;A</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=Fira+Code:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #060d1f; --surface: #0d1b35; --surface-2: #111e3d; --surface-3: #0a1628;
      --border: rgba(59,130,246,0.15); --border-strong: rgba(59,130,246,0.35);
      --text: #e2e8f0; --muted: #94a3b8; --text-muted: #475569;
      --primary: #3b82f6; --accent: #3b82f6;
      --code-bg: #0a1628; --tag-bg: #111e3d; --tag-border: rgba(59,130,246,0.15);
      --link: #93c5fd; --type-color: {type_color};
      --font-body: 'DM Sans', system-ui, sans-serif;
      --font-mono: 'Fira Code', 'Courier New', monospace;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background-color: var(--bg); background-image: linear-gradient(rgba(59,130,246,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.05) 1px, transparent 1px); background-size: 32px 32px; color: var(--text); font-family: var(--font-body); font-size: 14px; line-height: 1.7; min-height: 100vh; }}
    header {{ border-bottom: 1px solid var(--border); padding: 18px 32px; display: flex; align-items: center; justify-content: space-between; }}
    .back {{ font-size: 11px; color: var(--muted); text-decoration: none; font-family: var(--font-mono); }}
    .back:hover {{ color: var(--accent); }}
    .header-meta {{ font-size: 11px; color: var(--muted); font-family: var(--font-mono); }}
    .hero {{ border-bottom: 1px solid var(--border); padding: 32px; max-width: 860px; margin: 0 auto; }}
    .type-badge {{ display: inline-flex; align-items: center; gap: 6px; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--type-color); font-family: var(--font-mono); margin-bottom: 10px; }}
    .type-dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--type-color); }}
    .agent-label {{ font-size: 10px; color: var(--muted); font-family: var(--font-mono); margin-bottom: 6px; }}
    h1 {{ font-size: 22px; font-weight: 600; color: var(--accent); line-height: 1.3; margin-bottom: 12px; }}
    .tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }}
    .tag {{ font-size: 10px; padding: 3px 8px; background: var(--tag-bg); border: 1px solid var(--tag-border); border-radius: 3px; color: var(--muted); font-family: var(--font-mono); }}
    article {{ max-width: 860px; margin: 0 auto; padding: 32px; }}
    article h1 {{ font-size: 20px; margin: 28px 0 12px; color: var(--accent); }}
    article h2 {{ font-size: 15px; margin: 28px 0 10px; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
    article h3 {{ font-size: 13px; margin: 20px 0 8px; color: var(--text); text-transform: uppercase; letter-spacing: 0.06em; }}
    article p {{ margin-bottom: 12px; }}
    article ul {{ margin: 8px 0 12px 20px; }}
    article ol {{ margin: 8px 0 12px 20px; }}
    article ul.checklist {{ list-style: none; margin-left: 4px; }}
    article li {{ margin-bottom: 4px; }}
    article hr {{ border: none; border-top: 1px solid var(--border); margin: 24px 0; }}
    article a {{ color: var(--link); text-decoration: none; }}
    article a:hover {{ text-decoration: underline; }}
    article code {{ background: var(--code-bg); padding: 1px 5px; border-radius: 3px; font-family: var(--font-mono); font-size: 12px; color: #93c5fd; }}
    article pre {{ background: var(--code-bg); border: 1px solid var(--border); border-radius: 6px; padding: 16px; overflow-x: auto; margin: 12px 0 16px; }}
    article pre code {{ background: none; padding: 0; font-size: 12px; line-height: 1.55; }}{research_css}{postmortem_css}
    footer {{ border-top: 1px solid var(--border); padding: 16px 32px; text-align: center; font-size: 11px; color: var(--muted); font-family: var(--font-mono); margin-top: 48px; }}
  </style>
</head>
<body>
  <header>
    <a class="back" href="../">&#8592; archive</a>
    <div class="header-meta">{_esc(date_str)}</div>
  </header>
  <div class="hero">
    <div class="type-badge"><span class="type-dot"></span>{_esc(artifact_type)}</div>
    <div class="agent-label">{_esc(agent)}</div>
    <h1>{_esc(title)}</h1>
    <div class="tags">{tag_html}</div>
  </div>{research_meta_html}{postmortem_meta_html}
  <article>
    {body_html}
  </article>
  <footer>Principal &amp; Agent &mdash; internal</footer>{research_js}
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--agent", default="main")
    parser.add_argument("--body-md", help="Path to markdown file. If omitted, reads stdin.")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument(
        "--type",
        default="session",
        choices=["session", "diagram", "brainstorm", "design", "research", "postmortem"],
    )
    args = parser.parse_args()

    if args.body_md:
        body_md = Path(args.body_md).read_text()
    else:
        body_md = sys.stdin.read()

    frontmatter, body_md = parse_frontmatter(body_md)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d-%H%M%S")
    filename = f"{timestamp}.html"

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    body_html = md_to_html(body_md)
    html = build_html(
        title=args.title,
        agent=args.agent,
        date_str=date_str,
        artifact_type=args.type,
        tags=tags,
        body_html=body_html,
        frontmatter=frontmatter,
    )

    out_path = SESSIONS_DIR / filename
    out_path.write_text(html)

    manifest = json.loads(MANIFEST_FILE.read_text()) if MANIFEST_FILE.exists() else []
    manifest.append({
        "path": f"sessions/{filename}",
        "date": date_str,
        "title": args.title,
        "agent": args.agent,
        "tags": tags,
        "type": args.type,
    })
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))

    print(filename)


if __name__ == "__main__":
    main()
