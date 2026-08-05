"""v2.4 consistency test suite. Checks ast_cfg.py (Tier 2), verify_findings.py
Tier integration, and cross-version regression.

Strategy: Unit tests (ast_cfg) -> Integration tests (verify_findings) -> Regression (existing).
TDD: This file is written FIRST (RED). ast_cfg.py implements to make tests GREEN.

Covers:
  - C1-C15: CFGBuilder dead_code detection (Tier 2)
  - I1-I8: ImportGraphBuilder cycle detection (Tier 2)
  - V1-V6: verify_findings.py Tier 2/3 fallback integration
  - CR:    Cross-version regression (existing 250 tests still pass)
"""

import sys, os, textwrap, tempfile, time, json, subprocess
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


print("=" * 60)
print("test_v24_consistency.py: v2.4 ast CFG + Tier Integration")
print(f"Working dir: {ROOT}")
print("=" * 60)

# ── C1-C15: CFGBuilder dead_code detection ──
print("\n-- C1-C15: CFGBuilder dead_code detection (Tier 2) --")

try:
    from ast_cfg import verify_dead_code_in_source, CFGBuilder
    AST_CFG_AVAILABLE = True
except ImportError:
    AST_CFG_AVAILABLE = False

check("C0 ast_cfg.py importable", AST_CFG_AVAILABLE)


def make_code(src):
    """Dedent and strip leading newline, return clean source."""
    return textwrap.dedent(src).strip()


if AST_CFG_AVAILABLE:
    # C1-C3: dead code after return/raise
    print("\n  -- C1-C3: dead after return/raise --")

    result = verify_dead_code_in_source(make_code('''
        def foo():
            x = 1
            return x
            y = 2
    '''), line=4)
    check("C1 dead after return -> verified=True",
          result["verified"] is True, f"got {result.get('verified')}")
    check("C1 tier=2", result.get("tier") == 2)

    result = verify_dead_code_in_source(make_code('''
        def bar():
            raise ValueError()
            cleanup()
    '''), line=3)
    check("C2 dead after raise -> verified=True",
          result["verified"] is True, f"got {result.get('verified')}")

    result = verify_dead_code_in_source(make_code('''
        def foo():
            x = 1
            return x
    '''), line=3)
    check("C3 alive before return -> verified=False",
          result["verified"] is False, f"got {result.get('verified')}")

    # C4-C6: if/else branch reachability
    print("\n  -- C4-C6: if/else branch --")

    result = verify_dead_code_in_source(make_code('''
        def foo(cond):
            if cond:
                x = 1
            return x
    '''), line=3)
    check("C4 alive in then branch -> verified=False",
          result["verified"] is False)

    result = verify_dead_code_in_source(make_code('''
        def foo(cond):
            if cond:
                x = 1
            else:
                y = 2
            return x if cond else y
    '''), line=5)
    check("C5 alive in else branch -> verified=False",
          result["verified"] is False)

    result = verify_dead_code_in_source(make_code('''
        def foo(cond):
            if cond:
                return 1
                x = 2
            return 3
    '''), line=4)
    check("C6 dead after return in if -> verified=True",
          result["verified"] is True)

    # C7-C9: loop reachability
    print("\n  -- C7-C9: loop --")

    result = verify_dead_code_in_source(make_code('''
        def foo(items):
            for item in items:
                process(item)
            return None
    '''), line=3)
    check("C7 alive in for body -> verified=False",
          result["verified"] is False)

    result = verify_dead_code_in_source(make_code('''
        def foo(n):
            while n > 0:
                n -= 1
            return n
    '''), line=3)
    check("C8 alive in while body -> verified=False",
          result["verified"] is False)

    # C10-C13: try/except (incl. P1-2 regression)
    print("\n  -- C10-C13: try/except (P1-2 regression) --")

    result = verify_dead_code_in_source(make_code('''
        def foo():
            try:
                risky()
            except:
                handle()
    '''), line=3)
    check("C10 alive in try body -> verified=False",
          result["verified"] is False)

    result = verify_dead_code_in_source(make_code('''
        def foo():
            try:
                raise ValueError()
                cleanup()
            except:
                pass
    '''), line=4)
    check("C11 dead after raise in try -> verified=True",
          result["verified"] is True)

    result = verify_dead_code_in_source(make_code('''
        def foo():
            try:
                risky()
            except ValueError:
                handle_ve()
            except TypeError:
                handle_te()
    '''), line=5)
    check("C12 alive in except handler -> verified=False",
          result["verified"] is False)

    # P1-2 critical regression: try body has return, except still reachable
    result = verify_dead_code_in_source(make_code('''
        def foo():
            try:
                return 1
            except:
                handle()
    '''), line=4)
    check("C13 P1-2 except reachable after return in try -> verified=False",
          result["verified"] is False, f"got {result.get('verified')}")

    # C14-C15: nested structures
    print("\n  -- C14-C15: nested --")

    result = verify_dead_code_in_source(make_code('''
        def foo(a, b):
            if a:
                if b:
                    return 1
                    x = 2
            return 3
    '''), line=5)
    check("C14 dead in nested if after return -> verified=True",
          result["verified"] is True)

    result = verify_dead_code_in_source(make_code('''
        def foo(a, b, c):
            if a:
                if b:
                    if c:
                        deep_call()
            return None
    '''), line=6)
    check("C15 alive deeply nested -> verified=False",
          result["verified"] is False)

