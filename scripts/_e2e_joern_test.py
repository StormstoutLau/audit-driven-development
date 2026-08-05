"""E2E test: verify Joern CPG Tier 1 actually runs via WSL2 from Windows host.

Phase 7: Updated to test method-level dead code (what Joern actually detects).
  - Joern dead_code = method with NO callers (unused method)
  - ast_cfg dead_code = unreachable statement (after return/raise)
  These are different concepts; this E2E tests Joern's method-level detection.

Test scenarios:
  1. Used method (called from module) → verified=False (reachable)
  2. Unused method (never called) → verified=True (dead)
"""
import os
import sys
import tempfile
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import joern_cpg

print("=" * 60)
print("E2E Test: Joern CPG Tier 1 via WSL2 (Phase 7)")
print("=" * 60)

# Step 1: Check availability
print("\n[1] is_available() check...")
joern_cpg._WSL_DETECT_CACHE = None  # clear cache for fresh detection
avail = joern_cpg.is_available()
print(f"    is_available = {avail}")
if not avail:
    print("    SKIP: Joern not available (WSL2 not detected or JOERN_DISABLE set)")
    sys.exit(0)

# Step 2: Show WSL2 detection result
print("\n[2] WSL2 detection info...")
info = joern_cpg._detect_wsl_from_windows()
if info:
    print(f"    joern_path: {info.get('joern_path')}")
    print(f"    java_home:  {info.get('java_home')}")
else:
    print("    No WSL2 Joern detected")
    sys.exit(0)

# Step 3: Create test repo with method-level dead code
print("\n[3] Creating test repo with method-level dead code...")
with tempfile.TemporaryDirectory(prefix="add_e2e_") as tmpd:
    repo = Path(tmpd)
    # File with:
    #   line 1: used_func (called from module) → NOT dead
    #   line 4: unused_func (never called) → dead
    #   line 7: module-level call to used_func
    test_file = repo / "methods.py"
    test_file.write_text(textwrap.dedent("""\
        def used_func():
            return 1

        def unused_func():
            return 2

        used_func()
    """), encoding="utf-8")
    print(f"    repo: {tmpd}")
    print(f"    file: methods.py")
    print(f"    line 1: used_func (called) → NOT dead")
    print(f"    line 4: unused_func (never called) → dead")

    # Step 4: Test reachable method (line 1 = used_func)
    print("\n[4] verify_dead_code(repo, 'methods.py', line=1) [used_func]...")
    result1 = joern_cpg.verify_dead_code(str(repo), "methods.py", 1)
    tier1 = result1.get("tier")
    verified1 = result1.get("verified")
    print(f"    result: {result1}")
    print(f"    tier={tier1}, verified={verified1}")
    ok1 = tier1 == 1
    ok2 = verified1 is False  # used_func is called → NOT dead
    print(f"    tier==1 (Joern ran): {'PASS' if ok1 else 'FAIL'}")
    print(f"    verified==False (reachable): {'PASS' if ok2 else 'FAIL'}")

    # Step 5: Test dead method (line 4 = unused_func)
    print("\n[5] verify_dead_code(repo, 'methods.py', line=4) [unused_func]...")
    result2 = joern_cpg.verify_dead_code(str(repo), "methods.py", 4)
    tier2 = result2.get("tier")
    verified2 = result2.get("verified")
    print(f"    result: {result2}")
    print(f"    tier={tier2}, verified={verified2}")
    ok3 = tier2 == 1
    ok4 = verified2 is True  # unused_func never called → dead
    print(f"    tier==1 (Joern ran): {'PASS' if ok3 else 'FAIL'}")
    print(f"    verified==True (dead method): {'PASS' if ok4 else 'FAIL'}")

    # Step 6: Test import cycle detection
    print("\n[6] verify_imports(repo, 'no cycle') [no cycle in single file]...")
    result3 = joern_cpg.verify_imports(str(repo), "circular dependency check")
    tier3 = result3.get("tier")
    verified3 = result3.get("verified")
    print(f"    result: {result3}")
    print(f"    tier={tier3}, verified={verified3}")
    ok5 = tier3 == 1
    ok6 = verified3 is False  # no cycle
    print(f"    tier==1 (Joern ran): {'PASS' if ok5 else 'FAIL'}")
    print(f"    verified==False (no cycle): {'PASS' if ok6 else 'FAIL'}")

    print("\n" + "=" * 60)
    all_ok = ok1 and ok2 and ok3 and ok4 and ok5 and ok6
    print(f"E2E RESULT: {'ALL PASS' if all_ok else 'FAILURES'}")
    print(f"  Tier 1 (Joern) actually ran: {ok1 and ok3 and ok5}")
    print(f"  Dead code detection correct: {ok2 and ok4}")
    print(f"  Import cycle detection correct: {ok6}")
    print("=" * 60)
    sys.exit(0 if all_ok else 1)
