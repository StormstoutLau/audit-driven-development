"""v2.6 consistency test suite. 数据集集成 — 阶段 1 TDD 验证.

阶段 1 改动 1.1: 新增 scripts/swebench_to_findings.py
阶段 1 改动 1.2: run_phase8_benchmark.py 新增 --benchmark-dirs 参数

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
print("test_v26_consistency.py: v2.6 数据集集成 阶段 1")
print(f"Working dir: {ROOT}")
print("=" * 60)

# ════════════════════════════════════════════════════════════
# 改动 1.1: scripts/swebench_to_findings.py
# ════════════════════════════════════════════════════════════

print("\n── 改动 1.1: swebench_to_findings.py ──")
swb_path = ROOT / "scripts" / "swebench_to_findings.py"
check("L1.1.1 swebench_to_findings.py exists", swb_path.exists())

if swb_path.exists():
    # 动态导入模块
    spec = importlib.util.spec_from_file_location("swebench_to_findings", str(swb_path))
    swb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(swb)

    # ── L1.1.2: extract_file_line_from_patch 标准单文件 patch ──
    patch_single = """diff --git a/django/db/models/sql/query.py b/django/db/models/sql/query.py
index abc..def 100644
--- a/django/db/models/sql/query.py
+++ b/django/db/models/sql/query.py
@@ -1000,7 +1000,9 @@ class Query:
     def resolve_ref(self, name):
-        old = name
+        if not isinstance(name, str):
+            raise TypeError("name must be str")
+        old = name
         return old
"""
    result = swb.extract_file_line_from_patch(patch_single)
    check("L1.1.2 单文件 patch file_path 正确",
          result is not None and result[0] == "django/db/models/sql/query.py",
          f"got {result}")
    check("L1.1.3 单文件 patch line_start 正确",
          result is not None and result[1] == 1000,
          f"got {result}")

    # ── L1.1.4: 多文件 patch 只取第一个文件 ──
    patch_multi = """diff --git a/foo.py b/foo.py
index 111..222 100644
--- a/foo.py
+++ b/foo.py
@@ -50,3 +50,5 @@ def foo():
     pass
+    new_line()
diff --git a/bar.py b/bar.py
index 333..444 100644
--- a/bar.py
+++ b/bar.py
@@ -10,3 +10,5 @@ def bar():
     pass
+    another_line()
"""
    result_multi = swb.extract_file_line_from_patch(patch_multi)
    check("L1.1.4 多文件 patch 只取第一个文件",
          result_multi is not None and result_multi[0] == "foo.py",
          f"got {result_multi}")
    check("L1.1.5 多文件 patch line_start 取第一个 hunk",
          result_multi is not None and result_multi[1] == 50,
          f"got {result_multi}")

    # ── L1.1.6: 无效 patch 返回 None ──
    result_invalid = swb.extract_file_line_from_patch("not a valid patch")
    check("L1.1.6 无效 patch 返回 None",
          result_invalid is None,
          f"got {result_invalid}")

    # ── L1.1.7: 空 patch 返回 None ──
    result_empty = swb.extract_file_line_from_patch("")
    check("L1.1.7 空 patch 返回 None",
          result_empty is None,
          f"got {result_empty}")

    # ── L1.1.8: build_claim_from_issue 截断到 200 字符 ──
    long_issue = "A" * 300
    claim = swb.build_claim_from_issue(long_issue)
    check("L1.1.8 长 issue 截断到 200 字符",
          len(claim) <= 200,
          f"got len={len(claim)}")
    check("L1.1.9 截断后内容正确",
          claim == "A" * 200,
          f"got {claim[:20]}...")

    # ── L1.1.10: 短 issue 不截断 ──
    short_issue = "Buffer overflow in foo function"
    claim_short = swb.build_claim_from_issue(short_issue)
    check("L1.1.10 短 issue 不截断",
          claim_short == short_issue,
          f"got {claim_short}")

    # ── L1.1.11: 空 issue 返回占位 claim ──
    claim_empty = swb.build_claim_from_issue("")
    check("L1.1.11 空 issue 返回占位 claim",
          claim_empty and isinstance(claim_empty, str) and len(claim_empty) > 0,
          f"got {claim_empty}")

    # ── L1.1.12: convert_swebench_instance 输出格式正确 ──
    instance = {
        "instance_id": "django__django-12345",
        "repo": "django/django",
        "base_commit": "abc123",
        "patch": patch_single,
        "problem_statement": "Buffer overflow in resolve_ref when name is not str",
        "FAIL_TO_PASS": '["test_resolve_ref"]',
    }
    finding = swb.convert_swebench_instance(instance, 1)
    check("L1.1.12 finding id 格式 SWB-NNNN",
          finding["id"] == "SWB-0001",
          f"got {finding.get('id')}")
    check("L1.1.13 finding severity 为 P1",
          finding["severity"] == "P1",
          f"got {finding.get('severity')}")
    check("L1.1.14 finding claim 来自 problem_statement",
          finding["claim"] == instance["problem_statement"],
          f"got {finding.get('claim')}")
    check("L1.1.15 finding evidence.file 正确",
          finding["evidence"]["file"] == "django/db/models/sql/query.py",
          f"got {finding.get('evidence', {}).get('file')}")
    check("L1.1.16 finding evidence.line_start 正确",
          finding["evidence"]["line_start"] == 1000,
          f"got {finding.get('evidence', {}).get('line_start')}")
    check("L1.1.17 finding dimension 为 functional",
          finding["dimension"] == "functional",
          f"got {finding.get('dimension')}")

    # ── L1.1.18: 无效 patch 的 instance 被跳过 ──
    bad_instance = {
        "instance_id": "django__django-99999",
        "repo": "django/django",
        "base_commit": "abc123",
        "patch": "invalid patch text",
        "problem_statement": "test issue",
        "FAIL_TO_PASS": '["test"]',
    }
    finding_bad = swb.convert_swebench_instance(bad_instance, 2)
    check("L1.1.18 无效 patch instance 返回 None",
          finding_bad is None,
          f"got {finding_bad}")

    # ── L1.1.19-L1.1.23: 端到端 main() 测试 ──
    print("\n  ── 端到端 main() 测试 ──")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # 构造假 SWE-bench JSONL
        jsonl_path = tmpdir / "swebench_verified.jsonl"
        instances = [
            {
                "instance_id": "django__django-10001",
                "repo": "django/django",
                "base_commit": "abc",
                "patch": patch_single,
                "problem_statement": "Bug 1: resolve_ref type error",
                "FAIL_TO_PASS": '["test1"]',
            },
            {
                "instance_id": "flask__flask-20002",
                "repo": "pallets/flask",
                "base_commit": "def",
                "patch": """diff --git a/flask/app.py b/flask/app.py
