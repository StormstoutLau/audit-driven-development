"""v2.3 consistency test suite. Checks mcp_lookup, benchmark_syncer, live_knowledge,
SKILL.md Step 3.7, and cross-version regression.
"""

import json, sys, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")

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
print("test_v23_consistency.py: v2.3 External Knowledge Pipeline")
print(f"Working dir: {ROOT}")
print("=" * 60)

# ── M1-M5: mcp_lookup.py ──
print("\n── mcp_lookup.py (Shared: MCP query builder) ──")
ml_path = ROOT / "scripts" / "mcp_lookup.py"
check("M1 mcp_lookup.py exists", ml_path.exists())
if ml_path.exists():
    ml_src = ml_path.read_text(encoding="utf-8")
    check("M2 imports hashlib, json, argparse", all(kw in ml_src for kw in ["hashlib", "json", "argparse"]))
    check("M3 has --findings --output --cache-dir args",
          all(kw in ml_src for kw in ["--findings", "--output", "--cache-dir"]))
    check("M4 references 24h TTL cache (86400)", "86400" in ml_src)
    ml_result = subprocess.run([sys.executable, str(ml_path), "--help"],
        capture_output=True, text=True, timeout=5, cwd=str(ROOT))
    check("M5 --help runs without error", ml_result.returncode == 0)

# ── B1-B4: benchmark_syncer.py ──
print("\n── benchmark_syncer.py (Detection: OSS project monitor) ──")
bs_path = ROOT / "scripts" / "benchmark_syncer.py"
check("B1 benchmark_syncer.py exists", bs_path.exists())
if bs_path.exists():
    bs_src = bs_path.read_text(encoding="utf-8")
    check("B2 imports tempfile, subprocess, shutil",
          all(kw in bs_src for kw in ["tempfile", "subprocess", "shutil"]))
    check("B3 has --project --output --dry-run args",
          all(kw in bs_src for kw in ["--project", "--output", "--dry-run"]))
    check("B4 has fastapi/flask/requests/django project list",
          all(p in bs_src for p in ["fastapi", "flask", "requests", "django"]))

# ── L1-L4: live_knowledge.py ──
print("\n── live_knowledge.py (Shared: post-audit update) ──")
lk_path = ROOT / "scripts" / "live_knowledge.py"
check("L1 live_knowledge.py exists", lk_path.exists())
if lk_path.exists():
    lk_src = lk_path.read_text(encoding="utf-8")
    check("L2 imports subprocess, argparse", all(kw in lk_src for kw in ["subprocess", "argparse"]))
    check("L3 references rule_extractor + spec_graph rebuild",
          "rule_extractor" in lk_src and "spec_graph" in lk_src)
    lk_result = subprocess.run([sys.executable, str(lk_path), "--help"],
        capture_output=True, text=True, timeout=5, cwd=str(ROOT))
    check("L4 --help runs without error", lk_result.returncode == 0)

# ── SKILL.md Step 3.7 ──
print("\n── SKILL.md Step 3.7 (External Knowledge + Live Update) ──")
check("K1 SKILL.md contains 'External Knowledge' or 'Step 3.7'",
      "Step 3.7" in SKILL or "External Knowledge" in SKILL)
check("K2 SKILL.md references mcp_lookup.py or benchmark_syncer.py",
      "mcp_lookup.py" in SKILL or "benchmark_syncer.py" in SKILL)

# ── Cross-Regression ──
print("\n── Cross-Regression ──")
for suite in ["test_v022_consistency.py", "test_v03_consistency.py",
              "test_v04_consistency.py", "test_v05_consistency.py",
              "test_v20_consistency.py", "test_v21_consistency.py",
              "test_v22_consistency.py"]:
    suite_path = ROOT / "scripts" / suite
    if suite_path.exists():
        result = subprocess.run([sys.executable, str(suite_path)],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT))
        all_pass = result.returncode == 0 and "FAIL:" not in result.stdout
        check(f"REGR {suite} all PASS", all_pass, f"exit={result.returncode}")
    else:
        check(f"REGR {suite} file missing", False, f"expected {suite_path}")

print("\n" + "=" * 60)
print(f"Results: {passed} PASS / {failed} FAIL / {passed + failed} total")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
