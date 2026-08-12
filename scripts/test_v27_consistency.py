"""v2.7.3 consistency test suite. 学习管道闭环修复 — 5 个断点 TDD 验证.

断点①: run_phase8_benchmark.py 将 hallucinations 写入 docs/audit/hallucination_log.json
断点③: classify_claim() 读取 rule_suggestions.json 中的反例规则
断点④: verify_all_findings() 接受 history_threshold 参数并传递
断点⑤: fix_history.py 支持 --findings-format benchmark

TDD 流程: 本文件先于实现编写, Red → Green → Refactor.
"""
import json, sys, os, importlib.util, tempfile, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

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
print("test_v27_consistency.py: v2.7.3 学习管道闭环修复")
print(f"Working dir: {ROOT}")
print("=" * 60)

# ════════════════════════════════════════════════════════════
# 断点①: run_phase8_benchmark.py 写入 hallucination_log
# ════════════════════════════════════════════════════════════

print("\n── 断点①: hallucination_log 写入 ──")
bm_path = ROOT / "scripts" / "run_phase8_benchmark.py"
check("L7.3.1.1 run_phase8_benchmark.py exists", bm_path.exists())

if bm_path.exists():
    bm_src = bm_path.read_text(encoding="utf-8")

    # 动态导入模块
    spec_bm = importlib.util.spec_from_file_location("run_phase8_benchmark", str(bm_path))
    bm = importlib.util.module_from_spec(spec_bm)
    spec_bm.loader.exec_module(bm)

    # ── L7.3.1.2: run_benchmark 接受 hallucination_log_path 参数 ──
    check("L7.3.1.2 run_benchmark 接受 hallucination_log_path 参数",
          "hallucination_log_path" in bm_src,
          "missing hallucination_log_path param")

    # ── L7.3.1.3: 端到端测试 — 运行后 hallucination_log 非空 ──
    print("\n  ── 端到端: hallucination_log 写入 ──")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # 构造一个会产生 hallucination 的 benchmark
        # 使用不存在的文件路径 → L1 file_not_found → hallucination
        fake_findings = {
            "project": "test-hallucination-log",
            "findings": [
                {
                    "id": "HAL-TEST-001",
                    "severity": "P0",
                    "claim": "dead code in nonexistent_file.py:999",
                    "evidence": {"file": "nonexistent_file.py", "line_start": 999},
                    "dimension": "functional",
                },
            ],
        }
        bench_dir = tmpdir / "test-bench"
        bench_dir.mkdir()
        (bench_dir / "findings.json").write_text(
            json.dumps(fake_findings, ensure_ascii=False), encoding="utf-8"
        )
        (bench_dir / "ground_truth.json").write_text(
            json.dumps([
                {"id": "HAL-TEST-001", "ground_truth": "hallucination_file_not_found",
                 "expected_action": "removed"}
            ], ensure_ascii=False),
            encoding="utf-8",
        )

        hlog_path = tmpdir / "hallucination_log.json"

        # 调用 run_benchmark
        test_config = {
            "name": "test-hallucination-log",
            "findings_path": bench_dir / "findings.json",
            "repo_path": tmpdir,
            "ground_truth_path": bench_dir / "ground_truth.json",
        }
        try:
            metrics = bm.run_benchmark(test_config, hallucination_log_path=str(hlog_path))
            check("L7.3.1.3 run_benchmark 带 hallucination_log_path 运行成功",
                  metrics is not None,
                  f"got {metrics}")
        except Exception as e:
            check("L7.3.1.3 run_benchmark 带 hallucination_log_path 运行成功",
                  False, f"exception: {e}")

        check("L7.3.1.4 hallucination_log.json 生成",
              hlog_path.exists(),
              f"path: {hlog_path}")

        if hlog_path.exists():
            hlog_data = json.loads(hlog_path.read_text(encoding="utf-8"))
            check("L7.3.1.5 hallucination_log count > 0",
                  hlog_data.get("count", 0) > 0,
                  f"count: {hlog_data.get('count')}")
            check("L7.3.1.6 hallucination_log 含 hallucinations 数组",
                  "hallucinations" in hlog_data and isinstance(hlog_data["hallucinations"], list))
            if hlog_data.get("hallucinations"):
                check("L7.3.1.7 hallucation 含 id 字段",
                      "id" in hlog_data["hallucinations"][0],
                      f"keys: {list(hlog_data['hallucinations'][0].keys())}")


