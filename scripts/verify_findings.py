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

import argparse, json, re, sys
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


def classify_claim(claim):
    """Classify the finding claim into a structural verification type."""
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
    return types if types else ["generic"]


# ── Keyword Extraction (shared with verify_lines.py) ──

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


def verify_l3(lines, line_num, keywords):
    """Level 3: Keyword/pattern match in source context (±20 lines)."""
    if not keywords:
        return {"level": 2, "confirmed": False, "reason": "no_keywords_to_match"}

    target_line = lines[line_num - 1]
    target_lower = target_line.lower()

    # Exact match on target line
    if match := next((kw for kw in keywords if kw.lower() in target_lower), None):
        return {"level": 3, "confirmed": True, "matched_keyword": match,
                "matched_line": line_num, "offset": 0}

    # Proximity match ±20 lines
    for offset in range(1, 21):
        for direction in (-1, 1):
            check_line = line_num + direction * offset
            if 1 <= check_line <= len(lines):
                check_lower = lines[check_line - 1].lower()
                if match := next((kw for kw in keywords if kw.lower() in check_lower), None):
                    return {"level": 3, "confirmed": True, "matched_keyword": match,
                            "matched_line": check_line, "offset": direction * offset}

    return {"level": 2, "confirmed": False, "reason": "no keyword match within ±20 lines",
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
                         repo_root=None, file_path=None):
    """Level 4: Structural claim verification with Tier 2 fallback.

    Tier 2 (ast CFG) for dead_code/import_related — higher accuracy (~90%).
    Tier 3 (regex) for missing/wrong/violates/generic + Tier 2 fallback (~42%).

    P0-2 unified schema: all Tier results include "verified" field (True|False|None).
    Tier 3 (regex) originally returns "confirmed", mapped to "verified" for consistency.
    "verified=None" means this Tier cannot decide → trigger fallback to next Tier.
    """
    # Phase 3: 扩展 context 到 enclosing function 全范围 (解决 ±25 窗口局限).
    # 如果 line 在函数内, 用函数全范围; 否则回退到 ±50 行 (原 ±25 的 2 倍).
    context_text = _get_function_context(lines, line_num)

    checks = {}

    if "dead_code" in claim_types:
        result = None
        # Tier 1: Joern CPG (highest accuracy ~95%, optional dependency)
        # P1-5: joern_cpg never raises in normal operation, but V9 test hook
        # (JOERN_FORCE_RAISE=1) simulates runtime failure -> must catch & degrade
        if repo_root and file_path:
            try:
                import joern_cpg
                result = joern_cpg.verify_dead_code(repo_root, file_path, line_num)
            except Exception:
                result = None
        # Tier 2: Python ast CFG (higher accuracy ~90%, zero deps)
        # Phase 8: Joern dead_code is method-level (no callers); claims are
        #   usually statement-level (unreachable after return). Method-level
        #   dead (Joern True) does NOT pinpoint the specific statement, and
        #   method reachable (Joern False) does NOT imply statement reachable.
        #   Strategy: always run Tier 2 for double-check.
        #     - Joern True + Tier 2 True → keep Joern (tier=1, both agree)
        #     - Joern True + Tier 2 False → use Tier 2 (statement-level precise)
        #     - Joern False/None + Tier 2 any → use Tier 2
        #     - Joern True + Tier 2 None → keep Joern (Tier 2 cannot decide)
        if repo_root and file_path:
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
        if repo_root:
            try:
                import joern_cpg
                result = joern_cpg.verify_imports(repo_root, claim)
            except Exception:
                result = None
        # Tier 2: Python ast import graph
        # Phase 8: Joern verified=False → degrade to Tier 2 (conservative).
        #   Joern Python support (pysrc2cpg) may be incomplete; Tier 2 uses
        #   Python stdlib ast for reliable import graph construction.
        #   Only verified=True (confirmed cycle) prevents degradation.
        if (not result or result.get("verified") is not True) and repo_root:
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
    if "generic" in claim_types and not checks:
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


