"""幻觉样本自动合成器.

从真实 bug findings 自动合成 hallucination 样本, 扩展 benchmark 的幻觉覆盖.

三类变换 (确保 L1-L3 都能捕获):
  - line_offset: 将 line_start 偏移到文件范围外 → L2 line_out_of_range
  - file_replace: 将 evidence.file 替换为不存在路径 → L1 file_not_found
  - method_fabricate: 在 claim 中插入虚构方法名 → L3 no_keyword_match

合成流程:
  1. 读取真实 findings.json
  2. 对每条 finding 随机选 1 种 transform (三类各占约 1/3)
  3. 输出合成 findings.json + ground_truth.json (标注 hallucination_*)

用法:
  python scripts/synthesize_hallucinations.py <input_findings.json> --output <output_dir>
"""
import json
import random
import sys
import time
import argparse
from pathlib import Path


# ── 变换定义 ────────────────────────────────────────────────

TRANSFORMS = {
    "line_offset": {
        "description": "将 line_start 偏移 ±N 行 (N > 文件总行数 10%)",
        "ground_truth": "hallucination_line_out_of_range",
        "expected_l1_l2": "L2 line_out_of_range",
    },
    "file_replace": {
        "description": "将 evidence.file 替换为同 repo 内不存在路径",
        "ground_truth": "hallucination_file_not_found",
        "expected_l1_l2": "L1 file_not_found",
    },
    "method_fabricate": {
        "description": "在 claim 中插入 repo 内不存在的函数名",
        "ground_truth": "hallucination_method_not_in_source",
        "expected_l1_l2": "L3 no_keyword_match",
    },
}

# 虚构方法名池 (确保不在任何真实 repo 中)
_FAKE_METHODS = [
    "_phantom_validate_internal",
    "_nonexistent_dispatch_handler",
    "_fabricated_resolve_callback",
    "_ghost_process_pipeline",
    "_imaginary_sync_helper",
]

# 不存在文件名前缀
_FAKE_FILE_PREFIX = "nonexistent_"


# ── 变换函数 ────────────────────────────────────────────────

def transform_line_offset(finding, total_lines=None):
    """变换 1: 将 line_start 偏移到文件范围外.

    Args:
        finding: 原始 finding dict
        total_lines: 文件总行数 (用于计算偏移量, 默认 100)

    Returns:
        dict: 新 finding, line_start 被偏移到 total_lines + 10 以上
    """
    if total_lines is None:
        total_lines = 100
    original_line = finding.get("evidence", {}).get("line_start", 1)
    # 偏移到 total_lines + 10 以上 (确保超出范围)
    fake_line = total_lines + 10 + original_line
    new_finding = json.loads(json.dumps(finding))  # deep copy
    new_finding["evidence"]["line_start"] = fake_line
    new_finding["id"] = finding["id"].replace("R-", "HAL-") if finding["id"].startswith("R-") else f"HAL-{finding['id']}"
    return new_finding


def transform_file_replace(finding):
    """变换 2: 将 evidence.file 替换为不存在路径.

    Args:
        finding: 原始 finding dict

    Returns:
        dict: 新 finding, file 被替换为 nonexistent_*.py
    """
    original_file = finding.get("evidence", {}).get("file", "unknown.py")
    # 替换为 nonexistent_<原文件名>
    new_file = _FAKE_FILE_PREFIX + original_file.replace("/", "_").replace("\\", "_")
    new_finding = json.loads(json.dumps(finding))
    new_finding["evidence"]["file"] = new_file
    new_finding["id"] = finding["id"].replace("R-", "HAL-") if finding["id"].startswith("R-") else f"HAL-{finding['id']}"
    return new_finding


def transform_method_fabricate(finding):
    """变换 3: 在 claim 中插入虚构方法名.

    Args:
        finding: 原始 finding dict

    Returns:
        dict: 新 finding, claim 中插入了不存在的函数名
    """
    original_claim = finding.get("claim", "")
    fake_method = random.choice(_FAKE_METHODS)
    new_claim = f"{original_claim} — involves {fake_method} call"
    new_finding = json.loads(json.dumps(finding))
    new_finding["claim"] = new_claim
    new_finding["id"] = finding["id"].replace("R-", "HAL-") if finding["id"].startswith("R-") else f"HAL-{finding['id']}"
    return new_finding


