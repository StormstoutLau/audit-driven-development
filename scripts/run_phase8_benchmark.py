"""Phase 8 全量修复后性能评估脚本。

重跑 3 个测试库 (ADD self + stdlib + itsdangerous), 收集:
  - Tier 1/2/3 触发分布
  - Precision / Recall / F1
  - 每库总延迟 + 平均每 finding 延迟
  - 与 v2.4 修复前 (2026-08-05 报告) 对比

输出:
  - docs/benchmark/v2.4-phase8-performance-data.json  (结构化数据)
  - 控制台汇总表

用法:
  python scripts/run_phase8_benchmark.py
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import verify_findings

BENCH_DIR = ROOT / "docs" / "benchmark"


# ── 测试矩阵 ────────────────────────────────────────────────────────────

TEST_MATRIX = [
    {
        "name": "ADD self-audit",
        "findings_path": BENCH_DIR / "add-v2.4-self-audit" / "findings.json",
        "repo_path": ROOT,
        "ground_truth_path": BENCH_DIR / "add-v2.4-self-audit" / "ground_truth.json",
    },
    {
        "name": "Python stdlib (json/csv)",
        "findings_path": BENCH_DIR / "stdlib-oss-test" / "findings.json",
        "repo_path": Path(os.path.dirname(os.__file__)),
        "ground_truth_path": BENCH_DIR / "stdlib-oss-test" / "ground_truth.json",
    },
    {
        "name": "itsdangerous 2.2.0",
        "findings_path": BENCH_DIR / "itsdangerous-2.2.0" / "findings.json",
        "repo_path": BENCH_DIR / "oss-cache" / "itsdangerous-2.2.0" / "src" / "itsdangerous",
        "ground_truth_path": BENCH_DIR / "itsdangerous-2.2.0" / "ground_truth.json",
    },
]


def load_findings(path):
    """Load findings JSON, return list of finding dicts."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "findings" in data:
        return data["findings"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unexpected findings JSON structure in {path}")


def load_ground_truth(path):
    """Load ground truth JSON, return {id: {ground_truth, expected_action, ...}}."""
    if path is None or not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {item["id"]: item for item in data}


def classify_outcome(finding_id, action, ground_truth):
    """Classify outcome as TP/FP/FN/TN based on ground truth.

    For hallucinations (ground_truth starts with 'hallucination_'):
      - action == "unverified" (removed) → TP (correctly identified hallucination)
      - action in ("verified", "partial", "verified_l1l2") → FN (missed hallucination)

    For real bugs (ground_truth starts with 'real_'):
      - action in ("verified", "partial", "verified_l1l2") → TN (correctly kept real bug)
      - action == "unverified" (removed) → FP (wrongly removed real bug)
    """
    gt = ground_truth.get(finding_id, {})
    gt_label = gt.get("ground_truth", "unknown")

    is_hallucination = gt_label.startswith("hallucination_")
    is_real = gt_label.startswith("real_")

    if is_hallucination:
        if action == "unverified":
            return "TP"  # correctly removed hallucination
        else:
            return "FN"  # missed hallucination (kept or downgraded)
    elif is_real:
        if action == "unverified":
            return "FP"  # wrongly removed real bug
        else:
            return "TN"  # correctly kept real bug
    else:
        return "UNKNOWN"  # ground truth unknown


def extract_tier_info(verified_finding):
    """Extract Tier distribution from a verified finding's L4 checks.

    Also handles hallucination entries which carry 'best_tier' field (Phase 8 fix).
    """
    # Hallucination entries: use best_tier directly
    if "best_tier" in verified_finding:
        bt = verified_finding["best_tier"]
        if bt > 0:
            return [{"check": "hallucination", "tier": bt, "verified": False}]
        return []

    l4 = verified_finding.get("l4", {})
    checks = l4.get("checks", {})
    tiers = []
    for check_name, check_data in checks.items():
        if isinstance(check_data, dict):
            tier = check_data.get("tier", 0)
            verified = check_data.get("verified")
            tiers.append({"check": check_name, "tier": tier, "verified": verified})
    return tiers


def run_benchmark(test_config):
    """Run benchmark on a single test config, return metrics dict."""
    name = test_config["name"]
    findings_path = test_config["findings_path"]
    repo_path = test_config["repo_path"]
    gt_path = test_config["ground_truth_path"]

    print(f"\n{'='*60}")
    print(f"  Benchmark: {name}")
    print(f"{'='*60}")

    findings = load_findings(findings_path)
    ground_truth = load_ground_truth(gt_path)

    print(f"  Findings: {len(findings)}")
    print(f"  Ground truth entries: {len(ground_truth)}")
    print(f"  Repo: {repo_path}")

    # Run verification with timing
    t0 = time.perf_counter()
    verified, hallucinations, downgraded = verify_findings.verify_all_findings(
        findings, str(repo_path)
    )
    total_ms = (time.perf_counter() - t0) * 1000

    # Build finding_id → action map
    action_map = {}
    tier_distribution = {"tier1": 0, "tier2": 0, "tier3": 0, "no_l4": 0}
    for f in verified:
        fid = f.get("id", "unknown")
        action = f.get("_phase35_action", f.get("action", "unknown"))
        action_map[fid] = action
        # Extract tier info
        tiers = extract_tier_info(f)
        if not tiers:
            tier_distribution["no_l4"] += 1
        else:
            # Use the highest tier that ran (lowest number = highest priority)
            min_tier = min(t["tier"] for t in tiers if t["tier"] > 0)
            if min_tier == 1:
                tier_distribution["tier1"] += 1
            elif min_tier == 2:
                tier_distribution["tier2"] += 1
            elif min_tier == 3:
                tier_distribution["tier3"] += 1
            else:
                tier_distribution["no_l4"] += 1

    for h in hallucinations:
        fid = h.get("id", "unknown")
        action_map[fid] = "unverified"
        # Extract tier info from hallucination entries too
        tiers = extract_tier_info(h)
        if not tiers:
            tier_distribution["no_l4"] += 1
        else:
            min_tier = min(t["tier"] for t in tiers if t["tier"] > 0)
            if min_tier == 1:
                tier_distribution["tier1"] += 1
            elif min_tier == 2:
                tier_distribution["tier2"] += 1
            elif min_tier == 3:
                tier_distribution["tier3"] += 1
            else:
                tier_distribution["no_l4"] += 1

    # Classify outcomes
    tp = fp = fn = tn = 0
    unknown = 0
    per_finding_results = []
    for f in findings:
        fid = f.get("id", "unknown")
        action = action_map.get(fid, "unknown")
        outcome = classify_outcome(fid, action, ground_truth)
        if outcome == "TP":
            tp += 1
        elif outcome == "FP":
            fp += 1
        elif outcome == "FN":
            fn += 1
        elif outcome == "TN":
            tn += 1
        else:
            unknown += 1

        per_finding_results.append({
            "id": fid,
            "action": action,
            "ground_truth": ground_truth.get(fid, {}).get("ground_truth", "unknown"),
            "outcome": outcome,
        })

    # Calculate metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    avg_ms = total_ms / len(findings) if findings else 0

    metrics = {
        "name": name,
        "total_findings": len(findings),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn, "unknown": unknown,
        "precision": round(precision * 100, 1),
        "recall": round(recall * 100, 1),
        "f1": round(f1 * 100, 1),
        "total_latency_ms": round(total_ms, 1),
        "avg_latency_per_finding_ms": round(avg_ms, 1),
        "tier_distribution": tier_distribution,
        "hallucinations_removed": len(hallucinations),
        "downgraded": len(downgraded),
        "per_finding": per_finding_results,
    }

    print(f"\n  Results:")
    print(f"    TP={tp}, FP={fp}, FN={fn}, TN={tn}, Unknown={unknown}")
    print(f"    Precision={metrics['precision']}%, Recall={metrics['recall']}%, F1={metrics['f1']}%")
    print(f"    Total latency: {metrics['total_latency_ms']}ms ({metrics['avg_latency_per_finding_ms']}ms/finding)")
    print(f"    Tier distribution: {tier_distribution}")
    print(f"    Hallucinations removed: {len(hallucinations)}, Downgraded: {len(downgraded)}")

    return metrics


def main():
    print("=" * 70)
    print("Phase 8 全量修复后性能评估")
    print("=" * 70)
    print(f"\nFramework: ADD v2.4 (Phase 8 fix: import node naming + degradation logic)")
    print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Check Joern availability
    try:
        import joern_cpg
        joern_cpg._WSL_DETECT_CACHE = None
        joern_avail = joern_cpg.is_available()
    except Exception:
        joern_avail = False
    print(f"Joern Tier 1 available: {joern_avail}")

    all_metrics = []
    for test_config in TEST_MATRIX:
        try:
            metrics = run_benchmark(test_config)
            all_metrics.append(metrics)
        except Exception as e:
            print(f"\n  ERROR running {test_config['name']}: {e}")
            import traceback
            traceback.print_exc()
            all_metrics.append({
                "name": test_config["name"],
                "error": str(e),
                "total_findings": 0,
            })

    # Aggregate
    print(f"\n{'='*70}")
    print(f"  Aggregate Results")
    print(f"{'='*70}")

    valid = [m for m in all_metrics if "error" not in m]
    total_tp = sum(m["tp"] for m in valid)
    total_fp = sum(m["fp"] for m in valid)
    total_fn = sum(m["fn"] for m in valid)
    total_tn = sum(m["tn"] for m in valid)
    total_findings = sum(m["total_findings"] for m in valid)
    total_latency = sum(m["total_latency_ms"] for m in valid)

    agg_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    agg_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    agg_f1 = 2 * agg_precision * agg_recall / (agg_precision + agg_recall) if (agg_precision + agg_recall) > 0 else 0

    agg_tier = {"tier1": 0, "tier2": 0, "tier3": 0, "no_l4": 0}
    for m in valid:
        for k in agg_tier:
            agg_tier[k] += m["tier_distribution"].get(k, 0)

    print(f"\n  Total findings: {total_findings}")
    print(f"  TP={total_tp}, FP={total_fp}, FN={total_fn}, TN={total_tn}")
    print(f"  Precision={agg_precision*100:.1f}%, Recall={agg_recall*100:.1f}%, F1={agg_f1*100:.1f}%")
    print(f"  Total latency: {total_latency:.1f}ms")
    print(f"  Tier distribution: {agg_tier}")

    # Comparison with v2.4 baseline (2026-08-05 report)
    print(f"\n{'='*70}")
    print(f"  Comparison with v2.4 Baseline (2026-08-05)")
    print(f"{'='*70}")

    baseline = {
        "precision": 100.0, "recall": 42.1, "f1": 59.3,
        "tp": 8, "fp": 0, "fn": 11, "tn": 8,
        "tier1": 0, "tier2": 8, "tier3": 11,  # estimated from report
    }
    current = {
        "precision": round(agg_precision * 100, 1),
        "recall": round(agg_recall * 100, 1),
        "f1": round(agg_f1 * 100, 1),
        "tp": total_tp, "fp": total_fp, "fn": total_fn, "tn": total_tn,
        "tier1": agg_tier["tier1"], "tier2": agg_tier["tier2"], "tier3": agg_tier["tier3"],
    }

    print(f"\n  {'Metric':<15} {'Baseline':>10} {'Phase 8':>10} {'Delta':>10}")
    print(f"  {'-'*45}")
    for key in ["precision", "recall", "f1", "tp", "fp", "fn", "tn", "tier1", "tier2", "tier3"]:
        b = baseline[key]
        c = current[key]
        delta = c - b
        sign = "+" if delta > 0 else ""
        print(f"  {key:<15} {b:>10} {c:>10} {sign}{delta:>9}")

    # Save structured data
    output = {
        "phase": "Phase 8 Performance Evaluation",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "framework_version": "v2.4-phase8",
        "joern_available": joern_avail,
        "per_test": all_metrics,
        "aggregate": {
            "total_findings": total_findings,
            "tp": total_tp, "fp": total_fp, "fn": total_fn, "tn": total_tn,
            "precision": round(agg_precision * 100, 1),
            "recall": round(agg_recall * 100, 1),
            "f1": round(agg_f1 * 100, 1),
            "total_latency_ms": round(total_latency, 1),
            "tier_distribution": agg_tier,
        },
        "baseline_v24_20260805": baseline,
        "delta_from_baseline": {
            k: round(current[k] - baseline[k], 1) for k in baseline
        },
    }

    output_path = BENCH_DIR / "v2.4-phase8-performance-data.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Data saved to: {output_path}")

    return output


if __name__ == "__main__":
    main()
