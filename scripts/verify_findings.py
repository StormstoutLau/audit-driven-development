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
    ]
]

IMPORT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bimport\b", r"\bfrom\s+\S+\s+import\b",
        r"\bdependency\b", r"\bdepends\s+on\b",
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


def verify_l4_structural(lines, line_num, claim, claim_types):
    """Level 4: Structural claim verification — check if the actual code matches the claim.

    For each claim type, performs source-code-level verification:
    - missing: verify the claimed element IS absent in the context window
    - wrong: verify the wrong pattern IS present in the context window
    - violates: verify the violation pattern IS present
    - dead_code: verify the code appears unreachable
    - import_related: verify the import statement exists
    """
    context_start = max(0, line_num - 25)
    context_end = min(len(lines), line_num + 25)
    context_lines = lines[context_start:context_end]
    context_text = "\n".join(context_lines)

    checks = {}

    if "missing" in claim_types:
        checks["missing"] = _verify_missing(claim, context_text, lines, line_num)

    if "wrong" in claim_types:
        checks["wrong"] = _verify_wrong(claim, context_text)

    if "violates" in claim_types:
        checks["violates"] = _verify_violates(claim, context_text)

    if "dead_code" in claim_types:
        checks["dead_code"] = _verify_dead_code(context_text, lines, line_num)

    if "import_related" in claim_types:
        checks["import_related"] = _verify_import(claim, context_text, lines, line_num)

    # If no specific claim type matched, do generic verification
    if "generic" in claim_types and not checks:
        checks["generic"] = _verify_generic(claim, context_text)

    all_checks = [v for v in checks.values() if isinstance(v, dict)]
    if not all_checks:
        return {"level": 3, "confirmed": False, "reason": "no_structural_checks_applicable",
                "claim_types": claim_types}

    confirmed = all(c.get("confirmed", False) for c in all_checks)
    return {"level": 4 if confirmed else 3, "confirmed": confirmed,
            "claim_types": claim_types, "checks": checks,
            "reason": "all structural checks passed" if confirmed else "structural verification failed"}


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

    return {"confirmed": True, "reason": "could_not_extract_missing_thing",
            "note": "unable to determine what is claimed missing"}


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

    return {"confirmed": True, "reason": "could_not_extract_wrong_thing"}


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

    return {"confirmed": True, "reason": "could_not_extract_violation_thing"}


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

    # L4: Structural verification
    claim_types = classify_claim(claim)
    l4 = verify_l4_structural(l1l2["lines"], line_num, claim, claim_types)
    result["l4"] = l4
    result["verification_level"] = l4["level"]

    if l4["confirmed"]:
        result["action"] = "verified"
        return result, "verified"
    else:
        result["action"] = "partial"
        return result, "partial"


def verify_all_findings(findings, repo_root):
    """Run verification on all P0 findings. P1-P3 are skipped (not verified).

    Returns verified findings with actions and a hallucination log.
    """
    verified = []
    hallucinations = []
    downgraded = []

    for f in findings:
        if f.get("severity") != "P0":
            # P1-P3 pass through unchanged
            f["_phase35_verified"] = True
            f["_phase35_action"] = "skipped"
            verified.append(f)
            continue

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
            hallucinations.append({"id": result["id"], "claim": result["claim"],
                                   "file": result["file"], "line": result["line"],
                                   "reason": result.get("l1l2", {}).get("reason",
                                        result.get("l3", {}).get("reason", "unknown"))})
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
    parser.add_argument("--hallucination-log", default=None,
                        help="Path to write hallucination log JSON")
    args = parser.parse_args()

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
            "verified": sum(1 for f in verified if f.get("_phase35_action") == "verified"),
            "downgraded": len(downgraded),
            "removed_hallucinations": len(hallucinations),
            "skipped": sum(1 for f in verified if f.get("_phase35_action") == "skipped"),
        },
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
        Path(args.hallucination_log).write_text(
            json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    print(output_json)

    if hallucinations:
        return 1  # Non-zero exit = hallucinations found
    return 0


if __name__ == "__main__":
    run_script(main)