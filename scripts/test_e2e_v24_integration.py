"""E2E integration test for Phase 3.5 v2.4 three-tier verification.

Validates the complete L1→L2→L3→L4 pipeline with Tier 1→2→3 fallback
on a realistic synthetic repository. This is NOT a unit test — it exercises
the full verify_findings.verify_l4_structural() path end-to-end.

Scenarios covered:
  E2E-1: dead_code claim with Tier 2 (ast CFG) — Joern unavailable on Windows
  E2E-2: import_related claim with Tier 2 (ast import graph)
  E2E-3: missing claim (Tier 3 regex only, no structural improvement)
  E2E-4: Tier 1 unavailable fallback (JOERN_DISABLE=1) -> Tier 2 -> Tier 3
  E2E-5: Tier 1 exception (JOERN_FORCE_RAISE=1) -> caught -> Tier 2 -> Tier 3
  E2E-6: Performance — Tier 2 CFG build < 100ms for ~100 LOC
  E2E-7: Cross-claim regression — multiple claim types on same finding
"""

import os
import sys
import time
import tempfile
import shutil
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

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


print("=" * 70)
print("test_e2e_v24_integration.py: E2E Phase 3.5 v2.4 Three-Tier Verification")
print(f"Working dir: {ROOT}")
print("=" * 70)

# ── Setup: synthetic repo with realistic code patterns ──────────────────

print("\n-- Setup: synthetic repo --")

tmpdir = tempfile.mkdtemp(prefix="add_e2e_")
repo_root = Path(tmpdir)
print(f"  Repo: {repo_root}")

# File 1: dead code after return (Tier 2 should detect)
(repo_root / "dead_code_demo.py").write_text("""def process(data):
    if not data:
        return None
        cleanup()  # dead code after return
    return data.strip()
""", encoding="utf-8")

# File 2: circular import (Tier 2 import graph should detect)
(repo_root / "mod_a.py").write_text("import mod_b\nx = 1\n", encoding="utf-8")
(repo_root / "mod_b.py").write_text("import mod_a\ny = 2\n", encoding="utf-8")

# File 3: missing error handling (Tier 3 regex should detect pattern)
(repo_root / "risky_op.py").write_text("""def divide(a, b):
    result = a / b
    return result
""", encoding="utf-8")

# File 4: clean code (no issues — should return verified=False)
(repo_root / "clean_code.py").write_text("""def add(a, b):
    return a + b
""", encoding="utf-8")

print(f"  Created 4 .py files: dead_code_demo, mod_a/mod_b (cycle), risky_op, clean_code")


# ── E2E-1: dead_code claim — Tier 2 ast CFG ─────────────────────────────

print("\n-- E2E-1: dead_code claim (Tier 2 ast CFG) --")

try:
    import verify_findings
    # Line 4 is `cleanup()` — dead after return on line 3
    lines = (repo_root / "dead_code_demo.py").read_text().split("\n")
    result = verify_findings.verify_l4_structural(
        lines, 4, "dead code after return statement",
        ["dead_code"],
        repo_root=str(repo_root),
        file_path="dead_code_demo.py"
    )
    check("E2E-1a result has 'verified' field", "verified" in result,
          f"keys: {list(result.keys())}")
    check("E2E-1b dead_code detected (verified=True)",
          result.get("verified") is True, f"got {result.get('verified')}")
    check("E2E-1c tier is 2 (ast CFG, Joern unavailable on Win)",
          result.get("checks", {}).get("dead_code", {}).get("tier") == 2,
          f"got {result.get('checks', {}).get('dead_code', {}).get('tier')}")
except Exception as e:
    check("E2E-1 dead_code claim", False, f"Exception: {e}")


# ── E2E-2: import_related claim — Tier 2 ast import graph ───────────────

print("\n-- E2E-2: import_related claim (Tier 2 import graph) --")

