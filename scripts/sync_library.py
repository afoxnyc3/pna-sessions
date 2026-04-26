#!/usr/bin/env python3
"""
sync_library.py — Read pna-library/library.yaml and emit library_data.json
for the Mission Control library.html page.

Source of truth: ~/dev/projects/pna-library/library.yaml
Output:          <pna-sessions>/library_data.json

Categories are inferred from `# ── Section Name ──` comment headers in the
yaml. Source badges are inferred from the `source:` path:

  ~/dev/external/agent-skills/         → external
  ~/dev/external/ai-launchpad-*/       → ai-launchpad
  ~/dev/projects/rnd/skills/feynman/   → feynman
  ~/dev/projects/rnd/skills/aris/      → aris
  ~/dev/projects/rnd/skills/anthropic/ → anthropic
  ~/dev/projects/principal-plugin/     → principal
  ~/.claude/skills/*  or anything else → local
  https://...                          → external

Run from anywhere; resolves repo paths relative to its own location.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_YAML_DEFAULT = Path.home() / "dev/projects/pna-library/library.yaml"
LIBRARY_YAML_FALLBACKS = [
    Path.home() / "dev/pna-library/library.yaml",
    Path.home() / ".claude/skills/library/library.yaml",
]
OUT_FILE = REPO_ROOT / "library_data.json"

CATEGORY_HEADER_RE = re.compile(r"^\s*#\s*──+\s*(.+?)\s*──+\s*$")
NAME_RE = re.compile(r"^\s*-\s*name:\s*(.+?)\s*$")
DESC_INLINE_RE = re.compile(r"^\s*description:\s*(.+?)\s*$")
SOURCE_RE = re.compile(r"^\s*source:\s*(.+?)\s*$")
SECTION_RE = re.compile(r"^\s{0,4}(skills|agents|prompts)\s*:\s*$")


def find_yaml() -> Path:
    if LIBRARY_YAML_DEFAULT.exists():
        return LIBRARY_YAML_DEFAULT
    for candidate in LIBRARY_YAML_FALLBACKS:
        if candidate.exists():
            return candidate
    print(f"ERROR: library.yaml not found at {LIBRARY_YAML_DEFAULT} or fallbacks", file=sys.stderr)
    sys.exit(1)


def classify_source(source_path: str) -> str:
    s = source_path.strip().strip('"').strip("'")
    if s.startswith("http://") or s.startswith("https://"):
        return "external"
    s_expanded = s.replace("~", str(Path.home()))
    markers = [
        ("dev/external/agent-skills/", "external"),
        ("dev/external/ai-launchpad", "ai-launchpad"),
        ("dev/projects/rnd/skills/feynman/", "feynman"),
        ("dev/projects/rnd/skills/aris/", "aris"),
        ("dev/projects/rnd/skills/anthropic/", "anthropic"),
        ("dev/projects/principal-plugin/", "principal"),
    ]
    for marker, badge in markers:
        if marker in s_expanded:
            return badge
    return "local"


def initials(name: str) -> str:
    parts = re.split(r"[-_\s]+", name)
    if len(parts) >= 2:
        return (parts[0][:1] + parts[1][:1]).upper()
    return name[:2].upper()


def parse_library(yaml_path: Path) -> dict:
    """
    Hand-rolled minimal parser. Avoids a PyYAML dependency.

    Tracks current section (skills/agents/prompts) and current category
    header from `# ── Title ──` comments. Each `- name:` opens a new entry;
    `description:` and `source:` lines populate it. Multi-line `description: >`
    blocks are handled by reading subsequent indented lines until a non-indented
    or new-key line appears.
    """
    skills, agents, prompts = [], [], []
    current_section: str | None = None
    current_category = "Uncategorized"
    current_entry: dict | None = None
    in_multiline_desc = False
    multiline_buffer: list[str] = []

    def commit_entry():
        nonlocal current_entry, in_multiline_desc, multiline_buffer
        if current_entry is None:
            return
        if in_multiline_desc and multiline_buffer:
            current_entry["description"] = " ".join(
                line.strip() for line in multiline_buffer if line.strip()
            )
        if current_section == "skills":
            skills.append(current_entry)
        elif current_section == "agents":
            agents.append(current_entry)
        elif current_section == "prompts":
            prompts.append(current_entry)
        current_entry = None
        in_multiline_desc = False
        multiline_buffer = []

    lines = yaml_path.read_text().splitlines()
    for line in lines:
        # Section header (skills:, agents:, prompts:) at column 2 (under library:)
        section_match = SECTION_RE.match(line)
        if section_match:
            commit_entry()
            current_section = section_match.group(1)
            current_category = "Uncategorized"
            continue

        # Category header comment
        cat_match = CATEGORY_HEADER_RE.match(line)
        if cat_match:
            commit_entry()
            raw = cat_match.group(1)
            # Strip any trailing parenthetical e.g. "(agent-skills — Addy Osmani)"
            current_category = re.sub(r"\s*\(.*?\)\s*$", "", raw).strip()
            continue

        # Skip any comment line that isn't a category header
        if line.lstrip().startswith("#"):
            if in_multiline_desc:
                # comment ends multiline desc
                pass
            continue

        # New entry
        name_match = NAME_RE.match(line)
        if name_match:
            commit_entry()
            current_entry = {
                "name": name_match.group(1),
                "category": current_category,
                "description": "",
                "source_path": "",
            }
            continue

        if current_entry is None:
            continue

        # description (inline or multiline)
        desc_match = DESC_INLINE_RE.match(line)
        if desc_match:
            value = desc_match.group(1)
            if value == ">" or value == "|":
                in_multiline_desc = True
                multiline_buffer = []
            else:
                in_multiline_desc = False
                current_entry["description"] = value
            continue

        # source line
        source_match = SOURCE_RE.match(line)
        if source_match:
            if in_multiline_desc and multiline_buffer:
                current_entry["description"] = " ".join(
                    s.strip() for s in multiline_buffer if s.strip()
                )
                in_multiline_desc = False
                multiline_buffer = []
            current_entry["source_path"] = source_match.group(1)
            continue

        # accumulate multiline description body
        if in_multiline_desc:
            stripped = line.strip()
            if not stripped:
                continue
            # any other key resets multiline (e.g. `phase:`, `requires:`)
            if re.match(r"^\s*\w[\w_]*:\s", line):
                current_entry["description"] = " ".join(
                    s.strip() for s in multiline_buffer if s.strip()
                )
                in_multiline_desc = False
                multiline_buffer = []
            else:
                multiline_buffer.append(stripped)
            continue

    commit_entry()
    return {"skills": skills, "agents": agents, "prompts": prompts}


def to_ui_payload(parsed: dict) -> dict:
    skills_out = []
    for s in parsed["skills"]:
        skills_out.append({
            "name": s["name"],
            "desc": s["description"],
            "category": s["category"],
            "source": classify_source(s.get("source_path", "")),
        })

    agents_out = []
    for a in parsed["agents"]:
        agents_out.append({
            "name": a["name"],
            "desc": a["description"],
            "initials": initials(a["name"]),
        })

    prompts_out = []
    for p in parsed["prompts"]:
        prompts_out.append({
            "name": p["name"],
            "desc": p["description"],
            "source": classify_source(p.get("source_path", "")),
        })

    return {
        "skills": skills_out,
        "agents": agents_out,
        "prompts": prompts_out,
    }


def main() -> int:
    yaml_path = find_yaml()
    parsed = parse_library(yaml_path)
    payload = to_ui_payload(parsed)
    OUT_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"Wrote {OUT_FILE.relative_to(REPO_ROOT)} "
        f"({len(payload['skills'])} skills, "
        f"{len(payload['agents'])} agents, "
        f"{len(payload['prompts'])} prompts) "
        f"from {yaml_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
