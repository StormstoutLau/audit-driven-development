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
                 "--output", f"{args.audit_dir}/guards.learned.yml"]},
        {"name": "spec_graph (index rebuild)",
         "cmd": ["python", "scripts/spec_graph.py",
                 "--spec", "SKILL.md", "--adrs", "docs",
                 "--guards", f"{args.audit_dir}/guards.learned.yml",
                 "--repo", ".", "--output", f"{args.audit_dir}/spec_graph.json"]},
        # ── v2.5: 接通断裂管道 (B1/B3/B6 fix) ──
        {"name": "diff_miner (pattern mining)",
         "cmd": ["python", "scripts/diff_miner.py",
                 "--repo", ".", "--since", "2026-07-01",
                 "--output", f"{args.audit_dir}/pattern_candidates.json"]},
        {"name": "fix_history (RL threshold)",
         "cmd": ["python", "scripts/fix_history.py",
                 "--findings", f"{args.audit_dir}/issues.json",
                 "--history-dir", args.audit_dir,
                 "--output", f"{args.audit_dir}/augmented_issues.json"]},
        {"name": "rule_suggester (FP/FN→rule)",
         "cmd": ["python", "scripts/rule_suggester.py",
                 "--audit-log-dir", "docs/audit-log",
                 "--hallucination-log", f"{args.audit_dir}/hallucination_log.json",
                 "--output", f"{args.audit_dir}/rule_suggestions.json"]},
        # ── v2.5 阶段 3: Benchmark → Self-Calibration ──
        {"name": "benchmark_calibrate (recall check)",
         "cmd": ["python", "scripts/run_phase8_benchmark.py",
                 "--output", f"{args.audit_dir}/benchmark_latest.json",
                 "--baseline", "docs/benchmark/v2.4-phase8-performance-data.json"]},
    ]

    results = []
    for step in steps:
        # benchmark_calibrate 需要更长 timeout (实测 ~175s), 其他步骤 30s
        timeout = 240 if "benchmark" in step["name"] else 30
        try:
            r = subprocess.run(step["cmd"], capture_output=True, text=True,
                               timeout=timeout, cwd=str(Path.cwd()))
            status = "OK" if r.returncode == 0 else f"FAIL({r.returncode})"
        except subprocess.TimeoutExpired:
            status = f"TIMEOUT({timeout}s)"
        results.append(f"  {step['name']}: {status}")
    for line in results:
        print(line)

    if args.push_remote:
        print(f"  add-rules push: configured ({args.push_remote}) — manual push only")

    print("live_knowledge: knowledge pipeline updated")
    return 0

if __name__ == "__main__":
    run_script(main)