# ════════════════════════════════════════════════════════════
# 断点③: classify_claim() 读取 rule_suggestions.json
# ════════════════════════════════════════════════════════════

print("\n── 断点③: classify_claim 读取反例规则 ──")
vf_path = ROOT / "scripts" / "verify_findings.py"
check("L7.3.2.1 verify_findings.py exists", vf_path.exists())

if vf_path.exists():
    vf_src = vf_path.read_text(encoding="utf-8")

    # 动态导入模块
    spec_vf = importlib.util.spec_from_file_location("verify_findings", str(vf_path))
    vf = importlib.util.module_from_spec(spec_vf)
    spec_vf.loader.exec_module(vf)

    # ── L7.3.2.2: _load_learned_rules 函数存在 ──
    check("L7.3.2.2 _load_learned_rules 函数存在",
          hasattr(vf, "_load_learned_rules"),
          "missing _load_learned_rules")

    # ── L7.3.2.3: _load_learned_rules 读取不存在的文件返回空列表 ──
    if hasattr(vf, "_load_learned_rules"):
        # 重置缓存
        if hasattr(vf, "_LEARNED_RULES_CACHE"):
            vf._LEARNED_RULES_CACHE = None
        rules = vf._load_learned_rules("/nonexistent/path/rules.json")
        check("L7.3.2.3 不存在的规则文件返回空列表",
              rules == [],
              f"got {rules}")

    # ── L7.3.2.4: _load_learned_rules 读取有效规则文件 ──
    if hasattr(vf, "_load_learned_rules"):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            rules_file = tmpdir / "test_rules.json"
            test_rules = {
                "suggestions": [
                    {
                        "trigger": "3 hallucinations with reason: file_not_found",
                        "suggestion": "Add guard: reject findings matching pattern 'file_not_found'",
                        "source": "hallucination_log",
                        "severity": "critical",
                        "reason": "file_not_found_pattern",
                        "count": 3,
                    },
                ],
            }
            rules_file.write_text(json.dumps(test_rules), encoding="utf-8")

            # 重置缓存
            vf._LEARNED_RULES_CACHE = None
            rules = vf._load_learned_rules(str(rules_file))
            check("L7.3.2.4 有效规则文件返回 1 条规则",
                  len(rules) == 1,
                  f"got {len(rules)} rules")
            if len(rules) == 1:
                check("L7.3.2.5 规则内容正确",
                      rules[0].get("reason") == "file_not_found_pattern",
                      f"got {rules[0].get('reason')}")

    # ── L7.3.2.6: classify_claim 真正调用 _load_learned_rules (闭环消费端) ──
    # 审计发现: _load_learned_rules 曾是 dead code, classify_claim 未调用它
    # 修复后: classify_claim 应调用 _load_learned_rules 并标记匹配的 claim
    if hasattr(vf, "classify_claim") and hasattr(vf, "_load_learned_rules"):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            rules_file = tmpdir / "test_rules_classify.json"
            test_rules = {
                "suggestions": [
                    {
                        "trigger": "test trigger",
                        "suggestion": "test suggestion",
                        "source": "hallucination_log",
                        "severity": "critical",
                        "reason": "file_not_found_pattern",
                        "count": 5,
                    },
                ],
            }
            rules_file.write_text(json.dumps(test_rules), encoding="utf-8")

            # 重置缓存 + 加载测试规则
            vf._LEARNED_RULES_CACHE = None
            vf._load_learned_rules(str(rules_file))

            # claim 中包含 reason 字符串 → 应被标记为 "hallucination_pattern"
            matched_types = vf.classify_claim("missing file_not_found_pattern in module")
            check("L7.3.2.6 classify_claim 调用 _load_learned_rules 并标记匹配 claim",
                  "hallucination_pattern" in matched_types,
                  f"got types: {matched_types}")

            # claim 中不包含 reason 字符串 → 不应有 "hallucination_pattern"
            unmatched_types = vf.classify_claim("dead code in utils.py")
            check("L7.3.2.7 不匹配的 claim 不标记 hallucination_pattern",
                  "hallucination_pattern" not in unmatched_types,
                  f"got types: {unmatched_types}")

            # 重置缓存避免影响后续测试
            vf._LEARNED_RULES_CACHE = None


