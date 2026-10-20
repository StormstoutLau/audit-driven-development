"""Phase 3.5 Finding Verification — mandatory source-code-level verification for P0 findings.

Prevents hallucinated findings from entering the fix baseline.
Every P0 finding MUST pass source verification before proceeding to Phase 4.

Usage: python scripts/verify_findings.py --findings <findings.json> --repo <path> [--output <verified.json>]

Verification Levels:
  L1: File existence check
  L2: Line number validity
  L3: Keyword/pattern match in source context (±20 lines)
  L4: Structural claim verification (code pattern matching)

Actions:
  verified   (L4) → Keep severity, proceed to fix baseline
  partial    (L3) → Downgrade P0→P1, flag for human review
  unverified (L1/L2) → Remove from fix baseline, log as hallucination
"""

import argparse, json, os, re, sys
from pathlib import Path
from _script_utils import run_script

# ── Claim Type Classification ──

MISSING_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bmissing\b", r"\black(?:s|ing)\b", r"\babsent\b", r"\bwithout\b",
        r"\bno\s+(?:error\s+)?handling\b", r"\bnot\s+(?:handled|checked|validated|caught)\b",
        r"\bunhandled\b", r"\bnever\s+(?:checked|validated|caught)\b",
        r"\bdoesn'?t\s+(?:handle|check|validate|catch)\b",
        r"\bdoes\s+not\s+(?:handle|check|validate|catch)\b",
    ]
]

WRONG_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bwrong\b", r"\bincorrect\b", r"\binvalid\b", r"\bmisconfigured\b",
        r"\bmismatch\b", r"\binconsistent\b", r"\bincorrectly\b",
        r"\bshould\s+be\b", r"\bexpected\b.*\bbut\b",
    ]
]

VIOLATES_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bviolates?\b", r"\bbreaks?\b", r"\bconflicts?\s+with\b",
        r"\bagainst\s+(?:spec|ADR|contract|invariant)\b",
        r"\bcircular\s+(?:dep|dependency|import)\b",
    ]
]

DEAD_CODE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bdead\s+code\b", r"\bunreachable\b", r"\bunused\b",
        r"\bnever\s+(?:called|used|executed|reached)\b",
        r"\bimported\s+but\s+(?:never|not)\s+used\b",
        r"\bimport\b.*\b(?:not|never)\s+used\b",
    ]
]

IMPORT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bcircular\s+(?:dep|dependency|import)\b",
        r"\bimport\s+cycle\b",
        r"\bmutual\s+import\b",
        r"\bdependency\s+(?:cycle|issue|problem|violation)\b",
        r"\bdepends\s+on\s+(?:each\s+other|circular|mutual)\b",
    ]
]


# ── v3.0 T9' Phase 1: Taint claim identification (D-T9'-1 / ADR-027) ──

# 通道 A（结构化）: CWE 集合。定稿依据见 ADR-027（8/8 项均有上游 @kind path-problem 证据）。
# ⚠️ 限定: "CWE ∈ 集合 ⇒ taint 断言" 仅在该 CWE 由 taint-mode / path-problem 规则报出时成立;
#           对数据集标签 CWE（bigvul/cvefixes）不成立 —— 见设计 spec §7 R9。
TAINT_CWE_SET = frozenset({
    "CWE-78", "CWE-79", "CWE-89", "CWE-94",
    "CWE-22", "CWE-502", "CWE-918", "CWE-611",
})

# 通道 B（文本，兜底）: 预编译（§0.4 禁止函数内 re.compile）
TAINT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\btaint",
        r"\b(?:untrusted|attacker[- ]controlled|user[- ]controlled|user[- ]supplied)\b",
        r"\b(?:unsanitized|not\s+sanitized|without\s+sanitiz)",
        r"\bsource\s*(?:->|→|to)\s*sink\b",
        r"\bdata\s*flow",
        r"\binjection\b",
        r"\bflows?\s+from\b.*\bto\b",
        r"\bsanitiz",
    ]
]

# 通道 A 的 CWE 提取（E-6 / AC-2）: 从 evidence.cwe 提取 CWE 标识
_CWE_ID_RE = re.compile(r"CWE-(\d+)", re.IGNORECASE)

_TAINT_DISABLE_ENV = "ADD_TAINT_DISABLE"
_TAINT_DISPROOF_ENV = "ADD_TAINT_DISPROOF"


def _taint_enabled():
    """v3.0: taint 识别与分派的总开关 (kill switch, 对齐 joern_cpg.is_available 风格).

    ADD_TAINT_DISABLE=1 时返回 False ⇒ 全链路关闭 ⇒ 全量裁决与 v2.8 逐位一致 (AC-9)。
    """
    return os.environ.get(_TAINT_DISABLE_ENV) != "1"


# v3.0 T19 (D-T19-1): contract 文本通道 —— 模块级预编译（禁函数内 re）
# 实证收紧 (X-2): 禁用裸 `layers?` 与裸 `contract` —— F-4 实测二者在 882 条真实语料上
# 仅命中标识符子串（如 msPostGISLayerSetTimeFilter 的 "Layer"），属纯噪声。
CONTRACT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\blayer violation\b",
        r"\blayering\b",
        r"\bcross-module dependency\b",
        r"\barchitectural boundary\b",
        r"层序",
        r"分层契约",
        r"反向依赖",
        r"禁止依赖",
        r"跨模块依赖",
    ]
]

_CONTRACT_DISABLE_ENV = "ADD_CONTRACT_DISABLE"


def _contract_enabled():
    """v3.0 T19: contract 识别与分派的总开关 (kill switch, 对齐 _taint_enabled 风格).

    ADD_CONTRACT_DISABLE=1 时返回 False ⇒ 全链路关闭 ⇒ 与 v3.0-T9' 现状逐位一致 (AC-1)。
    """
    return os.environ.get(_CONTRACT_DISABLE_ENV) != "1"


def _resolve_taint_disproof(cli_value=None):
    """v3.0: 解析 taint 证伪动作. 优先级: CLI > env > 默认.

    Returns:
        str: "downgrade" (默认, D-T9'-4) | "remove"
    """
    if cli_value in ("downgrade", "remove"):
        return cli_value
    env = os.environ.get(_TAINT_DISPROOF_ENV, "").strip().lower()
    return "remove" if env == "remove" else "downgrade"


def _extract_taint_cwe(evidence):
    """v3.0: 从**结构化字段** evidence["cwe"] 提取用于通道 A 判定的 CWE 标识.

    G-3 (Step 6 审计发现, v1.1 修正): **不做 claim 文本回退**。理由:
      (a) 设计 D-T9'-1 / AC-2 明确通道 A 只消费 `evidence.cwe` (结构化通道);
      (b) 文本回退会使通道 A 与通道 B 语义重叠, 破坏"结构化 vs 文本"的双通道设计;
      (c) 会把**数据集标签 CWE** (R9, bigvul/cvefixes 语料) 引入结构化通道, 污染其判定质量。

    Args:
        evidence: dict|None finding 的 evidence 字段。

    Returns:
        str: 规范化后的 CWE 标识 (如 "CWE-78"), 或 "" (无结构化 CWE)。
    """
    if not isinstance(evidence, dict):
        return ""
    cwe = evidence.get("cwe", "")
    if not cwe:
        return ""
    m = _CWE_ID_RE.search(str(cwe))
    return f"CWE-{m.group(1)}" if m else ""


