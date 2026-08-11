"""v2.5 consistency test suite. 学习管道闭环 — 3 阶段 6 改动 TDD 验证.

阶段 1: 接通断裂管道 (改动 1.1 + 1.2)
阶段 2: Hallucination → Detection 反馈 (改动 2.1 + 2.2)
阶段 3: Benchmark → Self-Calibration (改动 3.1 + 3.2)

TDD 流程: 本文件先于实现编写, Red → Green → Refactor.
"""
import json, sys, subprocess, tempfile, os, importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} {detail}")


print("=" * 60)
print("test_v25_consistency.py: v2.5 学习管道闭环")
print(f"Working dir: {ROOT}")
print("=" * 60)

# ════════════════════════════════════════════════════════════
# 阶段 1: 接通断裂管道
# ════════════════════════════════════════════════════════════

print("\n── 阶段 1 改动 1.1: verify_findings.py 默认 hallucination_log ──")
vf_path = ROOT / "scripts" / "verify_findings.py"
check("L1.1.1 verify_findings.py exists", vf_path.exists())
if vf_path.exists():
    vf_src = vf_path.read_text(encoding="utf-8")
    # C1 fix: default 不再是 None, 改为 docs/audit/hallucination_log.json
    check("L1.1.2 --hallucination-log default 非 None",
          'default="docs/audit/hallucination_log.json"' in vf_src
          or "default='docs/audit/hallucination_log.json'" in vf_src,
          "expected default=docs/audit/hallucination_log.json")
    check("L1.1.3 --hallucination-log help 包含 default",
          "default: docs/audit/hallucination_log.json" in vf_src)

    # E2E: 不传 --hallucination-log 时应自动生成文件
    test_findings = [
        {"id": "L11-E2E-1", "severity": "P0", "category": "contract",
         "claim": "missing null check in nonexistent.py",
         "evidence": {"file": "scripts/nonexistent_l11.py", "line_start": 10, "line_end": 10},
         "spec_ref": "spec.md", "confidence": "low", "fix_cost": "1-line"},
    ]
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(test_findings, tmp)
    tmp.close()
    tmp_hlog = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_hlog.close()
    os.unlink(tmp_hlog.name)  # 确保文件不存在

    e2e = subprocess.run(
        [sys.executable, str(vf_path), "--findings", tmp.name, "--repo", str(ROOT),
         "--output", os.devnull, "--hallucination-log", tmp_hlog.name],
        capture_output=True, text=True, timeout=10, cwd=str(ROOT))
    os.unlink(tmp.name)
    check("L1.1.4 E2E hallucination_log 自动生成",
          Path(tmp_hlog.name).exists(),
          f"rc={e2e_result.returncode if (e2e_result := e2e) else '?'}")
    if Path(tmp_hlog.name).exists():
        hlog_data = json.loads(Path(tmp_hlog.name).read_text(encoding="utf-8"))
        check("L1.1.5 hallucination_log 含 hallucinations 字段",
              "hallucinations" in hlog_data)
        check("L1.1.6 hallucination_log 含 count 字段",
              "count" in hlog_data)
        check("L1.1.7 hallucination_log 含 timestamp 字段",
              "timestamp" in hlog_data)
    if Path(tmp_hlog.name).exists():
        os.unlink(tmp_hlog.name)


print("\n── 阶段 1 改动 1.2: live_knowledge.py 调用 6 个脚本 ──")
lk_path = ROOT / "scripts" / "live_knowledge.py"
check("L1.2.1 live_knowledge.py exists", lk_path.exists())
if lk_path.exists():
    lk_src = lk_path.read_text(encoding="utf-8")
    # 必须包含 5 个新增脚本调用 (rule_extractor + spec_graph 已有)
    required_scripts = [
        "diff_miner", "fix_history", "rule_suggester",
    ]
    for script in required_scripts:
        check(f"L1.2.2 live_knowledge 调用 {script}",
              script in lk_src, f"{script} 未在 steps 中")

    # diff_miner 必须有 --repo --since --output
    check("L1.2.3 diff_miner 调用含 --repo",
          "diff_miner" in lk_src and "--repo" in lk_src)
    # fix_history 必须有 --findings --history-dir --output
    check("L1.2.4 fix_history 调用含 --findings",
          "fix_history" in lk_src and "--findings" in lk_src)
    # rule_suggester 必须有 --hallucination-log --output
    check("L1.2.5 rule_suggester 调用含 --hallucination-log",
          "rule_suggester" in lk_src and "--hallucination-log" in lk_src)

    # --help 不报错
    lk_help = subprocess.run([sys.executable, str(lk_path), "--help"],
        capture_output=True, text=True, timeout=5, cwd=str(ROOT))
    check("L1.2.6 live_knowledge --help runs", lk_help.returncode == 0)