try:
    result = verify_findings.verify_l4_structural(
        [], 1, "circular dependency between mod_a and mod_b",
        ["violates", "import_related"],
        repo_root=str(repo_root),
        file_path="mod_a.py"
    )
    check("E2E-2a result has 'verified' field", "verified" in result,
          f"keys: {list(result.keys())}")
    check("E2E-2b circular import detected (verified=True)",
          result.get("verified") is True, f"got {result.get('verified')}")
    import_tier = result.get("checks", {}).get("import_related", {}).get("tier")
    check("E2E-2c tier is 2 (ast import graph)",
          import_tier == 2, f"got {import_tier}")
except Exception as e:
    check("E2E-2 import_related claim", False, f"Exception: {e}")


# ── E2E-3: missing claim — Tier 3 regex only ────────────────────────────

print("\n-- E2E-3: missing claim (Tier 3 regex) --")

try:
    lines = (repo_root / "risky_op.py").read_text().split("\n")
    result = verify_findings.verify_l4_structural(
        lines, 2, "missing error handling for division by zero",
        ["missing"],
        repo_root=str(repo_root),
        file_path="risky_op.py"
    )
    check("E2E-3a result has 'verified' field", "verified" in result,
          f"keys: {list(result.keys())}")
    # missing claim: Tier 3 regex checks if "error handling" IS present
    # It's NOT present in risky_op.py -> confirmed=True (the claim is correct)
    missing_tier = result.get("checks", {}).get("missing", {}).get("tier")
    check("E2E-3b tier is 3 (regex only for missing)",
          missing_tier == 3, f"got {missing_tier}")
except Exception as e:
    check("E2E-3 missing claim", False, f"Exception: {e}")


# ── E2E-4: Tier 1 unavailable fallback (JOERN_DISABLE=1) ────────────────

print("\n-- E2E-4: Tier 1 unavailable -> Tier 2 fallback --")

old_env = os.environ.get("JOERN_DISABLE")
try:
    os.environ["JOERN_DISABLE"] = "1"
    lines = (repo_root / "dead_code_demo.py").read_text().split("\n")
    result = verify_findings.verify_l4_structural(
        lines, 4, "dead code after return",
        ["dead_code"],
        repo_root=str(repo_root),
        file_path="dead_code_demo.py"
    )
    tier = result.get("checks", {}).get("dead_code", {}).get("tier")
    check("E2E-4 Tier 1 disabled, falls to Tier 2",
          tier == 2, f"got tier={tier}")
    check("E2E-4a verified=True still correct",
          result.get("verified") is True, f"got {result.get('verified')}")
finally:
    if old_env is None:
        os.environ.pop("JOERN_DISABLE", None)
    else:
        os.environ["JOERN_DISABLE"] = old_env


# ── E2E-5: Tier 1 exception -> caught -> Tier 2 fallback ────────────────

print("\n-- E2E-5: Tier 1 exception -> caught -> Tier 2 --")

old_disable = os.environ.get("JOERN_DISABLE")
old_raise = os.environ.get("JOERN_FORCE_RAISE")
try:
    # Don't disable Joern (let it try), but force it to raise
    os.environ.pop("JOERN_DISABLE", None)
    os.environ["JOERN_FORCE_RAISE"] = "1"
    lines = (repo_root / "dead_code_demo.py").read_text().split("\n")
    result = verify_findings.verify_l4_structural(
        lines, 4, "dead code after return",
        ["dead_code"],
        repo_root=str(repo_root),
        file_path="dead_code_demo.py"
    )
    tier = result.get("checks", {}).get("dead_code", {}).get("tier")
    check("E2E-5 Tier 1 exception caught, falls to Tier 2",
          tier == 2, f"got tier={tier}")
    check("E2E-5a no crash, verified=True",
          result.get("verified") is True, f"got {result.get('verified')}")
finally:
    if old_disable is None:
        os.environ.pop("JOERN_DISABLE", None)
    else:
        os.environ["JOERN_DISABLE"] = old_disable
    if old_raise is None:
        os.environ.pop("JOERN_FORCE_RAISE", None)
    else:
        os.environ["JOERN_FORCE_RAISE"] = old_raise


# ── E2E-6: Performance — Tier 2 CFG build < 100ms ───────────────────────

print("\n-- E2E-6: Performance (Tier 2 CFG build) --")

