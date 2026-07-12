"""Deterministic benchmark-to-guard extractor. v2.0 Knowledge Pipeline.

Usage: python scripts/rule_extractor.py
         --benchmark-dir <docs/benchmark/>
         --references-dir <references/>
         --output <docs/audit/guards.learned.yml>
         [--max-guards 50]

Logic (deterministic, no AI):
  1. Traverse benchmark/<project>/ directories
  2. For each project: prefer retest-result.json > benchmark-result.json
  3. Extract TP entries from tp_classification.exact_matches + close_matches
  4. Parse evidence field to extract file path and line numbers
  5. Infer scope glob from file path
  6. Map ADD severity (P0/P1/P2/P3) to guard severity (blocker/critical/warning/info)
  7. Generate human-readable 'check' description
  8. Extract rules from references/*.md (semi-structured Rule N format)
  9. Deduplicate guards by description similarity (>80% via difflib)
  10. Output guards.learned.yml in guards.template.yml format
"""

import argparse, json, sys, re, difflib, glob as glob_mod
from pathlib import Path
from _script_utils import run_script

SEVERITY_MAP = {"P0": "blocker", "P1": "critical", "P2": "warning", "P3": "info"}

_CONTROL_CHARS = dict.fromkeys(range(32))
_CONTROL_CHARS.pop(ord("\n"), None)
_CONTROL_CHARS.pop(ord("\r"), None)
_CONTROL_CHARS.pop(ord("\t"), None)


def sanitize(text):
    return text.translate(_CONTROL_CHARS) if text else text


def glob_to_scope(file_path):
    """Infer scope glob from a specific file path.
    Examples:
      fastapi/security/http.py → **/security/**/*.py
      utils.py → **/utils.py
      src/api/handlers/auth.py → **/handlers/**/*.py
    """
    parts = Path(file_path).parts
    if len(parts) >= 2:
        parent_dir = parts[-2]
        if parent_dir not in ("src", "lib", "app", "."):
            return f"**/{parent_dir}/**/*.py"
    if len(parts) >= 3:
        grandparent = parts[-3]
        if grandparent == "fastapi":
            return f"**/{parts[-2]}/**/*.py"
    return f"**/{Path(file_path).name}"


def parse_evidence(evidence_text):
    """Extract file path and line range from evidence string.
    Handles multiple formats:
      - "file.py:L123-L456 — description" (structured)
      - "description with file at file.py:L123 embedded" (embedded, P0-4 fix)
      - "description without file info" (free-text, returns None path)
    """
    if not evidence_text:
        return None, 0, 0, ""

    structured_pattern = re.match(r'^([\w.\-/]+):L?(\d+)(?:-L?(\d+))?\s*[—\-]\s*(.*)', evidence_text)
    if structured_pattern:
        file_path = structured_pattern.group(1)
        line_start = int(structured_pattern.group(2))
        line_end = int(structured_pattern.group(3)) if structured_pattern.group(3) else line_start
        description_rest = structured_pattern.group(4).strip()
        return file_path, line_start, line_end, description_rest

    simple_pattern = re.match(r'^([\w.\-/]+):L?(\d+)(?:-L?(\d+))?', evidence_text)
    if simple_pattern:
        file_path = simple_pattern.group(1)
        line_start = int(simple_pattern.group(2))
        line_end = int(simple_pattern.group(3)) if simple_pattern.group(3) else line_start
        return file_path, line_start, line_end, evidence_text

    embedded_pattern = re.search(r'(?:at|in|evidence|file)\s+([\w.\-/]+\.py)(?::L?(\d+)(?:-L?(\d+))?)?', evidence_text)
    if embedded_pattern:
        file_path = embedded_pattern.group(1)
        line_start = int(embedded_pattern.group(2)) if embedded_pattern.group(2) else 1
        line_end = int(embedded_pattern.group(3)) if embedded_pattern.group(3) else line_start
        return file_path, line_start, line_end, evidence_text

    return None, 0, 0, evidence_text


