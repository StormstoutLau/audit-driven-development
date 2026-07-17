"""v3.5 consistency test suite. Checks verify_findings.py, SKILL.md Phase 3.5,
and cross-version regression.
"""
import json, sys, subprocess, tempfile, os
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
print("test_v35_consistency.py: v3.5 Phase 3.5 Finding Verification")
print(f"Working dir: {ROOT}")
print("=" * 60)

# ── V1-V8: verify_findings.py ──
print("\n── verify_findings.py (Phase 3.5: Source-level verification) ──")
vf_path = ROOT / "scripts" / "verify_findings.py"
check("V1 verify_findings.py exists", vf_path.exists())
if vf_path.exists():
    vf_src = vf_path.read_text(encoding="utf-8")
    check("V2 imports argparse, json, re, sys, Path",
          all(kw in vf_src for kw in ["argparse", "json", "re", "sys", "Path"]))
    check("V3 uses _script_utils.run_script",
          "run_script" in vf_src)
    check("V4 has --findings --repo --output --hallucination-log args",
          all(kw in vf_src for kw in ["--findings", "--repo", "--output", "--hallucination-log"]))
    check("V5 has classify_claim function",
          "classify_claim" in vf_src)
    check("V6 has verify_l1_l2, verify_l3, verify_l4_structural functions",
          all(fn in vf_src for fn in ["verify_l1_l2", "verify_l3", "verify_l4_structural"]))
    check("V7 has 5 claim type patterns (missing/wrong/violates/dead_code/import)",
          all(kw in vf_src for kw in ["MISSING_PATTERNS", "WRONG_PATTERNS", "VIOLATES_PATTERNS", "DEAD_CODE_PATTERNS", "IMPORT_PATTERNS"]))
    vf_result = subprocess.run([sys.executable, str(vf_path), "--help"],
        capture_output=True, text=True, timeout=5, cwd=str(ROOT))
    check("V8 --help runs without error", vf_result.returncode == 0)

# ── V9-V12: End-to-end verification test ──
print("\n── End-to-end verification (4 levels) ──")
import tempfile

# Create test findings with all scenarios
test_findings = [
    {"id": "E2E-P0-VERIFIED", "severity": "P0", "category": "behavior",
     "claim": "missing error handling in verify_line function",
     "evidence": {"file": "scripts/verify_lines.py", "line_start": 21, "line_end": 21},
     "spec_ref": "spec.md", "confidence": "high", "fix_cost": "1-line"},
    {"id": "E2E-P0-UNVERIFIED-FILE", "severity": "P0", "category": "contract",
     "claim": "missing null check in nonexistent.py",
     "evidence": {"file": "scripts/nonexistent_module.py", "line_start": 10, "line_end": 10},
     "spec_ref": "spec.md", "confidence": "low", "fix_cost": "1-line"},
    {"id": "E2E-P0-UNVERIFIED-LINE", "severity": "P0", "category": "blind_spot",
     "claim": "dead code in verify_lines.py",
     "evidence": {"file": "scripts/verify_lines.py", "line_start": 99999, "line_end": 99999},
     "spec_ref": "spec.md", "confidence": "low", "fix_cost": "1-line"},
    {"id": "E2E-P1-SKIPPED", "severity": "P1", "category": "signature",
     "claim": "minor naming issue",
     "evidence": {"file": "scripts/verify_lines.py", "line_start": 1, "line_end": 1},
     "spec_ref": "spec.md", "confidence": "high", "fix_cost": "1-line"},
]

tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
json.dump(test_findings, tmp)
tmp.close()

e2e_result = subprocess.run(
    [sys.executable, str(vf_path), "--findings", tmp.name, "--repo", str(ROOT)],
    capture_output=True, text=True, timeout=10, cwd=str(ROOT))
os.unlink(tmp.name)

