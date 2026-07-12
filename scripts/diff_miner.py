"""Deterministic bug-pattern miner from git history. v2.1 Detection Track.

Usage: python scripts/diff_miner.py
         --repo <path>
         --since <date>
         --output <pattern_candidates.json>
         [--max-commits 200]

Algorithm:
  1. git log --grep="fix|bug|CVE|vuln|patch|security" --oneline --since=<date>
     --max-count=<max_commits>
  2. For each commit: git show --stat --name-only → get changed files
  3. Statistical clustering:
     - File edited in 3+ fix commits → "hotspot"
     - Commit message keyword clustering → "pattern" (e.g. "null check" ×5)
     - CVE keyword clustering → "security_pattern" (CVE ×2+)
  4. Output pattern_candidates.json with hotspots, patterns, suggested_guards

Performance cap: 60s (max 200 commits)
"""

import argparse, json, sys, subprocess, re, collections
from itertools import chain
from pathlib import Path
from _script_utils import run_script

SKIP_PREFIXES = frozenset({"commit", "Author", "Date"})
SKIP_KEYWORDS = frozenset({"file changed", "insertion", "deletion"})

def git_log(repo_path, since, max_commits):
    result = subprocess.run(
        ["git", "-C", str(repo_path), "log",
         "--grep=fix|bug|CVE|vuln|patch|security",
         "--oneline", f"--since={since}",
         f"--max-count={max_commits}"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return []
    return [
        {"sha": parts[0], "message": parts[1] if len(parts) > 1 else ""}
        for line in result.stdout.strip().split("\n")
        if line.strip() and (parts := line.split(" ", 1))
    ]

def commit_files(repo_path, sha):
    result = subprocess.run(
        ["git", "-C", str(repo_path), "show", "--stat", "--name-only", sha],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        return []
    return [
        s for l in result.stdout.strip().split("\n")
        if (s := l.strip()) and not s.startswith(tuple(SKIP_PREFIXES))
        and not any(kw in s.lower() for kw in SKIP_KEYWORDS)
    ]

def cluster_patterns(commits, repo_path):
    file_counts = collections.Counter()
    msg_keywords = collections.Counter()
    cve_patterns = collections.Counter()

    KEYWORD_RES = [
        ("null_check", re.compile(r'(?i)(?:\bnull\b|\bnone\b|\bmissing\s+check\b)')),
        ("overflow",   re.compile(r'(?i)(?:\boverflow\b|\boverrun\b|\bbounds\b)')),
        ("injection",  re.compile(r'(?i)(?:\binject\b|\bxss\b|\bsqli\b|\bsanitiz)')),
    ]
    cve_re = re.compile(r'CVE-\d{4}-\d{4,}', re.IGNORECASE)

    for commit in commits:
        file_counts.update(commit_files(repo_path, commit["sha"]))
        msg = commit["message"].lower()
        for kw, re_obj in KEYWORD_RES:
            if re_obj.search(msg):
                msg_keywords[kw] += 1
        if cve_match := cve_re.search(commit["message"]):
            cve_patterns[cve_match.group(0)] += 1

    return file_counts, msg_keywords, cve_patterns

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--since", required=True)
    parser.add_argument("--output", default="docs/audit/pattern_candidates.json")
    parser.add_argument("--max-commits", type=int, default=200)
    args = parser.parse_args()

    commits = git_log(args.repo, args.since, args.max_commits)
    file_counts, msg_keywords, cve_patterns = cluster_patterns(commits, args.repo)

    hotspots = [{"file": f, "fix_count": c}
                for f, c in file_counts.most_common(20)
                if c >= 3]

    patterns = [{"pattern": kw, "occurrence_count": c}
                for kw, c in msg_keywords.most_common(10)
                if c >= 2]

    security_patterns = [{"cve": cve, "occurrence_count": c}
                         for cve, c in cve_patterns.most_common(10)
                         if c >= 2]

    GUARD_TEMPLATES = {
        "null_check": (5, "critical", "Dict.get() or attribute access MUST use `or default` pattern for null-safety"),
        "injection":  (2, "blocker", "All user input MUST be sanitized before use in queries/rendering"),
        "overflow":   (5, "critical", "All buffer/array access MUST be bounds-checked"),
    }
    suggested_guards = [
        {
            "trigger": f"{p['pattern']} x{p['occurrence_count']}+",
            "suggested_guard": {"description": desc, "severity": sev, "scope": "**/*.py"}
        }
        for p in patterns
        if (tpl := GUARD_TEMPLATES.get(p["pattern"])) and p["occurrence_count"] >= tpl[0]
        for sev, desc in [(tpl[1], tpl[2])]
    ]

    output = {
        "repo": str(Path(args.repo).resolve()),
        "since": args.since,
        "fix_commits_analyzed": len(commits),
        "hotspots": hotspots,
        "patterns": patterns,
        "security_patterns": security_patterns,
        "suggested_guards": suggested_guards
    }

    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"diff_miner: {len(commits)} commits analyzed, "
          f"{len(hotspots)} hotspots, {len(patterns)} patterns, "
          f"{len(suggested_guards)} guard suggestions")
    return 0

if __name__ == "__main__":
    run_script(main)
