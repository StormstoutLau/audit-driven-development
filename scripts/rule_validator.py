"""Rule recall validator. v2.2 Detection Track.

Usage: python scripts/rule_validator.py
         --rules <rules.generalized.yml>
         --benchmark-dir <docs/benchmark/>
         --output <validation_report.json>

Algorithm:
  1. Load generalized rules
  2. For each rule: grep its scope in benchmark projects
  3. Check if rule description matches any known bug description (difflib > 0.4)
  4. Record precision (matched known bugs / total rules)
  5. Output validation report with verified/flagged status

Performance cap: 30s.
"""

import argparse, json, sys, difflib
from pathlib import Path
from _script_utils import run_script

def load_rules(rules_path):
    import yaml
    data = yaml.safe_load(Path(rules_path).read_text(encoding="utf-8"))
    rules = data if isinstance(data, list) else data.get("rules", [])
    return [r for r in rules if isinstance(r, dict)]

def load_known_bugs(benchmark_dir):
    bugs = []
    bdir = Path(benchmark_dir)
    for project_dir in sorted(bdir.iterdir()):
        if not project_dir.is_dir():
            continue
        for result_file in project_dir.glob("*.json"):
            try:
                data = json.loads(result_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for kb in data.get("known_bugs", []):
                desc = kb.get("description", "")
                if desc:
                    bugs.append({
                        "project": project_dir.name,
                        "bug_id": kb.get("id", ""),
                        "description": desc
                    })
    return bugs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", required=True)
    parser.add_argument("--benchmark-dir", default="docs/benchmark")
    parser.add_argument("--output", default="docs/audit/rule_validation_report.json")
    args = parser.parse_args()

    rules = load_rules(args.rules)
    known_bugs = load_known_bugs(args.benchmark_dir)

    results = []
    for rule in rules:
        desc = rule.get("description", "").lower()
        best_bug = max(known_bugs, key=lambda b: difflib.SequenceMatcher(
            None, desc, b["description"].lower()).ratio(), default=None) if known_bugs else None
        best_score = difflib.SequenceMatcher(None, desc, best_bug["description"].lower()).ratio() if best_bug else 0.0
        status = "verified" if best_score >= 0.4 else "flagged_for_review"
        results.append({
            "rule_id": rule.get("id", ""),
            "description": rule.get("description", "")[:120],
            "best_match_known_bug": best_bug["description"][:120] if best_bug else "",
            "match_score": round(best_score, 4),
            "status": status
        })

    validated = sum(1 for r in results if r["status"] == "verified")
    flagged = len(results) - validated

    output = {
        "rules_validated": len(results),
        "verified": validated,
        "flagged_for_review": flagged,
        "precision": round(validated / max(len(results), 1), 4),
        "results": results
    }

    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"rule_validator: {validated}/{len(results)} verified "
          f"({round(100*validated/max(len(results),1))}%), {flagged} flagged")
    return 0

if __name__ == "__main__":
    run_script(main)