# ── v2.7.1: Multi-language Support ──

# Joern frontend mapping: internal language name → Joern --language flag
_JOERN_LANGUAGE_MAP = {
    "python": "pythonsrc",
    "java": "javasrc2cpg",
    "cpp": "c2cpg",
}


def _detect_language(file_path):
    """v2.7.1: 根据文件扩展名检测语言.

    Args:
        file_path: str 文件路径 (相对或绝对).

    Returns:
        str: "python" | "java" | "cpp" | "unknown"
    """
    if not file_path:
        return "unknown"
    lower = file_path.lower()
    if lower.endswith(".py"):
        return "python"
    if lower.endswith(".java"):
        return "java"
    if lower.endswith((".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hh", ".hxx")):
        return "cpp"
    return "unknown"


def classify_claim(claim, evidence=None, category=None):
    """Classify the finding claim into a structural verification type.

    v2.7.3 断点③修复: 加载 rule_suggestions.json 中的反例规则,
    匹配到反例规则的 claim 会被标记为 "hallucination_pattern", 供调用方降级 severity.
    匹配逻辑: rule 的 reason 字段 (截断到 60 字符) 出现在 claim 中 → 匹配.

    v3.0 T9' Phase 1 (D-T9'-1):
        evidence 参数启用结构化通道 A（analysis_kind / CWE 集合）。
        evidence=None（默认）时通道 A 不激活 —— 但文本通道 B 仍生效，
        故输出不再是 v2.8 的逐位超集相等；v2.8 逐位一致性由 kill switch 承载。

    Args:
        claim: str claim 文本。
        evidence: dict|None finding 的 evidence 字段（可选，向后兼容）。
        category: str|None finding 的**顶层** category 字段（可选，v3.0 T19 新增，
            向后兼容；默认 None 时行为与 v3.0-T9' 完全一致）。

    Returns:
        list[str]: 类型标签列表，非空时不含 "generic"。
    """
    types = []
    if any(p.search(claim) for p in MISSING_PATTERNS):
        types.append("missing")
    if any(p.search(claim) for p in WRONG_PATTERNS):
        types.append("wrong")
    if any(p.search(claim) for p in VIOLATES_PATTERNS):
        types.append("violates")
    if any(p.search(claim) for p in DEAD_CODE_PATTERNS):
        types.append("dead_code")
    if any(p.search(claim) for p in IMPORT_PATTERNS):
        types.append("import_related")

    # v3.0: 通道 A（结构化，优先）—— 仅在 taint 总开关开启时激活
    if _taint_enabled():
        structured_hit = False
        if isinstance(evidence, dict) and evidence.get("analysis_kind") == "taint":
            structured_hit = True
        elif _extract_taint_cwe(evidence) in TAINT_CWE_SET:
            structured_hit = True
        # 通道 B（文本，兜底）—— 不依赖 evidence
        if structured_hit or any(p.search(claim) for p in TAINT_PATTERNS):
            types.append("taint")

    # v3.0 T19 (D-T19-1): 双通道 contract 识别 —— 仅在总开关开启时激活
    # 通道 A 的两条承载路径: category 经新增参数传入 / analysis_kind 经 evidence 传入
    if _contract_enabled():
        contract_hit = (category == "contract")
        if isinstance(evidence, dict) and evidence.get("analysis_kind") == "contract":
            contract_hit = True
        if contract_hit or any(p.search(claim) for p in CONTRACT_PATTERNS):
            types.append("contract_related")

    # v2.7.3 断点③: 检查反例规则 — 匹配到 → 添加 "hallucination_pattern" 标记
    # 调用方 (verify_single_finding) 可据此降级 severity 或加强审查
    learned_rules = _load_learned_rules()
    for rule in learned_rules:
        reason = rule.get("reason", "")
        if reason and reason[:60] in claim:
            if "hallucination_pattern" not in types:
                types.append("hallucination_pattern")
            break  # 匹配到一条即可, 避免重复标记

    return types if types else ["generic"]


# v2.7.3 断点③: 反例规则加载 (带模块级缓存)
_LEARNED_RULES_CACHE = None


def _load_learned_rules(rules_path="docs/audit/rule_suggestions.json"):
    """v2.7.3: 加载 rule_suggestions.json 中的反例规则 (带缓存).

    Args:
        rules_path: rule_suggestions.json 路径

    Returns:
        list[dict]: 反例规则列表, 每项含 reason/suggestion/severity 等字段.
        文件不存在时返回空列表.
    """
    global _LEARNED_RULES_CACHE
    if _LEARNED_RULES_CACHE is not None:
        return _LEARNED_RULES_CACHE
    path = Path(rules_path)
    if not path.exists():
        _LEARNED_RULES_CACHE = []
        return _LEARNED_RULES_CACHE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _LEARNED_RULES_CACHE = data.get("suggestions", [])
    except (json.JSONDecodeError, ValueError, OSError):
        _LEARNED_RULES_CACHE = []
    return _LEARNED_RULES_CACHE


# ── Keyword Extraction (shared with verify_lines.py) ──


def _threshold_to_min_keywords(threshold):
    """v2.8: 将 RL-adjusted threshold 映射到 L3 最小 keyword 匹配数.

    Args:
        threshold: float ∈ [0.55, 0.85] 或 None

    Returns:
        int: min_keywords (1 或 2)

    Mapping:
        None          → 1 (默认, 向后兼容)
        [0.55, 0.75)  → 1 (宽松, improving trend)
        [0.75, 0.85]  → 2 (严格, declining trend)
    """
    if threshold is None:
        return 1
    if threshold >= 0.75:
        return 2
    return 1


def extract_keywords(claim):
    """Extract search keywords from a finding claim."""
    tokens = re.findall(r'[A-Za-z_]\w+|[^\s\w]{2,}', claim)
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                 "to", "for", "of", "and", "or", "not", "with", "from", "by", "as",
                 "be", "has", "have", "it", "its", "that", "this", "should", "must",
                 "does", "but", "when", "if", "then", "else", "no", "yes", "all",
                 "any", "some", "each", "every", "both", "few", "many", "more",
                 "most", "other", "such", "only", "own", "same", "so", "than",
                 "too", "very", "just", "can", "will", "now", "up", "out", "also"}
    return [t for t in tokens if t.lower() not in stopwords and len(t) > 2][:5]


# ── Four-Level Verification ──

def verify_l1_l2(repo_root, file_path, line_num):
    """Level 1+2: File existence + line number validity."""
    abs_path = Path(repo_root) / file_path
    if not abs_path.exists():
        return {"level": 0, "confirmed": False, "reason": "file_not_found",
                "file_path": file_path}

    lines = abs_path.read_text(encoding="utf-8", errors="replace").split("\n")
    if line_num < 1 or line_num > len(lines):
        return {"level": 1, "confirmed": False,
                "reason": f"line {line_num} out of range (1-{len(lines)})",
                "file_path": file_path, "total_lines": len(lines)}

    return {"level": 2, "confirmed": True, "file_path": file_path,
            "total_lines": len(lines), "lines": lines, "line_num": line_num}