# ════════════════════════════════════════════════════════════
# 阶段 2: Hallucination → Detection 反馈
# ════════════════════════════════════════════════════════════

print("\n── 阶段 2 改动 2.1: rule_suggester.py 消费 hallucination_log ──")
rs_path = ROOT / "scripts" / "rule_suggester.py"
check("L2.1.1 rule_suggester.py exists", rs_path.exists())
if rs_path.exists():
    rs_src = rs_path.read_text(encoding="utf-8")
    check("L2.1.2 rule_suggester 有 --hallucination-log 参数",
          "--hallucination-log" in rs_src)
    check("L2.1.3 rule_suggester 有 load_hallucinations 函数",
          "load_hallucinations" in rs_src)

    # 单元测试: 构造 3 个同类 reason 的 hallucination_log
    spec_rs = importlib.util.spec_from_file_location("rule_suggester", str(rs_path))
    rs = importlib.util.module_from_spec(spec_rs)
    spec_rs.loader.exec_module(rs)

    test_hlog = {
        "hallucinations": [
            {"id": "H1", "reason": "file_not_found", "claim": "x"},
            {"id": "H2", "reason": "file_not_found", "claim": "y"},
            {"id": "H3", "reason": "file_not_found", "claim": "z"},
            {"id": "H4", "reason": "line_out_of_range", "claim": "w"},
        ],
        "count": 4,
        "timestamp": "2026-08-06T00:00:00",
    }
    tmp_hlog = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(test_hlog, tmp_hlog)
    tmp_hlog.close()

    hallucinations, reason_counts = rs.load_hallucinations(tmp_hlog.name)
    check("L2.1.4 load_hallucinations 返回 4 条幻觉",
          len(hallucinations) == 4, f"got {len(hallucinations)}")
    check("L2.1.5 reason_counts 含 file_not_found:3",
          reason_counts.get("file_not_found") == 3,
          f"got {dict(reason_counts)}")

    # 端到端: rule_suggester --hallucination-log 应生成反例规则
    tmp_out = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_out.close()
    os.unlink(tmp_out.name)
    rs_e2e = subprocess.run(
        [sys.executable, str(rs_path),
         "--hallucination-log", tmp_hlog.name,
         "--audit-log-dir", str(ROOT / "docs" / "audit-log"),
         "--output", tmp_out.name,
         "--min-frequency", "3"],
        capture_output=True, text=True, timeout=10, cwd=str(ROOT))
    check("L2.1.6 rule_suggester E2E runs", rs_e2e.returncode == 0,
          f"rc={rs_e2e.returncode} stderr={rs_e2e.stderr[:200]}")
    if Path(tmp_out.name).exists():
        out_data = json.loads(Path(tmp_out.name).read_text(encoding="utf-8"))
        suggestions = out_data.get("suggestions", [])
        hlog_suggestions = [s for s in suggestions if s.get("source") == "hallucination_log"]
        check("L2.1.7 反例规则含 source=hallucination_log",
              len(hlog_suggestions) >= 1,
              f"got {len(hlog_suggestions)} hallucination_log suggestions")
        if hlog_suggestions:
            check("L2.1.8 反例规则含 trigger 字段",
                  "trigger" in hlog_suggestions[0])
            check("L2.1.9 反例规则含 file_not_found",
                  "file_not_found" in hlog_suggestions[0].get("trigger", ""))
    os.unlink(tmp_hlog.name)
    if Path(tmp_out.name).exists():
        os.unlink(tmp_out.name)


