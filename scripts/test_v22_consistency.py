"""v2.2 consistency test suite. Checks llm_generalize, fix_recipes, rule_validator,
SKILL.md Step 3.6, and cross-version regression.
"""

import json, sys, subprocess
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
print("test_v22_consistency.py: v2.2 LLM Generalization + Recipe Book")
print(f"Working dir: {ROOT}")
print("=" * 60)

# ── G1-G6: llm_generalize.py ──
print("\n── llm_generalize.py (Shared: LLM prompt builder) ──")
lg_path = ROOT / "scripts" / "llm_generalize.py"
check("G1 llm_generalize.py exists", lg_path.exists())

if lg_path.exists():
    lg_src = lg_path.read_text(encoding="utf-8")
    check("G2 imports json, argparse, pathlib",
          all(kw in lg_src for kw in ["json", "argparse", "Path"]))
    check("G3 has --source-dir --output-dir args",
          all(kw in lg_src for kw in ["--source-dir", "--output-dir"]))
    check("G4 references pattern_candidates.json or guards.learned.yml",
          "pattern_candidates.json" in lg_src or "guards.learned.yml" in lg_src)
    check("G5 references augmented_issues.json (L3 data)",
          "augmented_issues.json" in lg_src)

    lg_result = subprocess.run([sys.executable, str(lg_path), "--help"],
        capture_output=True, text=True, timeout=5, cwd=str(ROOT))
    check("G6 --help runs without error", lg_result.returncode == 0)

# ── R1-R5: fix_recipes.py ──
print("\n── fix_recipes.py (Repair: recipe book manager) ──")
fr_path = ROOT / "scripts" / "fix_recipes.py"
check("R1 fix_recipes.py exists", fr_path.exists())

if fr_path.exists():
    fr_src = fr_path.read_text(encoding="utf-8")
    check("R2 imports yaml, argparse, pathlib",
          all(kw in fr_src for kw in ["yaml", "argparse", "Path"]))
    check("R3 has --recipes --output args",
          all(kw in fr_src for kw in ["--recipes", "--output"]))
    check("R4 has BUILT_IN_RECIPES with >= 3 entries",
          fr_src.count('"id": "FIX-') >= 3)
    check("R5 has --import-llm for LLM recipe import",
          "--import-llm" in fr_src)

# ── V1-V5: rule_validator.py ──
print("\n── rule_validator.py (Detection: benchmark recall validation) ──")
rv_path = ROOT / "scripts" / "rule_validator.py"
check("V1 rule_validator.py exists", rv_path.exists())

if rv_path.exists():
    rv_src = rv_path.read_text(encoding="utf-8")
    check("V2 imports difflib, json, argparse",
          all(kw in rv_src for kw in ["difflib", "json", "argparse"]))
    check("V3 has --rules --benchmark-dir --output args",
          all(kw in rv_src for kw in ["--rules", "--benchmark-dir", "--output"]))
    check("V4 references benchmark JSON loading",
          "benchmark" in rv_src.lower() and "json" in rv_src.lower())
    check("V5 uses SequenceMatcher for rule↔bug matching",
          "SequenceMatcher" in rv_src)

# ── SKILL.md Step 3.6 ──
print("\n── SKILL.md Step 3.6 (Generalized Rule Injection) ──")
check("K1 SKILL.md contains 'Generalized Rule' or 'Step 3.6'",
      "Step 3.6" in SKILL or "Generalized Rule" in SKILL or "fix_recipes" in SKILL)
check("K2 SKILL.md references fix_recipes.py or llm_generalize.py",
      "fix_recipes.py" in SKILL or "llm_generalize.py" in SKILL)

# ── ROADMAP v2.2 ──
print("\n── ROADMAP v2.2 Cross-Checks ──")
check("C1 ROADMAP Version Anchors contains v2.2",
      "v2.2" in ROADMAP.split("## Version Anchors")[-1].split("\n---\n")[0]
      if "## Version Anchors" in ROADMAP else False)

# ── Cross-Regression ──
print("\n── Cross-Regression ──")
for suite in ["test_v022_consistency.py", "test_v03_consistency.py",
              "test_v04_consistency.py", "test_v05_consistency.py",
              "test_v20_consistency.py", "test_v21_consistency.py"]:
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
