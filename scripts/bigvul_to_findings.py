"""Big-Vul → ADD findings 格式转换器.

读取 Big-Vul C/C++ 漏洞 CSV 数据,
转换为 ADD framework 的 findings.json + ground_truth.json 格式.

支持两种 CSV 列格式:
  1. 简化格式 (测试用): func_before, lines_before, vul, cve_id, cwe_id,
     cvss, cve_summary
  2. 真实 Big-Vul 格式 (all_c_cpp_release2.0.csv): cve_id, cwe_id, score,
     summary, commit_message, files_changed, project, lang, ... — 通过
     normalize_bigvul_row() 自动映射到简化格式

使用 csv.DictReader 解析 (正确处理含换行符的引号字段), 不依赖 pandas.

用法:
  python scripts/bigvul_to_findings.py <input.csv> --output <output_dir>
"""
import csv
import json
import re
import sys
import time
import argparse
from pathlib import Path


# ── Claim 模板 ──────────────────────────────────────────────

BIGVUL_CLAIM_TEMPLATE = (
    "function {func_name} has {cwe_id} vulnerability: {cve_summary} "
    "(CVSS {score}) — fix modifies lines {lines}"
)


# ── 真实 Big-Vul 列名映射 ───────────────────────────────────
# 真实 all_c_cpp_release2.0.csv 的列名与简化格式的对应关系
_REAL_COLUMN_ALIASES = {
    "score": "cvss",       # CVSS 评分
    "summary": "cve_summary",  # CVE 摘要
    # cve_id, cwe_id 在两种格式中名称一致
}

# 匹配 unified diff hunk 头: @@ -61,14 +61,28 @@ func_context
_PATCH_HUNK_RE = re.compile(
    r'@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@\s*(.*)'
)


def _parse_files_changed(files_changed_str):
    """解析真实 Big-Vul files_changed 字段 (JSON 字符串).

    从第一个文件的 patch 中提取文件名、起始行号和函数名上下文.

    Args:
        files_changed_str: files_changed 字段的原始字符串 (JSON)

    Returns:
        tuple: (filename, line_start, func_name)
            filename  — 文件路径 (如 "pango/glyphstring.c"), 解析失败为 None
            line_start— patch hunk 的旧行号起始, 解析失败为 1
            func_name — hunk 上下文中的函数名, 解析失败为 None
    """
    if not files_changed_str or not files_changed_str.strip():
        return None, 1, None
    try:
        data = json.loads(files_changed_str)
    except (ValueError, TypeError):
        return None, 1, None
    # files_changed 可能是单个 dict 或 dict 列表
    if isinstance(data, dict):
        files = [data]
    elif isinstance(data, list):
        files = data
    else:
        return None, 1, None
    if not files:
        return None, 1, None
    first = files[0]
    if not isinstance(first, dict):
        return None, 1, None

    filename = first.get("filename", "") or None
    patch = first.get("patch", "") or ""
    line_start = 1
    func_name = None

    if patch:
        m = _PATCH_HUNK_RE.search(patch)
        if m:
            try:
                line_start = int(m.group(1))
            except ValueError:
                line_start = 1
            # hunk 上下文在第二个 @@ 之后, 形如 "func_name (args)" 或 "class::method"
            context = m.group(3).strip()
            if context:
                fm = re.match(r'([A-Za-z_][\w:]*)', context)
                if fm:
                    func_name = fm.group(1)
    return filename, line_start, func_name


def normalize_bigvul_row(row):
    """将 Big-Vul CSV 行规范化为简化列格式.

    自动检测输入格式:
      - 简化格式 (含 func_before + vul 列): 原样返回
      - 真实 Big-Vul 格式 (含 score/summary/files_changed): 映射列名,
        并从 files_changed 的 patch 中提取文件名/行号/函数名

    Args:
        row: csv.DictReader 产生的 dict

    Returns:
        dict: 含简化列名的 dict, 真实格式额外附带 _func_name / _file_path 键
              供 convert_bigvul_row 使用
    """
    # 简化格式: 已含 func_before 和 vul 列 → 原样返回
    if "func_before" in row and "vul" in row:
        return row

    # 真实 Big-Vul 格式: 映射列名
    normalized = dict(row)
    for real_name, simp_name in _REAL_COLUMN_ALIASES.items():
        if simp_name not in normalized:
            normalized[simp_name] = row.get(real_name, "")

    # 真实 Big-Vul 无 vul 列: 每行均为 CVE 漏洞 → vul="1"
    if not normalized.get("vul"):
        normalized["vul"] = "1"

    # 从 files_changed 提取文件名/行号/函数名
    filename, line_start, func_name = _parse_files_changed(
        row.get("files_changed", ""))
    if not normalized.get("lines_before"):
        normalized["lines_before"] = str(line_start)
    if func_name:
        normalized["_func_name"] = func_name
        # 提供伪 func_before 使 extract_func_name 也能工作
        normalized["func_before"] = "void %s(void) {" % func_name
    elif not normalized.get("func_before"):
        normalized["func_before"] = row.get("commit_message", "") or "unknown"
    if filename:
        normalized["_file_path"] = filename
    return normalized


