"""Deterministic rule indexer. Extracts constraints from specs/ADRs for subagent lookup.

Usage: python scripts/rule_index.py --spec <spec.md> --adrs <dir>
      python scripts/rule_index.py --spec <spec.md>

Output: rule_index.json — keyword → constraint mapping. Subagent queries this
instead of re-reading entire spec documents, reducing context size.
"""

import argparse, json, sys, re, os
from pathlib import Path
from _rule_utils import extract_constraints, index_rules
from _script_utils import run_script


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