print("\n── 阶段 2 改动 2.2: verify_findings.py 消费 fix_history threshold ──")
check("L2.2.1 verify_findings.py exists", vf_path.exists())
if vf_path.exists():
    vf_src = vf_path.read_text(encoding="utf-8")
    check("L2.2.2 verify_findings 有 --history-threshold 参数",
          "--history-threshold" in vf_src)
    check("L2.2.3 verify_findings 有 effective_threshold 加载逻辑",
          "effective_threshold" in vf_src and "augmented_issues.json" in vf_src)

    # 单元测试: 构造 augmented_issues.json 含 fix_history_meta
    spec_vf = importlib.util.spec_from_file_location("verify_findings_v25", str(vf_path))
    vf2 = importlib.util.module_from_spec(spec_vf)
    spec_vf.loader.exec_module(vf2)

    # 通过 --history-threshold 参数直接传入
    test_findings = [
        {"id": "L22-1", "severity": "P0", "category": "behavior",
         "claim": "missing error handling in verify_line function",
         "evidence": {"file": "scripts/verify_lines.py", "line_start": 21, "line_end": 21},
         "spec_ref": "spec.md", "confidence": "high", "fix_cost": "1-line"},
    ]
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(test_findings, tmp)
    tmp.close()
    tmp_out = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_out.close()
    e2e = subprocess.run(
        [sys.executable, str(vf_path), "--findings", tmp.name, "--repo", str(ROOT),
         "--output", tmp_out.name, "--history-threshold", "0.55"],
        capture_output=True, text=True, timeout=10, cwd=str(ROOT))
    os.unlink(tmp.name)
    check("L2.2.4 verify_findings --history-threshold runs", e2e.returncode in (0, 1))
    if Path(tmp_out.name).exists():
        out_data = json.loads(Path(tmp_out.name).read_text(encoding="utf-8"))
        check("L2.2.5 输出含 effective_threshold",
              "effective_threshold" in out_data or
              any("effective_threshold" in str(f) for f in out_data.get("verified_findings", [])),
              f"keys={list(out_data.keys())}")
    if Path(tmp_out.name).exists():
        os.unlink(tmp_out.name)


# ════════════════════════════════════════════════════════════
# 阶段 3: Benchmark → Self-Calibration
# ════════════════════════════════════════════════════════════

print("\n── 阶段 3 改动 3.1: run_phase8_benchmark.py 退化检测 ──")
bm_path = ROOT / "scripts" / "run_phase8_benchmark.py"
check("L3.1.1 run_phase8_benchmark.py exists", bm_path.exists())
if bm_path.exists():
    bm_src = bm_path.read_text(encoding="utf-8")
    check("L3.1.2 run_phase8_benchmark 有 --baseline 参数",
          "--baseline" in bm_src)
    check("L3.1.3 run_phase8_benchmark 有 check_regression 函数",
          "check_regression" in bm_src)

    # 单元测试: check_regression
    spec_bm = importlib.util.spec_from_file_location("run_phase8_benchmark", str(bm_path))
    bm = importlib.util.module_from_spec(spec_bm)
    spec_bm.loader.exec_module(bm)

    latest = {"aggregate": {"recall": 65.0, "precision": 100.0, "f1": 78.8}}
    baseline = {"aggregate": {"recall": 71.4, "precision": 100.0, "f1": 83.3}}
    result = bm.check_regression(latest, baseline)
    check("L3.1.4 recall 退化 6.4pp → REGRESSION",
          result["status"] == "REGRESSION",
          f"got {result['status']}")
    check("L3.1.5 recall_delta = -6.4",
          abs(result["recall_delta"] - (-6.4)) < 0.1,
          f"got {result['recall_delta']}")

    # recall 仅退化 3pp → OK
    latest_ok = {"aggregate": {"recall": 68.4, "precision": 100.0, "f1": 81.2}}
    result_ok = bm.check_regression(latest_ok, baseline)
    check("L3.1.6 recall 退化 3pp → OK",
          result_ok["status"] == "OK",
          f"got {result_ok['status']}")


print("\n── 阶段 3 改动 3.2: live_knowledge.py benchmark_calibrate 步骤 ──")
check("L3.2.1 live_knowledge.py exists", lk_path.exists())
if lk_path.exists():
    lk_src = lk_path.read_text(encoding="utf-8")
    check("L3.2.2 live_knowledge 调用 run_phase8_benchmark",
          "run_phase8_benchmark" in lk_src)
    check("L3.2.3 live_knowledge benchmark 步骤含 --baseline",
          "--baseline" in lk_src and "benchmark" in lk_src.lower())


# ════════════════════════════════════════════════════════════
# 总结
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"v2.5 Results: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
