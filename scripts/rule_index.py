"""Deterministic rule indexer. Extracts constraints from specs/ADRs for subagent lookup.

Usage: python scripts/rule_index.py --spec <spec.md> --adrs <dir>
      python scripts/rule_index.py --spec <spec.md>

Output: rule_index.json — keyword → constraint mapping. Subagent queries this
instead of re-reading entire spec documents, reducing context size.
"""

import argparse, json, sys, re, os
from pathlib import Path
from _script_utils import run_script


def extract_constraints(text, source_name):
    """Extract 'must', 'must not', 'threshold', 'invariant' statements."""
    rules = []
    lines = text.split("\n")

    patterns = [
        (r'(?i)\b(must\s+(?:not\s+)?[^.]{10,200}?\.)', "must"),
        (r'(?i)\b(shall\s+(?:not\s+)?[^.]{10,200}?\.)', "must"),
        (r'(?i)\b(threshold[^.]{10,200}?\.)', "threshold"),
        (r'(?i)\b(invariant[^.]{10,200}?\.)', "invariant"),
        (r'(?i)\b(required\s+[^.]{10,200}?\.)', "required"),
        (r'(?i)\b(never\s+[^.]{10,200}?\.)', "forbidden"),
        (r'(?i)\b(always\s+[^.]{10,200}?\.)', "always"),
    ]

    for i, line in enumerate(lines):
        for pat, cat in patterns:
            for m in re.finditer(pat, line):
                rule_text = m.group(1).strip()
                rules.append({
                    "text": rule_text,
                    "category": cat,
                    "source": source_name,
                    "line": i + 1
                })

    for i, line in enumerate(lines):
        if re.search(r'(?i)#+\s*(?:rule|constraint|requirement)', line):
            rule_text = line.strip()
            cat = "explicit_rule"
            rules.append({
                "text": rule_text,
                "category": cat,
                "source": source_name,
                "line": i + 1
            })

    return rules


def index_rules(rules):
    """Create keyword→constraint index for fast lookup."""
    index = {}
    for r in rules:
        words = set(re.findall(r'\b[a-zA-Z_]\w{2,}\b', r["text"].lower()))
        for w in words:
            if w not in index:
                index[w] = []
            index[w].append(r)
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--adrs", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    all_rules = []

    spec_text = Path(args.spec).read_text(encoding="utf-8")
    all_rules.extend(extract_constraints(spec_text, os.path.basename(args.spec)))

    if args.adrs:
        adr_dir = Path(args.adrs)
        if adr_dir.is_dir():
            for adr_file in sorted(adr_dir.glob("*.md")):
                adr_text = adr_file.read_text(encoding="utf-8")
                all_rules.extend(extract_constraints(adr_text, str(adr_file.name)))

    index = index_rules(all_rules)

    output = {
        "total_rules": len(all_rules),
        "total_keywords": len(index),
        "rules": all_rules,
        "index": {k: [r["text"] for r in v] for k, v in list(index.items())[:200]}
    }

    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Written {len(all_rules)} rules to {args.output}")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    run_script(main)