def load_benchmark_tps(benchmark_dir):
    """Load all TP entries from benchmark directory.
    Priority: retest-result.json > benchmark-result.json per project.
    Returns list of {project, bug_id, description, evidence_raw, severity, category, file, line_start, line_end}
    """
    tps = []
    bdir = Path(benchmark_dir)
    if not bdir.is_dir():
        return tps

    for project_dir in sorted(bdir.iterdir()):
        if not project_dir.is_dir():
            continue
        project_name = project_dir.name

        retest_path = project_dir / "retest-result.json"
        benchmark_path = project_dir / "benchmark-result.json"

        data_path = retest_path if retest_path.exists() else benchmark_path
        if not data_path.exists():
            continue

        data = json.loads(data_path.read_text(encoding="utf-8"))

        tp_data = data.get("tp_classification", {})
        all_matches = []

        for match_list in [tp_data.get("exact_matches", []), tp_data.get("close_matches", [])]:
            if isinstance(match_list, list):
                all_matches.extend(match_list)

        known_bugs = {kb.get("id", ""): kb for kb in data.get("known_bugs", [])}
        scoped_modules = [
            m.split("/")[-2] if "/" in m else m
            for m in data.get("scoped_audit", {}).get("modules_audited", [])
        ]

        for match in all_matches:
            bug_id = match.get("known_bug_id", "")
            description = sanitize(match.get("description", ""))
            evidence_text = match.get("evidence", "")

            if not evidence_text:
                evidence_text = description

            severity = match.get("severity", "P1")

            file_path, line_start, line_end, desc_rest = parse_evidence(evidence_text)

            if file_path is None:
                kb = known_bugs.get(bug_id, {})
                kb_desc = kb.get("description", "")
                kb_file = kb.get("file", "")

                if kb_file:
                    file_path = kb_file
                    line_start = 1
                    line_end = 1
                elif scoped_modules:
                    lower_desc = (description + kb_desc).lower()
                    for mod in scoped_modules:
                        mod_dir = mod.rstrip("/").split("/")[-1]
                        if mod_dir.lower() in lower_desc:
                            file_path = f"{mod_dir}/__init__.py"
                            break

                if file_path is None:
                    file_path = "unknown.py"
                    line_start = 1
                    line_end = 1

            tps.append({
                "project": project_name,
                "bug_id": bug_id,
                "description": description,
                "evidence_raw": evidence_text,
                "severity": severity,
                "file": file_path,
                "line_start": line_start,
                "line_end": line_end,
            })

    return tps


def build_guard_from_tp(tp, index):
    """Convert a single benchmark TP to a guards.yml entry."""
    project_prefix = tp["project"].upper().replace("-", "_")[:12]
    guard_id = f"LEARNED-{project_prefix}-{index + 1:03d}"
    scope = glob_to_scope(tp["file"])
    severity = SEVERITY_MAP.get(tp["severity"], "warning")

    evidence_safe = sanitize(tp["evidence_raw"][:120])
    check_lines = [
        f"Evidence: {evidence_safe}",
        f"Source: benchmark/{tp['project']} {tp['bug_id']} (TP)",
    ]
    check = "\n".join(check_lines)

    return {
        "id": guard_id,
        "description": tp["description"][:120],
        "scope": scope,
        "severity": severity,
        "check": sanitize(check),
        "source": f"auto-extracted from benchmark/{tp['project']} {tp['bug_id']} (TP, {tp['severity']})",
        "confidence": "auto-extracted",
        "category": tp.get("category", "behavior"),
    }


