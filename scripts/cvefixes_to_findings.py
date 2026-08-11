"""CVEfixes → ADD findings 格式转换器.

读取 CVEfixes SQLite 数据库, 转换为 ADD framework 的 findings.json + ground_truth.json 格式.

支持两种 schema:
  1. test/简化 schema (cves + fixes):
     - cves 表: cve_id, cwe_id, cvss_score, description, project_name
     - fixes 表: cve_id, file_path, line_start, func_name
  2. real CVEfixes schema (多表 JOIN, 见 Zenodo DOI 10.5281/zenodo.4476563):
     - cve(cve_id, description, published_date, severity, cvss_score, ...)
     - fixes(cve_id, hash, repo_url)
     - commits(hash, repo_url, parents, msg, ...)
     - repository(repo_url, repo_name, repo_language, ...)
     - file_change(file_change_id, hash, filename, ...)
     - method_change(method_change_id, file_change_id, name, start_line, ...)
     - cwe_classification(cve_id, cwe_id), cwe(cwe_id, description)

流程:
  1. detect_schema: 自动识别 schema (test 或 real)
  2. get_top_projects: 查询 CVE 数量最多的 top N 项目
  3. 对每个项目 JOIN 相关表, 限制 max_per_project 条记录
  4. convert_cvefixes_record: 转换单条记录为 ADD finding
  5. 输出 findings.json (project="cvefixes") + ground_truth.json

用法:
  python scripts/cvefixes_to_findings.py <input.db> --output <output_dir> \
      [--top-projects N] [--max-per-project M]
"""
import json
import sys
import time
import argparse
import sqlite3
from pathlib import Path


# ── Claim 模板 ──────────────────────────────────────────────

CVEFIXES_CLAIM_TEMPLATE = (
    "function {func_name} has {cwe_id} vulnerability: {cve_summary} "
    "(CVSS {score}) — affects {project_name}"
)


# ── Schema 检测 ─────────────────────────────────────────────

def detect_schema(conn):
    """检测 SQLite 数据库使用哪种 schema.

    real CVEfixes schema 使用单数表名 `cve` + `repository` + `commits` +
    `file_change` + `method_change` 等多表; test/简化 schema 使用复数 `cves`
    单表 (含 project_name 列).

    Args:
        conn: sqlite3.Connection

    Returns:
        str: "real" 或 "test"
    """
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    # real CVEfixes: 单数 `cve` 表 + `repository` 表
    if "cve" in tables and "repository" in tables:
        return "real"
    return "test"


# ── Top projects 查询 ───────────────────────────────────────