else:
    print("  SKIP C1-C15: ast_cfg.py not yet implemented (RED phase expected)")


# ── I1-I8: ImportGraphBuilder cycle detection ──
print("\n-- I1-I8: ImportGraphBuilder cycle detection (Tier 2) --")

try:
    from ast_cfg import verify_imports_in_repo, detect_cycle
    IMPORT_GRAPH_AVAILABLE = True
except ImportError:
    IMPORT_GRAPH_AVAILABLE = False

check("I0 import graph functions importable", IMPORT_GRAPH_AVAILABLE)


def _make_repo(files: dict):
    """Create temp repo with given {relpath: content}. Returns (tmpdir_path, Path)."""
    tmpdir = tempfile.mkdtemp(prefix="add_test_")
    root = Path(tmpdir)
    for relpath, content in files.items():
        fpath = root / relpath
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
    return tmpdir, root


if IMPORT_GRAPH_AVAILABLE:
    # I1-I3: detect_cycle unit tests
    print("\n  -- I1-I3: detect_cycle algorithm --")

    # No cycle
    graph_no_cycle = {"a": ["b"], "b": ["c"], "c": []}
    cycle = detect_cycle(graph_no_cycle)
    check("I1 no cycle -> None", cycle is None, f"got {cycle}")

    # Simple cycle a->b->a
    graph_cycle = {"a": ["b"], "b": ["a"]}
    cycle = detect_cycle(graph_cycle)
    check("I2 simple cycle a->b->a -> list", cycle is not None and len(cycle) >= 3,
          f"got {cycle}")

    # Self-loop
    graph_self = {"a": ["a"]}
    cycle = detect_cycle(graph_self)
    check("I3 self-loop -> [a, a]", cycle is not None and cycle[0] == "a",
          f"got {cycle}")

    # I4-I6: verify_imports_in_repo on real temp repos
    print("\n  -- I4-I6: verify_imports_in_repo --")

    # No cycle: a -> b -> c
    tmpdir, root = _make_repo({
        "a.py": "import b\n",
        "b.py": "import c\n",
        "c.py": "x = 1\n",
    })
    try:
        result = verify_imports_in_repo(str(root), "circular dependency between a, b, c")
        check("I4 no cycle repo -> verified=False",
              result["verified"] is False, f"got {result.get('verified')}")
        check("I4 tier=2", result.get("tier") == 2)
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Cycle: a -> b -> a
    tmpdir, root = _make_repo({
        "a.py": "import b\n",
        "b.py": "import a\n",
    })
    try:
        result = verify_imports_in_repo(str(root), "circular dependency: a imports b imports a")
        check("I5 cycle a<->b -> verified=True",
              result["verified"] is True, f"got {result.get('verified')}")
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    # External deps (numpy) not in graph
    tmpdir, root = _make_repo({
        "main.py": "import numpy\nimport helper\n",
        "helper.py": "x = 1\n",
    })
    try:
        result = verify_imports_in_repo(str(root), "circular dependency in main")
        check("I6 external dep not counted -> verified=False",
              result["verified"] is False, f"got {result.get('verified')}")
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    # I7-I8: edge cases
    print("\n  -- I7-I8: edge cases --")

    # Empty repo
    tmpdir = tempfile.mkdtemp(prefix="add_empty_")
    try:
        result = verify_imports_in_repo(tmpdir, "no imports at all")
        check("I7 empty repo -> verified=False (no cycle)",
              result["verified"] is False, f"got {result.get('verified')}")
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Syntax error file should be skipped, not crash
    tmpdir, root = _make_repo({
        "good.py": "import other\n",
        "bad.py": "def broken(:\n",
        "other.py": "x = 1\n",
    })
    try:
        result = verify_imports_in_repo(str(root), "cycle check with syntax error file")
        check("I8 syntax error file skipped -> no crash, verified=False",
              result["verified"] is False, f"got {result.get('verified')}")
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

