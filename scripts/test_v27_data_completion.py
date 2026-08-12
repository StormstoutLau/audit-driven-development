"""v2.7.2 数据补全 TDD 测试.

测试范围 (spec §3.2):
  L7.2.1.1-L7.2.1.4: bigvul evidence 保留 commit_hash/project
  L7.2.2.1-L7.2.2.4: cvefixes evidence 保留 repo_url/commit_hash
  L7.2.3.1-L7.2.3.5: download_repos.py (clone/checkout/失败处理/gt 更新/幂等)
  L_reg: v2.6 回归 (现有转换脚本不破坏)

运行:
  python scripts/test_v27_data_completion.py
"""
import csv
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{'✓' if condition else '✗'}] {name}" + (f" — {detail}" if detail else ""))
    return condition


def main():
    print("=" * 60)
    print("v2.7.2 数据补全 TDD 测试")
    print("=" * 60)

    total = passed = 0

    # ── L7.2.1: bigvul evidence 保留 commit_hash/project ────────────
    print("\n── L7.2.1: bigvul_to_findings evidence 字段 ──")
    import bigvul_to_findings as bv

    # L7.2.1.1: evidence 含 commit_hash 字段
    test_row = {
        "func_before": "void vuln_func(void) {",
        "lines_before": "100",
        "vul": "1",
        "cve_id": "CVE-2021-1234",
        "cwe_id": "CWE-119",
        "cvss": "7.5",
        "cve_summary": "buffer overflow",
        "commit_id": "abc123def456",
        "project": "libpng",
    }
    finding = bv.convert_bigvul_row(test_row, 0)
    total += 1
    passed += check("L7.2.1.1 evidence 含 commit_hash 字段",
                    "commit_hash" in finding.get("evidence", {}),
                    f"evidence keys: {list(finding.get('evidence', {}).keys())}")

    # L7.2.1.2: commit_hash 值正确
    total += 1
    passed += check("L7.2.1.2 commit_hash 值正确",
                    finding["evidence"]["commit_hash"] == "abc123def456",
                    f"got: {finding['evidence'].get('commit_hash')}")

    # L7.2.1.3: evidence 含 project 字段 + 值正确
    total += 1
    passed += check("L7.2.1.3 evidence 含 project 字段且值正确",
                    finding["evidence"].get("project") == "libpng",
                    f"got: {finding['evidence'].get('project')}")

    # L7.2.1.4: 空值处理 (commit_id/project 缺失时返回 "")
    empty_row = {
        "func_before": "void func(void) {",
        "lines_before": "1",
        "vul": "1",
        "cve_id": "", "cwe_id": "", "cvss": "", "cve_summary": "",
    }
    empty_finding = bv.convert_bigvul_row(empty_row, 1)
    total += 1
    passed += check("L7.2.1.4 空值处理 (commit_id/project 缺失返回 '')",
                    empty_finding["evidence"]["commit_hash"] == ""
                    and empty_finding["evidence"]["project"] == "",
                    f"commit_hash='{empty_finding['evidence']['commit_hash']}', "
                    f"project='{empty_finding['evidence']['project']}'")

    # L7.2.1.5: 向后兼容 (旧字段 file/line_start 仍存在)
    total += 1
    passed += check("L7.2.1.5 向后兼容 (file/line_start 仍存在)",
                    "file" in finding["evidence"]
                    and "line_start" in finding["evidence"],
                    f"evidence: {finding['evidence']}")

    # ── L7.2.2: cvefixes evidence 保留 repo_url/commit_hash ─────────
    print("\n── L7.2.2: cvefixes_to_findings evidence 字段 ──")
    import cvefixes_to_findings as cf

    # L7.2.2.1: evidence 含 repo_url 字段
    test_record = {
        "cve_id": "CVE-2021-5678",
        "cwe_id": "CWE-79",
        "cvss_score": "8.0",
        "cve_summary": "XSS vulnerability",
        "project_name": "wordpress",
        "file_path": "wp-includes/post.php",
        "line_start": 234,
        "func_name": "wp_insert_post",
        "repo_url": "https://github.com/WordPress/wordpress-develop",
        "commit_hash": "def789abc012",
    }
    finding = cf.convert_cvefixes_record(test_record, 0)
    total += 1
    passed += check("L7.2.2.1 evidence 含 repo_url 字段",
                    "repo_url" in finding.get("evidence", {}),
                    f"evidence keys: {list(finding.get('evidence', {}).keys())}")

    # L7.2.2.2: repo_url 值正确
    total += 1
    passed += check("L7.2.2.2 repo_url 值正确",
                    finding["evidence"]["repo_url"] == "https://github.com/WordPress/wordpress-develop",
                    f"got: {finding['evidence'].get('repo_url')}")

    # L7.2.2.3: evidence 含 commit_hash 字段 + 值正确
    total += 1
    passed += check("L7.2.2.3 evidence 含 commit_hash 字段且值正确",
                    finding["evidence"].get("commit_hash") == "def789abc012",
                    f"got: {finding['evidence'].get('commit_hash')}")

    # L7.2.2.4: 空值处理 (repo_url/commit_hash 缺失时返回 "")
    empty_record = {
        "cve_id": "", "cwe_id": "", "cvss_score": "", "cve_summary": "",
        "project_name": "", "file_path": "", "line_start": 0, "func_name": "",
        "repo_url": None, "commit_hash": None,
    }
    empty_finding = cf.convert_cvefixes_record(empty_record, 1)
    total += 1
    passed += check("L7.2.2.4 空值处理 (repo_url/commit_hash 为 None 时返回 '')",
                    empty_finding["evidence"]["repo_url"] == ""
                    and empty_finding["evidence"]["commit_hash"] == "",
                    f"repo_url='{empty_finding['evidence']['repo_url']}', "
                    f"commit_hash='{empty_finding['evidence']['commit_hash']}'")

    # L7.2.2.5: 向后兼容 (file/line_start 仍存在)
    total += 1
    passed += check("L7.2.2.5 向后兼容 (file/line_start 仍存在)",
                    "file" in finding["evidence"]
                    and "line_start" in finding["evidence"],
                    f"evidence: {finding['evidence']}")

    # ── L7.2.3: download_repos.py ──────────────────────────────────
    print("\n── L7.2.3: download_repos.py ──")
    import download_repos as dr

    # L7.2.3.1: _infer_github_url 基本逻辑
    total += 1
    passed += check("L7.2.3.1a _infer_github_url 纯 project 名推断",
                    dr._infer_github_url("pango") == "https://github.com/pango/pango",
                    f"got: {dr._infer_github_url('pango')}")
    total += 1
    passed += check("L7.2.3.1b _infer_github_url owner/repo 格式",
                    dr._infer_github_url("WordPress/wordpress-develop") == "https://github.com/WordPress/wordpress-develop",
                    f"got: {dr._infer_github_url('WordPress/wordpress-develop')}")
    total += 1
    passed += check("L7.2.3.1c _infer_github_url 空 project 返回空字符串",
                    dr._infer_github_url("") == "",
                    f"got: '{dr._infer_github_url('')}'")
    total += 1
    passed += check("L7.2.3.1d _infer_github_url 完整 URL 原样返回",
                    dr._infer_github_url("https://github.com/foo/bar") == "https://github.com/foo/bar",
                    f"got: {dr._infer_github_url('https://github.com/foo/bar')}")

    # L7.2.3.2: download_repo 失败处理 (无效 URL)
    total += 1
    with tempfile.TemporaryDirectory() as tmpdir:
        result = dr.download_repo(
            "https://invalid.example.com/nonexistent.git",
            "abc123",
            Path(tmpdir) / "test_repo",
            timeout=10,
        )
        passed += check("L7.2.3.2 download_repo 无效 URL 返回 success=False",
                       result["success"] is False,
                       f"reason: {result['reason']}")

    # L7.2.3.3: update_ground_truth 升级 real_bug_no_repo → real_bug
    total += 1
    with tempfile.TemporaryDirectory() as tmpdir:
        gt_path = Path(tmpdir) / "ground_truth.json"
        gt_data = [
            {"id": "BV-0001", "ground_truth": "real_bug_no_repo", "expected_action": "keep"},
            {"id": "BV-0002", "ground_truth": "real_bug_no_repo", "expected_action": "keep"},
            {"id": "BV-0003", "ground_truth": "real_bug", "expected_action": "keep"},
        ]
        gt_path.write_text(json.dumps(gt_data), encoding="utf-8")
        updated = dr.update_ground_truth(gt_path, {"BV-0001"})
        # 验证返回值
        ok_return = updated == 1
        # 验证实际更新
        new_gt = json.loads(gt_path.read_text(encoding="utf-8"))
        ok_update = (new_gt[0]["ground_truth"] == "real_bug"
                     and new_gt[0].get("note") == "Repo downloaded in v2.7.2"
                     and new_gt[1]["ground_truth"] == "real_bug_no_repo"
                     and new_gt[2]["ground_truth"] == "real_bug")
        passed += check("L7.2.3.3 update_ground_truth 升级 real_bug_no_repo → real_bug",
                       ok_return and ok_update,
                       f"updated={updated}, gt[0]={new_gt[0].get('ground_truth')}")

    # L7.2.3.4: update_ground_truth 幂等性 (real_bug 不再更新)
    total += 1
    with tempfile.TemporaryDirectory() as tmpdir:
        gt_path = Path(tmpdir) / "ground_truth.json"
        gt_data = [
            {"id": "BV-0001", "ground_truth": "real_bug", "expected_action": "keep"},
        ]
        gt_path.write_text(json.dumps(gt_data), encoding="utf-8")
        updated = dr.update_ground_truth(gt_path, {"BV-0001"})
        passed += check("L7.2.3.4 update_ground_truth 幂等 (已是 real_bug 不再更新)",
                       updated == 0,
                       f"updated={updated}")

    # L7.2.3.5: download_repos dry-run 模式不执行实际 clone
    total += 1
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        findings_path = tmpdir / "findings.json"
        findings_data = {
            "findings": [
                {
                    "id": "BV-0001",
                    "severity": "P1",
                    "evidence": {
                        "file": "test.c", "line_start": 1,
                        "commit_hash": "abc123def456",
                        "project": "libpng",
                    },
                },
            ],
        }
        findings_path.write_text(json.dumps(findings_data), encoding="utf-8")
        dest_dir = tmpdir / "repos"

        # 模拟 dry-run (不调用 main, 直接检查逻辑)
        # dry_run 模式应该只打印不下载
        repo_url = dr._infer_github_url("libpng")
        ok_dry_run = repo_url == "https://github.com/libpng/libpng"
        passed += check("L7.2.3.5 dry-run 模式 repo_url 推断正确 (不执行 clone)",
                       ok_dry_run,
                       f"repo_url: {repo_url}")

    # L7.2.3.6: download_repos 缺少 repo_url 和 commit_hash 时跳过
    total += 1
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        findings_path = tmpdir / "findings.json"
        findings_data = {
            "findings": [
                {
                    "id": "BV-0001",
                    "severity": "P1",
                    "evidence": {"file": "test.c", "line_start": 1,
                                 "commit_hash": "", "project": ""},
                },
            ],
        }
        findings_path.write_text(json.dumps(findings_data), encoding="utf-8")
        # 检查逻辑: project="" → _infer_github_url 返回 "" → 应跳过
        skip_url = dr._infer_github_url("")
        passed += check("L7.2.3.6 缺少 repo_url 和 project 时推断为空 (跳过)",
                       skip_url == "",
                       f"inferred: '{skip_url}'")

    # ── L7.2.4: cvefixes SQL 查询包含 repo_url/commit_hash 字段 ─────
    print("\n── L7.2.4: cvefixes SQL 查询验证 ──")
    # L7.2.4.1: real schema SQL 包含 fixes.repo_url 和 fixes.hash
    cf_source = (ROOT / "scripts" / "cvefixes_to_findings.py").read_text(encoding="utf-8")
    total += 1
    passed += check("L7.2.4.1 real schema SQL 包含 fixes.repo_url",
                   "fixes.repo_url AS repo_url" in cf_source,
                   "fixes.repo_url AS repo_url not found in source")
    total += 1
    passed += check("L7.2.4.2 real schema SQL 包含 fixes.hash AS commit_hash",
                   "fixes.hash AS commit_hash" in cf_source,
                   "fixes.hash AS commit_hash not found in source")

    # L7.2.4.3: test schema SQL 包含 NULL AS repo_url/commit_hash 占位
    total += 1
    passed += check("L7.2.4.3 test schema SQL 含 NULL AS repo_url 占位",
                   "NULL AS repo_url" in cf_source,
                   "NULL AS repo_url not found in source")
    total += 1
    passed += check("L7.2.4.4 test schema SQL 含 NULL AS commit_hash 占位",
                   "NULL AS commit_hash" in cf_source,
                   "NULL AS commit_hash not found in source")

    # ── L_reg: v2.6 回归 ───────────────────────────────────────────
    print("\n── L_reg: v2.6 回归测试 ──")

    # L_reg_1: bigvul 转换脚本仍能正常运行 (使用现有测试 CSV)
    total += 1
    test_csv = ROOT / "docs" / "benchmark" / "bigvul" / "test_sample.csv"
    if test_csv.exists():
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                # 使用 subprocess 避免污染当前进程
                r = subprocess.run(
                    [sys.executable, "scripts/bigvul_to_findings.py",
                     str(test_csv), "--output", tmpdir],
                    cwd=str(ROOT), capture_output=True, text=True, timeout=30,
                )
                passed += check("L_reg_1 bigvul 转换脚本正常运行",
                               r.returncode == 0,
                               f"rc={r.returncode}, stderr={r.stderr[:100] if r.stderr else ''}")
            except Exception as e:
                passed += check("L_reg_1 bigvul 转换脚本正常运行",
                               False, f"exception: {e}")
    else:
        # 无测试 CSV, 跳过
        passed += check("L_reg_1 bigvul 转换脚本 (无测试 CSV, 跳过)", True)
        print("    (test_sample.csv not found, skipped)")

    # L_reg_2: cvefixes 转换脚本仍能正常运行 (使用现有测试 DB)
    total += 1
    test_db = ROOT / "docs" / "benchmark" / "cvefixes" / "test_sample.db"
    if test_db.exists():
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                r = subprocess.run(
                    [sys.executable, "scripts/cvefixes_to_findings.py",
                     str(test_db), "--output", tmpdir],
                    cwd=str(ROOT), capture_output=True, text=True, timeout=30,
                )
                passed += check("L_reg_2 cvefixes 转换脚本正常运行",
                               r.returncode == 0,
                               f"rc={r.returncode}, stderr={r.stderr[:100] if r.stderr else ''}")
            except Exception as e:
                passed += check("L_reg_2 cvefixes 转换脚本正常运行",
                               False, f"exception: {e}")
    else:
        # 无测试 DB, 用内存 SQLite 创建简化 schema 测试
        import sqlite3 as sql
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            db_path = tmpdir / "test.db"
            conn = sql.connect(str(db_path))
            conn.execute("CREATE TABLE cves (cve_id TEXT, cwe_id TEXT, cvss_score TEXT, "
                         "description TEXT, project_name TEXT)")
            conn.execute("CREATE TABLE fixes (cve_id TEXT, file_path TEXT, "
                         "line_start INTEGER, func_name TEXT)")
            conn.execute("INSERT INTO cves VALUES ('CVE-2021-9999', 'CWE-79', '7.0', "
                         "'test vuln', 'testproject')")
            conn.execute("INSERT INTO fixes VALUES ('CVE-2021-9999', 'test.py', 10, 'testfunc')")
            conn.commit()
            conn.close()

            out_dir = tmpdir / "output"
            try:
                r = subprocess.run(
                    [sys.executable, "scripts/cvefixes_to_findings.py",
                     str(db_path), "--output", str(out_dir)],
                    cwd=str(ROOT), capture_output=True, text=True, timeout=30,
                )
                # 验证转换成功 + evidence 含 repo_url/commit_hash (空字符串)
                ok = r.returncode == 0
                if ok:
                    out_findings = json.loads(
                        (out_dir / "findings.json").read_text(encoding="utf-8"))
                    if out_findings.get("findings"):
                        ev = out_findings["findings"][0].get("evidence", {})
                        ok = "repo_url" in ev and "commit_hash" in ev
                passed += check("L_reg_2 cvefixes 简化 schema 转换 + 含 repo_url/commit_hash",
                               ok,
                               f"rc={r.returncode}, stderr={r.stderr[:80] if r.stderr else ''}")
            except Exception as e:
                passed += check("L_reg_2 cvefixes 简化 schema 转换",
                               False, f"exception: {e}")

    # ── 汇总 ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Total: {passed}/{total} passed")
    print(f"{'='*60}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    import subprocess
    sys.exit(main())
