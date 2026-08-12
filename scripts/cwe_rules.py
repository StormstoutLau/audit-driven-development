#!/usr/bin/env python3
"""CWE Top 25 (2023) 规则映射表 + finding 增强.

v2.8 T5: CWE Top 25 (2023) 映射表 + enrich_finding_with_cwe + classify_cwe_severity.

源: https://cwe.mitre.org/top25/archive/2023/2023_top25_list.html
"""
import re

# CWE Top 25 (2023) — MITRE 官方排名
# ⚠️ 排名数据已对照 MITRE 官方修正 (spec H5 修正点)
CWE_TOP_25_2023 = {
    "CWE-787": {"name": "Out-of-bounds Write",               "rank": 1,  "category": "memory"},
    "CWE-79":  {"name": "XSS",                                "rank": 2,  "category": "injection"},
    "CWE-89":  {"name": "SQL Injection",                      "rank": 3,  "category": "injection"},
    "CWE-416": {"name": "Use-After-Free",                     "rank": 4,  "category": "memory"},
    "CWE-78":  {"name": "OS Command Injection",               "rank": 5,  "category": "injection"},
    "CWE-20":  {"name": "Input Validation",                   "rank": 6,  "category": "validation"},
    "CWE-125": {"name": "Out-of-bounds Read",                 "rank": 7,  "category": "memory"},
    "CWE-22":  {"name": "Path Traversal",                     "rank": 8,  "category": "fs"},
    "CWE-352": {"name": "CSRF",                               "rank": 9,  "category": "web"},
    "CWE-434": {"name": "Unrestricted Upload",                "rank": 10, "category": "fs"},
    "CWE-862": {"name": "Missing Authorization",              "rank": 11, "category": "auth"},
    "CWE-306": {"name": "Missing Authentication",             "rank": 12, "category": "auth"},
    "CWE-119": {"name": "Buffer Overflow",                    "rank": 13, "category": "memory"},
    "CWE-1059": {"name": "Insufficient Technical Controls",   "rank": 14, "category": "validation"},
    "CWE-276": {"name": "Incorrect Default Permissions",      "rank": 15, "category": "fs"},
    "CWE-918": {"name": "SSRF",                               "rank": 16, "category": "web"},
    "CWE-214": {"name": "Invocation of Process",              "rank": 17, "category": "injection"},
    "CWE-190": {"name": "Integer Overflow",                   "rank": 18, "category": "memory"},
    "CWE-502": {"name": "Deserialization",                    "rank": 19, "category": "injection"},
    "CWE-287": {"name": "Improper Authentication",            "rank": 20, "category": "auth"},
    "CWE-476": {"name": "NULL Pointer Dereference",           "rank": 21, "category": "memory"},
    "CWE-798": {"name": "Hard-coded Credentials",             "rank": 22, "category": "auth"},
    "CWE-807": {"name": "Reliance on Untrusted Input",        "rank": 23, "category": "validation"},
    "CWE-400": {"name": "Uncontrolled Resource Consumption",  "rank": 24, "category": "dos"},
    "CWE-269": {"name": "Improper Privilege Management",      "rank": 25, "category": "auth"},
}

# CWE category → 典型关键词映射 (用于 L3 验证增强)
CWE_KEYWORDS = {
    "memory": ["buffer", "overflow", "underflow", "pointer", "free", "alloc", "malloc"],
    "injection": ["inject", "sql", "command", "exec", "eval", "shell"],
    "validation": ["input", "validate", "sanitize", "check", "verify"],
    "fs": ["path", "traversal", "file", "upload", "directory"],
    "web": ["csrf", "ssrf", "request", "forgery", "origin"],
    "auth": ["auth", "login", "password", "credential", "session"],
    "dos": ["resource", "consume", "exhaust", "loop", "recursive"],
}

# 模块级预编译正则 (§0.4 性能规范)
_CWE_ID_RE = re.compile(r"CWE-\d+")


def enrich_finding_with_cwe(finding):
    """如果 finding 的 claim/evidence 含 CWE-XX, 添加 cwe_rank 和 cwe_category.

    Args:
        finding: dict, ADD finding

    Returns:
        dict: 增强后的 finding (原 finding 被 in-place 修改)

    Note:
        - 无 CWE 时 finding 不变 (不崩溃)
        - CWE 不在 Top 25 时仅添加 cwe_rank=None
    """
    evidence = finding.get("evidence", {})
    cwe_id = evidence.get("cwe", "")

    # 从 claim 中提取 CWE (如果 evidence.cwe 为空)
    if not cwe_id:
        claim = finding.get("claim", "")
        match = _CWE_ID_RE.search(claim)
        cwe_id = match.group(0) if match else ""

    if cwe_id and cwe_id in CWE_TOP_25_2023:
        info = CWE_TOP_25_2023[cwe_id]
        evidence["cwe_rank"] = info["rank"]
        evidence["cwe_category"] = info["category"]
        evidence["cwe_name"] = info["name"]
        if not evidence.get("cwe"):
            evidence["cwe"] = cwe_id
        finding["evidence"] = evidence

    return finding


def classify_cwe_severity(finding):
    """根据 CWE category 调整 severity.

    memory/injection 类 → P0 (高风险)
    其他类 → 保持原 severity

    Args:
        finding: dict, ADD finding (应先调用 enrich_finding_with_cwe)

    Returns:
        dict: 调整后的 finding (in-place 修改)
    """
    category = finding.get("evidence", {}).get("cwe_category", "")
    if category in ("memory", "injection"):
        finding["severity"] = "P0"
    return finding


def get_cwe_claim_keywords(cwe_id):
    """返回该 CWE 的典型关键词列表 (用于 L3 验证增强).

    Args:
        cwe_id: str, 如 "CWE-78"

    Returns:
        list: 关键词列表 (如 ["inject", "sql", "command", ...])
        若 CWE 不在 Top 25, 返回空列表
    """
    if cwe_id not in CWE_TOP_25_2023:
        return []
    category = CWE_TOP_25_2023[cwe_id]["category"]
    return CWE_KEYWORDS.get(category, [])


# §0.3 向后兼容硬规则第 4 点: 支持 python -m cwe_rules 调用
if __name__ == "__main__":
    # CLI 入口: 打印 CWE Top 25 列表 (用于调试和验证)
    print(f"CWE Top 25 (2023): {len(CWE_TOP_25_2023)} entries")
    for cwe_id, info in sorted(CWE_TOP_25_2023.items(), key=lambda x: x[1]["rank"]):
        print(f"  rank {info['rank']:2d}: {cwe_id} ({info['name']}) [{info['category']}]")
