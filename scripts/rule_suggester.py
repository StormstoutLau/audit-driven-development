"""Suggest new guards from audit-log TP/FP/FN pattern analysis. v2.1 Detection Track.

Usage: python scripts/rule_suggester.py
         --audit-log-dir <docs/audit-log/>
         --output <rule_suggestions.json>
         [--min-frequency 3]

Algorithm:
  1. Read all audit-log/*.md files
  2. Extract TP/FP/FN mentions with their categories
  3. For each FP category occurring >= min-frequency:
     - FP type = "over-aggressive": detection rule too strict → suggest severity downgrade
     - FP type = "factual-error": evidence rule violated → suggest evidence verification guard
     - FP type = "scope-error": scope definition too broad → suggest scope narrowing guard
  4. For each FN category occurring >= min-frequency:
     - Missing detection → suggest new guard with that category
  5. Output rule_suggestions.json

Performance cap: 30s.
"""

import argparse, json, sys, re, collections
from itertools import chain
from pathlib import Path
from _script_utils import run_script

CATEGORIES = frozenset({"security", "type", "behavioral", "contract", "edge", "compatibility"})

def _parse_findings(text, pattern, prefix, fields):
    for m in pattern.finditer(text):
        desc = (m.group(fields[1]).strip()[:120] if m.lastindex and m.lastindex >= fields[1] else "")
        extra = {}
        if len(fields) > 2 and fields[2]:
            extra_match = fields[2].search(text[m.start():m.start()+500])
            if extra_match:
                extra[fields[3]] = extra_match.group(1)
        yield {"id": f"{prefix}-{m.group(fields[0])}", "description": desc, **extra}

def parse_audit_log(file_path):
    text = file_path.read_text(encoding="utf-8")

    fp_re = re.compile(r'(?i)\bFP[-\s]*(\d+).*?(- |\* )(.*?)(?=\n|$)', re.MULTILINE)
    fn_re = re.compile(r'(?i)\bFN[-\s]*(\d+).*?(- |\* )(.*?)(?=\n|$)', re.MULTILINE)
    tp_re = re.compile(r'(?i)\bKnown Bug[-\s]*(\d+).*?(?:Exact Match|Close Match).*?(- |\* )(.*?)(?=\n|$)', re.MULTILINE)
    fp_type_re = re.compile(r'(over-aggressive|factual-error|scope-error)', re.IGNORECASE)

    return {
        "fp": list(_parse_findings(text, fp_re, "FP", (1, 3, fp_type_re, "type"))),
        "fn": list(_parse_findings(text, fn_re, "FN", (1, 3, None, None))),
        "tp": list(_parse_findings(text, tp_re, "KB", (1, 3, None, None))),
    }

def _infer_fn_category(desc):
    low = desc.lower()
    return next((c for c in CATEGORIES if c in low), "unknown")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-log-dir", default="docs/audit-log")
    parser.add_argument("--output", default="docs/audit/rule_suggestions.json")
    parser.add_argument("--min-frequency", type=int, default=3)
    args = parser.parse_args()

    log_dir = Path(args.audit_log_dir)
    log_files = sorted(log_dir.glob("*.md"))
    log_data = {f: parse_audit_log(f) for f in log_files}

    all_fps = list(chain.from_iterable(
        log_data[f]["fp"] for f in log_files
    ))
    all_fns = list(chain.from_iterable(
        log_data[f]["fn"] for f in log_files
    ))
    all_tps = list(chain.from_iterable(
        log_data[f]["tp"] for f in log_files
    ))

    fp_type_counts = collections.Counter(f["type"] for f in all_fps)
    fn_category_counts = collections.Counter(
        _infer_fn_category(fn["description"]) for fn in all_fns
    )

    FP_ACTION_MAP = {
        "over-aggressive": {
            "suggestion": "Subagent severity logic too strict — consider widening tolerance for P1/P2 classification",
            "action": "Review SKILL.md severity grading rules"
        },
        "factual-error": {
            "suggestion": "Evidence pointer rules violated — add guard: 'Every finding MUST have verified evidence pointer'",
            "suggested_guard": {
                "description": "All subagent findings MUST include verified evidence pointer (file:line_start-line_end)",
                "severity": "critical", "scope": "**/*.py"
            }
        },
    }

    suggestions = [
        {
            "trigger": f"{len(all_tps)} TPs accumulated",
            "suggestion": "Run rule_extractor to extract guards from TPs",
            "action": "python scripts/rule_extractor.py --benchmark-dir docs/benchmark --output docs/audit/guards.learned.yml"
        }
    ] if len(all_tps) >= 5 else []

    suggestions += [
        {"trigger": f"{count} {fp_type} FPs", **FP_ACTION_MAP.get(fp_type, {})}
        for fp_type, count in fp_type_counts.most_common()
        if count >= args.min_frequency and fp_type in FP_ACTION_MAP
    ]

    suggestions += [
        {
            "trigger": f"{count} FNs in '{cat}' category",
            "suggestion": f"Consider adding a '{cat}'-specific guard or lens",
            "action": f"Review DIMENSION checks for {cat} coverage"
        }
        for cat, count in fn_category_counts.most_common()
        if count >= args.min_frequency
    ]

    output = {
        "audit_logs_analyzed": len(log_files),
        "total_fps": len(all_fps),
        "total_fns": len(all_fns),
        "total_tps": len(all_tps),
        "fp_type_distribution": dict(fp_type_counts),
        "fn_category_distribution": dict(fn_category_counts),
        "suggestions": suggestions
    }

    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"rule_suggester: {len(suggestions)} suggestions from "
          f"{len(all_fps)} FPs + {len(all_fns)} FNs + {len(all_tps)} TPs")
    return 0

if __name__ == "__main__":
    run_script(main)
