"""SWE-bench → ADD findings 格式转换器.

读取 SWE-bench JSONL (HuggingFace princeton-nlp/SWE-bench_Verified),
转换为 ADD framework 的 findings.json + ground_truth.json 格式.

patch 解析规则 (避免幻觉):
  - 只取 +++ b/<path> 行提取 file_path
  - line_start 取第一个 @@ hunk header 的 -<start>,<count> 中的 start
  - 多文件 patch 只取第一个文件
  - 无法解析的 patch 跳过并记录到 conversion_errors.json

用法:
  python scripts/swebench_to_findings.py <input.jsonl> --output <output_dir>
"""
import json
import re
import sys
import time
import argparse
from pathlib import Path


# ── Patch 解析 ──────────────────────────────────────────────

# 匹配 +++ b/<path> 行 (unified diff 的新文件路径)
_NEW_FILE_RE = re.compile(r'^\+\+\+ b/(.+?)\s*$')

# 匹配 @@ hunk header, 捕获 -<start> 部分
# 格式: @@ -<start>,<count> +<start>,<count> <context>
_HUNK_RE = re.compile(r'^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@')


def extract_file_line_from_patch(patch_text):
    """从 unified diff patch 中提取第一个文件的 file_path 和 line_start.

    Args:
        patch_text: unified diff 格式的 patch 字符串

    Returns:
        tuple (file_path, line_start) 或 None (无法解析)
    """
    if not patch_text or not patch_text.strip():
        return None

    lines = patch_text.split("\n")

    # 找第一个 +++ b/<path> 行
    file_path = None
    file_line_idx = None
    for i, line in enumerate(lines):
        m = _NEW_FILE_RE.match(line)
        if m:
            file_path = m.group(1).strip()
            file_line_idx = i
            break

    if file_path is None or not file_path:
        return None

    # 从 file_line_idx 之后找第一个 @@ hunk header
    # hunk header 在 +++ 行之后 (同一文件的 diff 段)
    line_start = None
    for i in range(file_line_idx + 1, len(lines)):
        # 遇到下一个 +++ b/ 行说明当前文件的 diff 段已结束
        if _NEW_FILE_RE.match(lines[i]):
            break
        m = _HUNK_RE.match(lines[i])
        if m:
            line_start = int(m.group(1))
            break

    if line_start is None:
        return None

    return (file_path, line_start)


# ── Claim 生成 ──────────────────────────────────────────────

_MAX_CLAIM_LEN = 200


def build_claim_from_issue(problem_statement):
    """从 SWE-bench problem_statement 构建 claim 字符串.

    策略: 截取前 200 字符, 避免 LLM 引入二次幻觉.

    Args:
        problem_statement: SWE-bench issue 描述文本

    Returns:
        str: claim 字符串 (≤200 字符)
    """
    if not problem_statement or not problem_statement.strip():
        return "SWE-bench instance: no problem statement available"
    text = problem_statement.strip()
    if len(text) > _MAX_CLAIM_LEN:
        return text[:_MAX_CLAIM_LEN]
    return text


# ── 实例转换 ────────────────────────────────────────────────

def convert_swebench_instance(instance, idx):
    """转换单个 SWE-bench instance 为 ADD finding 格式.

    Args:
        instance: SWE-bench JSONL 的一行 (dict)
        idx: 序号 (从 0 开始)

    Returns:
        dict: ADD finding 或 None (patch 无法解析)
    """
    patch = instance.get("patch", "")
    result = extract_file_line_from_patch(patch)
    if result is None:
        return None

    file_path, line_start = result
    claim = build_claim_from_issue(instance.get("problem_statement", ""))

    return {
        "id": f"SWB-{idx:04d}",
        "severity": "P1",  # SWE-bench bugs are real but not necessarily P0
        "claim": claim,
        "evidence": {"file": file_path, "line_start": line_start},
        "dimension": "functional"  # SWE-bench bugs are functional, not structural
    }


# ── 主流程 ──────────────────────────────────────────────────

def main(argv=None):
    """读取 SWE-bench JSONL, 输出 findings.json + ground_truth.json + conversion_errors.json.

    用法:
      python swebench_to_findings.py <input.jsonl> --output <output_dir>
    """
    parser = argparse.ArgumentParser(
        description="Convert SWE-bench JSONL to ADD findings format")
    parser.add_argument("input", help="Path to SWE-bench JSONL file")
    parser.add_argument("--output", required=True,
                        help="Output directory for findings.json + ground_truth.json")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 读取 JSONL
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    findings = []
    ground_truth = []
    errors = []
    idx = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                instance = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append({
                    "line_num": line_num,
                    "error": f"JSON decode error: {e}",
                })
                continue

            finding = convert_swebench_instance(instance, idx)
            if finding is None:
                errors.append({
                    "instance_id": instance.get("instance_id", f"line_{line_num}"),
                    "error": "patch parsing failed (no +++ b/<path> or @@ hunk found)",
                })
                continue

            findings.append(finding)
            ground_truth.append({
                "id": finding["id"],
                "ground_truth": "real_bug",
                "expected_action": "verified",
                "note": f"SWE-bench instance {instance.get('instance_id', 'unknown')}",
            })
            idx += 1

    # 写出 findings.json
    findings_data = {
        "project": "swebench-verified",
        "version": "1.0",
        "audit_date": time.strftime("%Y-%m-%d"),
        "audit_mode": "dataset-integration layer-1",
        "description": "Converted from SWE-bench Verified subset",
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

    print(f"SWE-bench conversion complete:")
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
