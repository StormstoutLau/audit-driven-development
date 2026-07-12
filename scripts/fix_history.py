"""History-guided repair suggestion engine. v2.1 Repair Track.

Usage: python scripts/fix_history.py
         --findings <new_issues.json>
         --history-dir <docs/audit/>
         --output <augmented_issues.json>
         [--default-threshold 0.65]

Algorithm:
  1. Load scores.json → compute trend (▲/▼/─) from last 3 entries
  2. Adjust difflib threshold based on trend:
     ▲ (improving) → threshold = max(default_threshold - 0.05, 0.55)
     ▼ (declining) → threshold = min(default_threshold + 0.15, 0.85)
     ─ (stable)    → threshold = default_threshold
     "confident mode": 3 consecutive ▲ → threshold -= 0.05 extra
  3. Load all history issues-*.json → filter status=verified
  4. For each new finding, find best history match via max() + SequenceMatcher
  5. If ratio > threshold → inject history fix_suggestion as "suggested_fix"
  6. Output augmented issues JSON

Performance cap: 30s. Max history: 50 verified findings.
"""

import argparse, json, sys, difflib
from itertools import takewhile
from pathlib import Path
from _script_utils import run_script

def read_trend(scores_path):
    if not scores_path.exists():
        return "-", 1

    history = json.loads(scores_path.read_text(encoding="utf-8"))
    if len(history) < 2:
        return "-", 1

    last_scores = [h["score"] for h in history[-3:]]
    if len(last_scores) < 2:
        return "-", 1

    deltas = [last_scores[i+1] - last_scores[i] for i in range(len(last_scores)-1)]
    if all(d > 0 for d in deltas):
        trend = "▲"
    elif all(d < 0 for d in deltas):
        trend = "▼"
    else:
        trend = "─"

    rev = list(reversed(last_scores))
    pairs = zip(rev, rev[1:])
    consecutive_ups = sum(1 for _ in takewhile(lambda x: x[0] > x[1], pairs))

    return trend, consecutive_ups

def load_verified_history(history_dir):
    hdir = Path(history_dir)
    if not hdir.is_dir():
        return []

    entries = []
    for f in sorted(hdir.glob("issues-*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            continue
        audit_id = data.get("audit_id", "")
        version_tag = data.get("version", "")
        entries.extend(
            {
                "id": iss.get("id", ""),
                "severity": iss.get("severity", ""),
                "claim": iss.get("claim", "")[:200],
                "fix_suggestion": iss.get("fix_suggestion"),
                "source_audit": audit_id,
                "source_version": version_tag,
            }
            for iss in data.get("issues", [])
            if isinstance(iss, dict) and iss.get("status") == "verified"
        )
    return entries[:50]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings", required=True)
    parser.add_argument("--history-dir", default="docs/audit")
    parser.add_argument("--output", default="docs/audit/augmented_issues.json")
    parser.add_argument("--default-threshold", type=float, default=0.65)
    args = parser.parse_args()

    data = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    new_issues = data.get("issues", [])

    scores_path = Path(args.history_dir) / "scores.json"
    trend, consecutive = read_trend(scores_path)

    threshold = args.default_threshold
    if trend == "▲":
        threshold = max(args.default_threshold - 0.05, 0.55)
        if consecutive >= 3:
            threshold = max(threshold - 0.05, 0.50)
    elif trend == "▼":
        threshold = min(args.default_threshold + 0.15, 0.85)

    history = load_verified_history(args.history_dir)

    if not history:
        augmented_count = total_matches = 0
    else:
        def _ratio(h, txt):
            return difflib.SequenceMatcher(None, txt, h["claim"].lower()).ratio()

        augmented_count = total_matches = 0
        for issue in new_issues:
            if not isinstance(issue, dict):
                continue
            search_text = f"{issue.get('severity', '')} {issue.get('claim', '')}"[:200].lower()
            best = max(history, key=lambda h: _ratio(h, search_text), default=None)
            if best is not None:
                score = _ratio(best, search_text)
                if score > 0.5:
                    total_matches += 1
                if score >= threshold and best.get("fix_suggestion"):
                    issue["suggested_fix"] = best["fix_suggestion"]
                    issue["match_score"] = round(score, 4)
                    issue["source_history_id"] = best["id"]
                    issue["source_audit"] = best.get("source_audit", "")
                    augmented_count += 1

    output = {
        "audit_id": data.get("audit_id", ""),
        "fix_history_meta": {
            "trend": trend,
            "threshold_used": round(threshold, 4),
            "history_entries_loaded": len(history),
            "findings_augmented": augmented_count,
            "findings_with_any_match_above_50": total_matches,
            "confident_mode": consecutive >= 3,
        },
        "issues": new_issues
    }

    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    match_pct = round(100 * augmented_count / max(len(new_issues), 1))
    print(f"fix_history: trend={trend} threshold={threshold:.3f} "
          f"augmented={augmented_count}/{len(new_issues)} ({match_pct}%)")
    return 0

if __name__ == "__main__":
    run_script(main)