index aaa..bbb 100644
--- a/flask/app.py
+++ b/flask/app.py
@@ -200,3 +200,5 @@ class Flask:
     def run(self):
         pass
+        self._setup()
""",
                "problem_statement": "Bug 2: missing setup call",
                "FAIL_TO_PASS": '["test2"]',
            },
            {
                "instance_id": "bad__bad-30003",
                "repo": "bad/bad",
                "base_commit": "ghi",
                "patch": "invalid patch",
                "problem_statement": "Bug 3: should be skipped",
                "FAIL_TO_PASS": '["test3"]',
            },
        ]
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for inst in instances:
                f.write(json.dumps(inst) + "\n")

        out_dir = tmpdir / "output"
        swb.main([str(jsonl_path), "--output", str(out_dir)])

        # 验证 findings.json
        findings_path = out_dir / "findings.json"
        check("L1.1.19 findings.json 生成",
              findings_path.exists())
        if findings_path.exists():
            findings_data = json.loads(findings_path.read_text(encoding="utf-8"))
            check("L1.1.20 findings.json 含 project 字段",
                  "project" in findings_data,
                  f"keys: {list(findings_data.keys())}")
            check("L1.1.21 findings.json 含 findings 数组",
                  "findings" in findings_data and isinstance(findings_data["findings"], list))
            findings_list = findings_data["findings"]
            check("L1.1.22 findings 数量为 2 (跳过无效 patch)",
                  len(findings_list) == 2,
                  f"got {len(findings_list)}")
            if len(findings_list) == 2:
                check("L1.1.23 第一条 finding id = SWB-0000",
                      findings_list[0]["id"] == "SWB-0000",
                      f"got {findings_list[0].get('id')}")
                check("L1.1.24 第二条 finding id = SWB-0001",
                      findings_list[1]["id"] == "SWB-0001",
                      f"got {findings_list[1].get('id')}")

        # 验证 ground_truth.json
        gt_path = out_dir / "ground_truth.json"
        check("L1.1.25 ground_truth.json 生成",
              gt_path.exists())
        if gt_path.exists():
            gt_data = json.loads(gt_path.read_text(encoding="utf-8"))
            check("L1.1.26 ground_truth 是数组",
                  isinstance(gt_data, list))
            if isinstance(gt_data, list):
                check("L1.1.27 ground_truth 数量为 2",
                      len(gt_data) == 2,
                      f"got {len(gt_data)}")
                if len(gt_data) == 2:
                    check("L1.1.28 ground_truth 标注为 real_bug",
                          gt_data[0]["ground_truth"] == "real_bug",
                          f"got {gt_data[0].get('ground_truth')}")

        # 验证 conversion_errors.json
        err_path = out_dir / "conversion_errors.json"
        check("L1.1.29 conversion_errors.json 生成",
              err_path.exists())
        if err_path.exists():
            err_data = json.loads(err_path.read_text(encoding="utf-8"))
            check("L1.1.30 conversion_errors 记录 1 个失败",
                  isinstance(err_data, list) and len(err_data) == 1,
                  f"got {err_data}")
            if isinstance(err_data, list) and len(err_data) == 1:
                check("L1.1.31 conversion_errors 含 instance_id",
                      "instance_id" in err_data[0],
                      f"keys: {list(err_data[0].keys())}")


# ════════════════════════════════════════════════════════════
# 改动 1.2: run_phase8_benchmark.py --benchmark-dirs 参数
# ════════════════════════════════════════════════════════════

print("\n── 改动 1.2: run_phase8_benchmark.py --benchmark-dirs ──")
bm_path = ROOT / "scripts" / "run_phase8_benchmark.py"
check("L1.2.1 run_phase8_benchmark.py exists", bm_path.exists())

if bm_path.exists():
    bm_src = bm_path.read_text(encoding="utf-8")
    check("L1.2.2 --benchmark-dirs 参数存在",
          "--benchmark-dirs" in bm_src,
          "missing --benchmark-dirs arg")

    # 动态导入模块
    spec_bm = importlib.util.spec_from_file_location("run_phase8_benchmark", str(bm_path))
    bm = importlib.util.module_from_spec(spec_bm)
    spec_bm.loader.exec_module(bm)

    # ── L1.2.3: build_test_matrix 函数存在 ──
    check("L1.2.3 build_test_matrix 函数存在",
          hasattr(bm, "build_test_matrix"),
          "missing build_test_matrix function")

    if hasattr(bm, "build_test_matrix"):
        # ── L1.2.4: 默认含原 3 个 benchmark (Phase 3 后可能含 extra dirs) ──
        default_matrix = bm.build_test_matrix()
        names = [t["name"] for t in default_matrix]
        check("L1.2.4 默认含 ADD self-audit",
              "ADD self-audit" in names,
              f"got {names}")
        check("L1.2.5 默认含 Python stdlib",
              any("stdlib" in n for n in names),
              f"got {names}")
        check("L1.2.6 默认含 itsdangerous",
              any("itsdangerous" in n for n in names),
              f"got {names}")
        check("L1.2.7 默认含至少 3 个 benchmark",
              len(default_matrix) >= 3,
              f"got {len(default_matrix)}")

        # ── L1.2.8: 自定义 benchmark-dirs ──
        custom_matrix = bm.build_test_matrix(["docs/benchmark/add-v2.4-self-audit"])
        check("L1.2.8 自定义 1 个 benchmark-dirs",
              len(custom_matrix) == 1,
              f"got {len(custom_matrix)}")

        # ── L1.2.9: 不存在的 benchmark-dir 跳过 ──
        skip_matrix = bm.build_test_matrix(["docs/benchmark/nonexistent-test"])
        check("L1.2.9 不存在的 benchmark-dir 返回空列表",
              len(skip_matrix) == 0,
              f"got {len(skip_matrix)}")


# ════════════════════════════════════════════════════════════
# 阶段 2: 幻觉样本自动合成
# ════════════════════════════════════════════════════════════

print("\n── 阶段 2 改动 2.1: synthesize_hallucinations.py ──")
syn_path = ROOT / "scripts" / "synthesize_hallucinations.py"
check("L2.1.1 synthesize_hallucinations.py exists", syn_path.exists())

if syn_path.exists():
    spec_syn = importlib.util.spec_from_file_location("synthesize_hallucinations", str(syn_path))
    syn = importlib.util.module_from_spec(spec_syn)
    spec_syn.loader.exec_module(syn)

    # ── L2.1.2: 三类 transform 存在 ──
    check("L2.1.2 TRANSFORMS 字典存在",
          hasattr(syn, "TRANSFORMS") and isinstance(syn.TRANSFORMS, dict))
    if hasattr(syn, "TRANSFORMS"):
        check("L2.1.3 line_offset transform 存在",
              "line_offset" in syn.TRANSFORMS,
              f"keys: {list(syn.TRANSFORMS.keys())}")
        check("L2.1.4 file_replace transform 存在",
              "file_replace" in syn.TRANSFORMS)
        check("L2.1.5 method_fabricate transform 存在",
              "method_fabricate" in syn.TRANSFORMS)

    # ── L2.1.6: transform_line_offset ──
    check("L2.1.6 transform_line_offset 函数存在",
          hasattr(syn, "transform_line_offset"))
    if hasattr(syn, "transform_line_offset"):
        finding = {
            "id": "TEST-001",
            "claim": "test claim",
            "evidence": {"file": "foo.py", "line_start": 10},
        }
        # 偏移后的 line_start 应远超原值
        result = syn.transform_line_offset(finding, total_lines=100)
        check("L2.1.7 line_offset 返回新 finding",
              result is not None and "evidence" in result)
        if result and "evidence" in result:
            check("L2.1.8 line_offset line_start 偏移",
                  result["evidence"]["line_start"] != 10,
                  f"got {result['evidence']['line_start']}")
            check("L2.1.9 line_offset line_start 超出文件范围 (>110)",
                  result["evidence"]["line_start"] > 110,
                  f"got {result['evidence']['line_start']}")

    # ── L2.1.10: transform_file_replace ──
    check("L2.1.10 transform_file_replace 函数存在",
          hasattr(syn, "transform_file_replace"))
    if hasattr(syn, "transform_file_replace"):
        result = syn.transform_file_replace(finding)
        check("L2.1.11 file_replace 返回新 finding",
              result is not None and "evidence" in result)
        if result and "evidence" in result:
            check("L2.1.12 file_replace file 被替换",
                  result["evidence"]["file"] != "foo.py",
                  f"got {result['evidence']['file']}")
            check("L2.1.13 file_replace file 含 nonexistent",
                  "nonexistent" in result["evidence"]["file"].lower() or
                  "_fake_" in result["evidence"]["file"].lower(),
                  f"got {result['evidence']['file']}")

    # ── L2.1.14: transform_method_fabricate ──
    check("L2.1.14 transform_method_fabricate 函数存在",
          hasattr(syn, "transform_method_fabricate"))
    if hasattr(syn, "transform_method_fabricate"):
        result = syn.transform_method_fabricate(finding)
        check("L2.1.15 method_fabricate 返回新 finding",
              result is not None and "claim" in result)
        if result and "claim" in result:
            check("L2.1.16 method_fabricate claim 含虚构方法名",
                  result["claim"] != finding["claim"],
                  f"got {result['claim']}")

    # ── L2.1.17: synthesize_from_findings ──
    check("L2.1.17 synthesize_from_findings 函数存在",
          hasattr(syn, "synthesize_from_findings"))
    if hasattr(syn, "synthesize_from_findings"):
        findings = [
            {"id": "R-001", "severity": "P1", "claim": "real bug 1",
             "evidence": {"file": "a.py", "line_start": 10}, "dimension": "functional"},
            {"id": "R-002", "severity": "P1", "claim": "real bug 2",
             "evidence": {"file": "b.py", "line_start": 20}, "dimension": "functional"},
            {"id": "R-003", "severity": "P1", "claim": "real bug 3",
             "evidence": {"file": "c.py", "line_start": 30}, "dimension": "functional"},
            {"id": "R-004", "severity": "P1", "claim": "real bug 4",
             "evidence": {"file": "d.py", "line_start": 40}, "dimension": "functional"},
            {"id": "R-005", "severity": "P1", "claim": "real bug 5",
             "evidence": {"file": "e.py", "line_start": 50}, "dimension": "functional"},
            {"id": "R-006", "severity": "P1", "claim": "real bug 6",
             "evidence": {"file": "f.py", "line_start": 60}, "dimension": "functional"},
        ]
        syn_findings, syn_gt = syn.synthesize_from_findings(findings, seed=42)
        check("L2.1.18 合成 findings 数量 = 原始数量",
              len(syn_findings) == len(findings),
              f"got {len(syn_findings)} expected {len(findings)}")
        check("L2.1.19 合成 ground_truth 数量 = 原始数量",
              len(syn_gt) == len(findings),
              f"got {len(syn_gt)}")
        if len(syn_gt) == len(findings):
            # 所有 ground_truth 应标注为 hallucination_*
            all_halluc = all(
                gt["ground_truth"].startswith("hallucination_")
                for gt in syn_gt
            )
            check("L2.1.20 所有 ground_truth 标注为 hallucination_*",
                  all_halluc,
                  f"sample: {syn_gt[0] if syn_gt else 'empty'}")

        # 三类 transform 各占约 1/3
        transform_counts = {"line_offset": 0, "file_replace": 0, "method_fabricate": 0}
        for gt in syn_gt:
            reason = gt.get("ground_truth", "")
            if "line_out_of_range" in reason:
                transform_counts["line_offset"] += 1
            elif "file_not_found" in reason:
                transform_counts["file_replace"] += 1
            elif "method_not_in_source" in reason:
                transform_counts["method_fabricate"] += 1
        check("L2.1.21 三类 transform 都被使用",
              all(c > 0 for c in transform_counts.values()),
              f"got {transform_counts}")
        # 6 条各占 2 条
        max_count = max(transform_counts.values())
        min_count = min(transform_counts.values())
        check("L2.1.22 三类分布均匀 (max-min <= 1)",
              max_count - min_count <= 1,
              f"got {transform_counts}")

    # ── L2.1.23-L2.1.28: 端到端 main() ──
    print("\n  ── 端到端 main() 测试 ──")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # 构造假 findings.json
        findings_data = {
            "project": "test-synth",
            "findings": [
                {"id": "R-001", "severity": "P1", "claim": "real bug 1",
                 "evidence": {"file": "a.py", "line_start": 10}, "dimension": "functional"},
                {"id": "R-002", "severity": "P1", "claim": "real bug 2",
                 "evidence": {"file": "b.py", "line_start": 20}, "dimension": "functional"},
                {"id": "R-003", "severity": "P1", "claim": "real bug 3",
                 "evidence": {"file": "c.py", "line_start": 30}, "dimension": "functional"},
            ],
        }
        in_dir = tmpdir / "input"
        in_dir.mkdir()
        (in_dir / "findings.json").write_text(
            json.dumps(findings_data, indent=2), encoding="utf-8")

        out_dir = tmpdir / "output"
        syn.main([str(in_dir / "findings.json"), "--output", str(out_dir), "--seed", "42"])

        syn_findings_path = out_dir / "findings.json"
        check("L2.1.23 合成 findings.json 生成",
              syn_findings_path.exists())
        if syn_findings_path.exists():
            syn_data = json.loads(syn_findings_path.read_text(encoding="utf-8"))
            check("L2.1.24 合成 findings 数量为 3",
                  len(syn_data.get("findings", [])) == 3,
                  f"got {len(syn_data.get('findings', []))}")

        syn_gt_path = out_dir / "ground_truth.json"
        check("L2.1.25 合成 ground_truth.json 生成",
              syn_gt_path.exists())
        if syn_gt_path.exists():
            syn_gt_data = json.loads(syn_gt_path.read_text(encoding="utf-8"))
            check("L2.1.26 合成 ground_truth 数量为 3",
                  len(syn_gt_data) == 3,
                  f"got {len(syn_gt_data)}")
            if len(syn_gt_data) == 3:
                check("L2.1.27 ground_truth 全部 hallucination_*",
                      all(gt["ground_truth"].startswith("hallucination_")
                          for gt in syn_gt_data))
                check("L2.1.28 合成 finding id 含 HAL- 前缀",
                      all(f["id"].startswith("HAL-") for f in syn_data.get("findings", [])),
                      f"sample ids: {[f['id'] for f in syn_data.get('findings', [])]}")


# ════════════════════════════════════════════════════════════
# 改动 2.2: run_phase8_benchmark.py 默认 benchmark-dirs 扩展
# ════════════════════════════════════════════════════════════

print("\n── 改动 2.2: 默认 benchmark-dirs 扩展 (swebench + hallucinations) ──")
if bm_path.exists():
    # ── L2.2.1: DEFAULT_EXTRA_DIRS 常量存在 ──
    check("L2.2.1 DEFAULT_EXTRA_DIRS 常量存在",
          hasattr(bm, "DEFAULT_EXTRA_DIRS"),
          "missing DEFAULT_EXTRA_DIRS")
    if hasattr(bm, "DEFAULT_EXTRA_DIRS"):
        check("L2.2.2 DEFAULT_EXTRA_DIRS 含 swebench-verified",
              "docs/benchmark/swebench-verified" in bm.DEFAULT_EXTRA_DIRS,
              f"got {bm.DEFAULT_EXTRA_DIRS}")
        check("L2.2.3 DEFAULT_EXTRA_DIRS 含 swebench-verified-hallucinations",
              "docs/benchmark/swebench-verified-hallucinations" in bm.DEFAULT_EXTRA_DIRS,
              f"got {bm.DEFAULT_EXTRA_DIRS}")
        # v2.6 阶段 3: 新增多语言数据集
        check("L2.2.3a DEFAULT_EXTRA_DIRS 含 defects4j",
              "docs/benchmark/defects4j" in bm.DEFAULT_EXTRA_DIRS,
              f"got {bm.DEFAULT_EXTRA_DIRS}")
        check("L2.2.3b DEFAULT_EXTRA_DIRS 含 bigvul",
              "docs/benchmark/bigvul" in bm.DEFAULT_EXTRA_DIRS,
              f"got {bm.DEFAULT_EXTRA_DIRS}")
        check("L2.2.3c DEFAULT_EXTRA_DIRS 含 cvefixes",
              "docs/benchmark/cvefixes" in bm.DEFAULT_EXTRA_DIRS,
              f"got {bm.DEFAULT_EXTRA_DIRS}")

    # ── L2.2.4: 默认矩阵 = 原 3 + 已存在的 extra dirs ──
    default_matrix_v26 = bm.build_test_matrix()
    # 统计已存在的 extra dirs
    existing_extras = 0
    for bd in bm.DEFAULT_EXTRA_DIRS:
        if (ROOT / bd / "findings.json").exists():
            existing_extras += 1
    expected_default = 3 + existing_extras
    check(f"L2.2.4 默认 benchmark 数量为 {expected_default} (3 原 + {existing_extras} extra)",
          len(default_matrix_v26) == expected_default,
          f"got {len(default_matrix_v26)}, expected {expected_default}")

    # ── L2.2.5: swebench-verified 目录不存在 → 不在默认矩阵中 ──
    default_names = [t["name"] for t in default_matrix_v26]
    swebench_exists = (ROOT / "docs" / "benchmark" / "swebench-verified" / "findings.json").exists()
    if not swebench_exists:
        check("L2.2.5 默认矩阵不含 swebench-verified (目录不存在)",
              "swebench-verified" not in default_names,
              f"got {default_names}")

    # ── L2.2.6: --benchmark-dirs help 文本含 swebench ──
    bm_src_v26 = bm_path.read_text(encoding="utf-8")
    check("L2.2.6 help 文本含 swebench-verified",
          "swebench-verified" in bm_src_v26,
          "help text missing swebench-verified")

    # ── L2.2.7-L2.2.10: 模拟 swebench 目录存在时自动加入 ──
    print("\n  ── 模拟 swebench 目录存在时自动加入 ──")
    swebench_dir = ROOT / "docs" / "benchmark" / "swebench-verified"
    swebench_hall_dir = ROOT / "docs" / "benchmark" / "swebench-verified-hallucinations"
    created_swebench = False
    created_swebench_hall = False

    # 备份策略: 仅在目录不存在时创建, 测试后清理
    if not swebench_dir.exists():
        swebench_dir.mkdir(parents=True, exist_ok=True)
        (swebench_dir / "findings.json").write_text(
            json.dumps({"project": "test-swebench", "findings": []}, indent=2),
            encoding="utf-8")
        (swebench_dir / "ground_truth.json").write_text("[]", encoding="utf-8")
        created_swebench = True

    if not swebench_hall_dir.exists():
        swebench_hall_dir.mkdir(parents=True, exist_ok=True)
        (swebench_hall_dir / "findings.json").write_text(
            json.dumps({"project": "test-swebench-hall", "findings": []}, indent=2),
            encoding="utf-8")
        (swebench_hall_dir / "ground_truth.json").write_text("[]", encoding="utf-8")
        created_swebench_hall = True

    try:
        expanded_matrix = bm.build_test_matrix()
        expected_expanded = expected_default + (2 if created_swebench and created_swebench_hall else 0)
        check(f"L2.2.7 swebench 目录存在时默认矩阵扩展为 {expected_expanded}",
              len(expanded_matrix) == expected_expanded,
              f"got {len(expanded_matrix)}, expected {expected_expanded}")
        if len(expanded_matrix) == expected_expanded:
            expanded_names = [t["name"] for t in expanded_matrix]
            check("L2.2.8 含 swebench-verified",
                  "swebench-verified" in expanded_names,
                  f"got {expanded_names}")
            check("L2.2.9 含 swebench-verified-hallucinations",
                  "swebench-verified-hallucinations" in expanded_names,
                  f"got {expanded_names}")
            # 原 3 个 benchmark 仍在 (repo_path 未被破坏)
            check("L2.2.10 原 3 个 benchmark 保留",
                  "ADD self-audit" in expanded_names
                  and any("stdlib" in n for n in expanded_names)
                  and any("itsdangerous" in n for n in expanded_names),
                  f"got {expanded_names}")
    finally:
        # 清理测试创建的目录
        if created_swebench:
            import shutil
            shutil.rmtree(swebench_dir, ignore_errors=True)
        if created_swebench_hall:
            import shutil
            shutil.rmtree(swebench_hall_dir, ignore_errors=True)

    # 清理后恢复
    final_matrix = bm.build_test_matrix()
    check(f"L2.2.11 清理后默认矩阵恢复为 {expected_default}",
          len(final_matrix) == expected_default,
          f"got {len(final_matrix)}, expected {expected_default}")


# ════════════════════════════════════════════════════════════
# 阶段 3: Defects4J + Big-Vul + CVEfixes 集成
# ════════════════════════════════════════════════════════════

# ── 改动 3.1: defects4j_to_findings.py ──

print("\n── 阶段 3 改动 3.1: defects4j_to_findings.py ──")
d4j_path = ROOT / "scripts" / "defects4j_to_findings.py"
check("L3.1.1 defects4j_to_findings.py exists", d4j_path.exists())

if d4j_path.exists():
    spec_d4j = importlib.util.spec_from_file_location("defects4j_to_findings", str(d4j_path))
    d4j = importlib.util.module_from_spec(spec_d4j)
    spec_d4j.loader.exec_module(d4j)

    check("L3.1.2 DEFECTS4J_CLAIM_TEMPLATE exists",
          hasattr(d4j, "DEFECTS4J_CLAIM_TEMPLATE"))
    check("L3.1.3 convert_defects4j_bug function exists",
          hasattr(d4j, "convert_defects4j_bug"))

    if hasattr(d4j, "convert_defects4j_bug"):
        bug_row = {
            "project": "Chart",
            "bug_id": "1",
            "commit_hash": "abc123",
            "commit_message": "Fix NPE in chart rendering",
            "file_path": "src/org/jfree/chart/Chart.java",
            "line_start": 100,
        }
        finding = d4j.convert_defects4j_bug(bug_row, 0)
        check("L3.1.4 finding id 格式 D4J-NNNN",
              finding is not None and finding["id"] == "D4J-0000",
              f"got {finding.get('id') if finding else None}")
        check("L3.1.5 finding severity 为 P1",
              finding is not None and finding["severity"] == "P1")
        check("L3.1.6 finding l4_eligible 为 False",
              finding is not None and finding.get("l4_eligible") == False,
              f"got {finding.get('l4_eligible') if finding else None}")
        check("L3.1.7 finding dimension 为 functional",
              finding is not None and finding["dimension"] == "functional")
        check("L3.1.8 finding claim 含 project 名",
              finding is not None and "Chart" in finding["claim"])

    # 端到端 main()
    print("\n  ── 改动 3.1 端到端 main() ──")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        csv_path = tmpdir / "active-bugs.csv"
        csv_content = "project,bug_id,commit_hash,commit_message,file_path,line_start\n"
        csv_content += "Chart,1,abc123,Fix NPE in chart rendering,src/org/jfree/chart/Chart.java,100\n"
        csv_content += "Cli,2,def456,Fix arg parsing,src/cli/Parser.java,50\n"
        csv_content += "Chart,3,ghi789,Fix null ref,src/org/jfree/chart/Axis.java,200\n"
        csv_path.write_text(csv_content, encoding="utf-8")

        out_dir = tmpdir / "output"
        d4j.main([str(csv_path), "--output", str(out_dir), "--max-bugs", "50"])

        findings_path = out_dir / "findings.json"
        check("L3.1.9 findings.json 生成", findings_path.exists())
        if findings_path.exists():
            data = json.loads(findings_path.read_text(encoding="utf-8"))
            check("L3.1.10 findings 数量为 3",
                  len(data.get("findings", [])) == 3,
                  f"got {len(data.get('findings', []))}")
            check("L3.1.11 project 为 defects4j",
                  data.get("project") == "defects4j")

        gt_path = out_dir / "ground_truth.json"
        check("L3.1.12 ground_truth.json 生成", gt_path.exists())
        if gt_path.exists():
            gt_data = json.loads(gt_path.read_text(encoding="utf-8"))
            check("L3.1.13 ground_truth 标注为 real_bug",
                  len(gt_data) > 0 and gt_data[0]["ground_truth"] == "real_bug")

        err_path = out_dir / "conversion_errors.json"
        check("L3.1.14 conversion_errors.json 生成", err_path.exists())


# ── 改动 3.2: bigvul_to_findings.py ──

print("\n── 阶段 3 改动 3.2: bigvul_to_findings.py ──")
bv_path = ROOT / "scripts" / "bigvul_to_findings.py"
check("L3.2.1 bigvul_to_findings.py exists", bv_path.exists())

if bv_path.exists():
    spec_bv = importlib.util.spec_from_file_location("bigvul_to_findings", str(bv_path))
    bv = importlib.util.module_from_spec(spec_bv)
    spec_bv.loader.exec_module(bv)

    check("L3.2.2 BIGVUL_CLAIM_TEMPLATE exists",
          hasattr(bv, "BIGVUL_CLAIM_TEMPLATE"))
    check("L3.2.3 extract_func_name function exists",
          hasattr(bv, "extract_func_name"))
    check("L3.2.4 extract_line_start function exists",
          hasattr(bv, "extract_line_start"))
    check("L3.2.5 convert_bigvul_row function exists",
          hasattr(bv, "convert_bigvul_row"))

    if hasattr(bv, "extract_func_name"):
        # C 函数签名提取
        check("L3.2.6 提取 void 函数名",
              bv.extract_func_name("void my_func(int x) {") == "my_func",
              f"got {bv.extract_func_name('void my_func(int x) {')}")
        check("L3.2.7 提取 int 函数名",
              bv.extract_func_name("int calculate_sum(void) {") == "calculate_sum")
        check("L3.2.8 提取 static 函数名",
              bv.extract_func_name("static int helper(void) {") == "helper")
        check("L3.2.9 空字符串返回 unknown",
              bv.extract_func_name("") == "unknown")

    if hasattr(bv, "extract_line_start"):
        check("L3.2.10 提取单行号",
              bv.extract_line_start("100") == 100)
        check("L3.2.11 提取多行号首个",
              bv.extract_line_start("100,101,102") == 100)
        check("L3.2.12 空字符串返回 1",
              bv.extract_line_start("") == 1)

    if hasattr(bv, "convert_bigvul_row"):
        vul_row = {
            "func_before": "void vulnerable_func(char *buf) {\n  strcpy(buf, input);\n}",
            "lines_before": "100",
            "vul": "1",
            "cve_id": "CVE-2019-12345",
            "cwe_id": "CWE-119",
            "cvss": "7.5",
            "cve_summary": "Buffer overflow in vulnerable_func",
        }
        finding = bv.convert_bigvul_row(vul_row, 0)
        check("L3.2.13 vul=1 finding id 格式 BV-NNNN",
              finding is not None and finding["id"] == "BV-0000",
              f"got {finding.get('id') if finding else None}")
        check("L3.2.14 vul=1 l4_eligible 为 False",
              finding is not None and finding.get("l4_eligible") == False)
        check("L3.2.15 vul=1 dimension 为 security",
              finding is not None and finding["dimension"] == "security")
        check("L3.2.16 vul=1 claim 含 CWE",
              finding is not None and "CWE-119" in finding["claim"])

        safe_row = {
            "func_before": "void safe_func(void) {}",
            "lines_before": "50",
            "vul": "0",
            "cve_id": "",
            "cwe_id": "",
            "cvss": "0",
            "cve_summary": "",
        }
        finding_safe = bv.convert_bigvul_row(safe_row, 1)
        check("L3.2.17 vul=0 返回 None (跳过)",
              finding_safe is None)

    # 端到端 main()
    print("\n  ── 改动 3.2 端到端 main() ──")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        csv_path = tmpdir / "test_bigvul.csv"
        header = "func_before,lines_before,vul,cve_id,cwe_id,cvss,cve_summary\n"
        row1 = '"void func_a(char *b) {\n  strcpy(b, x);\n}",100,1,CVE-2019-001,CWE-119,7.5,Buffer overflow in func_a\n'
        row2 = '"void func_b(void) {}",50,0,,,0,\n'
        row3 = '"int func_c(int n) {\n  return arr[n];\n}",200,1,CVE-2019-002,CWE-125,5.5,Out of bounds read in func_c\n'
        csv_path.write_text(header + row1 + row2 + row3, encoding="utf-8")

        out_dir = tmpdir / "output"
        bv.main([str(csv_path), "--output", str(out_dir)])

        findings_path = out_dir / "findings.json"
        check("L3.2.18 findings.json 生成", findings_path.exists())
        if findings_path.exists():
            data = json.loads(findings_path.read_text(encoding="utf-8"))
            check("L3.2.19 findings 数量为 2 (跳过 vul=0)",
                  len(data.get("findings", [])) == 2,
                  f"got {len(data.get('findings', []))}")
            check("L3.2.20 project 为 bigvul",
                  data.get("project") == "bigvul")

        gt_path = out_dir / "ground_truth.json"
        check("L3.2.21 ground_truth.json 生成", gt_path.exists())


# ── 改动 3.3: cvefixes_to_findings.py ──

print("\n── 阶段 3 改动 3.3: cvefixes_to_findings.py ──")
cf_path = ROOT / "scripts" / "cvefixes_to_findings.py"
check("L3.3.1 cvefixes_to_findings.py exists", cf_path.exists())

if cf_path.exists():
    spec_cf = importlib.util.spec_from_file_location("cvefixes_to_findings", str(cf_path))
    cf = importlib.util.module_from_spec(spec_cf)
    spec_cf.loader.exec_module(cf)

    check("L3.3.2 get_top_projects function exists",
          hasattr(cf, "get_top_projects"))
    check("L3.3.3 convert_cvefixes_record function exists",
          hasattr(cf, "convert_cvefixes_record"))

    if hasattr(cf, "convert_cvefixes_record"):
        record = {
            "cve_id": "CVE-2020-12345",
            "cwe_id": "CWE-79",
            "cvss_score": "8.0",
            "cve_summary": "XSS vulnerability in web handler",
            "project_name": "wordpress",
            "file_path": "wp-includes/formatting.php",
            "line_start": 150,
            "func_name": "sanitize_text",
        }
        finding = cf.convert_cvefixes_record(record, 0)
        check("L3.3.4 finding id 格式 CF-NNNN",
              finding is not None and finding["id"] == "CF-0000",
              f"got {finding.get('id') if finding else None}")
        check("L3.3.5 finding l4_eligible 为 False",
              finding is not None and finding.get("l4_eligible") == False)
        check("L3.3.6 finding dimension 为 security",
              finding is not None and finding["dimension"] == "security")
        check("L3.3.7 finding claim 含 CWE",
              finding is not None and "CWE-79" in finding["claim"])

    # 端到端 main() with mock SQLite
    print("\n  ── 改动 3.3 端到端 main() ──")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = tmpdir / "test_cvefixes.db"
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        # CVEfixes schema (simplified)
        c.execute("""CREATE TABLE IF NOT EXISTS cves (
            cve_id TEXT, cwe_id TEXT, cvss_score REAL,
            description TEXT, project_name TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS fixes (
            cve_id TEXT, file_path TEXT, line_start INTEGER,
            func_name TEXT
        )""")
        # Insert mock data: 3 projects, varying CVE counts
        projects = [
            ("wordpress", "CVE-2020-001", "CWE-79", 8.0, "XSS in wp", "wp-includes/a.php", 100, "sanitize"),
            ("wordpress", "CVE-2020-002", "CWE-89", 9.0, "SQLi in wp", "wp-includes/db.php", 200, "query"),
            ("wordpress", "CVE-2020-003", "CWE-352", 6.5, "CSRF in wp", "wp-admin/b.php", 300, "handle"),
            ("drupal", "CVE-2020-004", "CWE-89", 9.0, "SQLi in drupal", "includes/db.php", 50, "db_query"),
            ("drupal", "CVE-2020-005", "CWE-79", 7.0, "XSS in drupal", "modules/filter.php", 80, "filter"),
            ("joomla", "CVE-2020-006", "CWE-89", 9.5, "SQLi in joomla", "libraries/db.php", 120, "query"),
        ]
        for p in projects:
            c.execute("INSERT INTO cves VALUES (?,?,?,?,?)", (p[1], p[2], p[3], p[4], p[0]))
            c.execute("INSERT INTO fixes VALUES (?,?,?,?)", (p[1], p[5], p[6], p[7]))
        conn.commit()
        conn.close()

        out_dir = tmpdir / "output"
        cf.main([str(db_path), "--output", str(out_dir), "--top-projects", "10", "--max-per-project", "50"])

        findings_path = out_dir / "findings.json"
        check("L3.3.8 findings.json 生成", findings_path.exists())
        if findings_path.exists():
            data = json.loads(findings_path.read_text(encoding="utf-8"))
            check("L3.3.9 findings 数量为 6 (全部 mock 数据)",
                  len(data.get("findings", [])) == 6,
                  f"got {len(data.get('findings', []))}")
            check("L3.3.10 project 为 cvefixes",
                  data.get("project") == "cvefixes")

        gt_path = out_dir / "ground_truth.json"
        check("L3.3.11 ground_truth.json 生成", gt_path.exists())

    # max-per-project 限制测试
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = tmpdir / "test_cvefixes_limit.db"
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS cves (
            cve_id TEXT, cwe_id TEXT, cvss_score REAL,
            description TEXT, project_name TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS fixes (
            cve_id TEXT, file_path TEXT, line_start INTEGER,
            func_name TEXT
        )""")
        # 1 project with 5 CVEs, limit to 2
        for i in range(5):
            c.execute("INSERT INTO cves VALUES (?,?,?,?,?)",
                      (f"CVE-2020-{i:03d}", "CWE-79", 7.0, f"XSS {i}", "testproject"))
            c.execute("INSERT INTO fixes VALUES (?,?,?,?)",
                      (f"CVE-2020-{i:03d}", f"file{i}.py", i * 10, f"func{i}"))
        conn.commit()
        conn.close()

        out_dir = tmpdir / "output"
        cf.main([str(db_path), "--output", str(out_dir), "--top-projects", "10", "--max-per-project", "2"])

        data = json.loads((out_dir / "findings.json").read_text(encoding="utf-8"))
        check("L3.3.12 max-per-project 限制生效 (5→2)",
              len(data.get("findings", [])) == 2,
              f"got {len(data.get('findings', []))}")


# ════════════════════════════════════════════════════════════
# 回归测试: v2.5 测试仍通过
# ════════════════════════════════════════════════════════════

print("\n── 回归: v2.5 测试无破坏 ──")
v25_path = ROOT / "scripts" / "test_v25_consistency.py"
if v25_path.exists():
    result = subprocess.run(
        [sys.executable, str(v25_path)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60
    )
    check("L_reg_1 v2.5 测试通过",
          result.returncode == 0,
          f"exit={result.returncode}\nstdout tail: {result.stdout[-300:]}")


# ════════════════════════════════════════════════════════════
# 总结
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"v2.6 阶段 1+2+3 Results: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