# ── 函数名/行号提取 ─────────────────────────────────────────

# 匹配可选返回类型前缀 (void/int/static 等), 捕获左括号前的函数名标识符
_FUNC_NAME_RE = re.compile(r'(?:[a-zA-Z_]\w*\s+)*([a-zA-Z_]\w*)\s*\(')


def extract_func_name(func_before):
    """从 C/C++ 函数源码中提取函数名.

    Args:
        func_before: C/C++ 函数源码字符串 (func_before 字段)

    Returns:
        str: 函数名, 无法提取时返回 "unknown"
    """
    if not func_before:
        return "unknown"
    m = _FUNC_NAME_RE.search(func_before)
    if m:
        return m.group(1)
    return "unknown"


def extract_line_start(lines_before):
    """从 lines_before 字段提取首个行号.

    Args:
        lines_before: 逗号分隔的行号字符串, 如 "100" 或 "100,101,102"

    Returns:
        int: 首个行号, 空字符串返回 1
    """
    if not lines_before or not lines_before.strip():
        return 1
    first = lines_before.split(",")[0].strip()
    try:
        return int(first)
    except ValueError:
        return 1


# ── 行转换 ──────────────────────────────────────────────────

def convert_bigvul_row(row, idx):
    """转换单个 Big-Vul CSV 行为 ADD finding 格式.

    Args:
        row: CSV 行 (dict), 含 func_before/lines_before/vul/cve_id/cwe_id/cvss/cve_summary.
            真实 Big-Vul 格式经 normalize_bigvul_row() 后可能额外含
            _func_name (从 patch 提取的函数名) 和 _file_path (真实文件路径).
        idx: 序号 (从 0 开始)

    Returns:
        dict: ADD finding, 或 None (vul=="0" 时跳过非漏洞行)
    """
    if row.get("vul") == "0":
        return None

    # 真实 Big-Vul 格式从 patch 提取的函数名优先; 否则从 func_before 源码提取
    func_name = row.get("_func_name") or extract_func_name(
        row.get("func_before", ""))
    line_start = extract_line_start(row.get("lines_before", ""))
    # 真实 Big-Vul 格式有真实文件路径; 否则用函数名推导
    file_path = row.get("_file_path") or "%s.c" % func_name
    claim = BIGVUL_CLAIM_TEMPLATE.format(
        func_name=func_name,
        cwe_id=row.get("cwe_id", ""),
        cve_summary=row.get("cve_summary", ""),
        score=row.get("cvss", ""),
        lines=row.get("lines_before", ""),
    )

    return {
        "id": f"BV-{idx:04d}",
        "severity": "P1",
        "l4_eligible": False,  # C/C++, 无 L4
        "dimension": "security",
        "claim": claim,
        "evidence": {
            "file": file_path,
            "line_start": line_start,
            # v2.7.2: 保留 repo 回溯字段, 供 download_repos.py 使用
            "commit_hash": row.get("commit_id", ""),
            "project": row.get("project", ""),
        },
    }


# ── 主流程 ──────────────────────────────────────────────────

def main(argv=None):
    """读取 Big-Vul CSV, 输出 findings.json + ground_truth.json.

    用法:
      python bigvul_to_findings.py <input.csv> --output <output_dir>
    """
    parser = argparse.ArgumentParser(
        description="Convert Big-Vul CSV to ADD findings format")
    parser.add_argument("input", help="Path to Big-Vul CSV file")
    parser.add_argument("--output", required=True,
                        help="Output directory for findings.json + ground_truth.json")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    findings = []
    ground_truth = []
    idx = 0

    # newline="" 是 Python csv 模块标准用法, 正确处理含换行符的引号字段
    with open(input_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 规范化: 真实 Big-Vul 格式 → 简化格式; 简化格式原样返回
            row = normalize_bigvul_row(row)
            finding = convert_bigvul_row(row, idx)
            if finding is None:
                continue
            findings.append(finding)
            ground_truth.append({
                "id": finding["id"],
                "ground_truth": "real_bug",
                "expected_action": "keep",
            })
            idx += 1

    # 写出 findings.json
    findings_data = {
        "project": "bigvul",
        "version": "1.0",
        "audit_date": time.strftime("%Y-%m-%d"),
        "audit_mode": "dataset-integration layer-3",
        "description": "Converted from Big-Vul C/C++ vulnerability dataset",
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

    print(f"Big-Vul conversion complete:")
    print(f"  Input: {input_path}")
    print(f"  Output dir: {out_dir}")
    print(f"  Findings: {len(findings)}")
    print(f"  Ground truth: {len(ground_truth)}")

    return {
        "findings": len(findings),
    }


if __name__ == "__main__":
    main()
