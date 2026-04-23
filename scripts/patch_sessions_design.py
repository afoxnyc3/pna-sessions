#!/usr/bin/env python3
"""
patch_sessions_design.py — One-off script to retrofit existing sessions/*.html
with the reference design system (DM Sans + Fira Code, navy palette, blue grid).

Safe to re-run — detects already-patched files via the presence of DM Sans font import.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = REPO_ROOT / "sessions"

FONT_LINK = (
    '  <link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=Fira+Code:wght@400;500;600&display=swap" rel="stylesheet">\n'
)

TITLE_TAG_RE = re.compile(r'(  <title>.*?</title>\n)', re.DOTALL)

# Match the old :root block — type-color value varies per file
ROOT_RE = re.compile(
    r'    :root \{[^}]*--type-color:\s*([^;]+);[^}]*\}',
    re.DOTALL
)

NEW_ROOT_TEMPLATE = (
    '    :root {{\n'
    '      --bg: #060d1f; --surface: #0d1b35; --surface-2: #111e3d; --surface-3: #0a1628;\n'
    '      --border: rgba(59,130,246,0.15); --border-strong: rgba(59,130,246,0.35);\n'
    '      --text: #e2e8f0; --muted: #94a3b8; --text-muted: #475569;\n'
    '      --primary: #3b82f6; --accent: #3b82f6;\n'
    '      --code-bg: #0a1628; --tag-bg: #111e3d; --tag-border: rgba(59,130,246,0.15);\n'
    '      --link: #93c5fd; --type-color: {type_color};\n'
    '      --font-body: \'DM Sans\', system-ui, sans-serif;\n'
    '      --font-mono: \'Fira Code\', \'Courier New\', monospace;\n'
    '    }}'
)

OLD_BODY = (
    "    body { background: var(--bg); color: var(--text); "
    "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; "
    "font-size: 14px; line-height: 1.7; min-height: 100vh; }"
)

NEW_BODY = (
    "    body { background-color: var(--bg); "
    "background-image: linear-gradient(rgba(59,130,246,0.05) 1px, transparent 1px), "
    "linear-gradient(90deg, rgba(59,130,246,0.05) 1px, transparent 1px); "
    "background-size: 32px 32px; "
    "color: var(--text); font-family: var(--font-body); font-size: 14px; line-height: 1.7; min-height: 100vh; }"
)


def patch_file(path: Path) -> bool:
    content = path.read_text(encoding="utf-8")

    # Skip already-patched files
    if "DM+Sans" in content or "DM Sans" in content:
        return False

    original = content

    # 1. Inject font links after </title>
    def inject_fonts(m):
        return m.group(1) + FONT_LINK

    content = TITLE_TAG_RE.sub(inject_fonts, content, count=1)

    # 2. Replace :root block, preserving --type-color
    m = ROOT_RE.search(content)
    if m:
        type_color = m.group(1).strip()
        new_root = NEW_ROOT_TEMPLATE.format(type_color=type_color)
        content = ROOT_RE.sub(new_root, content, count=1)

    # 3. Replace body rule
    content = content.replace(OLD_BODY, NEW_BODY)

    # 4. Replace SF Mono font references
    content = content.replace("'SF Mono', monospace", "var(--font-mono)")
    content = content.replace('"SF Mono", monospace', "var(--font-mono)")

    # 5. Replace old code text color
    content = content.replace("color: #d4d4d4;", "color: #93c5fd;")

    # 6. Replace hardcoded table row border
    content = content.replace(
        "border-bottom: 1px solid #1a1a1a;",
        "border-bottom: 1px solid var(--border);"
    )

    if content == original:
        return False

    path.write_text(content, encoding="utf-8")
    return True


def main():
    files = sorted(SESSIONS_DIR.glob("*.html"))
    patched = 0
    skipped = 0
    for f in files:
        if patch_file(f):
            print(f"  patched  {f.name}")
            patched += 1
        else:
            print(f"  skipped  {f.name}")
            skipped += 1

    print(f"\nDone: {patched} patched, {skipped} already up-to-date / unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