def get_top_projects(db_path, top_n=10):
    """查询 SQLite 数据库中 CVE 数量最多的 top N 项目.

    自动识别 schema: real schema 通过 repository.repo_name 取项目名,
    test schema 直接取 cves.project_name.

    Args:
        db_path: SQLite 数据库文件路径
        top_n: 返回的项目数量上限

    Returns:
        list[str]: 项目名称列表, 按 CVE 数量降序排列
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        schema = detect_schema(conn)
        if schema == "real":
            cur.execute(
                "SELECT repository.repo_name, COUNT(DISTINCT cve.cve_id) AS cve_count "
                "FROM cve "
                "JOIN fixes ON fixes.cve_id = cve.cve_id "
                "JOIN commits ON commits.hash = fixes.hash "
                "  AND commits.repo_url = fixes.repo_url "
                "JOIN repository ON repository.repo_url = commits.repo_url "
                "GROUP BY repository.repo_name "
                "ORDER BY cve_count DESC LIMIT ?",
                (top_n,)
            )
        else:
            cur.execute(
                "SELECT project_name, COUNT(*) as cve_count "
                "FROM cves GROUP BY project_name "
                "ORDER BY cve_count DESC LIMIT ?",
                (top_n,)
            )
        rows = cur.fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


# ── 实例转换 ────────────────────────────────────────────────

def convert_cvefixes_record(record, idx):
    """转换单条 CVEfixes 记录为 ADD finding 格式.

    Args:
        record: dict, 包含 cve_id, cwe_id, cvss_score, cve_summary,
                project_name, file_path, line_start, func_name
        idx: 序号 (从 0 开始)

    Returns:
        dict: ADD finding
    """
    cwe_id = record.get("cwe_id") or ""
    cve_summary = record.get("cve_summary") or ""
    cvss_score = record.get("cvss_score") or ""
    project_name = record.get("project_name") or ""
    func_name = record.get("func_name") or ""
    file_path = record.get("file_path") or ""
    line_start = record.get("line_start")
    if line_start is None:
        line_start = 0

    claim = CVEFIXES_CLAIM_TEMPLATE.format(
        func_name=func_name,
        cwe_id=cwe_id,
        cve_summary=cve_summary,
        score=cvss_score,
        project_name=project_name,
    )

    return {
        "id": f"CF-{idx:04d}",
        "severity": "P1",
        "l4_eligible": False,
        "dimension": "security",
        "claim": claim,
        "evidence": {"file": file_path, "line_start": line_start},
    }


# ── 主流程 ──────────────────────────────────────────────────

def main(argv=None):
    """读取 CVEfixes SQLite, 输出 findings.json + ground_truth.json.

    用法:
      python cvefixes_to_findings.py <input.db> --output <output_dir> \
          [--top-projects N] [--max-per-project M]
    """
    parser = argparse.ArgumentParser(
        description="Convert CVEfixes SQLite to ADD findings format")
    parser.add_argument("input", help="Path to CVEfixes SQLite database")
    parser.add_argument("--output", required=True,
                        help="Output directory for findings.json + ground_truth.json")
    parser.add_argument("--top-projects", type=int, default=10,
                        help="Top N projects by CVE count (default: 10)")
    parser.add_argument("--max-per-project", type=int, default=50,
                        help="Max records per project (default: 50)")
    args = parser.parse_args(argv)

    db_path = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    # 获取 top N 项目
    top_projects = get_top_projects(str(db_path), top_n=args.top_projects)

    findings = []
    ground_truth = []
    idx = 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        schema = detect_schema(conn)
        for project in top_projects:
            if schema == "real":
                # real CVEfixes schema: 多表 JOIN
                # cwe_id 通过子查询聚合 (一个 CVE 可对应多个 CWE, 用 ';' 分隔)
                # cvss_score 优先取 cve.cvss_score, 缺失则回退到 severity
                # func_name/line_start 取 before_change=1 的 method_change
                cur.execute(
                    "SELECT cve.cve_id AS cve_id, "
                    "  (SELECT GROUP_CONCAT(cwe_id, ';') FROM cwe_classification "
                    "   WHERE cwe_classification.cve_id = cve.cve_id) AS cwe_id, "
                    "  COALESCE(cve.cvss_score, 0) AS cvss_score, "
                    "  cve.description AS cve_summary, "
                    "  repository.repo_name AS project_name, "
                    "  file_change.filename AS file_path, "
                    "  COALESCE(method_change.start_line, 0) AS line_start, "
                    "  COALESCE(method_change.name, '') AS func_name "
                    "FROM cve "
                    "JOIN fixes ON fixes.cve_id = cve.cve_id "
                    "JOIN commits ON commits.hash = fixes.hash "
                    "  AND commits.repo_url = fixes.repo_url "
                    "JOIN repository ON repository.repo_url = commits.repo_url "
                    "JOIN file_change ON file_change.hash = commits.hash "
                    "LEFT JOIN method_change ON "
                    "  method_change.file_change_id = file_change.file_change_id "
                    "  AND method_change.before_change = 1 "
                    "WHERE repository.repo_name = ? "
                    "ORDER BY cve.cve_id LIMIT ?",
                    (project, args.max_per_project)
                )
            else:
                # test/简化 schema: cves + fixes 直接 JOIN
                cur.execute(
                    "SELECT cves.cve_id AS cve_id, cves.cwe_id AS cwe_id, "
                    "cves.cvss_score AS cvss_score, cves.description AS cve_summary, "
                    "cves.project_name AS project_name, fixes.file_path AS file_path, "
                    "fixes.line_start AS line_start, fixes.func_name AS func_name "
                    "FROM cves JOIN fixes ON cves.cve_id = fixes.cve_id "
                    "WHERE cves.project_name = ? "
                    "ORDER BY cves.cve_id LIMIT ?",
                    (project, args.max_per_project)
                )
            for row in cur.fetchall():
                record = dict(row)
                finding = convert_cvefixes_record(record, idx)
                findings.append(finding)
                ground_truth.append({
                    "id": finding["id"],
                    "ground_truth": "real_bug",
                    "expected_action": "keep",
                })
                idx += 1
    finally:
        conn.close()

    # 写出 findings.json
    findings_data = {
        "project": "cvefixes",
        "version": "1.0",
        "audit_date": time.strftime("%Y-%m-%d"),
        "audit_mode": "dataset-integration layer-3",
        "description": "Converted from CVEfixes SQLite database",
        "findings": findings,
    }
    (out_dir / "findings.json").write_text(
        json.dumps(findings_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # 写出 ground_truth.json
    (out_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"CVEfixes conversion complete:")
    print(f"  Input: {db_path}")
    print(f"  Output dir: {out_dir}")
    print(f"  Top projects: {len(top_projects)}")
    print(f"  Findings: {len(findings)}")
    print(f"  Ground truth: {len(ground_truth)}")

    return {
        "findings": len(findings),
        "projects": len(top_projects),
    }


if __name__ == "__main__":
    main()
