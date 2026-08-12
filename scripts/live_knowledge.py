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

    # v2.7.3 断点⑤: 当 issues.json 不存在时, fallback 到 benchmark findings.json
    # 使用 --findings-format benchmark 让 fix_history 能直接处理 benchmark 格式
    issues_path = Path(args.audit_dir) / "issues.json"
    if issues_path.exists():
        fix_history_cmd = ["python", "scripts/fix_history.py",
                           "--findings", str(issues_path),
                           "--history-dir", args.audit_dir,
                           "--output", f"{args.audit_dir}/augmented_issues.json"]
        fix_history_name = "fix_history (RL threshold, audit format)"
    else:
        # v2.7.3: fallback 到第一个可用的 benchmark findings.json
        benchmark_dirs = [
            "docs/benchmark/add-v2.4-self-audit",
            "docs/benchmark/swebench-verified",
            "docs/benchmark/defects4j",
        ]
        fallback_findings = None
        for bd in benchmark_dirs:
            candidate = Path(bd) / "findings.json"
            if candidate.exists():
                fallback_findings = str(candidate)
                break
        if fallback_findings:
            fix_history_cmd = ["python", "scripts/fix_history.py",
                               "--findings", fallback_findings,
                               "--history-dir", args.audit_dir,
                               "--output", f"{args.audit_dir}/augmented_issues.json",
                               "--findings-format", "benchmark"]
            fix_history_name = f"fix_history (RL threshold, benchmark format, src={fallback_findings})"
        else:
            # 无可用 findings → 跳过 fix_history
            fix_history_cmd = None
            fix_history_name = "fix_history (SKIPPED: no issues.json or benchmark findings)"

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
        {"name": fix_history_name,
         "cmd": fix_history_cmd},
        # v2.7.3: benchmark_calibrate 移到 rule_suggester 之前
        # benchmark 运行时将 hallucinations 写入 hallucination_log.json (断点①)
        # rule_suggester 随后消费 hallucination_log 生成反例规则 (断点②)
        {"name": "benchmark_calibrate (recall check + hallucination_log)",
         "cmd": ["python", "scripts/run_phase8_benchmark.py",
                 "--output", f"{args.audit_dir}/benchmark_latest.json",
                 "--baseline", "docs/benchmark/v2.4-phase8-performance-data.json"]},
        {"name": "rule_suggester (FP/FN→rule, consumes hallucination_log)",
         "cmd": ["python", "scripts/rule_suggester.py",
                 "--audit-log-dir", "docs/audit-log",
                 "--hallucination-log", f"{args.audit_dir}/hallucination_log.json",
                 "--output", f"{args.audit_dir}/rule_suggestions.json"]},
    ]

    results = []
    for step in steps:
        # v2.7.3: fix_history cmd 为 None 时跳过
        if step["cmd"] is None:
            results.append(f"  {step['name']}: SKIPPED")
            continue
        # benchmark_calibrate 需要更长 timeout (实测 ~175s), 其他步骤 30s
        timeout = 240 if "benchmark" in step["name"] else 30
        try:
            r = subprocess.run(step["cmd"], capture_output=True, text=True,
                               timeout=timeout, cwd=str(Path.cwd()))
            status = "OK" if r.returncode == 0 else f"FAIL({r.returncode})"
            # 失败时输出 stderr 摘要便于诊断
            if r.returncode != 0 and r.stderr:
                status += f" stderr={r.stderr[:150]}"
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
