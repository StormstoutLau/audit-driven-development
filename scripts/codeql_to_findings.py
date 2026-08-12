#!/usr/bin/env python3
"""Convert CodeQL SARIF output to ADD findings format.

v2.8 T4: CodeQL SARIF → ADD findings 转换器.

CodeQL --format sarif-latest 输出结构 (SARIF 2.1.0):
    {
      "runs": [{
        "results": [...],
        "tool": {
          "driver": {
            "rules": [
              {"id": "py/command-injection",
               "properties": {"tags": ["security", "external/cwe/cwe-78"]}}
            ]
          }
        }
      }]
    }

Note:
    SARIF properties.tags 是 CodeQL 约定 (非 SARIF 强制), 缺失时 cwe 为空.

用法:
    python scripts/codeql_to_findings.py <codeql-output.sarif> \\
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
_CWE_TAG_RE = re.compile(r"cwe-(\d+)", re.IGNORECASE)

LEVEL_MAP = {"error": "P0", "warning": "P1", "note": "P2"}


def parse_sarif(sarif_path):
    """解析 SARIF 文件, 返回 (results, rules_index) 元组.

    Args:
        sarif_path: SARIF JSON 文件路径

    Returns:
        tuple: (results list, rules_dict by ruleId)

    Note:
        SARIF 结构: runs[0].results + runs[0].tool.driver.rules
        rules_index 预构建为 {ruleId: rule_dict} 避免 O(n²) 查找
    """
    data = json.loads(sarif_path.read_text(encoding="utf-8"))
    runs = data.get("runs", [])
    if not runs:
        return [], {}

    run = runs[0]
    results = run.get("results", [])

    # 预构建 rules 索引 (O(n) 一次, 避免 result × rules O(n²) 查找)
    # SARIF 2.0.0 fallback: toolComponents
    rules_list = (
        run.get("tool", {}).get("driver", {}).get("rules", [])
        or run.get("tool", {}).get("toolComponents", [{}])[0].get("rules", [])
    )
    rules_index = {r.get("id", ""): r for r in rules_list}

    return results, rules_index


def _extract_cwe_from_tags(rule):
    """从 CodeQL rule 的 properties.tags 提取 CWE 标识.

    Args:
        rule: dict, SARIF rule 对象

    Returns:
        str: CWE 标识 (如 "CWE-78") 或空字符串

    Note:
        CodeQL 约定在 tags 中输出 "external/cwe/cwe-78" 等标签.
        SARIF 规范不强制要求 cwe 标签存在, 因此缺失时返回空字符串.
    """
    tags = rule.get("properties", {}).get("tags", [])
    if not tags or not isinstance(tags, list):
        return ""
    for tag in tags:
        # 匹配 "external/cwe/cwe-78" 或 "cwe-78" 等格式
        match = _CWE_TAG_RE.search(tag)
        if match:
            return f"CWE-{match.group(1)}"
    return ""


def convert_codeql_result(result, idx, rules_index):
    """转换单个 CodeQL SARIF result 到 ADD finding.

    Args:
        result: dict, 单个 SARIF result
        idx: int, 序号
        rules_index: dict, {ruleId: rule_dict} 预构建索引

    Returns:
        dict: ADD finding
    """
    rule_id = result.get("ruleId", f"unknown-{idx}")
    level = result.get("level", "note")
    locations = result.get("locations", [])
    message = result.get("message", {}).get("text", "")

    # 提取文件路径和行号
    file_path = ""
    line = 0
    if locations:
        phys = locations[0].get("physicalLocation", {})
        file_path = phys.get("artifactLocation", {}).get("uri", "")
        line = phys.get("region", {}).get("startLine", 0)

    # 从 rules_index 查找 rule (O(1) 查找)
    rule = rules_index.get(rule_id, {})
    cwe = _extract_cwe_from_tags(rule)

    finding = {
        "id": f"QL-{idx:04d}",  # 前缀 QL-
        "severity": LEVEL_MAP.get(level, "P2"),
        "claim": f"{rule_id}: {message} ({cwe}) — affects {file_path}:{line}",
        "evidence": {
            "file": file_path,
            "line_start": line,
            "cwe": cwe,
            "rule_id": rule_id,
            "source": "codeql",
        },
        "l4_eligible": True,
        "dimension": "security",
    }
    return finding


def main(argv=None):
    """读取 CodeQL SARIF, 输出 findings.json + ground_truth.json.

    Args:
        argv: 命令行参数列表 (None 时用 sys.argv)

    Returns:
        dict: {"findings": count}
    """
    parser = argparse.ArgumentParser(
        description="Convert CodeQL SARIF to ADD findings format")
    parser.add_argument("input", help="Path to CodeQL SARIF output")
    parser.add_argument("--output", required=True,
                        help="Output directory for findings.json + ground_truth.json")
    parser.add_argument("--repo-local-path", default="",
                        help="Local repo path for L4 verification (optional)")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    results, rules_index = parse_sarif(input_path)
    if not results:
        print(f"WARNING: no results in {input_path}", file=sys.stderr)

    # 转换所有 results
    findings = []
    ground_truth = []
    for idx, result in enumerate(results):
        finding = convert_codeql_result(result, idx, rules_index)
        if args.repo_local_path:
            finding["evidence"]["repo_local_path"] = args.repo_local_path
        # T5 集成: 增强 CWE 信息 (spec §2.4.2)
        if _CWE_ENRICH_AVAILABLE:
            finding = enrich_finding_with_cwe(finding)
        findings.append(finding)
        # 所有 CodeQL findings 标记为 real_bug_pending_verification (与 T3 一致)
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

    print(f"Converted {len(findings)} CodeQL results → {output_dir}")
    return {"findings": len(findings)}


if __name__ == "__main__":
    main()
