"""Spec-to-code knowledge graph builder. v2.0 Knowledge Pipeline.
Extends rule_index.py with module mapping, ADR tracing, and guard binding.

Usage: python scripts/spec_graph.py
         --spec <spec.md>
         --adrs <adr-dir>
         --guards <guards.yml>
         --repo <path>
         --output <spec_graph.json>
         [--timeout 30]

New capabilities vs rule_index.py:
  A. Module Mapping: "## Module: <name>" → associated code directories
  B. ADR Tracing: ADR "Decision:" paragraphs → grep code evidence
  C. Corrective Linking: spec "修正 X.Y" → code line references
  D. Guard Binding: guard scope → resolved file list via glob
  Preserves all keyword→constraint indexing from rule_index.py.
"""

import argparse, json, sys, re, subprocess, glob as glob_mod
from pathlib import Path
from _rule_utils import extract_constraints, index_rules
from _script_utils import run_script


def parse_spec_modules(spec_text):
    """A. Module Mapping: extract spec sections and link to code modules."""
    sections = []
    heading_pattern = re.compile(r'^#{2,3}\s+(.+)', re.MULTILINE)

    for m in re.finditer(r'(#{2,3}\s+.+?)(?=\n#{2,3}\s+|\n---|\Z)', spec_text, re.DOTALL):
        block = m.group(1)
        heading_match = heading_pattern.match(block)
        if not heading_match:
            continue
        section_title = heading_match.group(1).strip()

        constraints = extract_constraints(block, source_name=sanitize_filename(section_title))
        constraint_texts = [c["text"] for c in constraints]

        code_refs = re.findall(r'`([^`]+\.(?:py|ts|js|yml|json|md))`', block)
        file_refs = [
            {"file": ref, "line_start": ls,
             "line_end": int(lm.group(2)) if lm.group(2) else ls}
            for ref in set(code_refs)
            if (lm := re.search(rf'{re.escape(ref)}(?:\s*L?(\d+)(?:\s*[-–]\s*L?(\d+))?)?', block))
            and (ls := int(lm.group(1)) if lm.group(1) else 1)
        ]

        sections.append({
            "section": section_title[:100],
            "module": infer_module_name(section_title),
            "constraints": constraint_texts[:20],
            "code_locations": file_refs[:10],
        })

    return sections


def infer_module_name(section_title):
    """Infer module name from section heading. e.g. 'Phase 1: Spec Inventory' → 'SKILL.md'."""
    lower = section_title.lower()
    if "phase" in lower or "audit" in lower or "lens" in lower:
        return "SKILL.md"
    if "roadmap" in lower or "version" in lower:
        return "ROADMAP.md"
    if "benchmark" in lower:
        return "benchmark/"
    return "unknown"


def sanitize_filename(text):
    return re.sub(r'[^\w\-]', '_', text)[:50]


def parse_adr_decisions(adr_dir, repo_root, timeout=10):
    """B. ADR Tracing: extract Decision: paragraphs → grep code evidence."""
    decisions = []
    adr_path = Path(adr_dir)
    if not adr_path.is_dir():
        return decisions

    for adr_file in sorted(adr_path.glob("*.md")):
        text = adr_file.read_text(encoding="utf-8")

        decision_blocks = re.findall(
            r'(?:#{1,3}\s*Decision|#{1,3}\s*Decisions|Decision:)([^#]+?)(?=\n#{1,3}|\n---|\Z)',
            text, re.DOTALL | re.IGNORECASE
        )

        for block in decision_blocks:
            decision_lines = [l.strip("- ").strip() for l in block.strip().split("\n")
                              if l.strip() and not l.strip().startswith("#")]
            for decision_text in decision_lines[:10]:
                if len(decision_text) < 10:
                    continue
                evidence = grep_code_evidence(decision_text, repo_root, timeout)
                decisions.append({
                    "adr": str(adr_file.name),
                    "decision": decision_text[:200],
                    "code_evidence": evidence,
                })

    return decisions


def grep_code_evidence(decision_text, repo_root, timeout=10):
    """Grep repo for code evidence of an ADR decision.
    Extracts key terms from decision text and searches .py/.ts/.js files.
    """
    key_terms = re.findall(r'\b[A-Z][a-z]*(?:_[A-Z][a-z]*)*\b', decision_text)
    key_terms += re.findall(r'\b[a-z_]+(?:\.[a-z_]+)+\b', decision_text)
    key_terms = [t for t in key_terms if len(t) > 3 and t.lower() not in
                 {"this", "that", "with", "from", "must", "shall", "should", "when", "then", "each"}]

    evidence = []
    repo = Path(repo_root)

    for term in key_terms[:5]:
        try:
            result = subprocess.run(
                ["git", "grep", "-n", "-I", "--", term, "--", "*.py", "*.ts", "*.js", "*.yml"],
                capture_output=True, text=True, timeout=timeout,
                cwd=str(repo)
            )
            if result.returncode not in (0, 1):
                continue
            matches = result.stdout.strip().split("\n")[:3]
            for match in matches:
                if ":" in match:
                    parts = match.split(":", 2)
                    if len(parts) >= 2:
                        evidence.append({
                            "file": parts[0],
                            "line": int(parts[1]) if parts[1].isdigit() else 0,
                            "match": parts[2][:80] if len(parts) > 2 else match[:80],
                        })
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError):
            pass

    return evidence[:3]


def resolve_guard_scopes(guards_path, repo_root):
    """D. Guard Binding: resolve guard scope globs to concrete file lists."""
    mappings = []
    try:
        import yaml
        data = yaml.safe_load(Path(guards_path).read_text(encoding="utf-8"))
    except Exception:
        return mappings

    for guard in data.get("guards", []):
        scope = guard.get("scope", "**/*.py")
        resolved = []
        for f in glob_mod.glob(scope, root_dir=str(repo_root), recursive=True):
            full_path = Path(repo_root) / f
            if full_path.is_file():
                resolved.append(str(f))
        mappings.append({
            "guard_id": guard.get("id", ""),
            "scope_glob": scope,
            "resolved_files": resolved[:50],
            "audit_lens": guard.get("category", "behavior"),
        })

    return mappings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--adrs", default=None)
    parser.add_argument("--guards", default=None)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output", default=None)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    spec_text = Path(args.spec).read_text(encoding="utf-8")
    spec_sections = parse_spec_modules(spec_text)
    all_constraints = extract_constraints(spec_text, Path(args.spec).name)
    keyword_index = index_rules(all_constraints)

    adr_decisions = []
    if args.adrs:
        adr_timeout = max(5, args.timeout // 3)
        adr_decisions = parse_adr_decisions(args.adrs, args.repo, adr_timeout)

    guard_mappings = []
    if args.guards:
        guard_mappings = resolve_guard_scopes(args.guards, args.repo)

    proj_name = Path(args.repo).resolve().name
    output = {
        "project": proj_name,
        "version": "2.0",
        "spec_sections": spec_sections,
        "adr_decisions": adr_decisions,
        "guard_mappings": guard_mappings,
        "keyword_index": keyword_index,
        "total_constraints": len(all_constraints),
        "total_keywords": len(keyword_index),
    }

    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        sections_count = len(spec_sections)
        adr_count = len(adr_decisions)
        guard_count = len(guard_mappings)
        print(f"spec_graph: {sections_count} sections, {adr_count} ADR decisions, {guard_count} guard mappings")
        print(f"Written to {args.output}")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    run_script(main)
