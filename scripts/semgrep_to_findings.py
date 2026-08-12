#!/usr/bin/env python3
"""Convert Semgrep JSON output to ADD findings format.

v2.8 T3: Semgrep → ADD findings 转换器.

Semgrep --json 输出结构:
    {
      "results": [
        {
          "check_id": "python.lang.security.audit.dangerous-subprocess-use",
          "path": "src/main.py",
          "start": {"line": 42, "col": 5},
          "extra": {
            "message": "Dangerous subprocess use",
            "severity": "ERROR",
            "metadata": {
              "cwe": ["CWE-78: ..."],
              "owasp": ["A1: Injection"]
            }
          }
        }
      ]
    }

用法:
    python scripts/semgrep_to_findings.py <semgrep-output.json> \\
        --output <output_dir> \\
        [--repo-local-path <path>]
"""
import argparse
import json
import re
import sys
from pathlib import Path

# T5 集成: 调用 cwe_rules.enrich_finding_with_cwe 增强 finding (spec §2.4.2)
try:
    from cwe_rules import enrich_finding_with_cwe
    _CWE_ENRICH_AVAILABLE = True
except ImportError:
    _CWE_ENRICH_AVAILABLE = False

# 模块级常量 (§0.4 性能规范: 预编译正则 + 模块级 import)
SEVERITY_MAP = {"ERROR": "P0", "WARNING": "P1", "INFO": "P2"}
CLAIM_TEMPLATE = "{check_id}: {message} ({cwe}) — affects {path}:{line}"
_CWE_RE = re.compile(r"CWE-\d+")


def _extract_cwe(metadata):
    """从 Semgrep metadata.cwe 数组提取 CWE 标识.

    Args:
        metadata: dict, Semgrep result 的 extra.metadata

    Returns:
        str: CWE 标识 (如 "CWE-78") 或空字符串

    Note:
        Semgrep 的 cwe 字段是数组类型, 元素格式如:
        "CWE-78: Improper Neutralization of ... ('OS Command Injection')"
        需要提取 "CWE-78" 部分.
    """
    cwe_list = metadata.get("cwe", [])
    if not cwe_list or not isinstance(cwe_list, list):
        return ""
    # 取第一个元素, 用正则提取 CWE-XX
    match = _CWE_RE.search(cwe_list[0])
    return match.group(0) if match else ""


def _extract_owasp(metadata):
    """从 Semgrep metadata.owasp 数组提取 OWASP 分类."""
    owasp_list = metadata.get("owasp", [])
    if not owasp_list or not isinstance(owasp_list, list):
        return ""
    return owasp_list[0] if owasp_list else ""


def convert_semgrep_result(result, idx):
    """转换单个 Semgrep result 到 ADD finding.

    Args:
        result: dict, 单个 Semgrep result
        idx: int, 序号 (用于生成 finding id)

    Returns:
        dict: ADD finding
    """
    check_id = result.get("check_id", f"unknown-{idx}")
    path = result.get("path", "")
    start = result.get("start", {})
    line = start.get("line", 0)
    extra = result.get("extra", {})
    message = extra.get("message", "")
    severity_str = extra.get("severity", "INFO")
    metadata = extra.get("metadata", {})

    cwe = _extract_cwe(metadata)
    owasp = _extract_owasp(metadata)

    finding = {
        "id": f"SG-{idx:04d}",  # 前缀 SG- + 4 位序号
        "severity": SEVERITY_MAP.get(severity_str, "P2"),
        "claim": CLAIM_TEMPLATE.format(
            check_id=check_id, message=message, cwe=cwe,
            path=path, line=line),
        "evidence": {
            "file": path,
            "line_start": line,
            "cwe": cwe,
            "owasp": owasp,
            "rule_id": check_id,
            "source": "semgrep",
        },
        "l4_eligible": True,
        "dimension": "security",
    }
    return finding


def main(argv=None):
    """读取 Semgrep JSON, 输出 findings.json + ground_truth.json.

    Args:
        argv: 命令行参数列表 (None 时用 sys.argv)

    Returns:
        dict: {"findings": count}
    """
    parser = argparse.ArgumentParser(
        description="Convert Semgrep JSON to ADD findings format")
    parser.add_argument("input", help="Path to Semgrep JSON output")
    parser.add_argument("--output", required=True,
                        help="Output directory for findings.json + ground_truth.json")
    parser.add_argument("--repo-local-path", default="",
                        help="Local repo path for L4 verification (optional)")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in {input_path}: {e}", file=sys.stderr)
        sys.exit(1)

    results = data.get("results", [])
    if not results:
        print(f"WARNING: no results in {input_path}", file=sys.stderr)

    # 转换所有 results
    findings = []
    ground_truth = []
    for idx, result in enumerate(results):
        finding = convert_semgrep_result(result, idx)
        if args.repo_local_path:
            finding["evidence"]["repo_local_path"] = args.repo_local_path
        # T5 集成: 增强 CWE 信息 (spec §2.4.2)
        if _CWE_ENRICH_AVAILABLE:
            finding = enrich_finding_with_cwe(finding)
        findings.append(finding)
        # H7 修正: 所有 Semgrep findings 标记为 real_bug_pending_verification
        ground_truth.append({
            "id": finding["id"],
            "ground_truth": "real_bug_pending_verification",
            "expected_action": "pending",
        })

    # 写出
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "findings.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Converted {len(findings)} Semgrep results → {output_dir}")
    return {"findings": len(findings)}


if __name__ == "__main__":
    main()