def extract_reference_rules(references_dir):
    """Extract guards from semi-structured reference rule files.
    Parses ## Rule N: Title → ### Detection Pattern / Audit Checks.
    """
    guards = []
    ref_dir = Path(references_dir)
    if not ref_dir.is_dir():
        return guards

    for ref_file in sorted(ref_dir.glob("*.md")):
        text = ref_file.read_text(encoding="utf-8")
        current_rule = None
        current_section = None

        for line in text.split("\n"):
            rule_match = re.match(r'^##\s+Rule\s+(\d+):\s*(.+)', line)
            if rule_match:
                if current_rule and current_rule.get("check"):
                    guards.append(current_rule)
                current_rule = {
                    "id": f"REF-{ref_file.stem.upper()[:8]}-{rule_match.group(1).zfill(3)}",
                    "description": rule_match.group(2).strip()[:120],
                    "scope": "**/*.py",
                    "severity": "critical",
                    "check": "",
                    "source": f"auto-extracted from references/{ref_file.name}",
                    "confidence": "auto-extracted",
                }
                current_section = "description"
                continue

            if current_rule is None:
                continue

            if re.match(r'^###\s+(Detection Pattern|Audit Checks)', line):
                current_section = "check"
                continue

            if current_section == "check" and line.strip():
                current_rule["check"] += line.strip() + " "

        if current_rule and current_rule.get("check"):
            current_rule["check"] = sanitize(current_rule["check"].strip()[:300])
            current_rule["description"] = sanitize(current_rule["description"])
            guards.append(current_rule)

    return guards


def deduplicate_guards(guards, similarity_threshold=0.8):
    """Remove guards with highly similar descriptions. O(n²) worst case, n≈14 typical."""
    result = []
    for g in guards:
        if not any(
            difflib.SequenceMatcher(None, g["description"], r["description"]).ratio()
            >= similarity_threshold
            for r in result
        ):
            result.append(g)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-dir", default="docs/benchmark")
    parser.add_argument("--references-dir", default="references")
    parser.add_argument("--output", default="docs/audit/guards.learned.yml")
    parser.add_argument("--max-guards", type=int, default=50)
    args = parser.parse_args()

    tps = load_benchmark_tps(args.benchmark_dir)
    tp_guards = [build_guard_from_tp(tp, i) for i, tp in enumerate(tps)]

    ref_guards = extract_reference_rules(args.references_dir)

    all_guards = deduplicate_guards(tp_guards + ref_guards)

    if len(all_guards) > args.max_guards:
        print(f"Warning: {len(all_guards)} guards exceed cap of {args.max_guards}. Truncating.",
              file=sys.stderr)
        all_guards = all_guards[:args.max_guards]

    output_lines = [
        "# ADD Learned Guards / 自动提取的守卫规则",
        "# Generated by rule_extractor.py from benchmark data and reference rules.",
        "# source: auto-extracted — human review required before moving to guards.project.yml.",
        f"# Total: {len(all_guards)} guards from {len(tps)} benchmark TPs + {len(ref_guards)} reference rules.",
        "",
        f"version: \"1.0\"",
        f"description: \"Auto-extracted guards — review before use\"",
        f"",
        "guards:",
    ]

    for g in all_guards:
        output_lines.append(f"  - id: \"{g['id']}\"")
        output_lines.append(f"    description: \"{g['description']}\"")
        output_lines.append(f"    scope: \"{g['scope']}\"")
        output_lines.append(f"    severity: \"{g['severity']}\"")
        output_lines.append(f"    category: \"{g.get('category', 'behavior')}\"")
        check_text = g["check"].replace("\n", "\n      ")
        output_lines.append(f"    check: |")
        output_lines.append(f"      {check_text}")
        output_lines.append(f"    # source: {g['source']}")
        output_lines.append(f"    # confidence: {g['confidence']}")
        output_lines.append("")

    output_text = "\n".join(output_lines)
    Path(args.output).write_text(output_text, encoding="utf-8")
    tp_count = len(tps)
    ref_count = len(ref_guards)
    print(f"Extracted {len(all_guards)} guards ({tp_count} from benchmark TP, {ref_count} from references)")
    print(f"Written to {args.output}")
    return 0


if __name__ == "__main__":
    run_script(main)