# ════════════════════════════════════════════════════════════
# 断点④: verify_all_findings 接受 history_threshold 参数
# ════════════════════════════════════════════════════════════

print("\n── 断点④: threshold 参数传递 ──")

if vf_path.exists():
    # ── L7.3.3.1: verify_all_findings 签名含 history_threshold ──
    check("L7.3.3.1 verify_all_findings 签名含 history_threshold",
          "history_threshold" in vf_src,
          "missing history_threshold in verify_findings.py")

    # ── L7.3.3.2: 传入 threshold 不崩溃 ──
    if hasattr(vf, "verify_all_findings"):
        test_findings = [
            {
                "id": "TEST-THR-001",
                "severity": "P2",  # P2 直接跳过，不会触发 L4
                "claim": "test claim",
                "evidence": {"file": "test.py", "line_start": 1},
            },
        ]
        try:
            verified, hallucinations, downgraded = vf.verify_all_findings(
                test_findings, str(ROOT), history_threshold=0.75
            )
            check("L7.3.3.2 传入 history_threshold=0.75 不崩溃",
                  True)
        except Exception as e:
            check("L7.3.3.2 传入 history_threshold=0.75 不崩溃",
                  False, f"exception: {e}")

    # ── L7.3.3.3: 默认 threshold (None) 不崩溃 ──
    if hasattr(vf, "verify_all_findings"):
        try:
            verified, hallucinations, downgraded = vf.verify_all_findings(
                test_findings, str(ROOT)
            )
            check("L7.3.3.3 默认 history_threshold=None 不崩溃",
                  True)
        except Exception as e:
            check("L7.3.3.3 默认 history_threshold=None 不崩溃",
                  False, f"exception: {e}")

    # ── L7.3.3.4: threshold 写入 finding context (闭环消费端) ──
    # 审计发现: history_threshold 曾是 dead parameter, 函数体内未使用
    # 修复后: history_threshold 应写入每个 finding 的 _history_threshold 字段
    if hasattr(vf, "verify_all_findings"):
        test_findings_with_threshold = [
            {
                "id": "TEST-THR-CTX-001",
                "severity": "P2",  # P2 直接跳过, 不会触发 L4
                "claim": "test claim for threshold context",
                "evidence": {"file": "test.py", "line_start": 1},
            },
        ]
        try:
            verified, _, _ = vf.verify_all_findings(
                test_findings_with_threshold, str(ROOT), history_threshold=0.85
            )
            # P2 finding 应被跳过但仍写入 _history_threshold
            if verified:
                ctx_threshold = verified[0].get("_history_threshold")
                check("L7.3.3.4 history_threshold 写入 finding context",
                      ctx_threshold == 0.85,
                      f"got _history_threshold={ctx_threshold}")
            else:
                check("L7.3.3.4 history_threshold 写入 finding context",
                      False, "no verified findings returned")
        except Exception as e:
            check("L7.3.3.4 history_threshold 写入 finding context",
                  False, f"exception: {e}")

    # ── L7.3.3.5: threshold=None 时不写入 context (向后兼容) ──
    if hasattr(vf, "verify_all_findings"):
        test_findings_no_threshold = [
            {
                "id": "TEST-THR-CTX-002",
                "severity": "P2",
                "claim": "test claim no threshold",
                "evidence": {"file": "test.py", "line_start": 1},
            },
        ]
        try:
            verified, _, _ = vf.verify_all_findings(
                test_findings_no_threshold, str(ROOT)  # 不传 history_threshold
            )
            if verified:
                has_threshold = "_history_threshold" in verified[0]
                check("L7.3.3.5 threshold=None 时不写入 context",
                      not has_threshold,
                      f"_history_threshold present: {has_threshold}")
            else:
                check("L7.3.3.5 threshold=None 时不写入 context",
                      False, "no verified findings returned")
        except Exception as e:
            check("L7.3.3.5 threshold=None 时不写入 context",
                  False, f"exception: {e}")


# ════════════════════════════════════════════════════════════
# 断点⑤: fix_history.py 支持 --findings-format benchmark
# ════════════════════════════════════════════════════════════

print("\n── 断点⑤: fix_history --findings-format benchmark ──")
fh_path = ROOT / "scripts" / "fix_history.py"
check("L7.3.4.1 fix_history.py exists", fh_path.exists())

