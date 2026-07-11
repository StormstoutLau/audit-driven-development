"""ADD Numeric Scoring + Trend Tracking (P3.2).

Usage:
  python scripts/score_tracker.py compute <issues.json>
    → Output 0-100 score + letter grade based on finding counts

  python scripts/score_tracker.py trend <scores.json>
    → Output ASCII trend chart from score history

Score formula: max(0, 100 - (P0*20 + P1*8 + P2*3 + P3*1))
Grade mapping:  A+ >=95, A 85-94, B+ 75-84, B 65-74, C+ 55-64, D 40-54, F <40
"""

import json, sys
from pathlib import Path
from datetime import datetime

WEIGHTS = {"P0": 20, "P1": 8, "P2": 3, "P3": 1}

def score_to_grade(score):
    if score >= 95: return "A+"
    if score >= 85: return "A"
    if score >= 75: return "B+"
    if score >= 65: return "B"
    if score >= 55: return "C+"
    if score >= 40: return "D"
    return "F"

def compute_score(issues_json_path):
    """Compute 0-100 numeric score from issues.json."""
    data = json.loads(Path(issues_json_path).read_text(encoding="utf-8"))
    counts = {s: 0 for s in WEIGHTS}
    for issue in data.get("issues", []):
        sev = issue.get("severity", "P3")
        if sev in counts:
            counts[sev] += 1

    penalty = sum(counts[s] * WEIGHTS[s] for s in WEIGHTS)
    score = max(0, 100 - penalty)
    grade = score_to_grade(score)
    return score, grade, counts, penalty

def cmd_compute(issues_json_path, project_name=None, version_tag=None):
    score, grade, counts, penalty = compute_score(issues_json_path)
    print(f"Score: {score}/100 ({grade})")
    print(f"Penalty: -{penalty} (P0×{counts['P0']} P1×{counts['P1']} P2×{counts['P2']} P3×{counts['P3']})")

    scores_path = Path(issues_json_path).parent / "scores.json"
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "project": project_name or "unknown",
        "version": version_tag or "unknown",
        "score": score,
        "grade": grade,
        "p0_count": counts["P0"], "p1_count": counts["P1"],
        "p2_count": counts["P2"], "p3_count": counts["P3"]
    }

    history = []
    if scores_path.exists():
        history = json.loads(scores_path.read_text(encoding="utf-8"))
    history.append(entry)
    scores_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Appended to {scores_path}")

def cmd_trend(scores_json_path):
    """Print ASCII trend chart from scores.json history."""
    history = json.loads(Path(scores_json_path).read_text(encoding="utf-8"))
    if not history:
        print("No score history")
        return

    print(f"{'Date':<12} {'Project':<18} {'Version':<12} {'Score':>6} {'Grade':>5}  Trend")
    print("-" * 70)

    prev_score = None
    for entry in history:
        date = entry.get("date", "")
        proj = entry.get("project", "")[:17]
        ver = entry.get("version", "")[:11]
        score = entry.get("score", 0)
        grade = entry.get("grade", "")

        if prev_score is not None:
            delta = score - prev_score
            arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "─")
            trend = f"{arrow}{abs(delta):+d}"
        else:
            trend = " ●"

        bar = "█" * (score // 5) + "░" * (20 - score // 5)
        print(f"{date:<12} {proj:<18} {ver:<12} {score:>5}/100  {grade:>4}  {trend:>4}  {bar}")
        prev_score = score

def main():
    if len(sys.argv) < 2:
        print("Usage: python score_tracker.py <compute|trend> [args...]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "compute":
        if len(sys.argv) < 3:
            print("Usage: python score_tracker.py compute <issues.json> [--project NAME] [--version TAG]")
            sys.exit(1)
        proj, ver = None, None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--project" and i + 1 < len(sys.argv):
                proj = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--version" and i + 1 < len(sys.argv):
                ver = sys.argv[i + 1]; i += 2
            else:
                i += 1
        cmd_compute(sys.argv[2], proj, ver)

    elif cmd == "trend":
        if len(sys.argv) < 3:
            print("Usage: python score_tracker.py trend <scores.json>")
            sys.exit(1)
        cmd_trend(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(2)
