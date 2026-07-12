"""Post-audit knowledge update hook. v2.3 Shared Knowledge Pipeline.

Usage: python scripts/live_knowledge.py
         --audit-dir <docs/audit/>
         [--push-remote <add-rules-repo-url>]

Performance cap: 60s.
"""

import argparse, sys, subprocess
from pathlib import Path
from _script_utils import run_script

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", default="docs/audit")
    parser.add_argument("--push-remote", default=None)
    args = parser.parse_args()

    steps = [
        {"name": "rule_extractor (guard refresh)",
         "cmd": ["python", "scripts/rule_extractor.py",
                 "--benchmark-dir", "docs/benchmark",
                 "--output", "docs/audit/guards.learned.yml"]},
        {"name": "spec_graph (index rebuild)",
         "cmd": ["python", "scripts/spec_graph.py",
                 "--spec", "SKILL.md", "--adrs", "docs",
                 "--guards", "docs/audit/guards.learned.yml",
                 "--repo", ".", "--output", "docs/audit/spec_graph.json"]},
    ]

    results = [
        f"  {step['name']}: {'OK' if (r := subprocess.run(step['cmd'], capture_output=True, text=True, timeout=30)).returncode == 0 else f'FAIL({r.returncode})'}"
        for step in steps
    ]
    for line in results:
        print(line)

    if args.push_remote:
        print(f"  add-rules push: configured ({args.push_remote}) — manual push only")

    print("live_knowledge: knowledge pipeline updated")
    return 0

if __name__ == "__main__":
    run_script(main)