def verify_l3(lines, line_num, keywords, min_keywords=1):
    """Level 3: Keyword/pattern match in source context (±20 lines).

    v2.8: 新增 min_keywords 参数, 控制 confirmed 所需的最小匹配 keyword 数.
        min_keywords=1 (默认): 至少 1 个 keyword 匹配 (v2.7 行为)
        min_keywords=2: 至少 2 个不同 keyword 匹配 (严格模式)

    Args:
        lines: list of source code lines (from L2).
        line_num: 1-indexed line number to verify.
        keywords: list of keyword strings to search.
        min_keywords: minimum number of distinct keywords that must match.

    Returns:
        dict. confirmed=True 时含 matched_keywords (list) + matched_keyword (单数兼容字段).
    """
    if not keywords:
        return {"level": 2, "confirmed": False, "reason": "no_keywords_to_match"}

    matched_keywords = []
    matched_lines = []

    # 收集 target_line 上的所有匹配 (不是找到第一个就返回)
    target_lower = lines[line_num - 1].lower()
    for kw in keywords:
        if kw.lower() in target_lower and kw not in matched_keywords:
            matched_keywords.append(kw)
            matched_lines.append(line_num)

    # 若 target_line 已满足 min_keywords, 提前返回 (短路优化)
    if len(matched_keywords) >= min_keywords:
        return {"level": 3, "confirmed": True,
                "matched_keywords": matched_keywords[:min_keywords],
                "matched_lines": matched_lines[:min_keywords],
                # ⚠️ 兼容字段 (v2.7 下游读取 matched_keyword/matched_line 单数)
                "matched_keyword": matched_keywords[0],
                "matched_line": matched_lines[0]}

    # 邻近窗口 ±20 行扫描
    for offset in range(1, 21):
        for direction in (-1, 1):
            check_line = line_num + direction * offset
            if 1 <= check_line <= len(lines):
                check_lower = lines[check_line - 1].lower()
                for kw in keywords:
                    if kw.lower() in check_lower and kw not in matched_keywords:
                        matched_keywords.append(kw)
                        matched_lines.append(check_line)
                        # 满足 min_keywords 时立即返回 (短路)
                        if len(matched_keywords) >= min_keywords:
                            return {"level": 3, "confirmed": True,
                                    "matched_keywords": matched_keywords,
                                    "matched_lines": matched_lines,
                                    "matched_keyword": matched_keywords[0],
                                    "matched_line": matched_lines[0]}

    # 未达到 min_keywords
    if matched_keywords:  # 有匹配但不足
        return {"level": 3, "confirmed": False,
                "reason": f"only {len(matched_keywords)} keywords matched, need {min_keywords}",
                "matched_keywords": matched_keywords,
                "matched_lines": matched_lines}
    return {"level": 2, "confirmed": False,
            "reason": "no keyword match within ±20 lines",
            "keywords_searched": keywords}


def _get_function_context(lines, line_num):
    """Phase 3: 扩展 context 到 enclosing function 全范围.

    解决原 ±25 行窗口的局限: 如果 claim 在函数内, 但 try/except 在 30 行外,
    ±25 窗口看不到 → 假阳性. 全函数窗口能覆盖整个函数体.

    Returns:
        str: context text for L4 verification.
    """
    import ast
    try:
        source = "\n".join(lines)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if (node.lineno <= line_num and
                    hasattr(node, "end_lineno") and
                    node.end_lineno and node.end_lineno >= line_num):
                    start = max(0, node.lineno - 1)
                    end = min(len(lines), node.end_lineno)
                    return "\n".join(lines[start:end])
    except Exception:
        pass
    # Fallback: ±50 行 (原 ±25 的 2 倍)
    context_start = max(0, line_num - 50)
    context_end = min(len(lines), line_num + 50)
    return "\n".join(lines[context_start:context_end])


