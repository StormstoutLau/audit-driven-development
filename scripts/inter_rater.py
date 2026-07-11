"""Inter-rater reliability helper. Computes Cohen's kappa between two subagent outputs.
v2.0 Knowledge Pipeline — P2.7 (v1.0 legacy item).

Usage: python scripts/inter_rater.py
         --findings-a <module_audit_result_a.json>
         --findings-b <module_audit_result_b.json>
         --spec-graph <spec_graph.json>
         [--dimension behavior]

Logic:
  1. Read spec_graph.json → find overlapping spec sections for both lenses
  2. Extract files covered by those sections
  3. For each file in overlap: check if subagent A found issues, subagent B found issues
  4. Build 2x2 contingency matrix:
     a = both found, b = only A found, c = only B found, d = neither found
  5. Compute Cohen's kappa = (p_o - p_e) / (1 - p_e)
  6. Output: kappa value, agreement rate, per-file breakdown
"""

import argparse, json, sys
from pathlib import Path


def load_finding_files(findings_path):
    """Extract set of files with findings from an audit result JSON."""
    data = json.loads(Path(findings_path).read_text(encoding="utf-8"))
    findings = data.get("findings", []) if isinstance(data, dict) else data
    files_with_findings = set()

    for f in findings:
        if isinstance(f, dict):
            evidence = f.get("evidence", {})
            file_path = evidence.get("file", "") if isinstance(evidence, dict) else ""
            if not file_path:
                file_path = f.get("file", "")
            if file_path:
                files_with_findings.add(file_path)

    return files_with_findings


def load_overlap_files(spec_graph_path, dimension="behavior"):
    """Extract files from spec_graph that appear in sections relevant to dimension."""
    data = json.loads(Path(spec_graph_path).read_text(encoding="utf-8"))
    files = set()

    for section in data.get("spec_sections", []):
        section_title = section.get("section", "").lower()
        if dimension.lower() in section_title or "audit" in section_title or "phase" in section_title:
            for loc in section.get("code_locations", []):
                fname = loc.get("file", "")
                if fname:
                    files.add(fname)

    return files


def compute_cohens_kappa(files_a, files_b, overlap_files):
    """Compute Cohen's kappa for per-file finding presence.
    a = both found issues in this file
    b = only A found
    c = only B found
    d = neither found
    """
    all_files = overlap_files if overlap_files else (files_a | files_b)
    if not all_files:
        return {"kappa": 0.0, "agreement_rate": 0.0, "note": "no overlapping files"}

    a = b = c = d = 0
    for f in all_files:
        found_a = f in files_a
        found_b = f in files_b
        if found_a and found_b:
            a += 1
        elif found_a and not found_b:
            b += 1
        elif not found_a and found_b:
            c += 1
        else:
            d += 1

    n = a + b + c + d
    if n == 0:
        return {"kappa": 0.0, "agreement_rate": 0.0, "note": "empty file set"}

    p_o = (a + d) / n
    p_e = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)

    if p_e >= 1.0:
        kappa = 1.0
    else:
        kappa = (p_o - p_e) / (1 - p_e)

    return {
        "kappa": round(kappa, 4),
        "agreement_rate": round(p_o, 4),
        "matrix": {"a_both": a, "b_only_a": b, "c_only_b": c, "d_neither": d, "n_total": n},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings-a", required=True)
    parser.add_argument("--findings-b", required=True)
    parser.add_argument("--spec-graph", default=None)
    parser.add_argument("--dimension", default="behavior")
    args = parser.parse_args()

    files_a = load_finding_files(args.findings_a)
    files_b = load_finding_files(args.findings_b)

    overlap_files = set()
    if args.spec_graph:
        overlap_files = load_overlap_files(args.spec_graph, args.dimension)

    result = compute_cohens_kappa(files_a, files_b, overlap_files)

    result["files_a_count"] = len(files_a)
    result["files_b_count"] = len(files_b)
    result["overlap_file_count"] = len(overlap_files)

    interpretation = ""
    k = result["kappa"]
    if k < 0:
        interpretation = "less than chance"
    elif k < 0.2:
        interpretation = "slight agreement"
    elif k < 0.4:
        interpretation = "fair agreement"
    elif k < 0.6:
        interpretation = "moderate agreement"
    elif k < 0.8:
        interpretation = "substantial agreement"
    else:
        interpretation = "almost perfect agreement"

    result["interpretation"] = interpretation

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if k < 0.5:
        print(f"\nWARNING: kappa={k:.3f} — low agreement. Manual review recommended.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(2)