# ── 合成主逻辑 ──────────────────────────────────────────────

_TRANSFORM_FUNCS = {
    "line_offset": transform_line_offset,
    "file_replace": transform_file_replace,
    "method_fabricate": transform_method_fabricate,
}


def synthesize_from_findings(findings, seed=None):
    """对 findings 列表逐条合成幻觉样本.

    Args:
        findings: 真实 findings 列表
        seed: 随机种子 (可复现)

    Returns:
        tuple (syn_findings, syn_ground_truth):
            - syn_findings: 合成的 findings 列表 (数量 = len(findings))
            - syn_ground_truth: 合成的 ground_truth 列表, 全部标注 hallucination_*
    """
    if seed is not None:
        random.seed(seed)

    transform_names = list(TRANSFORMS.keys())
    # 轮转分配, 确保三类各占约 1/3
    transform_schedule = [transform_names[i % len(transform_names)] for i in range(len(findings))]
    random.shuffle(transform_schedule)

    syn_findings = []
    syn_ground_truth = []

    for i, finding in enumerate(findings):
        transform_name = transform_schedule[i]
        transform_func = _TRANSFORM_FUNCS[transform_name]

        # line_offset 需要一个 total_lines 参数 (用固定 100 模拟)
        if transform_name == "line_offset":
            new_finding = transform_func(finding, total_lines=100)
        else:
            new_finding = transform_func(finding)

        syn_findings.append(new_finding)

        gt_info = TRANSFORMS[transform_name]
        syn_ground_truth.append({
            "id": new_finding["id"],
            "ground_truth": gt_info["ground_truth"],
            "expected_action": "removed",
            "transform": transform_name,
            "original_id": finding.get("id", ""),
        })

    return syn_findings, syn_ground_truth


# ── 主流程 ──────────────────────────────────────────────────

def main(argv=None):
    """读取真实 findings.json, 输出合成幻觉 findings.json + ground_truth.json.

    用法:
      python synthesize_hallucinations.py <input_findings.json> --output <output_dir> [--seed N]
    """
    parser = argparse.ArgumentParser(
        description="Synthesize hallucination samples from real bug findings")
    parser.add_argument("input", help="Path to real findings.json")
    parser.add_argument("--output", required=True,
                        help="Output directory for synthesized findings.json + ground_truth.json")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    findings = data.get("findings", []) if isinstance(data, dict) else data

    if not findings:
        print("WARNING: no findings found in input, output will be empty")

    syn_findings, syn_gt = synthesize_from_findings(findings, seed=args.seed)

    # 写出合成 findings.json
    syn_data = {
        "project": f"{data.get('project', 'unknown')}-hallucinations",
        "version": data.get("version", "1.0"),
        "audit_date": time.strftime("%Y-%m-%d"),
        "audit_mode": "dataset-integration layer-2 hallucination-synthesis",
        "description": "Auto-synthesized hallucination samples from real bug findings",
        "source_findings": str(input_path),
        "seed": args.seed,
        "findings": syn_findings,
    }
    (out_dir / "findings.json").write_text(
        json.dumps(syn_data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # 写出 ground_truth.json
    (out_dir / "ground_truth.json").write_text(
        json.dumps(syn_gt, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Hallucination synthesis complete:")
    print(f"  Input: {input_path}")
    print(f"  Output dir: {out_dir}")
    print(f"  Source findings: {len(findings)}")
    print(f"  Synthesized hallucinations: {len(syn_findings)}")
    print(f"  Seed: {args.seed}")

    # 变换分布统计
    transform_counts = {}
    for gt in syn_gt:
        t = gt.get("transform", "unknown")
        transform_counts[t] = transform_counts.get(t, 0) + 1
    print(f"  Transform distribution: {transform_counts}")

    return {
        "synthesized": len(syn_findings),
        "transforms": transform_counts,
    }


if __name__ == "__main__":
    main()