def verify_single_finding(finding, repo_root):
    """Run full 4-level verification on a single finding.

    Returns: (verification_result, action)
      action ∈ {"verified", "partial", "unverified"}
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
    l3 = verify_l3(l1l2["lines"], line_num, keywords)
    result["l3"] = l3
    result["keywords"] = keywords

    if not l3["confirmed"]:
        result["verification_level"] = 2
        result["action"] = "unverified"
        return result, "unverified"

    # L4: Structural verification (Tier 2 fallback needs repo_root + file_path)
    claim_types = classify_claim(claim)
    l4 = verify_l4_structural(l1l2["lines"], line_num, claim, claim_types,
                              repo_root=repo_root, file_path=file_path)
    result["l4"] = l4
    result["verification_level"] = l4["level"]

    if l4["confirmed"]:
        result["action"] = "verified"
        return result, "verified"

    # Phase 1: 区分 Tier 1/2 结构化证伪 (→ removed) vs Tier 3 regex 失败 (→ downgraded)
    # Tier 1/2 verified=False 是基于 CFG/import-graph 的结构化证明, 置信度高 → removed
    # Tier 3 verified=False 仅 regex 失败, 置信度低 → downgraded (保守, 避免误删)
    checks = l4.get("checks", {})
    structural_false = any(
        isinstance(c, dict) and c.get("tier", 3) <= 2 and c.get("verified") is False
        for c in checks.values()
    )
    if structural_false:
        result["action"] = "unverified"
        result["unverified_reason"] = "tier12_structural_disproof"
        return result, "unverified"

    result["action"] = "partial"
    return result, "partial"


def verify_all_findings(findings, repo_root, verify_p1_l4=False):
    """Run verification on all P0 (full L1-L4) and P1 (lightweight L1+L2) findings.
    P2-P3 are skipped.

    Args:
        findings: list of finding dicts.
        repo_root: path to repo root for source verification.
        verify_p1_l4: if True, also run L4 structural verification on P1 findings
            (default False for backward compatibility; set True when finding count
            is low and higher recall is needed).

    Returns verified findings with actions and a hallucination log.
    """
    verified = []
    hallucinations = []
    downgraded = []

    for f in findings:
        sev = f.get("severity")

        if sev not in ("P0", "P1"):
            # P2-P3 pass through unchanged
            f["_phase35_verified"] = True
            f["_phase35_action"] = "skipped"
            verified.append(f)
            continue

        if sev == "P1":
            # P1: L1+L2 only by default; optional L4 when verify_p1_l4=True
            result, action = verify_single_finding_l1l2(f, repo_root)
            if action != "verified_l1l2":
                # L1/L2 failed → hallucination (file/line not found)
                hallucinations.append({"id": result["id"], "claim": result["claim"],
                                       "file": result["file"], "line": result["line"],
                                       "severity": "P1",
                                       "reason": result.get("l1l2", {}).get("reason", "unknown")})
                continue

            # L1+L2 passed. If verify_p1_l4, also run L4 structural verification
            if verify_p1_l4:
                result_p1, action_p1 = verify_single_finding(f, repo_root)
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
        result, action = verify_single_finding(f, repo_root)

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
    args = parser.parse_args()

    # v2.5: 从 fix_history 输出加载 RL-adjusted threshold (RL loop 闭环)
    # fix_history 根据 scores.json trend 动态调整匹配阈值:
    #   improving (▲) → 宽松 (0.55), degrading (▼) → 严格 (0.85)
    # 该 threshold 反馈给后续验证, 使 RL loop 不再空转.
    effective_threshold = args.history_threshold
    if effective_threshold is None:
        augmented_path = Path("docs/audit/augmented_issues.json")
        if augmented_path.exists():
            try:
                aug_data = json.loads(augmented_path.read_text(encoding="utf-8"))
                meta = aug_data.get("fix_history_meta", {})
                effective_threshold = meta.get("effective_threshold")
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

    verified, hallucinations, downgraded = verify_all_findings(items, args.repo)

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