if fh_path.exists():
    fh_src = fh_path.read_text(encoding="utf-8")

    # ── L7.3.4.2: --findings-format 参数存在 ──
    check("L7.3.4.2 --findings-format 参数存在",
          "--findings-format" in fh_src,
          "missing --findings-format")

    # 动态导入模块
    spec_fh = importlib.util.spec_from_file_location("fix_history", str(fh_path))
    fh = importlib.util.module_from_spec(spec_fh)
    spec_fh.loader.exec_module(fh)

    # ── L7.3.4.3: benchmark 格式解析 — 直接读 findings 数组 ──
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        bench_findings = {
            "project": "test-benchmark-format",
            "findings": [
                {
                    "id": "BV-0001",
                    "severity": "P1",
                    "claim": "buffer overflow in function foo",
                    "evidence": {"file": "foo.c", "line_start": 100},
                },
            ],
        }
        findings_file = tmpdir / "bench_findings.json"
        findings_file.write_text(json.dumps(bench_findings), encoding="utf-8")

        # 创建空的 scores.json (避免 trend 读取失败)
        scores_file = tmpdir / "scores.json"
        scores_file.write_text("[]", encoding="utf-8")

        output_file = tmpdir / "augmented.json"

        # 运行 fix_history --findings-format benchmark
        try:
            cmd = [
                sys.executable, str(fh_path),
                "--findings", str(findings_file),
                "--history-dir", str(tmpdir),
                "--output", str(output_file),
                "--findings-format", "benchmark",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            check("L7.3.4.3 fix_history --findings-format benchmark 运行成功",
                  result.returncode == 0,
                  f"stderr: {result.stderr[:200]}")

            if output_file.exists():
                aug_data = json.loads(output_file.read_text(encoding="utf-8"))
                check("L7.3.4.4 输出含 fix_history_meta",
                      "fix_history_meta" in aug_data,
                      f"keys: {list(aug_data.keys())}")
                check("L7.3.4.5 输出含 findings 数组",
                      "findings" in aug_data or "issues" in aug_data,
                      f"keys: {list(aug_data.keys())}")
        except subprocess.TimeoutExpired:
            check("L7.3.4.3 fix_history --findings-format benchmark 运行成功",
                  False, "timeout")
        except Exception as e:
            check("L7.3.4.3 fix_history --findings-format benchmark 运行成功",
                  False, f"exception: {e}")

    # ── L7.3.4.6: 默认 audit 格式仍正常工作 ──
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        audit_findings = {
            "audit_id": "test-audit-format",
            "issues": [
                {
                    "id": "AUD-001",
                    "claim": "test audit issue",
                    "severity": "P1",
                },
            ],
        }
        findings_file = tmpdir / "audit_findings.json"
        findings_file.write_text(json.dumps(audit_findings), encoding="utf-8")

        scores_file = tmpdir / "scores.json"
        scores_file.write_text("[]", encoding="utf-8")

        output_file = tmpdir / "augmented.json"

        try:
            cmd = [
                sys.executable, str(fh_path),
                "--findings", str(findings_file),
                "--history-dir", str(tmpdir),
                "--output", str(output_file),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            check("L7.3.4.6 默认 audit 格式仍正常工作",
                  result.returncode == 0,
                  f"stderr: {result.stderr[:200]}")
        except Exception as e:
            check("L7.3.4.6 默认 audit 格式仍正常工作",
                  False, f"exception: {e}")


# ════════════════════════════════════════════════════════════
# v2.7.1: L4 多语言扩展
# ════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("v2.7.1: L4 多语言扩展 (L7.1.1-L7.1.4)")
print("=" * 60)

# ── L7.1.1: _detect_language ──
print("\n── L7.1.1: _detect_language ──")

if vf_path.exists():
    # L7.1.1.1: .py → python
    check("L7.1.1.1 .py → python",
          vf._detect_language("src/main.py") == "python")

    # L7.1.1.2: .java → java
    check("L7.1.1.2 .java → java",
          vf._detect_language("src/Main.java") == "java")

    # L7.1.1.3: .c/.cpp/.h/.hpp → cpp
    check("L7.1.1.3a .c → cpp",
          vf._detect_language("src/utils.c") == "cpp")
    check("L7.1.1.3b .cpp → cpp",
          vf._detect_language("src/utils.cpp") == "cpp")
    check("L7.1.1.3c .h → cpp",
          vf._detect_language("src/utils.h") == "cpp")
    check("L7.1.1.3d .hpp → cpp",
          vf._detect_language("src/utils.hpp") == "cpp")

    # L7.1.1.4: unknown extension
    check("L7.1.1.4a .txt → unknown",
          vf._detect_language("README.txt") == "unknown")
    check("L7.1.1.4b empty string → unknown",
          vf._detect_language("") == "unknown")
    check("L7.1.1.4c None-like → unknown",
          vf._detect_language(None) == "unknown")

    # L7.1.1.5: 大小写不敏感
    check("L7.1.1.5 .JAVA (uppercase) → java",
          vf._detect_language("src/Main.JAVA") == "java")

# ── L7.1.2: joern_cpg 多语言 ──
print("\n── L7.1.2: joern_cpg 多语言 ──")

jc_path = ROOT / "scripts" / "joern_cpg.py"
check("L7.1.2.0 joern_cpg.py exists", jc_path.exists())

if jc_path.exists():
    jc_src = jc_path.read_text(encoding="utf-8")

    spec_jc = importlib.util.spec_from_file_location("joern_cpg", str(jc_path))
    jc = importlib.util.module_from_spec(spec_jc)
    spec_jc.loader.exec_module(jc)

    # L7.1.2.1: verify_dead_code 接受 language 参数
    check("L7.1.2.1a verify_dead_code 接受 language 参数",
          "language" in jc_src and "def verify_dead_code" in jc_src)

    # L7.1.2.1b: verify_imports 接受 language 参数
    check("L7.1.2.1b verify_imports 接受 language 参数",
          "def verify_imports(repo_root, claim, language=" in jc_src)

    # L7.1.2.1c: _generate_cpg 接受 language 参数
    check("L7.1.2.1c _generate_cpg 接受 language 参数",
          "def _generate_cpg(repo_root, cache_key, language=" in jc_src)

    # L7.1.2.2: JOERN_LANGUAGE_MAP 包含 java → javasrc2cpg
    check("L7.1.2.2a JOERN_LANGUAGE_MAP 含 java → javasrc2cpg",
          hasattr(jc, "JOERN_LANGUAGE_MAP") and
          jc.JOERN_LANGUAGE_MAP.get("java") == "javasrc2cpg")

    # L7.1.2.2b: JOERN_LANGUAGE_MAP 包含 cpp → c2cpg
    check("L7.1.2.2b JOERN_LANGUAGE_MAP 含 cpp → c2cpg",
          hasattr(jc, "JOERN_LANGUAGE_MAP") and
          jc.JOERN_LANGUAGE_MAP.get("cpp") == "c2cpg")

    # L7.1.2.2c: JOERN_LANGUAGE_MAP 包含 python → pythonsrc
    check("L7.1.2.2c JOERN_LANGUAGE_MAP 含 python → pythonsrc",
          hasattr(jc, "JOERN_LANGUAGE_MAP") and
          jc.JOERN_LANGUAGE_MAP.get("python") == "pythonsrc")

    # L7.1.2.3: 缓存隔离 — 不同 language 生成不同 cache key
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "test.py").write_text("x = 1", encoding="utf-8")
        (tmpdir / "Test.java").write_text("class T {}", encoding="utf-8")

        key_py = jc._get_cache_key(str(tmpdir), language="python")
        key_java = jc._get_cache_key(str(tmpdir), language="java")
        check("L7.1.2.3a python 和 java cache key 不同",
              key_py != key_java,
              f"py={key_py}, java={key_java}")

        key_cpp = jc._get_cache_key(str(tmpdir), language="cpp")
        check("L7.1.2.3b python 和 cpp cache key 不同",
              key_py != key_cpp,
              f"py={key_py}, cpp={key_cpp}")

        # L7.1.2.3c: cache key 前缀包含语言标识
        check("L7.1.2.3c python cache key 前缀为 'py'",
              key_py.startswith("py_"))
        check("L7.1.2.3d java cache key 前缀为 'ja'",
              key_java.startswith("ja_"))

    # L7.1.2.4: 错误处理 — language=unknown 不崩溃, 回退到 pythonsrc
    os.environ["JOERN_DISABLE"] = "1"
    try:
        result = jc.verify_dead_code("/nonexistent", "test.py", 1, language="java")
        check("L7.1.2.4a language=java 不崩溃 (joern disabled)",
              result is not None and "verified" in result)
    except Exception as e:
        check("L7.1.2.4a language=java 不崩溃 (joern disabled)",
              False, f"exception: {e}")
    finally:
        del os.environ["JOERN_DISABLE"]

    # L7.1.2.5: verify_imports language 参数不崩溃
    os.environ["JOERN_DISABLE"] = "1"
    try:
        result = jc.verify_imports("/nonexistent", "circular import", language="cpp")
        check("L7.1.2.5 verify_imports language=cpp 不崩溃 (joern disabled)",
              result is not None and "verified" in result)
    except Exception as e:
        check("L7.1.2.5 verify_imports language=cpp 不崩溃 (joern disabled)",
              False, f"exception: {e}")
    finally:
        del os.environ["JOERN_DISABLE"]

# ── L7.1.3: l4_eligible 检查 ──
print("\n── L7.1.3: l4_eligible 检查 ──")

if vf_path.exists():
    # L7.1.3.1: l4_eligible=False 跳过 L4 (P0 finding)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "test.py"
        test_file.write_text(
            "def foo():\n    x = 1\n    return x\n\n"
            "# unused_var is not used here\n"
            "foo()\n", encoding="utf-8")

        # P0 finding with l4_eligible=False
        finding_no_l4 = {
            "id": "TEST-L4-001",
            "severity": "P0",
            "l4_eligible": False,
            "claim": "unused variable x missing error handling",
            "evidence": {"file": "test.py", "line_start": 2},
        }
        result, action = vf.verify_single_finding(finding_no_l4, str(tmpdir))
        check("L7.1.3.1a l4_eligible=False → action='partial'",
              action == "partial",
              f"action={action}")
        check("L7.1.3.1b l4_skipped 标记存在",
              result.get("l4_skipped") is True,
              f"result={result}")
        check("L7.1.3.1c l4_skip_reason 正确",
              result.get("l4_skip_reason") == "l4_eligible=False")

    # L7.1.3.2: l4_eligible=True 跑 L4
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "test.py"
        test_file.write_text(
            "def foo():\n    x = 1\n    return x\n"
            "foo()\n", encoding="utf-8")

        finding_with_l4 = {
            "id": "TEST-L4-002",
            "severity": "P0",
            "l4_eligible": True,
            "claim": "missing error handling in foo function",
            "evidence": {"file": "test.py", "line_start": 2},
        }
        result, action = vf.verify_single_finding(finding_with_l4, str(tmpdir))
        check("L7.1.3.2 l4_eligible=True → L4 被执行 (l4 字段存在)",
              "l4" in result,
              f"result keys: {list(result.keys())}")
        check("L7.1.3.2b l4_eligible=True → l4_skipped 不存在或为 False",
              not result.get("l4_skipped", False))

    # L7.1.3.3: 默认 l4_eligible (未设置) → True (跑 L4)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "test.py"
        test_file.write_text(
            "def foo():\n    x = 1\n    return x\n"
            "foo()\n", encoding="utf-8")

        finding_default = {
            "id": "TEST-L4-003",
            "severity": "P0",
            # l4_eligible 未设置
            "claim": "missing error handling in foo function",
            "evidence": {"file": "test.py", "line_start": 2},
        }
        result, action = vf.verify_single_finding(finding_default, str(tmpdir))
        check("L7.1.3.3 默认 l4_eligible (未设置) → L4 被执行",
              "l4" in result and not result.get("l4_skipped", False))

    # L7.1.3.4: P0 + l4_eligible=False → 仅 L1-L3, 不调用 L4
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "test.java"
        test_file.write_text(
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        int x = 1;\n"
            "    }\n"
            "}\n", encoding="utf-8")

        finding_java = {
            "id": "TEST-L4-004",
            "severity": "P0",
            "l4_eligible": False,
            "claim": "missing null check in Main class",
            "evidence": {"file": "test.java", "line_start": 3},
        }
        result, action = vf.verify_single_finding(finding_java, str(tmpdir))
        check("L7.1.3.4a P0+l4_eligible=False → action='partial' (Java finding)",
              action == "partial",
              f"action={action}")
        check("L7.1.3.4b L4 不被调用 (no l4 key)",
              "l4" not in result or result.get("l4_skipped") is True,
              f"result keys: {list(result.keys())}")

# ── L7.1.4: Scala 脚本多语言 ──
print("\n── L7.1.4: Scala 脚本多语言 ──")

if jc_path.exists():
    # L7.1.4.1: Java Scala 脚本包含 .java 后缀剥离
    script_java = jc._gen_import_script(language="java")
    check("L7.1.4.1a Java import 脚本剥离 .java 后缀",
          '.java' in script_java and 'substring' in script_java)

    # L7.1.4.1b: Java dead_code 脚本标注 language=java
    dc_java = jc._gen_dead_code_script(42, language="java")
    check("L7.1.4.1b Java dead_code 脚本标注 language=java",
          "language=java" in dc_java)

    # L7.1.4.2: C++ Scala 脚本包含 .cpp/.h 后缀剥离
    script_cpp = jc._gen_import_script(language="cpp")
    check("L7.1.4.2a C++ import 脚本剥离 .cpp 后缀",
          '.cpp' in script_cpp)
    check("L7.1.4.2b C++ import 脚本剥离 .h 后缀",
          '".h"' in script_cpp or "'.h'" in script_cpp)

    # L7.1.4.2c: C++ dead_code 脚本标注 language=cpp
    dc_cpp = jc._gen_dead_code_script(99, language="cpp")
    check("L7.1.4.2c C++ dead_code 脚本标注 language=cpp",
          "language=cpp" in dc_cpp)

    # L7.1.4.3: Python 向后兼容 — 默认 language 参数生成原有脚本
    script_py = jc._gen_import_script()  # 不传 language, 默认 python
    check("L7.1.4.3a Python import 脚本默认剥离 .py 后缀 (向后兼容)",
          '.py' in script_py and 'substring' in script_py)

    dc_py = jc._gen_dead_code_script(10)  # 不传 language
    check("L7.1.4.3b Python dead_code 脚本默认标注 language=python",
          "language=python" in dc_py)

    # L7.1.4.3c: Python import 脚本含 cpg.imports.l (通用 API)
    check("L7.1.4.3c Python import 脚本使用 cpg.imports.l",
          "cpg.imports.l" in script_py)

    # L7.1.4.3d: 所有语言的 dead_code 脚本都含 cpg.method.lineNumber
    check("L7.1.4.3d Python dead_code 含 cpg.method.lineNumber",
          "cpg.method.lineNumber" in dc_py)
    check("L7.1.4.3e Java dead_code 含 cpg.method.lineNumber",
          "cpg.method.lineNumber" in dc_java)
    check("L7.1.4.3f C++ dead_code 含 cpg.method.lineNumber",
          "cpg.method.lineNumber" in dc_cpp)


# ════════════════════════════════════════════════════════════
# 回归检查: v2.6 测试无破坏
# ════════════════════════════════════════════════════════════

print("\n── 回归检查: v2.6 测试无破坏 ──")
v26_test = ROOT / "scripts" / "test_v26_consistency.py"
if v26_test.exists():
    try:
        result = subprocess.run(
            [sys.executable, str(v26_test)],
            capture_output=True, text=True, timeout=60,
            cwd=str(ROOT),
        )
        # v2.6 测试输出最后几行通常有 "X passed, Y failed"
        output = result.stdout + result.stderr
        check("L_reg_1 v2.6 测试无破坏 (exit code 0)",
              result.returncode == 0,
              f"exit code: {result.returncode}")
        if "failed" in output.lower():
            # 提取 failed 数
            for line in output.split("\n"):
                if "failed" in line.lower() and "0 failed" not in line.lower():
                    check(f"v2.6 测试有失败: {line.strip()}", False)
                    break
    except subprocess.TimeoutExpired:
        check("L_reg_1 v2.6 测试无破坏", False, "timeout")
    except Exception as e:
        check("L_reg_1 v2.6 测试无破坏", False, f"exception: {e}")


# ════════════════════════════════════════════════════════════
# 汇总
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"v2.7 Results: {passed} passed, {failed} failed")
print(f"  (v2.7.3 学习管道闭环修复 + v2.7.1 L4 多语言扩展)")
print("=" * 60)
sys.exit(1 if failed > 0 else 0)
