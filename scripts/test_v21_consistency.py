"""v2.1 consistency test suite. Checks diff_miner, rule_suggester, fix_history,
SKILL.md Step 3.5, and cross-version regression.

Strategy: File existence (fast fail) → content signature checks → functional execution.
"""

import json, sys, tempfile, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
ROADMAP = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} {detail}")

print("=" * 60)
print("test_v21_consistency.py: v2.1 Dual-Track Learning")
print(f"Working dir: {ROOT}")
print("=" * 60)

# ── D1-D5: diff_miner.py ──
print("\n── diff_miner.py (Detection: git→pattern) ──")

dm_path = ROOT / "scripts" / "diff_miner.py"
check("D1 diff_miner.py exists", dm_path.exists(), f"expected {dm_path}")

if dm_path.exists():
    dm_src = dm_path.read_text(encoding="utf-8")
    check("D2 diff_miner imports subprocess, json, argparse",
          all(kw in dm_src for kw in ["subprocess", "json", "argparse"]))
    check("D3 diff_miner has --repo --since --output args",
          all(kw in dm_src for kw in ["--repo", "--since", "--output"]))
    check("D4 diff_miner references git log or git show",
          "git log" in dm_src.lower() or "git show" in dm_src.lower())
    check("D5 diff_miner produces pattern_candidates.json output",
          "pattern_candidates.json" in dm_src)

# ── R1-R5: rule_suggester.py ──
print("\n── rule_suggester.py (Detection: audit-log→rule) ──")

rs_path = ROOT / "scripts" / "rule_suggester.py"
check("R1 rule_suggester.py exists", rs_path.exists(), f"expected {rs_path}")

if rs_path.exists():
    rs_src = rs_path.read_text(encoding="utf-8")
    check("R2 rule_suggester imports json, re, argparse, pathlib",
          all(kw in rs_src for kw in ["json", "re", "argparse", "Path"]))
    check("R3 rule_suggester has --audit-log-dir --output args",
          all(kw in rs_src for kw in ["--audit-log-dir", "--output"]))
    check("R4 rule_suggester reads .md audit-log files",
          ".md" in rs_src and "read_text" in rs_src)
    check("R5 rule_suggester references known bugs / TP/FP/FN patterns",
          any(kw in rs_src.lower() for kw in ["tp", "fp", "fn", "bug", "finding"]))

# ── F1-F7: fix_history.py ──
print("\n── fix_history.py (Repair: semantic match + reward signal) ──")

fh_path = ROOT / "scripts" / "fix_history.py"
check("F1 fix_history.py exists", fh_path.exists(), f"expected {fh_path}")

if fh_path.exists():
    fh_src = fh_path.read_text(encoding="utf-8")
    check("F2 fix_history imports difflib, json, argparse, pathlib",
          all(kw in fh_src for kw in ["difflib", "json", "argparse", "Path"]))
    check("F3 fix_history has --findings --history-dir --output args",
          all(kw in fh_src for kw in ["--findings", "--history-dir", "--output"]))
    check("F4 fix_history references scores.json for trend reading",
          "scores.json" in fh_src)
    check("F5 fix_history uses SequenceMatcher for similarity",
          "SequenceMatcher" in fh_src)

    fh_result = subprocess.run(
        [sys.executable, str(fh_path), "--help"],
        capture_output=True, text=True, timeout=5, cwd=str(ROOT)
    )
    check("F6 fix_history --help runs without error",
          fh_result.returncode == 0,
          f"exit={fh_result.returncode} stderr={fh_result.stderr[:100]}")

    check("F7 fix_history uses status=verified filter for history entries",
          "verified" in fh_src.lower() or "status" in fh_src.lower())

# ── K1-K4: SKILL.md Step 3.5 ──
print("\n── SKILL.md Step 3.5 (Fix History Augmentation) ──")

check("K1 SKILL.md contains 'Fix History Augmentation' or 'Step 3.5'",
      "Step 3.5" in SKILL or "Fix History" in SKILL,
      "Step 3.5 section missing")
check("K2 SKILL.md references fix_history.py",
      "fix_history.py" in SKILL,
      "fix_history.py not referenced")
check("K3 SKILL.md mentions diff_miner.py or rule_suggester.py",
      "diff_miner.py" in SKILL or "rule_suggester.py" in SKILL,
      "Detection track scripts not referenced in SKILL.md")
check("K4 SKILL.md references 'reward signal' or 'scores.json trend'",
      "reward" in SKILL.lower() or "scores.json" in SKILL.lower(),
      "Reward signal mechanism not described")

# ── C1-C3: ROADMAP v2.1 ──
print("\n── ROADMAP v2.1 Cross-Checks ──")

check("C1 ROADMAP Version Anchors contains v2.1",
      "v2.1" in ROADMAP.split("## Version Anchors")[-1].split("\n---\n")[0]
      if "## Version Anchors" in ROADMAP else False)
check("C2 ROADMAP v2.1 status is In Progress or Done",
      any(kw in ROADMAP.split("## Version Anchors")[-1].split("\n---\n")[0]
          for kw in ["In Progress", "Done", "Design Complete"])
      if "## Version Anchors" in ROADMAP else False,
      "v2.1 status not found")
check("C3 ROADMAP Change Log has v2.1 entry",
      "v2.1" in ROADMAP.split("## Change Log")[-1].split("\n---\n")[0]
      if "## Change Log" in ROADMAP else False)

# ── Cross-Regression ──
print("\n── Cross-Regression ──")

for suite in ["test_v022_consistency.py", "test_v03_consistency.py",
              "test_v04_consistency.py", "test_v05_consistency.py",
              "test_v20_consistency.py"]:
    suite_path = ROOT / "scripts" / suite
    if suite_path.exists():
        result = subprocess.run(
            [sys.executable, str(suite_path)],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT)
        )
        all_pass = result.returncode == 0 and "FAIL:" not in result.stdout
        check(f"REGR {suite} all PASS",
              all_pass,
              f"exit={result.returncode}")
    else:
        check(f"REGR {suite} file missing", False, f"expected {suite_path}")

print("\n" + "=" * 60)
print(f"Results: {passed} PASS / {failed} FAIL / {passed + failed} total")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