check("V9 E2E runs without crash", e2e_result.returncode in (0, 1))
try:
    e2e_output = json.loads(e2e_result.stdout)
    summary = e2e_output.get("summary", {})
    check("V10 E2E summary has verified >= 1", summary.get("verified", 0) >= 1)
    check("V11 E2E summary has removed_hallucinations >= 2", summary.get("removed_hallucinations", 0) >= 2)
    check("V12 E2E summary has skipped >= 1", summary.get("skipped", 0) >= 1)
    hallucinations = e2e_output.get("hallucinations", [])
    check("V13 hallucination log has entries", len(hallucinations) >= 2)
    verified_findings = e2e_output.get("verified_findings", [])
    verified_p0 = [f for f in verified_findings if f.get("_phase35_action") == "verified"]
    check("V14 verified P0 finding has _phase35_action=verified", len(verified_p0) >= 1)
    check("V15 verified P0 finding has verification_level=4",
          any(f.get("verification_level") == 4 for f in verified_findings))
except json.JSONDecodeError:
    check("V9-V15 JSON parse", False, f"stdout: {e2e_result.stdout[:200]}")

# ── V16-V22: SKILL.md Phase 3.5 ──
print("\n── SKILL.md Phase 3.5 (Finding Verification) ──")
check("K1 SKILL.md contains 'Phase 3.5' or 'Finding Verification'",
      "Phase 3.5" in SKILL or "Finding Verification" in SKILL)
check("K2 SKILL.md references verify_findings.py",
      "verify_findings.py" in SKILL)
check("K3 SKILL.md has '4-Level Verification' or '四级验证'",
      "4-Level Verification" in SKILL or "四级验证" in SKILL)
check("K4 SKILL.md has 'Action Matrix' or '动作矩阵'",
      "Action Matrix" in SKILL or "动作矩阵" in SKILL)
check("K5 SKILL.md has 'Claim Type Classification' or '声明类型分类'",
      "Claim Type Classification" in SKILL or "声明类型分类" in SKILL)
check("K6 SKILL.md pipeline diagram shows Phase 3.5 (p35)",
      "p35" in SKILL)
check("K7 SKILL.md has '幻觉防护'",
      "幻觉防护" in SKILL)

# ── V23-V25: Structural verification unit tests ──
print("\n── Structural verification unit tests ──")
import importlib.util
spec = importlib.util.spec_from_file_location("verify_findings", str(vf_path))
vf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vf)

# classify_claim
check("U1 classify_claim('missing error handling') -> ['missing']",
      "missing" in vf.classify_claim("missing error handling"))
check("U2 classify_claim('wrong return type') -> ['wrong']",
      "wrong" in vf.classify_claim("wrong return type"))
check("U3 classify_claim('violates ADR invariant') -> ['violates']",
      "violates" in vf.classify_claim("violates ADR invariant"))
check("U4 classify_claim('dead code in module') -> ['dead_code']",
      "dead_code" in vf.classify_claim("dead code in module"))
check("U5 classify_claim('import not used') -> ['import_related']",
      "import_related" in vf.classify_claim("import from X not used"))
check("U6 classify_claim('no match') -> ['generic']",
      "generic" in vf.classify_claim("no match pattern here"))

# extract_keywords
kw = vf.extract_keywords("missing error handling in verify_line function")
check("U7 extract_keywords filters stopwords", "error" not in kw or len(kw) <= 5)
check("U8 extract_keywords returns non-empty", len(kw) > 0)

# _verify_missing
missing_result = vf._verify_missing(
    "missing error handling", "def foo():\n    pass\n", [], 1)
check("U9 _verify_missing confirms absence when pattern absent",
      missing_result.get("confirmed") == True)

# _verify_wrong
wrong_result = vf._verify_wrong(
    "wrong threshold value 0.5", "threshold = 0.5\n")
check("U10 _verify_wrong confirms presence when pattern present",
      wrong_result.get("confirmed") == True)

# ── Cross-Regression ──
print("\n── Cross-Regression ──")
for suite in ["test_v022_consistency.py", "test_v03_consistency.py",
              "test_v04_consistency.py", "test_v05_consistency.py",
              "test_v20_consistency.py", "test_v21_consistency.py",
              "test_v22_consistency.py", "test_v23_consistency.py"]:
    suite_path = ROOT / "scripts" / suite
    if suite_path.exists():
        result = subprocess.run([sys.executable, str(suite_path)],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT))
        check(f"CR {suite} passes", result.returncode == 0,
              f"exit={result.returncode}")
    else:
        check(f"CR {suite} exists", False, "file not found")

# ── Summary ──
print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed+failed} total")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)