try:
    import ast_cfg
    # Build a ~100 LOC file
    big_code = "\n".join([f"def func_{i}():\n    x = {i}\n    return x" for i in range(25)])
    big_file = repo_root / "big_file.py"
    big_file.write_text(big_code, encoding="utf-8")

    t0 = time.perf_counter()
    result = ast_cfg.verify_dead_code(str(repo_root), "big_file.py", 2)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    check(f"E2E-6 CFG build + verify < 100ms (got {elapsed_ms:.1f}ms)",
          elapsed_ms < 100, f"got {elapsed_ms:.1f}ms")
    check("E2E-6a result is valid", "verified" in result, f"keys: {list(result.keys())}")
except Exception as e:
    check("E2E-6 performance", False, f"Exception: {e}")


# ── E2E-7: Cross-claim regression ───────────────────────────────────────

print("\n-- E2E-7: Cross-claim regression (multiple types) --")

try:
    lines = (repo_root / "dead_code_demo.py").read_text().split("\n")
    # Claim with both dead_code and missing keywords
    result = verify_findings.verify_l4_structural(
        lines, 4, "dead code and missing cleanup after return",
        ["dead_code", "missing"],
        repo_root=str(repo_root),
        file_path="dead_code_demo.py"
    )
    checks = result.get("checks", {})
    check("E2E-7a both dead_code and missing checks present",
          "dead_code" in checks and "missing" in checks,
          f"keys: {list(checks.keys())}")
    check("E2E-7b dead_code verified=True",
          checks.get("dead_code", {}).get("verified") is True,
          f"got {checks.get('dead_code', {}).get('verified')}")
    check("E2E-7c overall verified=True (all checks pass)",
          result.get("verified") is True, f"got {result.get('verified')}")
except Exception as e:
    check("E2E-7 cross-claim", False, f"Exception: {e}")


# ── E2E-8: Full pipeline L1→L2→L3→L4 (verify_l1_l2 + verify_l3 + L4) ───

print("\n-- E2E-8: Full pipeline L1→L2→L3→L4 --")

try:
    file_path = "dead_code_demo.py"
    line_num = 4
    # L1+L2
    l1l2 = verify_findings.verify_l1_l2(str(repo_root), file_path, line_num)
    check("E2E-8a L1+L2 confirmed (file exists, line valid)",
          l1l2.get("confirmed") is True, f"got {l1l2.get('confirmed')}")

    # L3
    keywords = verify_findings.extract_keywords("dead code after return")
    l3 = verify_findings.verify_l3(l1l2["lines"], line_num, keywords)
    check("E2E-8b L3 keyword match in context",
          l3.get("confirmed") is True, f"got {l3.get('confirmed')}")

    # L4
    l4 = verify_findings.verify_l4_structural(
        l1l2["lines"], line_num, "dead code after return",
        ["dead_code"],
        repo_root=str(repo_root),
        file_path=file_path
    )
    check("E2E-8c L4 structural verification passed",
          l4.get("verified") is True, f"got {l4.get('verified')}")
    check("E2E-8d L4 level=4 (all checks passed)",
          l4.get("level") == 4, f"got level={l4.get('level')}")

    print(f"\n  Full pipeline result:")
    print(f"    L1+L2: confirmed={l1l2.get('confirmed')}, total_lines={l1l2.get('total_lines')}")
    print(f"    L3:    confirmed={l3.get('confirmed')}, matched='{l3.get('matched_keyword', '')}'")
    print(f"    L4:    verified={l4.get('verified')}, level={l4.get('level')}, tier={l4.get('checks', {}).get('dead_code', {}).get('tier')}")
except Exception as e:
    check("E2E-8 full pipeline", False, f"Exception: {e}")


# ── Cleanup ─────────────────────────────────────────────────────────────

print("\n-- Cleanup --")
shutil.rmtree(tmpdir, ignore_errors=True)
check("E2E cleanup temp repo", not Path(tmpdir).exists())


# ── Summary ─────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print(f"RESULTS: {passed} PASS / {failed} FAIL / {passed + failed} total")
print("=" * 70)

sys.exit(1 if failed > 0 else 0)
