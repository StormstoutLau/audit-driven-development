"""LLM generalization prompt builder. v2.2 Shared Engine (Detection+Repair).

Usage: python scripts/llm_generalize.py
         --source-dir <docs/audit/>
         --output-dir <docs/audit/>
         [--dry-run]

This script builds the prompt. The main agent reads the output and dispatches
a Subagent to execute the generalization.

Output files:
  rules.generalized.yml — generalized detection rules
  recipes.generalized.yml — generalized fix recipes

Layers (from concrete to abstract):
  L1: git diff patterns → code change generalizations
  L2: specific guard descriptions → general guard patterns
  L3: specific fix_suggestions → general fix recipes
"""

import argparse, json, sys
from pathlib import Path
from _script_utils import run_script


def load_l1_data(source_dir):
    candidates = source_dir / "pattern_candidates.json"
    if not candidates.exists():
        return []
    data = json.loads(candidates.read_text(encoding="utf-8"))
    return data.get("patterns", []) + data.get("suggested_guards", [])


def load_l2_data(source_dir):
    guards_file = source_dir / "guards.learned.yml"
    if not guards_file.exists():
        return []
    import yaml
    data = yaml.safe_load(guards_file.read_text(encoding="utf-8"))
    return [{"id": g["id"], "description": g.get("description", ""), "severity": g.get("severity", "")}
            for g in data.get("guards", [])]


def load_l3_data(source_dir):
    augmented = source_dir / "augmented_issues.json"
    if not augmented.exists():
        return []
    data = json.loads(augmented.read_text(encoding="utf-8"))
    return [
        {"claim": iss.get("claim", "")[:150],
         "fix_suggestion": iss["suggested_fix"],
         "match_score": iss.get("match_score", 0)}
        for iss in data.get("issues", [])
        if isinstance(iss, dict) and "suggested_fix" in iss
    ]


def build_prompt(l1, l2, l3):
    lines = [
        "# ADD v2.2 LLM Generalization Prompt",
        "",
        "You are the ADD LLM Generalization Engine. Your task is to generalize",
        "specific bug-fix instances into reusable detection rules and repair recipes.",
        "",
        "## Instructions",
        "",
        "For each group of related instances below, produce TWO outputs:",
        "1. A generalized DETECTION RULE (guard): what pattern to detect",
        "2. A generalized REPAIR RECIPE (fix): how to fix it when found",
        "",
        "Format rules.generalized.yml entries as:",
        "  - id: 'GEN-DET-001'",
        "    description: '[generalized description]'",
        "    check: '[how to verify this rule]'",
        "    scope: '**/*.py'",
        "    severity: '[blocker|critical|warning]'",
        "    source: 'LLM generalization v2.2 from L[N]'",
        "",
        "Format recipes.generalized.yml entries as:",
        "  - id: 'GEN-FIX-001'",
        "    pattern: '[what bug pattern this fixes]'",
        "    fix:",
        "      steps: ['Step 1', 'Step 2']",
        "      regression_risk: '[none|low|medium|high]'",
        "      verification: '[how to verify fix]'",
        "    source: 'LLM generalization v2.2 from L[N]'",
        "",
        f"## L1: Specific Fix Patterns from Git History ({len(l1)} patterns)",
    ]
    for i, p in enumerate(l1[:10]):
        lines.append(f"{i+1}. {json.dumps(p)[:200]}")
    lines.append("")
    lines.append(f"## L2: Specific Detection Rules from Guards ({len(l2)} guards)")
    for i, g in enumerate(l2[:10]):
        lines.append(f"{i+1}. [{g['severity']}] {g['description'][:150]}")
    lines.append("")
    lines.append(f"## L3: Specific Fix Recipes from History ({len(l3)} fixes)")
    for i, f in enumerate(l3[:10]):
        lines.append(f"{i+1}. Claim: {f['claim']}")
        lines.append(f"   Fix: {json.dumps(f['fix_suggestion'])[:200]}")
    lines.append("")
    lines.append("## Output")
    lines.append("Produce rules.generalized.yml and recipes.generalized.yml based on the above instances.")
    lines.append("Generalize: merge similar patterns, abstract project-specific details, keep the essence.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default="docs/audit")
    parser.add_argument("--output-dir", default="docs/audit")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    src = Path(args.source_dir)
    l1 = load_l1_data(src)
    l2 = load_l2_data(src)
    l3 = load_l3_data(src)

    prompt = build_prompt(l1, l2, l3)

    if args.dry_run:
        print(prompt[:1000])
        print(f"\n... (total {len(prompt)} chars)")
    else:
        prompt_file = Path(args.output_dir) / "llm_generalization_prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        print(f"Prompt written to {prompt_file} ({len(prompt)} chars)")
        print(f"Data: L1={len(l1)} L2={len(l2)} L3={len(l3)}")
        print("Next: dispatch Subagent with this prompt to generate rules.generalized.yml + recipes.generalized.yml")

    return 0


if __name__ == "__main__":
    run_script(main)
