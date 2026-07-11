"""Inter-rater reliability helper. Computes Cohen's kappa between two subagent outputs.
v2.0 Knowledge Pipeline — P2.7 full spec (v1.0 legacy item, completed v2.0.1).

Usage: python scripts/inter_rater.py
         --findings-a <module_audit_result_a.json>
         --findings-b <module_audit_result_b.json>
         --spec-graph <spec_graph.json>
         [--dimension behavior]
         [--per-dimension]

P2.7 Full Spec:
  1. Load findings from two independent subagent outputs
  2. Use spec_graph.json for overlapping file selection
  3. Compute per-file Cohen's kappa (2x2 contingency matrix)
  4. (NEW v2.0.1) --per-dimension: compute kappa per category (signature/behavior/...)
  5. (NEW v2.0.1) Severity escalation: flag findings with severity gap > 1 level

Logic:
  1. Read spec_graph.json → find overlapping spec sections for both lenses
  2. Extract files covered by those sections
  3. For each file in overlap: check if subagent A found issues, subagent B found issues
  4. Build 2x2 contingency matrix:
     a = both found, b = only A found, c = only B found, d = neither found
  5. Compute Cohen's kappa = (p_o - p_e) / (1 - p_e)
  6. Output: kappa value, agreement rate, per-file breakdown, per-dimension kappa
"""

import argparse, json, sys
from pathlib import Path
from _script_utils import run_script


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


def compute_per_dimension_kappa(findings_a_path, findings_b_path, overlap_files):
    """P2.7 step 4: Compute kappa per finding category (signature/behavior/contract/...).

    Groups findings by category, computes separate Cohen's kappa for each.
    Returns {category: {kappa, agreement_rate, matrix}}.
    """
    data_a = json.loads(Path(findings_a_path).read_text(encoding="utf-8"))
    data_b = json.loads(Path(findings_b_path).read_text(encoding="utf-8"))
    findings_a = data_a.get("findings", []) if isinstance(data_a, dict) else data_a
    findings_b = data_b.get("findings", []) if isinstance(data_b, dict) else data_b

    categories = set()
    for f in findings_a + findings_b:
        cat = f.get("category", "unknown") if isinstance(f, dict) else "unknown"
        categories.add(cat)

    result = {}
    for cat in sorted(categories):
        files_a = set()
        files_b = set()
        for f in findings_a:
            if isinstance(f, dict) and f.get("category", "") == cat:
                ev = f.get("evidence", {})
                fp = ev.get("file", "") if isinstance(ev, dict) else f.get("file", "")
                if fp:
                    files_a.add(fp)
        for f in findings_b:
            if isinstance(f, dict) and f.get("category", "") == cat:
                ev = f.get("evidence", {})
                fp = ev.get("file", "") if isinstance(ev, dict) else f.get("file", "")
                if fp:
                    files_b.add(fp)

        if files_a or files_b:
            result[cat] = compute_cohens_kappa(files_a, files_b, overlap_files)

    return result


def escalate_severity_gaps(findings_a_path, findings_b_path):
    """P2.7 step 5: Flag findings with severity gap > 1 level between subagents.
    Returns list of {file, severity_a, severity_b, gap} for manual review.
    """
    data_a = json.loads(Path(findings_a_path).read_text(encoding="utf-8"))
    data_b = json.loads(Path(findings_b_path).read_text(encoding="utf-8"))
    findings_a = data_a.get("findings", []) if isinstance(data_a, dict) else data_a
    findings_b = data_b.get("findings", []) if isinstance(data_b, dict) else data_b

    severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    escalations = []

    findings_by_file_a = {}
    findings_by_file_b = {}
    for f in findings_a:
        if isinstance(f, dict):
            ev = f.get("evidence", {})
            fp = ev.get("file", "") if isinstance(ev, dict) else f.get("file", "")
            if fp:
                findings_by_file_a.setdefault(fp, []).append(f)
    for f in findings_b:
        if isinstance(f, dict):
            ev = f.get("evidence", {})
            fp = ev.get("file", "") if isinstance(ev, dict) else f.get("file", "")
            if fp:
                findings_by_file_b.setdefault(fp, []).append(f)

    for fp in set(findings_by_file_a.keys()) & set(findings_by_file_b.keys()):
        for fa in findings_by_file_a[fp]:
            sa = severity_order.get(fa.get("severity", "P3"), 3)
            for fb in findings_by_file_b[fp]:
                sb = severity_order.get(fb.get("severity", "P3"), 3)
                gap = abs(sa - sb)
                if gap > 1:
                    escalations.append({
                        "file": fp,
                        "finding_a_id": fa.get("id", ""),
                        "finding_b_id": fb.get("id", ""),
                        "severity_a": fa.get("severity", ""),
                        "severity_b": fb.get("severity", ""),
                        "gap": gap,
                        "needs_manual_review": True,
                    })

    return escalations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings-a", required=True)
    parser.add_argument("--findings-b", required=True)
    parser.add_argument("--spec-graph", default=None)
    parser.add_argument("--dimension", default="behavior")
    parser.add_argument("--per-dimension", action="store_true",
                        help="Compute kappa per finding category (P2.7 step 4)")
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

    if args.per_dimension:
        dim_kappas = compute_per_dimension_kappa(args.findings_a, args.findings_b, overlap_files)
        result["per_dimension_kappas"] = dim_kappas

    result["severity_escalations"] = escalate_severity_gaps(args.findings_a, args.findings_b)

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

    severities = result.get("severity_escalations", [])
    if severities:
        print(f"\nWARNING: {len(severities)} severity escalation(s) detected — manual review required.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    run_script(main)