def verify_l4_structural(lines, line_num, claim, claim_types,
                         repo_root=None, file_path=None, language="python",
                         evidence=None, taint_disproof=None):
    """Level 4: Structural claim verification with Tier 2 fallback.

    Tier 2 (ast CFG) for dead_code/import_related — higher accuracy (~90%).
    Tier 3 (regex) for missing/wrong/violates/generic + Tier 2 fallback (~42%).

    P0-2 unified schema: all Tier results include "verified" field (True|False|None).
    Tier 3 (regex) originally returns "confirmed", mapped to "verified" for consistency.
    "verified=None" means this Tier cannot decide → trigger fallback to next Tier.

    v2.7.1: language 参数控制 Tier 1 Joern 前端 (pythonsrc/javasrc2cpg/c2cpg)
    和 Tier 2 ast CFG 是否启用 (仅 python 启用, java/cpp 跳过 Tier 2).
    """
    # Phase 3: 扩展 context 到 enclosing function 全范围 (解决 ±25 窗口局限).
    # 如果 line 在函数内, 用函数全范围; 否则回退到 ±50 行 (原 ±25 的 2 倍).
    context_text = _get_function_context(lines, line_num)

    # v2.7.1: 将内部 language 名映射为 Joern --language flag
    joern_lang = _JOERN_LANGUAGE_MAP.get(language, "pythonsrc")

    checks = {}

    if "dead_code" in claim_types:
        result = None
        # Tier 1: Joern CPG (highest accuracy ~95%, optional dependency)
        # P1-5: joern_cpg never raises in normal operation, but V9 test hook
        # (JOERN_FORCE_RAISE=1) simulates runtime failure -> must catch & degrade
        # v2.7.1: 传递 language 给 joern_cpg, 选择对应前端
        if repo_root and file_path:
            try:
                import joern_cpg
                result = joern_cpg.verify_dead_code(repo_root, file_path, line_num,
                                                     language=language)
            except Exception:
                result = None
        # Tier 2: Python ast CFG (higher accuracy ~90%, zero deps)
        # v2.7.1: Tier 2 仅支持 Python; Java/C++ 跳过 Tier 2 直接降级到 Tier 3
        # Phase 8: Joern dead_code is method-level (no callers); claims are
        #   usually statement-level (unreachable after return). Method-level
        #   dead (Joern True) does NOT pinpoint the specific statement, and
        #   method reachable (Joern False) does NOT imply statement reachable.
        #   Strategy: always run Tier 2 for double-check (Python only).
        #     - Joern True + Tier 2 True → keep Joern (tier=1, both agree)
        #     - Joern True + Tier 2 False → use Tier 2 (statement-level precise)
        #     - Joern False/None + Tier 2 any → use Tier 2
        #     - Joern True + Tier 2 None → keep Joern (Tier 2 cannot decide)
        if language == "python" and repo_root and file_path:
            try:
                import ast_cfg
                result_t2 = ast_cfg.verify_dead_code(repo_root, file_path, line_num)
                if result_t2 and result_t2.get("verified") is not None:
                    # Tier 2 has a definitive answer
                    joern_true = (result and result.get("verified") is True)
                    tier2_true = (result_t2.get("verified") is True)
                    if joern_true and tier2_true:
                        pass  # both agree True → keep Joern (tier=1)
                    else:
                        result = result_t2  # disagreement or Joern non-True → Tier 2 wins
                # else: Tier 2 None → keep Joern result (if any)
            except Exception:
                pass  # keep Joern result (if any)
        # Tier 3: regex fallback (~42%, always available)
        if not result or result.get("verified") is None:
            regex_result = _verify_dead_code(context_text, lines, line_num)
            regex_result["tier"] = 3
            regex_result["verified"] = regex_result["confirmed"]  # P0-2: field alignment
            checks["dead_code"] = regex_result
        else:
            checks["dead_code"] = result

    if "import_related" in claim_types:
        result = None
        # Tier 1: Joern CPG (highest accuracy, optional)
        # v2.7.1: 传递 language 给 joern_cpg
        if repo_root:
            try:
                import joern_cpg
                result = joern_cpg.verify_imports(repo_root, claim, language=language)
            except Exception:
                result = None
        # Tier 2: Python ast import graph
        # v2.7.1: Tier 2 仅支持 Python; Java/C++ 跳过
        # Phase 8: Joern verified=False → degrade to Tier 2 (conservative).
        #   Joern Python support (pysrc2cpg) may be incomplete; Tier 2 uses
        #   Python stdlib ast for reliable import graph construction.
        #   Only verified=True (confirmed cycle) prevents degradation.
        if language == "python" and (not result or result.get("verified") is not True) and repo_root:
            try:
                import ast_cfg
                result_t2 = ast_cfg.verify_imports(repo_root, claim)
                if result_t2 and result_t2.get("verified") is not None:
                    result = result_t2
            except Exception:
                pass
        # Tier 3: regex fallback
        if not result or result.get("verified") is None:
            regex_result = _verify_import(claim, context_text, lines, line_num)
            regex_result["tier"] = 3
            regex_result["verified"] = regex_result["confirmed"]  # P0-2: field alignment
            checks["import_related"] = regex_result
        else:
            checks["import_related"] = result

    # v3.0 T19: contract 分支 (Tier 2, 纯 stdlib) — 无裁决 => 不落 check (D-T19-4 / AC-4)
    if "contract_related" in claim_types and _contract_enabled():
        import contract_graph
        contract_check = contract_graph.verify_contract(
            repo_root, claim, evidence=evidence, language=language)
        if contract_check is not None:
            checks["contract"] = contract_check

    # v3.0 T9' Phase 1: taint 分支 (L5 语义层, ADR-026) — 无裁决 => 不落 check (D-T9'-5)
    if "taint" in claim_types and _taint_enabled():
        taint_check = _verify_l5_taint(claim, claim_types, repo_root, file_path,
                                       line_num, language, evidence,
                                       context_text, lines, taint_disproof)
        if taint_check is not None:
            checks["taint"] = taint_check

    # missing/wrong/violates/generic: Tier 3 regex only (no structural improvement)
    if "missing" in claim_types:
        checks["missing"] = _verify_missing(claim, context_text, lines, line_num)
        checks["missing"]["tier"] = 3
        checks["missing"]["verified"] = checks["missing"]["confirmed"]  # P0-2
    if "wrong" in claim_types:
        checks["wrong"] = _verify_wrong(claim, context_text)
        checks["wrong"]["tier"] = 3
        checks["wrong"]["verified"] = checks["wrong"]["confirmed"]  # P0-2
    if "violates" in claim_types:
        checks["violates"] = _verify_violates(claim, context_text)
        checks["violates"]["tier"] = 3
        checks["violates"]["verified"] = checks["violates"]["confirmed"]  # P0-2
    # v3.0 (E-5) / v3.0 T19: taint 或 contract 已产出裁决 => 抑制 generic（原意图）;
    #            二者无裁决 => 仍回落 generic（恢复 v2.8 行为, 忠实实现 D-T9'-5 / D-T19-4）
    if not checks and ("generic" in claim_types or "taint" in claim_types
                       or "contract_related" in claim_types):
        checks["generic"] = _verify_generic(claim, context_text)
        checks["generic"]["tier"] = 3
        checks["generic"]["verified"] = checks["generic"]["confirmed"]  # P0-2

    all_checks = [v for v in checks.values() if isinstance(v, dict)]
    if not all_checks:
        return {"level": 3, "confirmed": False, "verified": False,  # P0-2: dual field
                "reason": "no_structural_checks_applicable",
                "claim_types": claim_types}

    # E2E-2b fix: 准确率优先聚合 — 结构化检查 (Tier 1/2) 优先于 Tier 3 正则
    # 如果任一结构化检查 (tier <= 2) verified=True,则整体 verified=True,
    # 忽略 Tier 3 正则的 verified=False (正则无法理解代码结构,易误判)
    # 仅当所有结构化检查都 verified=False/None 时,才采用 Tier 3 结果
    structural_checks = [c for c in all_checks if c.get("tier", 3) <= 2]
    regex_checks = [c for c in all_checks if c.get("tier", 3) == 3]

    if structural_checks:
        # 有结构化检查: 任一 True -> 整体 True (准确率优先)
        any_structural_true = any(
            c.get("verified", c.get("confirmed", False)) for c in structural_checks
        )
        if any_structural_true:
            verified = True
        else:
            # 结构化检查全部 False/None — 如果有 None (无法判定),看 Tier 3
            any_structural_none = any(
                c.get("verified") is None for c in structural_checks
            )
            if any_structural_none and regex_checks:
                verified = any(c.get("verified", c.get("confirmed", False))
                               for c in regex_checks)
            else:
                verified = False
    else:
        # 无结构化检查 (全是 Tier 3): 全部 True 才 True
        verified = all(c.get("verified", c.get("confirmed", False)) for c in all_checks)

    return {"level": 4 if verified else 3, "confirmed": verified, "verified": verified,
            "claim_types": claim_types, "checks": checks,
            "reason": "all structural checks passed" if verified else "structural verification failed"}


def _verify_missing(claim, context_text, all_lines, line_num):
    """Verify a 'missing X' claim: extract what is claimed missing and check it's absent."""
    # Extract the thing claimed missing (e.g., "error handling", "null check", "try/except")
    missing_patterns = [
        r"(?:missing|lacks?|absent|without|no)\s+(.+?)(?:\s*[-–—]\s*|\s*\(|\s*\.\s|$)",
        r"(?:not|never|doesn'?t|does\s+not)\s+(?:handled?|checked|validated|caught)\s+(.+?)(?:\s*[-–—]|\s*\(|\s*\.\s|$)",
        r"(?:not|never|doesn'?t|does\s+not)\s+(handle|check|validate|catch)\s+(.+?)(?:\s*[-–—]|\s*\(|\s*\.\s|$)",
    ]
    missing_thing = None
    for pattern in missing_patterns:
        if m := re.search(pattern, claim, re.IGNORECASE):
            missing_thing = m.group(1).strip().rstrip(".,;:")
            break

    if not missing_thing:
        # Try extracting key nouns from the claim
        nouns = re.findall(r'\b(error\s+handling|null\s+check|try\s*/\s*except|'
                          r'validation|retry|fallback|timeout|exception|'
                          r'input\s+validation|type\s+check|boundary\s+check)\b',
                          claim, re.IGNORECASE)
        if nouns:
            missing_thing = nouns[0]

    if missing_thing:
        # Check if the missing thing IS present in the context
        pattern_present = _check_pattern_present(missing_thing, context_text)
        return {"confirmed": not pattern_present,
                "missing_thing": missing_thing,
                "found_in_context": pattern_present}

    return {"confirmed": False, "reason": "could_not_extract_missing_thing",
            "note": "unable to determine what is claimed missing — downgraded to P1 for human review"}


