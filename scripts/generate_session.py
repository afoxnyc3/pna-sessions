#!/usr/bin/env python3
"""
generate_session.py — Creates a self-contained HTML session summary and
registers it in sessions/index.json.

Usage:
  python3 generate_session.py \
    --title "Title of this session" \
    --agent "principal_architect" \
    --body-md "path/to/summary.md" \
    [--tags "tag1,tag2"]

Or pipe markdown body via stdin:
  echo "# Summary..." | python3 generate_session.py --title "..." --agent "..."

Output:
  sessions/YYYY-MM-DD-HHMMSS.html  (created)
  sessions/index.json              (updated)
  Prints the filename on stdout so callers can capture it.
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
INDEX_FILE = SESSIONS_DIR / "index.json"

# ── Minimal Markdown → HTML (enough for session notes) ──────────────────────

def md_to_html(md: str) -> str:
    lines = md.splitlines()
    html_lines = []
    in_code = False
    in_list = False

    for line in lines:
        # Code fence
        if line.strip().startswith("```"):
            if not in_code:
                lang = line.strip()[3:].strip() or "text"
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f'<pre><code class="lang-{lang}">')
                in_code = True
            else:
                html_lines.append("</code></pre>")
                in_code = False
            continue

        if in_code:
            html_lines.append(_esc(line))
            continue

        # Headings
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            level = len(m.group(1))
            tag = f"h{level}"
            html_lines.append(f"<{tag}>{_inline(m.group(2))}</{tag}>")
            continue

        # Horizontal rule
        if re.match(r'^---+$', line.strip()):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<hr>")
            continue

        # List items
        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline(m.group(1))}</li>")
            continue

        # Checkboxes
        m = re.match(r'^[-*]\s+\[([ x])\]\s+(.*)', line)
        if m:
            checked = ' checked' if m.group(1) == 'x' else ''
            if not in_list:
                html_lines.append('<ul class="checklist">')
                in_list = True
            html_lines.append(f'<li><input type="checkbox" disabled{checked}> {_inline(m.group(2))}</li>')
            continue

        # Close list on blank line
        if not line.strip():
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("")
            continue

        # Paragraph
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{_inline(line)}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_code:
        html_lines.append("</code></pre>")

    return "\n".join(html_lines)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(s: str) -> str:
    # Bold
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    # Italic
    s = re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)
    # Inline code
    s = re.sub(r'`([^`]+)`', lambda m: f'<code>{_esc(m.group(1))}</code>', s)
    # Links
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', s)
    return s


# ── HTML Template ────────────────────────────────────────────────────────────

def build_html(title: str, agent: str, date_str: str, tags: list[str], body_html: str) -> str:
    tag_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_esc(title)} — P&amp;A Session</title>
  <style>
    :root {{
      --bg: #0d0d0d;
      --surface: #141414;
      --border: #222;
      --text: #e8e8e8;
      --muted: #666;
      --accent: #fff;
      --code-bg: #111;
      --tag-bg: #1e1e1e;
      --tag-border: #333;
      --link: #a0c4ff;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px;
      line-height: 1.7;
      min-height: 100vh;
    }}
    header {{
      border-bottom: 1px solid var(--border);
      padding: 18px 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .back {{
      font-size: 11px;
      color: var(--muted);
      text-decoration: none;
      letter-spacing: 0.08em;
      font-family: 'SF Mono', monospace;
    }}
    .back:hover {{ color: var(--accent); }}
    .header-meta {{
      font-size: 11px;
      color: var(--muted);
      font-family: 'SF Mono', monospace;
    }}
    .hero {{
      border-bottom: 1px solid var(--border);
      padding: 32px;
      max-width: 860px;
      margin: 0 auto;
    }}
    .agent-badge {{
      display: inline-block;
      font-size: 10px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--muted);
      font-family: 'SF Mono', monospace;
      margin-bottom: 10px;
    }}
    h1 {{
      font-size: 22px;
      font-weight: 600;
      color: var(--accent);
      line-height: 1.3;
      margin-bottom: 12px;
    }}
    .tags {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .tag {{
      font-size: 10px;
      padding: 3px 8px;
      background: var(--tag-bg);
      border: 1px solid var(--tag-border);
      border-radius: 3px;
      color: var(--muted);
      font-family: 'SF Mono', monospace;
      letter-spacing: 0.05em;
    }}
    article {{
      max-width: 860px;
      margin: 0 auto;
      padding: 32px;
    }}
    article h1 {{ font-size: 20px; margin: 28px 0 12px; color: var(--accent); }}
    article h2 {{ font-size: 15px; margin: 28px 0 10px; color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
    article h3 {{ font-size: 13px; margin: 20px 0 8px; color: var(--text); text-transform: uppercase; letter-spacing: 0.06em; }}
    article h4 {{ font-size: 13px; margin: 16px 0 6px; color: var(--muted); }}
    article p {{ margin-bottom: 12px; color: var(--text); }}
    article ul {{ margin: 8px 0 12px 20px; }}
    article ul.checklist {{ list-style: none; margin-left: 4px; }}
    article li {{ margin-bottom: 4px; }}
    article hr {{ border: none; border-top: 1px solid var(--border); margin: 24px 0; }}
    article a {{ color: var(--link); text-decoration: none; }}
    article a:hover {{ text-decoration: underline; }}
    article code {{
      background: var(--code-bg);
      padding: 1px 5px;
      border-radius: 3px;
      font-family: 'SF Mono', 'Fira Code', monospace;
      font-size: 12px;
      color: #d4d4d4;
    }}
    article pre {{
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 16px;
      overflow-x: auto;
      margin: 12px 0 16px;
    }}
    article pre code {{
      background: none;
      padding: 0;
      font-size: 12px;
      line-height: 1.55;
    }}
    article input[type=checkbox] {{ accent-color: var(--muted); }}
    footer {{
      border-top: 1px solid var(--border);
      padding: 16px 32px;
      text-align: center;
      font-size: 11px;
      color: var(--muted);
      font-family: 'SF Mono', monospace;
      margin-top: 48px;
    }}
  </style>
</head>
<body>
  <header>
    <a class="back" href="../">&#8592; archive</a>
    <div class="header-meta">{_esc(date_str)}</div>
  </header>
  <div class="hero">
    <span class="agent-badge">{_esc(agent)}</span>
    <h1>{_esc(title)}</h1>
    <div class="tags">{tag_html}</div>
  </div>
  <article>
    {body_html}
  </article>
  <footer>Principal &amp; Agent &mdash; internal</footer>
</body>
</html>"""


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--agent", default="main")
    parser.add_argument("--body-md", help="Path to markdown file. If omitted, reads stdin.")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    args = parser.parse_args()

    # Read markdown
    if args.body_md:
        body_md = Path(args.body_md).read_text()
    else:
        body_md = sys.stdin.read()

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
        tags=tags,
        body_html=body_html,
    )

    out_path = SESSIONS_DIR / filename
    out_path.write_text(html)

    # Update index.json
    index = json.loads(INDEX_FILE.read_text()) if INDEX_FILE.exists() else []
    index.append({
        "file": filename,
        "date": date_str,
        "title": args.title,
        "agent": args.agent,
        "tags": tags,
    })
    INDEX_FILE.write_text(json.dumps(index, indent=2))

    print(filename)


if __name__ == "__main__":
    main()
