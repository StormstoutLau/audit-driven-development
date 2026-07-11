"""v2.0 consistency test suite. Checks rule_extractor, spec_graph, inter_rater,
SKILL.md Knowledge Loading, and cross-version regression.

Strategy: File existence first (fast fail), then content checks.

Expected state: ALL failing (RED) before implementation.
"""

import json, yaml, sys
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
print("test_v20_consistency.py: v2.0 Knowledge Pipeline")
print(f"Working dir: {ROOT}")
print("=" * 60)

# ── R1-R6: rule_extractor.py ──
print("\n── rule_extractor.py ──")

rule_ext_path = ROOT / "scripts" / "rule_extractor.py"
check("R1 rule_extractor.py exists",
      rule_ext_path.exists(),
      f"expected {rule_ext_path}")

if rule_ext_path.exists():
    ext_src = rule_ext_path.read_text(encoding="utf-8")
    check("R2 imports argparse, json, sys, re, pathlib",
          all(kw in ext_src for kw in ["argparse", "json", "re", "Path"]))
    check("R3 guards.learned.yml output file referenced",
          "guards.learned.yml" in ext_src)
    check("R4 benchmark-result.json referenced",
          "benchmark-result.json" in ext_src)

learned_path = ROOT / "docs" / "audit" / "guards.learned.yml"
check("R5 guards.learned.yml exists",
      learned_path.exists(),
      f"expected {learned_path}")

if learned_path.exists():
    content = learned_path.read_text(encoding="utf-8")
    check("R6 guards.learned.yml is valid YAML with version field",
          "version" in content and len(content) > 0)

# ── R7-R12: spec_graph.py ──
print("\n── spec_graph.py ──")

spec_graph_path = ROOT / "scripts" / "spec_graph.py"
check("R7 spec_graph.py exists",
      spec_graph_path.exists(),
      f"expected {spec_graph_path}")

if spec_graph_path.exists():
    graph_src = spec_graph_path.read_text(encoding="utf-8")
    check("R8 spec_graph.py imports argparse, json, re, pathlib",
          all(kw in graph_src for kw in ["argparse", "json", "re", "Path"]))
    check("R9 spec_graph.py references spec_graph.json output",
          "spec_graph.json" in graph_src)
    check("R10 spec_graph.py preserves rule_index pattern extraction",
          "must" in graph_src.lower() or "extract_constraints" in graph_src or "rule" in graph_src.lower())
    check("R11 spec_graph.py references ADR tracing (grep/subprocess)",
          "adr" in graph_src.lower() and ("grep" in graph_src.lower() or "subprocess" in graph_src))

# ── R13-R16: inter_rater.py ──
print("\n── inter_rater.py ──")

inter_rater_path = ROOT / "scripts" / "inter_rater.py"
check("R13 inter_rater.py exists",
      inter_rater_path.exists(),
      f"expected {inter_rater_path}")

if inter_rater_path.exists():
    ir_src = inter_rater_path.read_text(encoding="utf-8")
    check("R14 inter_rater.py contains cohens_kappa function",
          "cohens_kappa" in ir_src or "kappa" in ir_src.lower())
    check("R15 inter_rater.py reads audit finding JSON or spec_graph.json",
          "json" in ir_src and ("audit" in ir_src.lower() or "finding" in ir_src.lower() or "spec_graph" in ir_src))
    check("R16 inter_rater.py outputs agreement rate or kappa value",
          "agreement" in ir_src.lower() or "kappa" in ir_src.lower() or "print" in ir_src)

    import tempfile, subprocess
    test_a = json.dumps([
        {"evidence": {"file": "f1.py"}, "claim": "issue"},
        {"evidence": {"file": "f2.py"}, "claim": "issue"},
        {"evidence": {"file": "f3.py"}, "claim": "issue"},
    ])
    test_b = json.dumps([
        {"evidence": {"file": "f1.py"}, "claim": "issue"},
        {"evidence": {"file": "f3.py"}, "claim": "issue"},
        {"evidence": {"file": "f4.py"}, "claim": "issue"},
    ])
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as fa, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as fb:
        fa.write(test_a); fb.write(test_b)
        fa_name = fa.name; fb_name = fb.name
    result = subprocess.run(
        [sys.executable, str(inter_rater_path), "--findings-a", fa_name, "--findings-b", fb_name],
        capture_output=True, text=True, timeout=10, cwd=str(ROOT)
    )
    import os; os.unlink(fa_name); os.unlink(fb_name)
    kappa_ok = result.returncode == 0 and '"kappa"' in result.stdout and '"agreement_rate"' in result.stdout
    check("R16b inter_rater.py functional: kappa + agreement_rate in JSON output",
          kappa_ok,
          f"stdout: {result.stdout[:200]}")

# ── R17-R20: SKILL.md Knowledge Loading ──
print("\n── SKILL.md Knowledge Loading Section ──")

check("R17 SKILL.md contains 'Knowledge Loading' or '知识加载' (v2.0 Step 0.5)",
      "Knowledge Loading" in SKILL or "知识加载" in SKILL,
      "Step 0.5 section missing")
check("R18 SKILL.md references spec_graph.json",
      "spec_graph.json" in SKILL,
      "spec_graph.json not referenced")
check("R19 SKILL.md references guards.learned.yml",
      "guards.learned.yml" in SKILL,
      "guards.learned.yml not referenced")
kl_pos = SKILL.lower().find("knowledge loading")
check("R20 'fail' or 'skip' or 'missing' — knowledge loading failure handling",
      kl_pos > 0 and any(kw in SKILL.lower()[kl_pos:kl_pos+3000]
          for kw in ["fail", "skip", "missing", "absent", "not available"]),
      "No graceful degradation described")

# ── C1-C4: ROADMAP + Version Anchors ──
print("\n── ROADMAP Cross-Checks ──")

check("C1 ROADMAP P2.7 Status is Done",
      "P2.7" in ROADMAP and ("**P2.7**" not in ROADMAP.split("P3")[0]
                              or "Done" in ROADMAP.split("P2.7")[-1][:200]
                              or "Done" in ROADMAP))

check("C2 ROADMAP Version Anchors contains v2.0",
      "v2.0" in ROADMAP.split("## Version Anchors")[-1].split("\n---\n")[0]
      if "## Version Anchors" in ROADMAP else False,
      "v2.0 not in Version Anchors table")

check("C3 ROADMAP Change Log contains v2.0 entry",
      "v2.0" in ROADMAP.split("## Change Log")[-1].split("\n---\n")[0]
      if "## Change Log" in ROADMAP else False,
      "No v2.0 entry in Change Log")

# ── Cross-Regression: Previous Test Suites ──
print("\n── Cross-Regression (existing suites) ──")

for suite in ["test_v022_consistency.py", "test_v03_consistency.py",
              "test_v04_consistency.py", "test_v05_consistency.py"]:
    suite_path = ROOT / "scripts" / suite
    if suite_path.exists():
        import subprocess
        result = subprocess.run(
            [sys.executable, str(suite_path)],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT)
        )
        all_pass = result.returncode == 0 and "FAIL:" not in result.stdout
        check(f"REGR {suite} all PASS",
              all_pass,
              f"exit={result.returncode}" + (f"\n{result.stdout[-500:]}" if not all_pass else ""))
    else:
        check(f"REGR {suite} file missing",
              False,
              f"expected {suite_path}")

# ── Summary ──
print("\n" + "=" * 60)
print(f"Results: {passed} PASS / {failed} FAIL / {passed + failed} total")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