def _check_pattern_present(thing, context_text):
    """Check if a named pattern is present in the code context."""
    context_lower = context_text.lower()
    thing_lower = thing.lower()

    # Direct substring match
    if thing_lower in context_lower:
        return True

    # Pattern-specific checks
    if "error handling" in thing_lower or "try" in thing_lower:
        if re.search(r'\btry\s*:', context_text):
            return True
    if "except" in thing_lower:
        if re.search(r'\bexcept\b', context_text):
            return True
    if "null" in thing_lower or "none" in thing_lower:
        if re.search(r'\b(?:is\s+None|is\s+not\s+None|==\s*None|!=\s*None)\b', context_text):
            return True
    if "validation" in thing_lower or "validate" in thing_lower:
        if re.search(r'\b(?:validate|assert|check|verify)\b', context_text, re.IGNORECASE):
            return True
    if "timeout" in thing_lower:
        if re.search(r'\btimeout\b', context_text, re.IGNORECASE):
            return True
    if "retry" in thing_lower:
        if re.search(r'\bretry\b', context_text, re.IGNORECASE):
            return True

    return False


def _verify_wrong(claim, context_text):
    """Verify a 'wrong X' claim: check the wrong pattern is actually present."""
    # Extract what is claimed wrong
    wrong_patterns = [
        r"(?:wrong|incorrect|invalid|misconfigured)\s+(.+?)(?:\s*[-–—]|\s*\(|\s*\.\s|$)",
        r"(?:should\s+be|expected)\s+(.+?)(?:\s+but\b|\s*,\s*but\b|\s*[-–—]|\s*\.\s|$)",
    ]
    wrong_thing = None
    for pattern in wrong_patterns:
        if m := re.search(pattern, claim, re.IGNORECASE):
            wrong_thing = m.group(1).strip().rstrip(".,;:")
            break

    if wrong_thing:
        # For "wrong X" claims, we verify the wrong thing IS present in the code
        keywords = extract_keywords(wrong_thing)
        context_lower = context_text.lower()
        found = any(kw.lower() in context_lower for kw in keywords)
        return {"confirmed": found,
                "wrong_thing": wrong_thing,
                "found_in_context": found}

    return {"confirmed": False, "reason": "could_not_extract_wrong_thing"}


def _verify_violates(claim, context_text):
    """Verify a 'violates X' claim: check the violation pattern is actually present."""
    # Extract what is violated
    violate_patterns = [
        r"(?:violates?|breaks?|conflicts?\s+with)\s+(.+?)(?:\s*[-–—]|\s*\(|\s*\.\s|$)",
        r"against\s+(?:spec|ADR|contract|invariant)\s+(.+?)(?:\s*[-–—]|\s*\(|\s*\.\s|$)",
    ]
    violation_thing = None
    for pattern in violate_patterns:
        if m := re.search(pattern, claim, re.IGNORECASE):
            violation_thing = m.group(1).strip().rstrip(".,;:")
            break

    if violation_thing:
        keywords = extract_keywords(violation_thing)
        context_lower = context_text.lower()
        found = any(kw.lower() in context_lower for kw in keywords)
        return {"confirmed": found,
                "violation_thing": violation_thing,
                "evidence_in_context": found}

    return {"confirmed": False, "reason": "could_not_extract_violation_thing"}


def _verify_dead_code(context_text, all_lines, line_num):
    """Verify dead code claim: check if the code is in an unreachable position."""
    # Check if the code is after return/raise/exit
    has_return_before = False
    for i in range(line_num - 2, -1, -1):
        stripped = all_lines[i].strip()
        if stripped and not stripped.startswith("#"):
            if re.match(r'^\s*(?:return|raise|sys\.exit|exit)\b', stripped):
                has_return_before = True
            break

    return {"confirmed": has_return_before,
            "has_return_before": has_return_before,
            "note": "dead code if code follows return/raise/exit"}


def _verify_import(claim, context_text, all_lines, line_num):
    """Verify import-related claim: check if the import statement exists."""
    # Check if the claimed import is in the file
    import_names = re.findall(r'(?:import|from)\s+(\S+)', claim)
    if import_names:
        found_imports = []
        for name in import_names:
            pattern = re.compile(r'(?:import|from)\s+' + re.escape(name) + r'\b')
            found = bool(pattern.search(context_text))
            found_imports.append({"name": name, "found": found})

        return {"confirmed": any(f["found"] for f in found_imports),
                "imports_checked": found_imports}

    return {"confirmed": True, "reason": "could_not_extract_import_name"}


def _verify_generic(claim, context_text):
    """Generic verification: check if claim keywords exist in source context."""
    keywords = extract_keywords(claim)
    context_lower = context_text.lower()
    matched = [kw for kw in keywords if kw.lower() in context_lower]
    return {"confirmed": len(matched) >= 1,
            "keywords_matched": matched,
            "total_keywords": len(keywords)}


# ── v3.0 T9' Phase 1: taint Tier 3 (regex) + L5 dispatch (ADR-026) ──

