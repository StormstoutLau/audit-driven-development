"""Deterministic line verifier. Confirms evidence pointer line numbers before scoring.

Usage: python scripts/verify_lines.py --finding-json <finding.json> --repo <path>

Output: verified.json with line_number_confirmed: true/false for each finding.
"""

import argparse, json, sys
from pathlib import Path
from _script_utils import run_script


def extract_keywords(claim):
    """Extract search keywords from a finding claim."""
    import re
    tokens = re.findall(r'[A-Za-z_]\w+|[^\s\w]{2,}', claim)
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "and", "or", "not", "with", "from", "by", "as", "be", "has", "have", "it", "its", "that", "this", "should", "must"}
    return [t for t in tokens if t.lower() not in stopwords and len(t) > 2][:5]


def verify_line(repo_root, file_path, line_num, keywords):
    """Verify that the claimed line contains at least one keyword."""
    abs_path = Path(repo_root) / file_path
    if not abs_path.exists():
        return {"confirmed": False, "reason": "file_not_found"}

    lines = abs_path.read_text(encoding="utf-8", errors="replace").split("\n")
    if line_num < 1 or line_num > len(lines):
        return {"confirmed": False, "reason": f"line {line_num} out of range (1-{len(lines)})"}

    target_line = lines[line_num - 1]
    target_lower = target_line.lower()
    if match := next((kw for kw in keywords if kw.lower() in target_lower), None):
        return {"confirmed": True, "matched_keyword": match}

    for offset in range(1, 21):
        for direction in (-1, 1):
            check_line = line_num + direction * offset
            if 1 <= check_line <= len(lines):
                check_lower = lines[check_line - 1].lower()
                if match := next((kw for kw in keywords if kw.lower() in check_lower), None):
                    return {"confirmed": True, "matched_keyword": match,
                            "nearest_line": check_line, "offset": direction * offset}

    return {"confirmed": False, "reason": "no keyword match within ±20 lines"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--finding-json", required=True)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()

    findings = json.loads(Path(args.finding_json).read_text(encoding="utf-8"))

    if isinstance(findings, dict) and "findings" in findings:
        items = findings["findings"]
    elif isinstance(findings, list):
        items = findings
    else:
        print(json.dumps({"error": "Invalid finding JSON structure"}))
        sys.exit(2)

    verified = []
    for f in items:
        fid = f.get("id", "unknown")
        claim = f.get("claim", "")
        file_path = f.get("evidence", {}).get("file", "") or f.get("file", "")
        line_num = f.get("evidence", {}).get("line_start", 0) or f.get("line", 0)

        keywords = extract_keywords(claim)
        result = verify_line(args.repo, file_path, line_num, keywords)
        result["id"] = fid
        result["file"] = file_path
        result["line"] = line_num
        result["keywords_searched"] = keywords
        verified.append(result)

    confirmed = sum(1 for v in verified if v.get("confirmed"))
    total = len(verified)
    output = {"verified": confirmed, "total": total, "confidence": f"{confirmed}/{total} ({100*confirmed//max(total,1)}%)", "findings": verified}
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if confirmed == total else 1


if __name__ == "__main__":
    run_script(main)