else:
    print("  SKIP I1-I8: import graph functions not yet implemented (RED phase expected)")


# ── V1-V6: verify_findings.py Tier 2/3 fallback integration ──
print("\n-- V1-V6: verify_findings.py Tier integration --")

try:
    import verify_findings
    VF_AVAILABLE = True
except ImportError:
    VF_AVAILABLE = False

check("V0 verify_findings.py importable", VF_AVAILABLE)

if VF_AVAILABLE:
    # V1: verify_l4_structural accepts new params (repo_root, file_path)
    print("\n  -- V1-V2: signature & fallback --")

    lines = ["def foo():", "    return 1", "    x = 2"]
    try:
        result = verify_findings.verify_l4_structural(
            lines, 3, "dead code after return", ["dead_code"],
            repo_root=".", file_path="dummy.py"
        )
        check("V1 verify_l4_structural accepts repo_root/file_path", True)
        check("V2 result has 'verified' field", "verified" in result,
              f"keys: {list(result.keys())}")
    except Exception as e:
        check("V1 verify_l4_structural accepts repo_root/file_path", False, str(e))

    # V3: Tier 3 fallback when ast_cfg unavailable
    # Force Tier 2 to fail by passing nonexistent file_path
    lines = ["def foo():", "    return 1", "    x = 2"]
    try:
        result = verify_findings.verify_l4_structural(
            lines, 3, "dead code after return", ["dead_code"],
            repo_root=".", file_path="nonexistent_file_xyz.py"
        )
        # Should fall back to Tier 3 (regex) and still get a result
        check("V3 Tier 3 fallback works on Tier 2 failure",
              result.get("verified") is not None or result.get("confirmed") is not None,
              f"result: {result}")
    except Exception as e:
        check("V3 Tier 3 fallback works on Tier 2 failure", False, str(e))

    # V4: classify_claim still works
    print("\n  -- V4-V6: regression --")
    types = verify_findings.classify_claim("missing error handling")
    check("V4 classify_claim 'missing' -> ['missing']", "missing" in types, f"got {types}")

    types = verify_findings.classify_claim("dead code after return")
    check("V5 classify_claim 'dead code' -> ['dead_code']", "dead_code" in types, f"got {types}")

    types = verify_findings.classify_claim("circular dependency")
    check("V6 classify_claim 'circular dep' -> ['violates']", "violates" in types, f"got {types}")

else:
    print("  SKIP V1-V6: verify_findings.py not importable")


# ── Cross-Regression: existing test suites still pass ──
print("\n-- Cross-Regression: existing tests --")

regression_tests = [
    "test_v03_consistency.py",
    "test_v04_consistency.py",
    "test_v05_consistency.py",
    "test_v022_consistency.py",
    "test_v20_consistency.py",
    "test_v21_consistency.py",
    "test_v22_consistency.py",
    "test_v23_consistency.py",
    "test_v35_consistency.py",
]

for tname in regression_tests:
    tpath = HERE / tname
    if not tpath.exists():
        check(f"CR {tname} exists", False, "file not found")
        continue
    try:
        r = subprocess.run([sys.executable, str(tpath)],
                           capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        ok = r.returncode == 0
        check(f"CR {tname} passes", ok,
              f"rc={r.returncode}, last_line: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else 'no output'}")
    except subprocess.TimeoutExpired:
        check(f"CR {tname} passes", False, "timeout 60s")
    except Exception as e:
        check(f"CR {tname} passes", False, str(e))


# ── Summary ──
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed, {passed + failed} total")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