# 预编译（§0.4）: 从 claim 中提取"点分调用名"，如 subprocess.call / os.system / cursor.execute
_TAINT_SINK_RE = re.compile(r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\(")

# 已知 sink 家族（用于从 claim 中优先识别，MVP 保守集合）
TAINT_SINK_HINTS = (
    "system", "popen", "call", "check_call", "check_output", "run", "Popen",
    "eval", "exec", "execfile", "compile",
    "execute", "executemany", "raw",
    "loads", "load", "load_all", "Unpickler", "read", "parse", "fromstring",
    "get", "post", "request", "urlopen", "send",
)


def _verify_taint_regex(claim, context_text, all_lines, line_num):
    """Tier 3 (regex): 验证 claim 断言的 sink API 是否存在于源码上下文.

    E-3 语义限定:
      仅当 sink 名由 **claim** 派生时, 才产出 True/False。
      若 claim 中无法派生 sink 名 => 返回 None (不写 check, D-T9'-5)。
      ⚠️ 不从"目标行"派生 sink 名: 目标行派生必然命中自身 => 恒 True => 自证陷阱。

    G-4 (Step 6 审计发现): all_lines / line_num 必须**被实际使用** ——
      否则是 dead parameter。用途: 把目标行原文纳入 evidence 供人工复核
      (**不参与 verified 判定**, 以保持 E-3 的语义限定)。

    Returns:
        dict|None: {"verified": bool, "evidence": str, "sink_api": str,
                    "target_line": int, "target_text": str} 或 None
    """
    sink_api = ""
    for m in _TAINT_SINK_RE.finditer(claim or ""):
        cand = m.group(1)
        tail = cand.rsplit(".", 1)[-1]
        if tail in TAINT_SINK_HINTS:
            sink_api = cand
            break
    if not sink_api:
        return None                     # 无裁决 (E-3)
    found = sink_api in context_text or sink_api.rsplit(".", 1)[-1] in context_text
    # G-4: 消费 all_lines / line_num (仅供证据留痕, 不参与判定)
    target_text = all_lines[line_num - 1].strip() if 1 <= line_num <= len(all_lines) else ""
    return {"verified": bool(found),
            "evidence": f"regex: sink api '{sink_api}' "
                        f"{'present' if found else 'absent'} in source context; "
                        f"target line {line_num}: {target_text[:80]}",
            "sink_api": sink_api,
            "target_line": line_num,
            "target_text": target_text[:80]}


def _verify_l5_taint(claim, claim_types, repo_root, file_path, line_num,
                     language, evidence, context_text, lines, taint_disproof=None):
    """L5 dispatch (ADR-026): taint finding 专属验证. 无裁决时返回 None (不写 check).

    Tier 顺序 (设计 spec §4): T1 Joern → T2 ast def-use → T3 regex.
      降级一致性: T1 verified=True => 不降级; T1 verified=False => 仍跑 T2 双检。
      聚合取向 = **保守向** (G-6 定稿): T1 False + T2 True => 取 T2; T1 False + T2 False => 取 T1;
      T1 None + T2 any => 取 T2。**不**取"更强证伪者" —— T1 的 False 可能源于前端能力缺口,
      误删真阳性代价高于漏删假阳性 (ADR-027)。

    Returns:
        dict|None: None = 三层均无裁决 (=> 不写 checks["taint"], D-T9'-5)
        dict: {
          "verified": True|False, "tier": 1|2|3,
          "evidence": str,                              # 人类可读证据
          "disproof_action": "downgrade"|"remove",      # 仅 verified=False 时有意义 (D-T9'-4)
          "taint_mode": "exact"|"broad",                # 来源模式
          "sink_nodes": int, "source_nodes": int,       # 仅 Tier 1
          "cwe_source": "evidence"|"analysis_kind"|"",  # R9 审计追踪 (G-3: 无 claim 来源)
        }
    """
    mode = _resolve_taint_disproof(taint_disproof)
    ev = evidence if isinstance(evidence, dict) else {}
    source_line = ev.get("source_line")
    source_name = ev.get("source_name")
    cwe_source = "analysis_kind" if ev.get("analysis_kind") == "taint" else (
        "evidence" if _extract_taint_cwe(ev) else "")

    # ── Tier 1: Joern CPG ──
    result = None
    if repo_root and file_path and _taint_enabled():
        try:
            import joern_cpg
            result = joern_cpg.verify_taint_flow(
                repo_root, file_path, line_num, language=language,
                source_file=ev.get("source_file"), source_line=source_line)
        except Exception:
            result = None            # JOERN_FORCE_RAISE 钩子亦在此被吸收 (AC-15)

    # ── Tier 2 (仅 python; T1 verified=True 时不降级) ──
    if (language == "python" and repo_root and file_path
            and not (result and result.get("verified") is True)):
        try:
            import ast_cfg
            r2 = ast_cfg.verify_taint_flow(repo_root, file_path, line_num,
                                           source_line=source_line,
                                           source_name=source_name)
            if r2 and r2.get("verified") is not None:
                if (result and result.get("verified") is False
                        and r2.get("verified") is True):
                    # T1 证伪但 T2 证真 ⇒ 取 T2 (更保守, 避免误删)
                    result = r2
                elif result is None or result.get("verified") is None:
                    result = r2
                # T1 False + T2 False ⇒ 保留 T1 (更强证伪者)
        except Exception:
            pass

    # ── Tier 3 ──
    if not result or result.get("verified") is None:
        r3 = _verify_taint_regex(claim, context_text, lines, line_num)
        if r3 is not None:
            r3["tier"] = 3
            result = r3

    # ── 无裁决 ⇒ None ──
    if not result or result.get("verified") is None:
        return None

    if result["verified"]:
        result["disproof_action"] = None       # verified=True 无证伪动作
    else:
        result["disproof_action"] = mode
    result.setdefault("taint_mode", None)
    result["cwe_source"] = cwe_source
    return result


# ── Main Verification Pipeline ──

def verify_single_finding_l1l2(finding, repo_root):
    """Run L1+L2-only verification for P1 findings (lightweight existence check).

    Used by verify_all_findings() for P1 severity to catch file/line hallucinations
    without incurring L3/L4 structural verification cost.
    """
    fid = finding.get("id", "unknown")
    claim = finding.get("claim", "")
    evidence = finding.get("evidence", {})
    file_path = evidence.get("file", "") or finding.get("file", "")
    line_num = evidence.get("line_start", 0) or finding.get("line", 0)
    severity = finding.get("severity", "P1")

    result = {"id": fid, "severity": severity, "file": file_path,
              "line": line_num, "claim": claim}

    l1l2 = verify_l1_l2(repo_root, file_path, line_num)
    result["l1l2"] = l1l2

    if not l1l2["confirmed"]:
        result["verification_level"] = l1l2["level"]
        result["action"] = "unverified"
        return result, "unverified"

    result["verification_level"] = 2
    result["action"] = "verified_l1l2"
    return result, "verified_l1l2"


def verify_single_finding(finding, repo_root, taint_disproof=None):
    """Run full 4-level verification on a single finding.

    Returns: (verification_result, action)
      action ∈ {"verified", "partial", "unverified"}

    v2.7.1: 支持 l4_eligible 字段 — l4_eligible=False 时跳过 L4, 仅跑 L1-L3.
    v2.7.1: 自动检测 language 并传递给 verify_l4_structural.
    v3.0: taint_disproof 参数透传至 L5 taint 分支 (D-T9'-4); 默认 None => env/默认.
    """
    fid = finding.get("id", "unknown")
    claim = finding.get("claim", "")
    evidence = finding.get("evidence", {})
    file_path = evidence.get("file", "") or finding.get("file", "")
    line_num = evidence.get("line_start", 0) or finding.get("line", 0)
    severity = finding.get("severity", "P0")

    result = {"id": fid, "severity": severity, "file": file_path,
              "line": line_num, "claim": claim}

    # L1+L2: File existence + line validity
    l1l2 = verify_l1_l2(repo_root, file_path, line_num)
    result["l1l2"] = l1l2
    if not l1l2["confirmed"]:
        result["verification_level"] = l1l2["level"]
        result["action"] = "unverified"
        return result, "unverified"

    # L3: Keyword match
    keywords = extract_keywords(claim)

    # v2.8: 从 finding context 读取 threshold, 映射到 min_keywords
    history_threshold = finding.get("_history_threshold")
    min_keywords = _threshold_to_min_keywords(history_threshold)

    l3 = verify_l3(l1l2["lines"], line_num, keywords, min_keywords=min_keywords)
    result["l3"] = l3
    result["keywords"] = keywords
    result["min_keywords_used"] = min_keywords  # 审计追踪字段

    if not l3["confirmed"]:
        result["verification_level"] = 2
        result["action"] = "unverified"
        # v2.8: 在 result 中标注 threshold 影响 (审计追踪字段)
        # 消费方: verify_all_findings() 将 unverified findings 写入 hallucination_log,
        # 该字段保留到 hallucination_log 条目, 供 benchmark_calibrate 分析
        if min_keywords > 1:
            result["hallucination_reason"] = f"keyword_insufficient (min={min_keywords})"
        return result, "unverified"

    # v2.7.1: 检查 l4_eligible — 默认 True (向后兼容)
    # l4_eligible=False 的 finding 跳过 L4, 仅保留 L1-L3 结果
    # L3 已通过 → 返回 "partial" (降级 P0→P1, 保留在 baseline 中)
    l4_eligible = finding.get("l4_eligible", True)
    if not l4_eligible:
        result["verification_level"] = 3
        result["action"] = "partial"
        result["l4_skipped"] = True
        result["l4_skip_reason"] = "l4_eligible=False"
        return result, "partial"

    # v2.7.1: 检测语言并传递给 L4
    language = _detect_language(file_path)

    # L4: Structural verification (Tier 2 fallback needs repo_root + file_path)
    # v3.0: 结构化通道 A 需要 evidence ⇒ 必须同步传参, 否则通道 A 永不命中 (死代码)
    claim_types = classify_claim(claim, evidence, finding.get("category"))
    l4 = verify_l4_structural(l1l2["lines"], line_num, claim, claim_types,
                              repo_root=repo_root, file_path=file_path,
                              language=language,
                              evidence=evidence,               # v3.0 NEW
                              taint_disproof=taint_disproof)   # v3.0 NEW
    result["l4"] = l4
    result["verification_level"] = l4["level"]
    result["language"] = language

    # v3.0 (E-6): 字段仅在 taint 分类时写入 ⇒ kill switch 下逐位一致 (AC-9)
    if "taint" in claim_types:
        tc = (l4.get("checks") or {}).get("taint")
        result["taint_verified"] = tc.get("verified") if tc else None
        result["taint_mode"] = tc.get("taint_mode") if tc else None
        result["taint_disproof_action"] = tc.get("disproof_action") if tc else None

    # v3.0 T19 (D-T19-5): 同一模式 —— 仅在 contract_related 分类时写入
    #   ⇒ 关闭态键集合与 v3.0-T9' 逐位一致 (AC-1 / AC-16)
    if "contract_related" in claim_types:
        cc = (l4.get("checks") or {}).get("contract")
        result["contract_verified"] = cc.get("verified") if cc else None
        result["contract_kind"] = cc.get("kind") if cc else None
        result["contract_rule_id"] = cc.get("rule_id") if cc else None

    if l4["confirmed"]:
        result["action"] = "verified"
        return result, "verified"

    # Phase 1: 区分 Tier 1/2 结构化证伪 (→ removed) vs Tier 3 regex 失败 (→ downgraded)
    # Tier 1/2 verified=False 是基于 CFG/import-graph 的结构化证明, 置信度高 → removed
    # Tier 3 verified=False 仅 regex 失败, 置信度低 → downgraded (保守, 避免误删)
    # v3.0 (D-T9'-4 / AC-6): 尊重 disproof_action —— taint 默认 downgrade 不得命中移除路径。
    #   既有类型 (dead_code / import_related) 无 disproof_action 字段 ⇒ 默认 "remove"
    #   ⇒ 行为与 v2.8 逐位一致 (ADR-018)。
    checks = l4.get("checks", {})
    structural_false = any(
        isinstance(c, dict) and c.get("tier", 3) <= 2 and c.get("verified") is False
        and c.get("disproof_action", "remove") != "downgrade"
        for c in checks.values()
    )
    if structural_false:
        result["action"] = "unverified"
        result["unverified_reason"] = "tier12_structural_disproof"
        return result, "unverified"

    result["action"] = "partial"
    return result, "partial"


def verify_all_findings(findings, repo_root, verify_p1_l4=False,
                        history_threshold=None, taint_disproof=None):
    """Run verification on all P0 (full L1-L4) and P1 (lightweight L1+L2) findings.
    P2-P3 are skipped.

    Args:
        findings: list of finding dicts.
        repo_root: path to repo root for source verification.
        verify_p1_l4: if True, also run L4 structural verification on P1 findings
            (default False for backward compatibility; set True when finding count
            is low and higher recall is needed).
        history_threshold: v2.7.3 断点④修复 + v2.8 T1 闭环 — 来自 fix_history
            的 RL-adjusted threshold. v2.8 通过 `_threshold_to_min_keywords()` 映射
            驱动 L3 验证的 `min_keywords` 参数 (0.85→2 严格, 0.55→1 宽松, None→1 兼容).
            同时写入每个 finding 的 `_history_threshold` 字段供审计追踪.
        taint_disproof: v3.0 — taint 证伪动作 ("downgrade"|"remove"|None);
            None => 由 `_resolve_taint_disproof()` 回退 env / 默认. 透传至
            `verify_single_finding` (两条路径均传).

    Returns verified findings with actions and a hallucination log.
    """
    verified = []
    hallucinations = []
    downgraded = []

    # v2.7.3 断点④: 将 history_threshold 写入每个 finding 的 context 中
    # 供下游调用方 (如 fix_history 的下一轮 RL 调整) 使用
    if history_threshold is not None:
        for f in findings:
            f["_history_threshold"] = history_threshold

    for f in findings:
        sev = f.get("severity")

        if sev not in ("P0", "P1"):
            # P2-P3 pass through unchanged
            f["_phase35_verified"] = True
            f["_phase35_action"] = "skipped"
            verified.append(f)
            continue

        # v2.7.2: 支持 per-finding repo path (Big-Vul/CVEfixes 多 repo 场景)
        # 若 finding 的 evidence 含 repo_local_path, 用它替代全局 repo_root
        finding_repo = f.get("evidence", {}).get("repo_local_path", "") or repo_root

        if sev == "P1":
            # P1: L1+L2 only by default; optional L4 when verify_p1_l4=True
            result, action = verify_single_finding_l1l2(f, finding_repo)
            if action != "verified_l1l2":
                # L1/L2 failed → hallucination (file/line not found)
                hallucinations.append({"id": result["id"], "claim": result["claim"],
                                       "file": result["file"], "line": result["line"],
                                       "severity": "P1",
                                       "reason": result.get("l1l2", {}).get("reason", "unknown")})
                continue

            # L1+L2 passed. If verify_p1_l4, also run L4 structural verification
            if verify_p1_l4:
                result_p1, action_p1 = verify_single_finding(
                    f, finding_repo, taint_disproof=taint_disproof)
                if action_p1 == "verified":
                    f["_phase35_verified"] = True
                    f["_phase35_action"] = "verified_l1l2_l4"
                    f["_phase35_verification"] = {k: v for k, v in result_p1.items()
                                                  if k not in f}
                    verified.append(f)
                elif action_p1 == "unverified":
                    # Phase 1: Tier 1/2 structural disproof → removed
                    hallucinations.append({
                        "id": result_p1["id"], "claim": result_p1["claim"],
                        "file": result_p1["file"], "line": result_p1["line"],
                        "severity": "P1",
                        "reason": result_p1.get("unverified_reason",
                                                 result_p1.get("l4", {}).get("reason", "tier12 disproof"))})
                else:  # partial → downgraded (kept as P1, flagged)
                    f["_phase35_verified"] = False
                    f["_phase35_action"] = "downgraded_l1l2_l4"
                    f["_phase35_verification"] = {k: v for k, v in result_p1.items()
                                                  if k not in f}
                    verified.append(f)
            else:
                # Default: L1+L2 only
                f["_phase35_verified"] = True
                f["_phase35_action"] = "verified_l1l2"
                f["_phase35_verification"] = {k: v for k, v in result.items()
                                              if k not in f}
                verified.append(f)
            continue

        # P0: full L1-L4 verification
        result, action = verify_single_finding(
            f, finding_repo, taint_disproof=taint_disproof)

        if action == "verified":
            result["_phase35_verified"] = True
            result["_phase35_action"] = "verified"
            verified.append({**f, **{k: v for k, v in result.items()
                                     if k not in f}})
        elif action == "partial":
            # Downgrade P0 → P1, flag for human review
            downgraded.append({"id": result["id"], "from": "P0", "to": "P1",
                               "reason": result.get("l4", {}).get("reason", "structural verification failed")})
            f["severity"] = "P1"
            f["_phase35_verified"] = False
            f["_phase35_action"] = "downgraded"
            f["_phase35_verification"] = {k: v for k, v in result.items()
                                          if k not in f}
            verified.append(f)
        else:  # unverified
            # Preserve L4/tier info for benchmark tier distribution analysis
            l4_data = result.get("l4", {})
            checks = l4_data.get("checks", {})
            best_tier = 0
            for c in checks.values():
                if isinstance(c, dict) and c.get("tier", 0) > 0:
                    if best_tier == 0 or c["tier"] < best_tier:
                        best_tier = c["tier"]
            hallucinations.append({"id": result["id"], "claim": result["claim"],
                                   "file": result["file"], "line": result["line"],
                                   "severity": "P0",
                                   "reason": result.get("l1l2", {}).get("reason",
                                        result.get("l3", {}).get("reason", "unknown")),
                                   "l4": l4_data if checks else None,
                                   "best_tier": best_tier})
            # Do NOT add to verified list — removed from fix baseline

    return verified, hallucinations, downgraded


def main():
    parser = argparse.ArgumentParser(
        description="Phase 3.5 Finding Verification — mandatory source-code-level verification for P0 findings")
    parser.add_argument("--findings", required=True,
                        help="Path to findings JSON (from Phase 3 aggregation)")
    parser.add_argument("--repo", required=True,
                        help="Path to repository root for source verification")
    parser.add_argument("--output", default=None,
                        help="Path to write verified findings JSON (default: stdout)")
    parser.add_argument("--hallucination-log",
                        default="docs/audit/hallucination_log.json",
                        help="Path to write hallucination log JSON "
                             "(default: docs/audit/hallucination_log.json)")
    parser.add_argument("--history-threshold", default=None, type=float,
                        help="RL-adjusted threshold from fix_history "
                             "(auto-loaded from docs/audit/augmented_issues.json if omitted)")
    parser.add_argument("--taint-disproof", default=None,
                        choices=["downgrade", "remove"],
                        help="v3.0: taint 证伪动作 "
                             "(default: env ADD_TAINT_DISPROOF, else 'downgrade')")
    args = parser.parse_args()

    # v2.5: 从 fix_history 输出加载 RL-adjusted threshold (RL loop 闭环)
    # fix_history 根据 scores.json trend 动态调整匹配阈值:
    #   improving (▲) → 宽松 (0.55), degrading (▼) → 严格 (0.85)
    # 该 threshold 反馈给后续验证, 使 RL loop 不再空转.
    # v2.7.3 断点④修复: 字段名对齐 fix_history 输出的 "threshold_used"
    effective_threshold = args.history_threshold
    if effective_threshold is None:
        augmented_path = Path("docs/audit/augmented_issues.json")
        if augmented_path.exists():
            try:
                aug_data = json.loads(augmented_path.read_text(encoding="utf-8"))
                meta = aug_data.get("fix_history_meta", {})
                # v2.7.3: fix_history 输出字段名是 "threshold_used"
                effective_threshold = meta.get("threshold_used")
            except (json.JSONDecodeError, ValueError, OSError):
                pass

    findings_data = json.loads(Path(args.findings).read_text(encoding="utf-8"))

    # Normalize input: handle both full AuditReport and plain findings list
    if isinstance(findings_data, dict) and "findings" in findings_data:
        items = findings_data["findings"]
    elif isinstance(findings_data, dict) and "module_results" in findings_data:
        items = []
        for module in findings_data.get("module_results", []):
            items.extend(module.get("findings", []))
        for module in findings_data.get("cross_module_results", []):
            items.extend(module.get("findings", []))
    elif isinstance(findings_data, list):
        items = findings_data
    else:
        print(json.dumps({"error": "Invalid findings JSON structure"}))
        sys.exit(2)

    verified, hallucinations, downgraded = verify_all_findings(
        items, args.repo, history_threshold=effective_threshold,
        taint_disproof=args.taint_disproof,
    )

    output = {
        "phase": "3.5 Finding Verification",
        "summary": {
            "total_findings": len(items),
            "verified_p0": sum(1 for f in verified if f.get("_phase35_action") == "verified"),
            "verified_p1_l1l2": sum(1 for f in verified if f.get("_phase35_action") == "verified_l1l2"),
            "downgraded": len(downgraded),
            "removed_hallucinations": len(hallucinations),
            "hallucinations_p0": sum(1 for h in hallucinations if h.get("severity") == "P0"),
            "hallucinations_p1": sum(1 for h in hallucinations if h.get("severity") == "P1"),
            "skipped": sum(1 for f in verified if f.get("_phase35_action") == "skipped"),
        },
        "effective_threshold": effective_threshold,
        "downgraded": downgraded,
        "hallucinations": hallucinations,
        "verified_findings": verified,
    }

    output_json = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Verified findings written to {args.output}")

    if args.hallucination_log:
        log = {"hallucinations": hallucinations, "count": len(hallucinations),
               "timestamp": __import__("datetime").datetime.now().isoformat()}
        hlog_path = Path(args.hallucination_log)
        hlog_path.parent.mkdir(parents=True, exist_ok=True)
        hlog_path.write_text(
            json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    print(output_json)

    if hallucinations:
        return 1  # Non-zero exit = hallucinations found
    return 0


if __name__ == "__main__":
    run_script(main)