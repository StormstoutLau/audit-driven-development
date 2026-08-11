"""Defects4J → ADD findings 格式转换器.

读取 Defects4J active-bugs CSV, 转换为 ADD framework 的
findings.json + ground_truth.json + conversion_errors.json 格式.

CSV 列: project,bug_id,commit_hash,commit_message,file_path,line_start

Java findings 注意事项 (v2.6):
  - l4_eligible = False (Joern v2.6 无 Java 结构化验证支持)
  - dimension = "functional" (Defects4J 为功能 bug, 非安全/结构)

用法:
  python scripts/defects4j_to_findings.py <input.csv> --output <output_dir> [--max-bugs 50]
"""
import csv
import json
import sys
import time
import argparse
from pathlib import Path


# ── Claim 模板 ──────────────────────────────────────────────

DEFECTS4J_CLAIM_TEMPLATE = (
    "bug in {project} {file}:{line} — "
    "fix commit {commit}: {message}"
)

# commit_message 截断长度 (避免 claim 过长导致 LLM 二次幻觉)
_MAX_MESSAGE_LEN = 200


# ── Claim 生成 ──────────────────────────────────────────────

def build_claim(project, file_path, line_start, commit_hash, commit_message):
    """构建 Defects4J finding 的 claim 字符串.

    Args:
        project: 项目名 (如 "Chart")
        file_path: 文件路径
        line_start: 起始行号
        commit_hash: 修复 commit hash
        commit_message: commit message (截断到 200 字符)

    Returns:
        str: claim 字符串
    """
    message = commit_message or ""
    if len(message) > _MAX_MESSAGE_LEN:
        message = message[:_MAX_MESSAGE_LEN]
    return DEFECTS4J_CLAIM_TEMPLATE.format(
        project=project or "",
        file=file_path or "",
        line=line_start,
        commit=commit_hash or "",
        message=message,
    )


# ── 实例转换 ────────────────────────────────────────────────

def convert_defects4j_bug(bug_row, idx):
    """转换单个 Defects4J bug row 为 ADD finding 格式.

    Args:
        bug_row: dict, 含 project/bug_id/commit_hash/commit_message/
                 file_path/line_start
        idx: 序号 (从 0 开始)

    Returns:
        dict: ADD finding (id 格式 D4J-NNNN), 或 None (file_path 缺失)
    """
    file_path = bug_row.get("file_path", "")
    if not file_path:
        return None

    # line_start 转 int (CSV 读取时为字符串)
    line_start_raw = bug_row.get("line_start")
    try:
        line_start = int(line_start_raw)
    except (TypeError, ValueError):
        line_start = 1

    project = bug_row.get("project", "")
    commit_hash = bug_row.get("commit_hash", "")
    commit_message = bug_row.get("commit_message", "")

    claim = build_claim(
        project=project,
        file_path=file_path,
        line_start=line_start,
        commit_hash=commit_hash,
        commit_message=commit_message,
    )

    return {
        "id": f"D4J-{idx:04d}",
        "severity": "P1",
        "l4_eligible": False,  # Java: Joern v2.6 无 Java 结构化验证
        "dimension": "functional",
        "claim": claim,
        "evidence": {"file": file_path, "line_start": line_start},
    }


# ── 主流程 ──────────────────────────────────────────────────

# CSV 必需列
_REQUIRED_COLUMNS = (
    "project", "bug_id", "commit_hash", "commit_message",
    "file_path", "line_start",
)


def main(argv=None):
    """读取 Defects4J CSV, 输出 findings.json + ground_truth.json + conversion_errors.json.

    用法:
      python defects4j_to_findings.py <input.csv> --output <output_dir> [--max-bugs N]
    """
    parser = argparse.ArgumentParser(
        description="Convert Defects4J active-bugs CSV to ADD findings format")
    parser.add_argument("input", help="Path to Defects4J active-bugs CSV file")
    parser.add_argument("--output", required=True,
                        help="Output directory for findings.json + ground_truth.json")
    parser.add_argument("--max-bugs", type=int, default=50,
                        help="Maximum number of bugs to convert (default: 50)")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    findings = []
    ground_truth = []
    errors = []
    idx = 0
    bugs_read = 0

    with open(input_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        # 检查必需列是否存在
        if reader.fieldnames is not None:
            missing_cols = [c for c in _REQUIRED_COLUMNS
                            if c not in reader.fieldnames]
            if missing_cols:
                errors.append({
                    "error": f"missing required columns: {missing_cols}",
                    "fieldnames": list(reader.fieldnames),
                })
                # 列缺失, 不再逐行解析
                reader = iter([])
        else:
            # 空 CSV (无 header)
            reader = iter([])

        for row_num, row in enumerate(reader, 2):  # 2 = header 行 + 首数据行
            if bugs_read >= args.max_bugs:
                break
            bugs_read += 1

            bug_id = row.get("bug_id", "")

            # file_path 缺失 → 记录错误并跳过
            if not row.get("file_path"):
                errors.append({
                    "row_num": row_num,
                    "bug_id": bug_id,
                    "error": "missing file_path",
                })
                continue

            try:
                finding = convert_defects4j_bug(row, idx)
            except Exception as e:
                errors.append({
                    "row_num": row_num,
                    "bug_id": bug_id,
                    "error": f"conversion failed: {e}",
                })
                continue

            if finding is None:
                errors.append({
                    "row_num": row_num,
                    "bug_id": bug_id,
                    "error": "conversion returned None (missing file_path)",
                })
                continue

            findings.append(finding)
            ground_truth.append({
                "id": finding["id"],
                "ground_truth": "real_bug",
                "expected_action": "keep",
                "note": f"Defects4J {row.get('project', '')}/{bug_id}",
            })
            idx += 1

    # 写出 findings.json
    findings_data = {
        "project": "defects4j",
        "version": "1.0",
        "audit_date": time.strftime("%Y-%m-%d"),
        "audit_mode": "dataset-integration layer-1",
        "description": "Converted from Defects4J active-bugs CSV",
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

    # 写出 conversion_errors.json
    (out_dir / "conversion_errors.json").write_text(
        json.dumps(errors, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Defects4J conversion complete:")
    print(f"  Input: {input_path}")
    print(f"  Output dir: {out_dir}")
    print(f"  Findings: {len(findings)}")
    print(f"  Ground truth: {len(ground_truth)}")
    print(f"  Conversion errors: {len(errors)}")

    return {
        "findings": len(findings),
        "errors": len(errors),
    }


if __name__ == "__main__":
    main()
