"""Fix recipe book manager. v2.2 Repair Track (Mechanism A).

Usage: python scripts/fix_recipes.py
         --recipes <recipes.generalized.yml>
         --output <docs/audit/recipes.generalized.yml>
         [--import-llm <llm_output_yml>]

The recipe book supports two sources:
  Human-authored: 5 built-in recipes (always available)
  LLM-imported: auto-extracted from LLM generalization output
"""

import argparse, sys, yaml
from pathlib import Path
from _script_utils import run_script

BUILT_IN_RECIPES = [
    {
        "id": "FIX-NULL-DICT-GET",
        "pattern": "dict.get('key', default) returns None when JSON value is null",
        "fix": {
            "steps": ["Change .get('key', 'default') to .get('key') or 'default'"],
            "regression_risk": "none",
            "verification": "grep -rn \"\\.get(\" affected_files | grep -v \" or \""
        },
        "confidence": "verified",
        "source": "v2.0 self-audit ADD-P0-1 + human curation"
    },
    {
        "id": "FIX-TRACEBACK-LOSS",
        "pattern": "Top-level except discards traceback — no traceback.print_exc()",
        "fix": {
            "steps": ["import traceback", "traceback.print_exc()"],
            "regression_risk": "none",
            "verification": "python -c \"import traceback; print('ok')\""
        },
        "confidence": "verified",
        "source": "v2.0 self-audit ADD-P1-2 + human curation"
    },
    {
        "id": "FIX-EVIDENCE-PARSING",
        "pattern": "Evidence text parse fails for embedded file:line references",
        "fix": {
            "steps": [
                "Add re.search(r'(?:at|in|evidence|file)\\s+([\\w.\\-/]+\\.py)(?::L?(\\d+))?')",
                "Use finditer-based extraction instead of re.match for non-prefix matches"
            ],
            "regression_risk": "low",
            "verification": "python scripts/rule_extractor.py --benchmark-dir docs/benchmark"
        },
        "confidence": "verified",
        "source": "v2.0 self-audit ADD-P0-4 + human curation"
    },
    {
        "id": "FIX-SCOPE-GLOB",
        "pattern": "Guard scope glob resolves to **/unknown.py — useless",
        "fix": {
            "steps": [
                "Parse evidence to extract actual file path with embedded pattern",
                "Fall back to known_bugs[].file or scoped_modules inference"
            ],
            "regression_risk": "medium",
            "verification": "grep -c 'unknown.py' docs/audit/guards.learned.yml"
        },
        "confidence": "verified",
        "source": "v2.0 self-audit ADD-P0-4 scope fix + human curation"
    },
    {
        "id": "FIX-RETURNCODE-CHECK",
        "pattern": "subprocess.run without returncode check — errors silent",
        "fix": {
            "steps": [
                "Add: if result.returncode not in (0, 1): continue",
                "Add PermissionError, OSError to exception handling"
            ],
            "regression_risk": "low",
            "verification": "python scripts/spec_graph.py --spec SKILL.md"
        },
        "confidence": "verified",
        "source": "v2.0 self-audit ADD-P2-3 + human curation"
    }
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", default="docs/audit/recipes.generalized.yml")
    parser.add_argument("--output", default="docs/audit/recipes.generalized.yml")
    parser.add_argument("--import-llm", default=None)
    args = parser.parse_args()

    all_recipes = list(BUILT_IN_RECIPES)

    if args.import_llm:
        llm_path = Path(args.import_llm)
        if llm_path.exists():
            llm_data = yaml.safe_load(llm_path.read_text(encoding="utf-8"))
            if isinstance(llm_data, list):
                for r in llm_data:
                    if isinstance(r, dict) and r.get("id", "").startswith("GEN-FIX-"):
                        r["confidence"] = "llm-generated"
                        r["source"] = r.get("source", "") + " (imported by fix_recipes.py)"
                        all_recipes.append(r)

    output = {
        "version": "2.2",
        "description": f"Fix recipe book — {len(BUILT_IN_RECIPES)} human + {len(all_recipes) - len(BUILT_IN_RECIPES)} LLM-imported recipes",
        "recipes": all_recipes
    }

    out_path = Path(args.output)
    out_path.write_text(yaml.dump(output, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    print(f"fix_recipes: {len(all_recipes)} recipes ({len(BUILT_IN_RECIPES)} built-in + {len(all_recipes) - len(BUILT_IN_RECIPES)} LLM)")
    return 0

if __name__ == "__main__":
    run_script(main)
