"""Sync main SKILL.md content to all 7 adapter files."""

import re
from pathlib import Path

REPO = Path(r"F:\Coding\audit-driven-development")
MAIN_SKILL = REPO / "SKILL.md"
ADAPTERS = REPO / "adapters"

def main():
    full_content = MAIN_SKILL.read_text(encoding="utf-8")

    frontmatter_match = re.match(r"^---\n.*?\n---\n\n", full_content, re.DOTALL)
    if not frontmatter_match:
        print("ERROR: No frontmatter found in SKILL.md")
        return
    frontmatter = frontmatter_match.group()
    body = full_content[frontmatter_match.end():]

    header = "# Audit-Driven Development\n\n> **Multi-dimensional audit of code vs design spec alignment.**\n\n"

    # 1) Claude Code — full copy (with frontmatter)
    (ADAPTERS / "claude-code" / "SKILL.md").write_text(full_content, encoding="utf-8")
    print("OK: adapters/claude-code/SKILL.md")

    # 2) Generic AGENTS.md — no frontmatter, with header
    (ADAPTERS / "AGENTS.md").write_text(header + body, encoding="utf-8")
    print("OK: adapters/AGENTS.md")

    # 3) Codex AGENTS.md — same as generic
    (ADAPTERS / "codex" / "AGENTS.md").write_text(header + body, encoding="utf-8")
    print("OK: adapters/codex/AGENTS.md")

    # 4) OpenCode AGENTS.md — same as generic
    (ADAPTERS / "opencode" / "AGENTS.md").write_text(header + body, encoding="utf-8")
    print("OK: adapters/opencode/AGENTS.md")

    # 5) Cursor .mdc — specific frontmatter + body
    mdc_frontmatter = (
        "---\n"
        'description: Multi-dimensional audit of code vs design spec alignment. Produces scoring, issue severity, fix priority matrix, and fix baseline. Invoke after implementation completes or when checking code-design alignment.\n'
        'globs: ["**/*.py", "**/*.ts", "**/*.js", "**/*.go", "**/*.rs", "**/*.java"]\n'
        "alwaysApply: false\n"
        "---\n\n"
    )
    (ADAPTERS / "cursor" / "audit-driven-development.mdc").write_text(mdc_frontmatter + body, encoding="utf-8")
    print("OK: adapters/cursor/audit-driven-development.mdc")

    # 6) GitHub Copilot — instructions header
    copilot_header = "# Audit-Driven Development Instructions\n\n"
    (ADAPTERS / "github-copilot" / "copilot-instructions.md").write_text(copilot_header + header + body, encoding="utf-8")
    print("OK: adapters/github-copilot/copilot-instructions.md")

    # 7) Windsurf — rules header
    windsurf_header = "# Audit-Driven Development Rules\n\n"
    (ADAPTERS / "windsurf" / ".windsurfrules").write_text(windsurf_header + header + body, encoding="utf-8")
    print("OK: adapters/windsurf/.windsurfrules")

    print("\nAll 7 adapters synced.")

if __name__ == "__main__":
    main()
