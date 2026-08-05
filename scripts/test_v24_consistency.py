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


# ── J1-J10: joern_cpg.py Tier 1 (Joern CPG) ──
print("\n-- J1-J10: joern_cpg.py Tier 1 (Joern CPG) --")

try:
    import joern_cpg
    JOERN_CPG_AVAILABLE = True
except ImportError:
    JOERN_CPG_AVAILABLE = False

check("J0 joern_cpg.py importable", JOERN_CPG_AVAILABLE)

if JOERN_CPG_AVAILABLE:
    # J1: is_available returns bool
    print("\n  -- J1-J2: is_available & schema --")
    try:
        avail = joern_cpg.is_available()
        check("J1 is_available returns bool", isinstance(avail, bool),
              f"got {type(avail).__name__}")
    except Exception as e:
        check("J1 is_available returns bool", False, str(e))

    # J2: is_available respects JOERN_DISABLE env var (force-disable for test isolation)
    old_env = os.environ.get("JOERN_DISABLE")
    try:
        os.environ["JOERN_DISABLE"] = "1"
        avail_disabled = joern_cpg.is_available()
        check("J2 is_available respects JOERN_DISABLE=1", avail_disabled is False,
              f"got {avail_disabled}")
    finally:
        if old_env is None:
            os.environ.pop("JOERN_DISABLE", None)
        else:
            os.environ["JOERN_DISABLE"] = old_env

    # J3-J5: verify_dead_code returns unified schema when Joern unavailable
    print("\n  -- J3-J5: verify_dead_code schema when unavailable --")

    # Force Joern unavailable to get deterministic result without WSL2 dependency
    old_env = os.environ.get("JOERN_DISABLE")
    try:
        os.environ["JOERN_DISABLE"] = "1"
        result = joern_cpg.verify_dead_code(".", "dummy.py", 1)
        check("J3 verify_dead_code returns dict", isinstance(result, dict),
              f"got {type(result).__name__}")
        check("J3a verify_dead_code has 'verified' field", "verified" in result,
              f"keys: {list(result.keys())}")
        check("J3b verify_dead_code verified=None when unavailable",
              result.get("verified") is None, f"got {result.get('verified')}")
        check("J3c verify_dead_code tier=0 when unavailable",
              result.get("tier") == 0, f"got {result.get('tier')}")
        check("J4 verify_dead_code has latency_ms",
              "latency_ms" in result, f"keys: {list(result.keys())}")

        result_imp = joern_cpg.verify_imports(".", "circular dependency")
        check("J5 verify_imports returns dict with verified=None when unavailable",
              isinstance(result_imp, dict) and result_imp.get("verified") is None,
              f"got {result_imp}")
    finally:
        if old_env is None:
            os.environ.pop("JOERN_DISABLE", None)
        else:
            os.environ["JOERN_DISABLE"] = old_env

    # J6: _get_cache_key deterministic (same repo → same key)
    print("\n  -- J6-J7: cache key & script generation --")
    key1 = joern_cpg._get_cache_key(".")
    key2 = joern_cpg._get_cache_key(".")
    check("J6 _get_cache_key deterministic for same path", key1 == key2,
          f"{key1} != {key2}")
    check("J6a _get_cache_key returns str", isinstance(key1, str),
          f"got {type(key1).__name__}")

    # J7: Scala script generation contains correct P1-5 API
    dead_script = joern_cpg._gen_dead_code_script(42)
    check("J7a dead_code script uses lineNumber (not location.line)",
          "lineNumber" in dead_script and "location.line" not in dead_script,
          "wrong API")
    check("J7b dead_code script uses caller.l",
          "caller.l" in dead_script, "no caller.l")
    check("J7c dead_code script line param injected", "42" in dead_script)

    import_script = joern_cpg._gen_import_script()
    check("J7d import script uses cpg.imports", "cpg.imports" in import_script)
    check("J7e import script uses importedEntity (not imported)",
          "importedEntity" in import_script and "imp.imported" not in
          import_script.replace("imp.importedEntity", ""),
          "wrong field")

    # J8: _detect_wsl returns bool (Windows detection helper)
    print("\n  -- J8-J10: WSL detection & subprocess wrapping --")
    try:
        is_wsl = joern_cpg._detect_wsl()
        check("J8 _detect_wsl returns bool", isinstance(is_wsl, bool))
    except Exception as e:
        check("J8 _detect_wsl returns bool", False, str(e))

    # J9: _build_joern_parse_command returns list (cmd array)
    # Phase 6: In WSL2 mode, cmd may be wrapped as ["wsl.exe", "-e", "bash", "-c", "..."]
    # so "pythonsrc" may appear inside the bash string rather than as a list element.
    try:
        # Clear WSL2 cache to get deterministic native-mode command in tests
        if hasattr(joern_cpg, "_WSL_DETECT_CACHE"):
            joern_cpg._WSL_DETECT_CACHE = None
        old_j9 = {k: os.environ.get(k) for k in
                  ["JOERN_FORCE_WSL", "JOERN_WSL_JOERN_PATH", "JOERN_WSL_JAVA_HOME", "JOERN_DISABLE"]}
        try:
            os.environ.pop("JOERN_FORCE_WSL", None)
            os.environ.pop("JOERN_WSL_JOERN_PATH", None)
            os.environ.pop("JOERN_WSL_JAVA_HOME", None)
            cmd = joern_cpg._build_joern_parse_command(
                "/tmp/repo", "/tmp/cpg.bin", language="pythonsrc")
        finally:
            for k, v in old_j9.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            if hasattr(joern_cpg, "_WSL_DETECT_CACHE"):
                joern_cpg._WSL_DETECT_CACHE = None
        check("J9 _build_joern_parse_command returns list",
              isinstance(cmd, list) and len(cmd) > 0, f"got {cmd}")
        # pythonsrc may be a list element (native) or inside bash string (WSL2)
        cmd_str = " ".join(str(c) for c in cmd)
        check("J9a cmd uses --language pythonsrc (not python)",
              "--language" in cmd_str and "pythonsrc" in cmd_str, f"got {cmd}")
    except Exception as e:
        check("J9 _build_joern_parse_command returns list", False, str(e))

    # J10: _parse_joern_output parses key=value lines
    sample = "dead=true\nsize=0\nhas_cycle=false\n"
    parsed = joern_cpg._parse_joern_output(sample)
    check("J10 _parse_joern_output parses dead=true",
          parsed.get("dead") == "true", f"got {parsed}")
    check("J10a _parse_joern_output parses has_cycle=false",
          parsed.get("has_cycle") == "false", f"got {parsed}")
else:
    print("  SKIP J1-J10: joern_cpg.py not importable")


# ── V7-V9: verify_findings.py Tier 1/2/3 三层降级 ──
print("\n-- V7-V9: verify_findings.py Tier 1/2/3 三层降级 --")

if VF_AVAILABLE:
    # V7: verify_l4_structural calls joern_cpg before ast_cfg (Tier 1 → 2 → 3)
    print("\n  -- V7: Tier 1 integration --")
    lines = ["def foo():", "    return 1", "    x = 2"]

    # Force Joern unavailable → should fall to Tier 2/3
    old_env = os.environ.get("JOERN_DISABLE")
    try:
        os.environ["JOERN_DISABLE"] = "1"
        result = verify_findings.verify_l4_structural(
            lines, 3, "dead code after return", ["dead_code"],
            repo_root=".", file_path="dummy.py"
        )
        check("V7 Tier 1 disabled falls through to Tier 2/3",
              result.get("verified") is not None or result.get("confirmed") is not None,
              f"got {result}")
    finally:
        if old_env is None:
            os.environ.pop("JOERN_DISABLE", None)
        else:
            os.environ["JOERN_DISABLE"] = old_env

    # V8: import_related also tries Tier 1
    print("\n  -- V8: Tier 1 import_related --")
    old_env = os.environ.get("JOERN_DISABLE")
    try:
        os.environ["JOERN_DISABLE"] = "1"
        result = verify_findings.verify_l4_structural(
            lines, 1, "circular dependency import",
            ["violates", "import_related"],
            repo_root="."
        )
        check("V8 Tier 1 import_related falls through cleanly",
              "verified" in result or "confirmed" in result, f"got {result}")
    finally:
        if old_env is None:
            os.environ.pop("JOERN_DISABLE", None)
        else:
            os.environ["JOERN_DISABLE"] = old_env

    # V9: Tier 1 exceptions don't crash (Tier 2/3 fallback)
    print("\n  -- V9: Tier 1 exception safety --")
    old_env = os.environ.get("JOERN_FORCE_RAISE")
    try:
        os.environ["JOERN_FORCE_RAISE"] = "1"  # joern_cpg should catch & degrade
        os.environ["JOERN_DISABLE"] = ""  # Joern enabled but will raise
        result = verify_findings.verify_l4_structural(
            lines, 3, "dead code after return", ["dead_code"],
            repo_root=".", file_path="dummy.py"
        )
        check("V9 Tier 1 exception doesn't crash (falls through)",
              result is not None, f"got {result}")
    finally:
        os.environ.pop("JOERN_DISABLE", None)
        os.environ.pop("JOERN_FORCE_RAISE", None)
        if old_env is not None:
            os.environ["JOERN_FORCE_RAISE"] = old_env
else:
    print("  SKIP V7-V9: verify_findings.py not importable")


# ── P1A-P1D: Phase 1 verified=False → removed (Tier 1/2 结构化证明) ──
print("\n-- P1A-P1D: Phase 1 Tier 1/2 verified=False → removed --")

if VF_AVAILABLE:
    import tempfile, textwrap as _tw

    # P1A: Tier 2 dead_code verified=False → action="unverified" (removed)
    # 场景: line 在 if 分支后, ast 视为可达 (结构可达), 但 claim 说 dead
    print("\n  -- P1A: Tier 2 dead_code verified=False → removed --")
    with tempfile.TemporaryDirectory() as tmpd:
        p = Path(tmpd) / "reach.py"
        p.write_text(_tw.dedent("""\
            def foo():
                if cond:
                    return 1
                x = 2  # line 4: reachable via if-false, claim says dead
            """), encoding="utf-8")
        finding = {
            "id": "P1A", "severity": "P0",
            "claim": "dead code after return in foo",
            "evidence": {"file": "reach.py", "line_start": 4},
        }
        try:
            result, action = verify_findings.verify_single_finding(finding, tmpd)
            check("P1A Tier 2 dead_code verified=False → action=unverified",
                  action == "unverified",
                  f"action={action}, l4={result.get('l4', {}).get('verified')}")
        except Exception as e:
            check("P1A Tier 2 dead_code verified=False → action=unverified",
                  False, f"Exception: {e}")

    # P1B: Tier 3 missing verified=False → action="partial" (downgraded, NOT removed)
    print("\n  -- P1B: Tier 3 missing verified=False → downgraded --")
    with tempfile.TemporaryDirectory() as tmpd:
        p = Path(tmpd) / "mod.py"
        p.write_text("def foo():\n    return 1\n", encoding="utf-8")
        finding = {
            "id": "P1B", "severity": "P0",
            "claim": "missing error handling in foo — no try/except",
            "evidence": {"file": "mod.py", "line_start": 1},
        }
        try:
            result, action = verify_findings.verify_single_finding(finding, tmpd)
            # missing 走 Tier 3 regex; _verify_missing 找不到 try → confirmed=True → verified=True
            # 所以这里 actually verified=True. 需要构造 Tier 3 verified=False 的场景.
            # 但 missing 逻辑: found_in_context=False → confirmed=True (claim 正确)
            # 要 Tier 3 verified=False, 需要 found_in_context=True (try 存在) → confirmed=False
            # 但这样 claim "missing" 是幻觉 → 应该 downgraded (Tier 3, 不是 removed)
            pass
        except Exception as e:
            check("P1B Tier 3 missing verified=False → downgraded",
                  False, f"Exception: {e}")

    # P1B-revised: Tier 3 missing verified=False (try exists) → action="partial"
    print("\n  -- P1B-revised: Tier 3 missing (try exists) → downgraded --")
    with tempfile.TemporaryDirectory() as tmpd:
        p = Path(tmpd) / "mod.py"
        p.write_text("try:\n    x = 1\nexcept:\n    pass\n", encoding="utf-8")
        finding = {
            "id": "P1B", "severity": "P0",
            "claim": "missing error handling — no try/except for ValueError",
            "evidence": {"file": "mod.py", "line_start": 1},
        }
        try:
            result, action = verify_findings.verify_single_finding(finding, tmpd)
            l4 = result.get("l4", {})
            checks = l4.get("checks", {})
            missing_check = checks.get("missing", {})
            tier = missing_check.get("tier")
            verified = missing_check.get("verified")
            check("P1B-revised Tier 3 missing (try exists) → verified=False",
                  verified is False, f"verified={verified}, tier={tier}")
            check("P1B-revised Tier 3 verified=False → action=partial (downgraded)",
                  action == "partial",
                  f"action={action} (should be partial, not unverified)")
        except Exception as e:
            check("P1B-revised Tier 3 missing → downgraded",
                  False, f"Exception: {e}")

    # P1C: Tier 2 dead_code verified=True → action="verified" (unchanged)
    print("\n  -- P1C: Tier 2 dead_code verified=True → verified --")
    with tempfile.TemporaryDirectory() as tmpd:
        p = Path(tmpd) / "dead.py"
        p.write_text(_tw.dedent("""\
            def foo():
                return 1
                x = 2  # line 3: genuinely unreachable after return
            """), encoding="utf-8")
        finding = {
            "id": "P1C", "severity": "P0",
            "claim": "dead code after return in foo",
            "evidence": {"file": "dead.py", "line_start": 3},
        }
        try:
            result, action = verify_findings.verify_single_finding(finding, tmpd)
            check("P1C Tier 2 dead_code verified=True → action=verified",
                  action == "verified",
                  f"action={action}")
        except Exception as e:
            check("P1C Tier 2 dead_code verified=True → verified",
                  False, f"Exception: {e}")

    # P1D: verify_all_findings propagates unverified → hallucinations list
    print("\n  -- P1D: verify_all_findings removes Tier 2 disproved findings --")
    with tempfile.TemporaryDirectory() as tmpd:
        p = Path(tmpd) / "reach.py"
        p.write_text("def foo():\n    if cond:\n        return 1\n    x = 2\n", encoding="utf-8")
        findings = [
            {"id": "P1D-1", "severity": "P0",
             "claim": "dead code after return in foo",
             "evidence": {"file": "reach.py", "line_start": 4}},
        ]
        try:
            verified, hallucinations, downgraded = verify_findings.verify_all_findings(
                findings, tmpd)
            check("P1D-1a Tier 2 disproved → in hallucinations list",
                  any(h["id"] == "P1D-1" for h in hallucinations),
                  f"hallucinations: {[h['id'] for h in hallucinations]}")
            check("P1D-1b Tier 2 disproved → NOT in verified list",
                  not any(f.get("id") == "P1D-1" for f in verified),
                  f"verified ids: {[f.get('id') for f in verified]}")
        except Exception as e:
            check("P1D Tier 2 disproved → removed", False, f"Exception: {e}")

else:
    print("  SKIP P1A-P1D: verify_findings.py not importable")


# ── P2A-P2C: Phase 2 P1 可选触发 L4 ──
print("\n-- P2A-P2C: Phase 2 P1 可选触发 L4 --")

if VF_AVAILABLE:
    # P2A: P1 finding 默认仅 L1+L2 (向后兼容, 不触发 L4)
    print("\n  -- P2A: P1 默认 L1+L2 only --")
    with tempfile.TemporaryDirectory() as tmpd:
        p = Path(tmpd) / "mod.py"
        p.write_text("def foo():\n    return 1\n", encoding="utf-8")
        findings = [
            {"id": "P2A-1", "severity": "P1",
             "claim": "missing error handling in foo",
             "evidence": {"file": "mod.py", "line_start": 1}},
        ]
        try:
            verified, hallucinations, downgraded = verify_findings.verify_all_findings(
                findings, tmpd)
            f0 = verified[0] if verified else {}
            check("P2A-1a P1 default → action=verified_l1l2",
                  f0.get("_phase35_action") == "verified_l1l2",
                  f"action={f0.get('_phase35_action')}")
            check("P2A-1b P1 default → no l4 in verification",
                  "l4" not in f0.get("_phase35_verification", {}),
                  f"keys: {list(f0.get('_phase35_verification', {}).keys())}")
        except Exception as e:
            check("P2A P1 default L1+L2", False, f"Exception: {e}")

    # P2B: P1 finding + verify_p1_l4=True → 触发 L4
    print("\n  -- P2B: P1 + verify_p1_l4=True 触发 L4 --")
    with tempfile.TemporaryDirectory() as tmpd:
        p = Path(tmpd) / "reach.py"
        p.write_text("def foo():\n    if cond:\n        return 1\n    x = 2\n", encoding="utf-8")
        findings = [
            {"id": "P2B-1", "severity": "P1",
             "claim": "dead code after return in foo",
             "evidence": {"file": "reach.py", "line_start": 4}},
        ]
        try:
            verified, hallucinations, downgraded = verify_findings.verify_all_findings(
                findings, tmpd, verify_p1_l4=True)
            check("P2B-1a P1+L4 Tier 2 disproved → in hallucinations",
                  any(h["id"] == "P2B-1" for h in hallucinations),
                  f"hallucinations: {[h['id'] for h in hallucinations]}")
        except Exception as e:
            check("P2B P1+L4 triggers", False, f"Exception: {e}")

    # P2C: verify_all_findings 接受 verify_p1_l4 参数 (签名兼容)
    print("\n  -- P2C: verify_all_findings 签名兼容 --")
    import inspect
    try:
        sig = inspect.signature(verify_findings.verify_all_findings)
        check("P2C verify_all_findings has verify_p1_l4 param",
              "verify_p1_l4" in sig.parameters,
              f"params: {list(sig.parameters.keys())}")
    except Exception as e:
        check("P2C signature compatible", False, f"Exception: {e}")

else:
    print("  SKIP P2A-P2C: verify_findings.py not importable")


# ── P3A-P3C: Phase 3 context 窗口 ±25 → 全函数 ──
print("\n-- P3A-P3C: Phase 3 context 窗口扩展 --")

if VF_AVAILABLE:
    # P3A: claim "missing error handling" 但 try/except 在 30 行外 (±25 窗口看不到)
    #      全函数窗口应该能找到 try → verified=False (claim 是幻觉)
    print("\n  -- P3A: 全函数窗口检测到远端 try/except --")
    with tempfile.TemporaryDirectory() as tmpd:
        # 构造: 函数内 line 5 claim "missing error handling"
        #        但 try/except 在 line 40 (距离 35 行, ±25 窗口看不到)
        p = Path(tmpd) / "mod.py"
        lines = ["def foo():"]
        for i in range(1, 35):
            lines.append(f"    x{i} = {i}")
        lines.append("    try:")           # line 36
        lines.append("        y = 1")      # line 37
        lines.append("    except Exception:")  # line 38
        lines.append("        pass")       # line 39
        lines.append("    return 1")       # line 40
        p.write_text("\n".join(lines), encoding="utf-8")

        finding = {
            "id": "P3A", "severity": "P0",
            "claim": "missing error handling in foo — no try/except",
            "evidence": {"file": "mod.py", "line_start": 5},
        }
        try:
            result, action = verify_findings.verify_single_finding(finding, tmpd)
            l4 = result.get("l4", {})
            checks = l4.get("checks", {})
            missing = checks.get("missing", {})
            check("P3A-1a 全函数窗口 → missing.found_in_context=True",
                  missing.get("found_in_context") is True,
                  f"found_in_context={missing.get('found_in_context')}")
            check("P3A-1b 全函数窗口 → missing.verified=False (claim 是幻觉)",
                  missing.get("verified") is False,
                  f"verified={missing.get('verified')}")
        except Exception as e:
            check("P3A 全函数窗口", False, f"Exception: {e}")

    # P3B: 模块级 (不在函数内) → 回退到 ±50 行
    # 直接测试 _get_function_context 函数
    print("\n  -- P3B: 模块级 → ±50 回退 --")
    try:
        # 70 行模块级代码, try 在 line 41
        mod_lines = [f"x{i} = {i}" for i in range(1, 41)]
        mod_lines.append("try:")              # line 41
        mod_lines.append("    y = 1")         # line 42
        mod_lines.append("except Exception:")  # line 43
        mod_lines.append("    pass")           # line 44
        mod_lines.extend([f"x{i} = {i}" for i in range(45, 70)])

        # line 5 不在函数内 → 回退到 ±50
        ctx = verify_findings._get_function_context(mod_lines, 5)
        check("P3B-1a 模块级 ±50 回退包含 try:",
              "try:" in ctx,
              f"context length={len(ctx)}, 'try:' in ctx: {'try:' in ctx}")
        check("P3B-1b ±50 窗口覆盖 line 41 (距离 36 行, 原 ±25 看不到)",
              "except Exception:" in ctx,
              f"'except Exception:' in ctx: {'except Exception:' in ctx}")
    except Exception as e:
        check("P3B 模块级 ±50 回退", False, f"Exception: {e}")

else:
    print("  SKIP P3A-P3C: verify_findings.py not importable")


# ── P4A-P4E: Phase 4 import_related 模块对解析 ──
print("\n-- P4A-P4E: Phase 4 import_related 模块对解析 --")

if IMPORT_GRAPH_AVAILABLE:
    import shutil

    # P4A: claim 指明 a<->b 循环, 实际存在 a<->b → verified=True
    print("\n  -- P4A: claim 指明 a<->b, 实际 a<->b → True --")
    tmpdir, root = _make_repo({
        "a.py": "import b\n",
        "b.py": "import a\n",
    })
    try:
        result = verify_imports_in_repo(str(root),
            "circular dependency between a and b")
        check("P4A claim a<->b 实际 a<->b → verified=True",
              result["verified"] is True, f"got {result.get('verified')}")
        check("P4A evidence mentions cycle path",
              "a" in result.get("evidence", "") and "b" in result.get("evidence", ""),
              f"evidence: {result.get('evidence')}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # P4B: claim 指明 c<->d 循环, 但实际只有 a<->b → verified=False (语义错位 FN 修复)
    print("\n  -- P4B: claim 指明 c<->d, 实际 a<->b → False (修复 FN) --")
    tmpdir, root = _make_repo({
        "a.py": "import b\n",
        "b.py": "import a\n",
        "c.py": "x = 1\n",
        "d.py": "y = 2\n",
    })
    try:
        result = verify_imports_in_repo(str(root),
            "circular dependency between c and d")
        check("P4B claim c<->d 实际 a<->b → verified=False (语义错位修复)",
              result["verified"] is False, f"got {result.get('verified')}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # P4C: claim 无具体模块 (generic "circular dependency") → 回退到原行为 (任意循环 True)
    print("\n  -- P4C: claim 无具体模块 → 回退任意循环 --")
    tmpdir, root = _make_repo({
        "a.py": "import b\n",
        "b.py": "import a\n",
    })
    try:
        result = verify_imports_in_repo(str(root), "circular dependency")
        check("P4C generic claim 有循环 → verified=True (回退行为)",
              result["verified"] is True, f"got {result.get('verified')}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # P4D: claim 指明 a->b->a (链式), 实际存在 → verified=True
    print("\n  -- P4D: claim 链式 a->b->a → True --")
    tmpdir, root = _make_repo({
        "a.py": "import b\n",
        "b.py": "import a\n",
    })
    try:
        result = verify_imports_in_repo(str(root),
            "circular dependency: a imports b imports a")
        check("P4D claim 链式 a->b->a → verified=True",
              result["verified"] is True, f"got {result.get('verified')}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # P4E: claim 指明 a, b, c 三方循环, 实际 a<->b (c 不在循环中) → verified=False
    print("\n  -- P4E: claim a,b,c 三方循环, 实际仅 a<->b → False --")
    tmpdir, root = _make_repo({
        "a.py": "import b\n",
        "b.py": "import a\n",
        "c.py": "import a\n",  # c 依赖 a 但 a 不依赖 c, 不在循环中
    })
    try:
        result = verify_imports_in_repo(str(root),
            "circular dependency among a, b, and c")
        check("P4E claim a,b,c 三方但实际 a<->b → verified=False",
              result["verified"] is False, f"got {result.get('verified')}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # P4F: claim 模块名带 .py 后缀 → 应规范化为模块名
    print("\n  -- P4F: claim 模块名带 .py 后缀 → 规范化 --")
    tmpdir, root = _make_repo({
        "a.py": "import b\n",
        "b.py": "import a\n",
    })
    try:
        result = verify_imports_in_repo(str(root),
            "circular dependency between a.py and b.py")
        check("P4F claim 带 .py 后缀 → 规范化后匹配 → verified=True",
              result["verified"] is True, f"got {result.get('verified')}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # P4G: claim 指明单模块自循环 a->a, 实际存在 → verified=True
    print("\n  -- P4G: claim 单模块自循环 a->a → True --")
    tmpdir, root = _make_repo({
        "a.py": "import a\n",  # 自循环 (罕见但合法语法)
    })
    try:
        result = verify_imports_in_repo(str(root),
            "circular dependency: a imports itself")
        check("P4G claim a->a 自循环 → verified=True",
              result["verified"] is True, f"got {result.get('verified')}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

else:
    print("  SKIP P4A-P4G: import graph functions not importable")


# ── P5A-P5C: Phase 5 Tier 2 dead_code 假阳性修复 (OSS-H3) ──
print("\n-- P5A-P5C: Phase 5 Tier 2 dead_code 假阳性修复 (OSS-H3) --")

if AST_CFG_AVAILABLE:
    from ast_cfg import _find_enclosing_function
    import ast as _ast

    # P5A: _find_enclosing_function 返回最内层函数 (最小 span)
    print("\n  -- P5A: _find_enclosing_function 返回最内层函数 --")
    # 场景: outer (1-20) 包含 inner (5-10), target_line=7
    # 应返回 inner (span=5), 不是 outer (span=19)
    src = make_code('''
        def outer():
            x = 1
            def inner():
                y = 2
                z = 3
                return y + z
            return x + inner()

        result = outer()
    ''')
    tree = _ast.parse(src)
    # inner 函数定义在 line 3 (dedent 后), target line 5 (y=2 在 inner 内)
    # 找到 inner 的实际 lineno
    inner_node = None
    outer_node = None
    for node in _ast.walk(tree):
        if isinstance(node, _ast.FunctionDef):
            if node.name == "outer":
                outer_node = node
            elif node.name == "inner":
                inner_node = node
    check("P5A-0a 找到 outer 函数", outer_node is not None)
    check("P5A-0b 找到 inner 函数", inner_node is not None)

    if inner_node and outer_node:
        # target_line 在 inner 函数体内
        target_line = inner_node.lineno + 1
        found = _find_enclosing_function(tree, target_line)
        check("P5A-1 返回 inner (最内层), 不是 outer",
              found is not None and found.name == "inner",
              f"got {found.name if found else None}")
        check("P5A-2 inner span < outer span",
              (inner_node.end_lineno - inner_node.lineno) <
              (outer_node.end_lineno - outer_node.lineno))

    # P5B: 模拟 OSS-H3 场景 — 外层函数嵌套内层函数, target 是内层定义行
    # 场景: outer (1-10) 嵌套 inner (3-6), target=3 (inner 定义行)
    # 应返回 inner (span=3), 不是 outer (span=9)
    print("\n  -- P5B: 模拟 OSS-H3 嵌套函数, target=内层定义行 --")
    src_oss = make_code('''
        def outer():
            x = 1
            def inner():
                y = 2
                return y
            return inner()
        outer()
    ''')
    tree_oss = _ast.parse(src_oss)
    outer_func_node = None
    inner_func_node = None
    for node in _ast.walk(tree_oss):
        if isinstance(node, _ast.FunctionDef):
            if node.name == "outer":
                outer_func_node = node
            elif node.name == "inner":
                inner_func_node = node

    check("P5B-0a 找到 outer", outer_func_node is not None)
    check("P5B-0b 找到 inner", inner_func_node is not None)

    if outer_func_node and inner_func_node:
        # target_line = inner 的定义行 (同时在 outer 和 inner 范围内)
        target_line = inner_func_node.lineno
        outer_span = outer_func_node.end_lineno - outer_func_node.lineno
        inner_span = inner_func_node.end_lineno - inner_func_node.lineno
        check("P5B-0c inner span < outer span",
              inner_span < outer_span,
              f"inner_span={inner_span}, outer_span={outer_span}")
        check("P5B-0d target_line 在 outer 范围内",
              outer_func_node.lineno <= target_line <= outer_func_node.end_lineno,
              f"outer range: {outer_func_node.lineno}-{outer_func_node.end_lineno}")
        check("P5B-0e target_line 在 inner 范围内",
              inner_func_node.lineno <= target_line <= inner_func_node.end_lineno,
              f"inner range: {inner_func_node.lineno}-{inner_func_node.end_lineno}")

        found = _find_enclosing_function(tree_oss, target_line)
        check("P5B-1 返回 inner (最小 span), 不是 outer",
              found is not None and found.name == "inner",
              f"got {found.name if found else None}")

    # P5C: verify_dead_code_in_source 对方法定义行返回 verified=False (reachable)
    # 这是 OSS-H3 的核心修复: line 100 (def __init__) 应该是 reachable, 不是 None
    print("\n  -- P5C: verify_dead_code_in_source 对方法定义行 → reachable --")
    src_method = make_code('''
        class MyClass:
            """Docstring."""
            # comment
            def __init__(self, x):
                self.x = x
                return None
    ''')
    tree_method = _ast.parse(src_method)
    init_node = None
    for node in _ast.walk(tree_method):
        if isinstance(node, _ast.FunctionDef) and node.name == "__init__":
            init_node = node
            break

    if init_node:
        # 对 __init__ 定义行做 dead_code 验证
        result = verify_dead_code_in_source(src_method, init_node.lineno)
        check("P5C-1 方法定义行 → verified=False (reachable, 不是 dead code)",
              result["verified"] is False,
              f"got {result.get('verified')}, evidence: {result.get('evidence')}")
        check("P5C-2 tier=2 (不是 None 降级到 Tier 3)",
              result.get("tier") == 2,
              f"got tier={result.get('tier')}")

    # P5D: 非语句行 (else:/try:/except:) → verified=False, 不是 None
    # OSS-H3 根因: line 100 是 'else:' 不是 CFG 节点 → None → Tier 3 假阳性
    print("\n  -- P5D: 非语句行 (else:/except:) → verified=False --")

    # else: 行
    result = verify_dead_code_in_source(make_code('''
        def foo(cond):
            if cond:
                return 1
            else:
                return 2
    '''), line=4)  # line 4 is "else:"
    check("P5D-1 else: 行 → verified=False (不是 dead code)",
          result["verified"] is False,
          f"got {result.get('verified')}, evidence: {result.get('evidence')}")
    check("P5D-1a else: 行 → tier=2 (不降级到 Tier 3)",
          result.get("tier") == 2, f"got tier={result.get('tier')}")

    # except: 行
    result = verify_dead_code_in_source(make_code('''
        def foo():
            try:
                x = 1
            except:
                pass
    '''), line=4)  # line 4 is "except:"
    check("P5D-2 except: 行 → verified=False (不是 dead code)",
          result["verified"] is False,
          f"got {result.get('verified')}")

    # 空行
    result = verify_dead_code_in_source(make_code('''
        def foo():
            x = 1

            return x
    '''), line=3)  # line 3 is blank
    check("P5D-3 空行 → verified=False (不是 dead code)",
          result["verified"] is False,
          f"got {result.get('verified')}")

    # 注释行
    result = verify_dead_code_in_source(make_code('''
        def foo():
            x = 1
            # this is a comment
            return x
    '''), line=3)  # line 3 is comment
    check("P5D-4 注释行 → verified=False (不是 dead code)",
          result["verified"] is False,
          f"got {result.get('verified')}")

    # P5E: 回归 — 真正的 dead code 仍正确识别
    print("\n  -- P5E: 回归 真正的 dead code → verified=True --")
    result = verify_dead_code_in_source(make_code('''
        def foo():
            return 1
            x = 2
    '''), line=3)
    check("P5E-1 真 dead code → verified=True (回归不变)",
          result["verified"] is True,
          f"got {result.get('verified')}")

    # 回归: reachable 语句
    result = verify_dead_code_in_source(make_code('''
        def foo():
            x = 1
            return x
    '''), line=2)
    check("P5E-2 reachable 语句 → verified=False (回归不变)",
          result["verified"] is False,
          f"got {result.get('verified')}")

else:
    print("  SKIP P5A-P5E: ast_cfg.py not importable")


# ── P6A-P6G: Phase 6 Joern Windows→WSL2 调用链路修复 ──
print("\n-- P6A-P6G: Phase 6 Joern Windows→WSL2 调用链路 --")

if JOERN_CPG_AVAILABLE:
    import tempfile as _tf
    import shutil as _shutil

    # Helper: save/restore env vars for test isolation
    _env_keys_p6 = ["JOERN_FORCE_WSL", "JOERN_WSL_JOERN_PATH",
                    "JOERN_WSL_JAVA_HOME", "JOERN_DISABLE", "JOERN_HOME"]

    def _save_env_p6():
        return {k: os.environ.get(k) for k in _env_keys_p6}

    def _restore_env_p6(saved):
        for k in _env_keys_p6:
            if saved[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = saved[k]

    # P6A: _translate_path_to_wsl 正确转换 Windows 驱动器路径
    print("\n  -- P6A: _translate_path_to_wsl 路径转换 --")
    try:
        # Windows drive path -> /mnt/<drive>/...
        wsl_path = joern_cpg._translate_path_to_wsl("F:\\Coding\\audit\\file.py")
        check("P6A-1 F:\\... -> /mnt/f/...",
              wsl_path == "/mnt/f/Coding/audit/file.py",
              f"got {wsl_path}")
        # Lowercase drive
        wsl_path2 = joern_cpg._translate_path_to_wsl("f:\\test.py")
        check("P6A-2 lowercase drive f: -> /mnt/f/...",
              wsl_path2 == "/mnt/f/test.py", f"got {wsl_path2}")
        # Linux path unchanged
        wsl_path3 = joern_cpg._translate_path_to_wsl("/home/user/repo")
        check("P6A-3 Linux path unchanged",
              wsl_path3 == "/home/user/repo", f"got {wsl_path3}")
        # Backslash conversion
        wsl_path4 = joern_cpg._translate_path_to_wsl("C:\\a\\b\\c.py")
        check("P6A-4 backslashes -> forward slashes",
              wsl_path4 == "/mnt/c/a/b/c.py", f"got {wsl_path4}")
    except Exception as e:
        check("P6A _translate_path_to_wsl", False, f"Exception: {e}")

    # P6B: _detect_wsl_from_windows() 新函数存在且返回 dict|None
    print("\n  -- P6B: _detect_wsl_from_windows 函数 --")
    try:
        has_func = hasattr(joern_cpg, "_detect_wsl_from_windows")
        check("P6B-0 _detect_wsl_from_windows 函数存在", has_func,
              "函数未定义 — Phase 6 尚未实现")
    except Exception as e:
        check("P6B-0 _detect_wsl_from_windows 函数存在", False, f"Exception: {e}")

    if hasattr(joern_cpg, "_detect_wsl_from_windows"):
        # 用 JOERN_FORCE_WSL=1 + 显式路径覆盖, 避免 WSL2 实际调用
        saved = _save_env_p6()
        try:
            os.environ["JOERN_FORCE_WSL"] = "1"
            os.environ["JOERN_WSL_JOERN_PATH"] = "/home/test/bin/joern/joern-cli/joern-parse"
            os.environ["JOERN_WSL_JAVA_HOME"] = "/home/test/jdk"
            os.environ.pop("JOERN_DISABLE", None)
            # Phase 6 fix: 清除缓存, 否则 J9 的真实 WSL2 检测结果会污染
            joern_cpg._WSL_DETECT_CACHE = None
            info = joern_cpg._detect_wsl_from_windows()
            check("P6B-1 强制 WSL2 模式返回 dict",
                  isinstance(info, dict), f"got {type(info).__name__}: {info}")
            if isinstance(info, dict):
                check("P6B-2 dict 包含 joern_path",
                      "joern_path" in info, f"keys: {list(info.keys())}")
                check("P6B-3 joern_path 与 env 覆盖一致",
                      info.get("joern_path") == "/home/test/bin/joern/joern-cli/joern-parse",
                      f"got {info.get('joern_path')}")
                check("P6B-4 dict 包含 java_home",
                      "java_home" in info, f"keys: {list(info.keys())}")
                check("P6B-5 java_home 与 env 覆盖一致",
                      info.get("java_home") == "/home/test/jdk",
                      f"got {info.get('java_home')}")
        finally:
            _restore_env_p6(saved)
            joern_cpg._WSL_DETECT_CACHE = None

        # 不强制时: Linux 上应返回 None (非 Windows)
        saved2 = _save_env_p6()
        try:
            os.environ.pop("JOERN_FORCE_WSL", None)
            os.environ.pop("JOERN_WSL_JOERN_PATH", None)
            os.environ.pop("JOERN_WSL_JAVA_HOME", None)
            joern_cpg._WSL_DETECT_CACHE = None
            info2 = joern_cpg._detect_wsl_from_windows()
            # 在 Linux 上 (CI) 应返回 None; 在 Windows 上可能返回 dict 或 None
            check("P6B-6 非强制模式返回 dict|None",
                  info2 is None or isinstance(info2, dict),
                  f"got {type(info2).__name__}")
        finally:
            _restore_env_p6(saved2)
            joern_cpg._WSL_DETECT_CACHE = None

    # P6C: _find_joern_binary() 在 WSL2 强制模式下返回路径
    print("\n  -- P6C: _find_joern_binary WSL2 模式 --")
    saved = _save_env_p6()
    try:
        os.environ["JOERN_FORCE_WSL"] = "1"
        os.environ["JOERN_WSL_JOERN_PATH"] = "/home/test/bin/joern/joern-cli/joern-parse"
        os.environ["JOERN_WSL_JAVA_HOME"] = "/home/test/jdk"
        os.environ.pop("JOERN_DISABLE", None)
        os.environ.pop("JOERN_HOME", None)
        joern_cpg._WSL_DETECT_CACHE = None
        # 清除 PATH 中的 joern (用空 PATH 不现实, 改为直接调用)
        binary = joern_cpg._find_joern_binary()
        check("P6C-1 WSL2 强制模式返回非 None",
              binary is not None, f"got {binary}")
        if binary is not None:
            check("P6C-2 返回 WSL2 路径 (包含 /home/test)",
                  "/home/test" in str(binary) or "wsl" in str(binary).lower(),
                  f"got {binary}")
    finally:
        _restore_env_p6(saved)
        joern_cpg._WSL_DETECT_CACHE = None

    # P6D: _build_joern_parse_command 在 WSL2 模式下包含 wsl.exe
    print("\n  -- P6D: _build_joern_parse_command WSL2 包装 --")
    saved = _save_env_p6()
    try:
        os.environ["JOERN_FORCE_WSL"] = "1"
        os.environ["JOERN_WSL_JOERN_PATH"] = "/home/test/bin/joern/joern-cli/joern-parse"
        os.environ["JOERN_WSL_JAVA_HOME"] = "/home/test/jdk"
        os.environ.pop("JOERN_DISABLE", None)
        os.environ.pop("JOERN_HOME", None)
        # 清除缓存避免污染
        if hasattr(joern_cpg, "_WSL_DETECT_CACHE"):
            joern_cpg._WSL_DETECT_CACHE = None
        cmd = joern_cpg._build_joern_parse_command(
            "/mnt/f/repo", "/tmp/cpg.bin", language="pythonsrc")
        check("P6D-1 WSL2 模式 cmd 包含 wsl.exe",
              any("wsl.exe" in str(c).lower() or c == "wsl.exe" for c in cmd),
              f"got {cmd}")
        # WSL2 模式下 --language pythonsrc 在 bash 字符串内, 用 join 检查
        cmd_str = " ".join(str(c) for c in cmd)
        check("P6D-2 cmd 仍包含 --language pythonsrc",
              "pythonsrc" in cmd_str, f"got {cmd}")
        check("P6D-3 cmd 包含 joern-parse 或 joern 路径",
              any("joern" in str(c).lower() for c in cmd),
              f"got {cmd}")
    finally:
        _restore_env_p6(saved)

    # P6E: _build_joern_query_command 在 WSL2 模式下包含 wsl.exe
    print("\n  -- P6E: _build_joern_query_command WSL2 包装 --")
    saved = _save_env_p6()
    try:
        os.environ["JOERN_FORCE_WSL"] = "1"
        os.environ["JOERN_WSL_JOERN_PATH"] = "/home/test/bin/joern/joern-cli/joern-parse"
        os.environ["JOERN_WSL_JAVA_HOME"] = "/home/test/jdk"
        os.environ.pop("JOERN_DISABLE", None)
        os.environ.pop("JOERN_HOME", None)
        if hasattr(joern_cpg, "_WSL_DETECT_CACHE"):
            joern_cpg._WSL_DETECT_CACHE = None
        cmd = joern_cpg._build_joern_query_command("/tmp/cpg.bin", "/tmp/query.sc")
        check("P6E-1 WSL2 模式 cmd 包含 wsl.exe",
              any("wsl.exe" in str(c).lower() or c == "wsl.exe" for c in cmd),
              f"got {cmd}")
        # WSL2 模式下 --script 在 bash 字符串内, 用 join 检查
        cmd_str = " ".join(str(c) for c in cmd)
        check("P6E-2 cmd 包含 --script",
              "--script" in cmd_str, f"got {cmd}")
    finally:
        _restore_env_p6(saved)

    # P6F: _build_clean_env 在 WSL2 模式下设置 JAVA_HOME
    print("\n  -- P6F: _build_clean_env WSL2 JAVA_HOME --")
    saved = _save_env_p6()
    try:
        os.environ["JOERN_FORCE_WSL"] = "1"
        os.environ["JOERN_WSL_JOERN_PATH"] = "/home/test/bin/joern/joern-cli/joern-parse"
        os.environ["JOERN_WSL_JAVA_HOME"] = "/home/test/jdk"
        os.environ.pop("JOERN_DISABLE", None)
        os.environ.pop("JOERN_HOME", None)
        if hasattr(joern_cpg, "_WSL_DETECT_CACHE"):
            joern_cpg._WSL_DETECT_CACHE = None
        env = joern_cpg._build_clean_env()
        check("P6F-1 env 包含 JAVA_HOME",
              "JAVA_HOME" in env, f"keys: {list(env.keys())[:5]}")
        # 在 WSL2 强制模式下, JAVA_HOME 应该是 WSL2 路径 (不是 Windows 路径)
        java_home_val = env.get("JAVA_HOME", "")
        check("P6F-2 WSL2 JAVA_HOME 是 Linux 路径 (/home/test/jdk)",
              java_home_val == "/home/test/jdk" or "/home/test" in java_home_val,
              f"got JAVA_HOME={java_home_val}")
    finally:
        _restore_env_p6(saved)

    # P6G: is_available() 在 WSL2 强制模式下返回 True
    print("\n  -- P6G: is_available WSL2 模式 --")
    saved = _save_env_p6()
    try:
        os.environ["JOERN_FORCE_WSL"] = "1"
        os.environ["JOERN_WSL_JOERN_PATH"] = "/home/test/bin/joern/joern-cli/joern-parse"
        os.environ["JOERN_WSL_JAVA_HOME"] = "/home/test/jdk"
        os.environ.pop("JOERN_DISABLE", None)
        os.environ.pop("JOERN_HOME", None)
        if hasattr(joern_cpg, "_WSL_DETECT_CACHE"):
            joern_cpg._WSL_DETECT_CACHE = None
        avail = joern_cpg.is_available()
        check("P6G-1 WSL2 强制模式 is_available=True",
              avail is True, f"got {avail}")
    finally:
        _restore_env_p6(saved)

    # P6G-2: JOERN_DISABLE 仍优先于 WSL2 (测试隔离)
    saved = _save_env_p6()
    try:
        os.environ["JOERN_FORCE_WSL"] = "1"
        os.environ["JOERN_WSL_JOERN_PATH"] = "/home/test/bin/joern/joern-cli/joern-parse"
        os.environ["JOERN_DISABLE"] = "1"
        if hasattr(joern_cpg, "_WSL_DETECT_CACHE"):
            joern_cpg._WSL_DETECT_CACHE = None
        avail = joern_cpg.is_available()
        check("P6G-2 JOERN_DISABLE=1 优先 → is_available=False",
              avail is False, f"got {avail}")
    finally:
        _restore_env_p6(saved)

    # 清理缓存避免污染后续测试
    if hasattr(joern_cpg, "_WSL_DETECT_CACHE"):
        joern_cpg._WSL_DETECT_CACHE = None

else:
    print("  SKIP P6A-P6G: joern_cpg.py not importable")


# ── P7A-P7D: Phase 7 Hallucination Fix (@main + <module> exclusion) ──
# 源码级别溯源发现两个幻觉:
#   H1: @main 注解在 Joern v4.0.595 script mode 不工作 (所有 @main 脚本编译失败)
#       E2E 验证: 5种裸脚本全部 returncode=0, 5种 @main 脚本全部 returncode=1
#       根因: ScalaReplPP.main 编译失败 (Joern script mode 用 REPL 语义不是 @main)
#       修复: 移除 @main, 移除 loadCpg, 用位置参数 CPG (cpg 自动可用)
#
#   H2: <module> 排除逻辑错误 (方法只被 <module> 调用 ≠ dead code)
#       E2E 验证: def foo(): ... foo() → dead=true (错误, foo 被 <module> 调用)
#       根因: <module> 是 Python 模块入口, 方法被它调用 = reachable
#       修复: 移除 .filter(_.name != "<module>"), 有任何 caller = not dead
print("\n-- P7A-P7D: Phase 7 Hallucination Fix (@main + <module>) --")

if JOERN_CPG_AVAILABLE:
    # P7A: _gen_dead_code_script 不应包含 @main (幻觉修复)
    print("\n  -- P7A: dead_code script 不含 @main --")
    dead_script = joern_cpg._gen_dead_code_script(42)
    check("P7A-1 dead_code script 不含 @main",
          "@main" not in dead_script,
          f"still has @main: {dead_script[:100]}")
    check("P7A-2 dead_code script 不含 loadCpg",
          "loadCpg" not in dead_script,
          f"still has loadCpg: {dead_script[:100]}")
    check("P7A-3 dead_code script 不含 .get (loadCpg残留)",
          ".get" not in dead_script,
          f"still has .get: {dead_script[:200]}")
    # 裸脚本方式: 直接用 cpg 变量 (位置参数自动可用)
    check("P7A-4 dead_code script 用 cpg 直接访问",
          "cpg.method" in dead_script,
          f"no cpg.method: {dead_script[:200]}")

    # P7B: _gen_dead_code_script 不应排除 <module> (幻觉修复)
    print("\n  -- P7B: dead_code script 不排除 <module> --")
    check("P7B-1 dead_code script 不含 <module> 过滤",
          "<module>" not in dead_script,
          f"still filters <module>: {dead_script[:300]}")
    check("P7B-2 dead_code script 用 callers.isEmpty (任何 caller = not dead)",
          "callers.isEmpty" in dead_script or "isEmpty" in dead_script,
          f"no isEmpty: {dead_script[:300]}")

    # P7C: _gen_import_script 不应包含 @main
    print("\n  -- P7C: import script 不含 @main --")
    import_script = joern_cpg._gen_import_script()
    check("P7C-1 import script 不含 @main",
          "@main" not in import_script,
          f"still has @main: {import_script[:100]}")
    check("P7C-2 import script 不含 loadCpg",
          "loadCpg" not in import_script,
          f"still has loadCpg: {import_script[:100]}")
    check("P7C-3 import script 用 cpg.imports 直接访问",
          "cpg.imports" in import_script,
          f"no cpg.imports: {import_script[:200]}")

    # P7D: _build_joern_query_command 用位置参数 (不是 --param)
    print("\n  -- P7D: query command 用位置参数 CPG --")
    saved = _save_env_p6()
    try:
        os.environ["JOERN_FORCE_WSL"] = "1"
        os.environ["JOERN_WSL_JOERN_PATH"] = "/home/test/bin/joern/joern-cli/joern-parse"
        os.environ["JOERN_WSL_JAVA_HOME"] = "/home/test/jdk"
        os.environ.pop("JOERN_DISABLE", None)
        os.environ.pop("JOERN_HOME", None)
        if hasattr(joern_cpg, "_WSL_DETECT_CACHE"):
            joern_cpg._WSL_DETECT_CACHE = None
        cmd = joern_cpg._build_joern_query_command("/tmp/cpg.bin", "/tmp/query.sc")
        cmd_str = " ".join(str(c) for c in cmd)
        # 位置参数: CPG 路径直接出现在 --script 之后, 不用 --param cpgFile=
        check("P7D-1 cmd 不含 --param cpgFile=",
              "--param cpgFile=" not in cmd_str and "cpgFile=" not in cmd_str,
              f"still uses --param: {cmd_str[:200]}")
        check("P7D-2 cmd 包含 CPG 路径 (位置参数)",
              "/tmp/cpg.bin" in cmd_str,
              f"no CPG path in cmd: {cmd_str[:200]}")
        check("P7D-3 cmd 仍包含 --script",
              "--script" in cmd_str, f"got {cmd_str[:200]}")
    finally:
        _restore_env_p6(saved)

else:
    print("  SKIP P7A-P7D: joern_cpg.py not importable")


# ── P8A-P8C: Phase 8 Import Node Naming + Degradation Logic Fix ─────────
# 源码级别溯源发现两个真实 bug (非幻觉):
#
#   B1: joern_cpg.py _gen_import_script() 节点命名不一致
#       src = imp.file.head.name = "mod_a.py" (带 .py 后缀)
#       dst = imp.importedEntity    = "mod_b"   (不带 .py)
#       graph = {"mod_a.py": {"mod_b"}, "mod_b.py": {"mod_a"}}
#       DFS 找不到回边 (mod_b 不是 graph 的 key, mod_b.py 才是)
#       E2E 验证: mod_a<->mod_b cycle → has_cycle=false (错误)
#       ast_cfg.py L418 用 with_suffix("") 正确去掉了 .py
#       修复: Scala 脚本中 src 去掉 .py 后缀, 统一节点命名
#
#   B2: verify_findings.py 降级逻辑 - Joern verified=False 不降级
#       dead_code: Joern method-level vs claim statement-level 语义不匹配
#         Joern verified=False (方法被调用) ≠ statement-level 没有 dead code
#         修复: verified is not True (None 或 False) → 降级到 Tier 2
#       import_related: Joern Python 支持可能不完善 (pysrc2cpg)
#         保守策略: verified=False → 降级到 Tier 2 做双重验证
#         如果 Tier 2 也 False → 最终 False; 如果 Tier 2 True → 纠正 Joern 误判
print("\n-- P8A-P8C: Phase 8 Import Node Naming + Degradation Fix --")

if JOERN_CPG_AVAILABLE:
    # P8A: _gen_import_script 节点命名统一 (src 去掉 .py)
    print("\n  -- P8A: import script 节点命名统一 --")
    import_script_p8 = joern_cpg._gen_import_script()
    # 修复: src 应该去掉 .py 后缀
    # 实现方式: endsWith(".py") + substring 或 replaceAll 或 stripSuffix
    check("P8A-1 import script 包含 .py 去除逻辑",
          "replaceAll" in import_script_p8 or "stripSuffix" in import_script_p8 or
          'endsWith(".py")' in import_script_p8 or 'endsWith(".py")' in import_script_p8 or
          ".py" in import_script_p8 and "substring" in import_script_p8,
          f"no .py stripping in script: {import_script_p8[:400]}")
    # 不应直接用 imp.file.head.name 作为节点 (会导致 mod_a.py vs mod_b 不匹配)
    check("P8A-2 import script 不直接用 file.name 作为 graph 节点",
          "graph(src)" in import_script_p8 or "graph(updatedSrc)" in import_script_p8 or
          "graph(src" in import_script_p8,
          f"no graph node assignment: {import_script_p8[:400]}")

    # P8B: _gen_import_script 生成的脚本逻辑正确性 (静态检查)
    print("\n  -- P8B: import script 逻辑正确性 --")
    # 确保脚本仍然用 cpg.imports.l (P1-5 verified API)
    check("P8B-1 import script 仍用 cpg.imports.l",
          "cpg.imports.l" in import_script_p8,
          f"no cpg.imports.l: {import_script_p8[:200]}")
    # 确保脚本仍然用 imp.importedEntity (P1-5 verified API)
    check("P8B-2 import script 仍用 imp.importedEntity",
          "imp.importedEntity" in import_script_p8,
          f"no imp.importedEntity: {import_script_p8[:200]}")
    # 确保 DFS 3-color 检测仍然存在
    check("P8B-3 import script 仍有 DFS 3-color 检测",
          "hasCycle" in import_script_p8 and "GRAY" in import_script_p8,
          f"no DFS cycle detection: {import_script_p8[:400]}")

else:
    print("  SKIP P8A-P8B: joern_cpg.py not importable")


# P8C: verify_findings.py 降级逻辑 - Joern verified=False → 降级到 Tier 2
print("\n  -- P8C: 降级逻辑 (Joern verified=False → Tier 2) --")

if VF_AVAILABLE:
    # 创建临时 repo 测试降级逻辑
    tmpdir_p8 = tempfile.mkdtemp(prefix="add_p8_")
    root_p8 = Path(tmpdir_p8)
    try:
        # 场景: process 函数被调用 (Joern verified=False, method reachable)
        # 但 return 后有 dead code (Tier 2 应检测到 statement-level dead)
        (root_p8 / "alive_method_dead_stmt.py").write_text(textwrap.dedent("""\
            def process(data):
                if not data:
                    return None
                    cleanup()
                return data.strip()

            process(None)
        """), encoding="utf-8")

        lines_p8 = (root_p8 / "alive_method_dead_stmt.py").read_text().split("\n")

        # P8C-1: 用 monkey-patching 强制 Joern 返回 verified=False
        # 模拟 Joern 可用但方法被调用 (method reachable) 的场景
        print("\n  -- P8C-1: mock Joern verified=False → degrade to Tier 2 --")
        original_verify_dead_code = None
        try:
            import joern_cpg as _jc
            original_verify_dead_code = _jc.verify_dead_code
            _jc.verify_dead_code = lambda rr, fp, ln: {
                "verified": False, "evidence": "mock: method reachable",
                "tier": 1, "latency_ms": 10
            }
        except ImportError:
            # joern_cpg 不可用, 用 verify_findings 内部的 mock
            pass

        try:
            result_p8 = verify_findings.verify_l4_structural(
                lines_p8, 4, "dead code after return statement",
                ["dead_code"],
                repo_root=str(root_p8),
                file_path="alive_method_dead_stmt.py"
            )
            dc_check = result_p8.get("checks", {}).get("dead_code", {})
            # Joern verified=False → 应降级到 Tier 2
            # Tier 2: return 后 cleanup() → verified=True (statement-level dead)
            check("P8C-1a mock Joern False → verified=True (Tier 2 degraded)",
                  result_p8.get("verified") is True,
                  f"got verified={result_p8.get('verified')}, tier={dc_check.get('tier')}")
            # tier 应该是 2 (从 Joern False 降级到 Tier 2)
            # 不能是 tier=1 且 verified=False (没降级 = bug)
            tier_p8 = dc_check.get("tier")
            check("P8C-1b tier=2 (degraded from Joern False)",
                  tier_p8 == 2,
                  f"got tier={tier_p8} (expected 2, if 1+False=bug)")
            # 不能是 tier=1 且 verified=False
            check("P8C-1c NOT (tier=1 + verified=False) = no stuck",
                  not (tier_p8 == 1 and dc_check.get("verified") is False),
                  f"tier={tier_p8}, verified={dc_check.get('verified')} (stuck on Joern False!)")
        finally:
            # 恢复原始函数
            if original_verify_dead_code is not None:
                _jc.verify_dead_code = original_verify_dead_code

        # P8C-2: mock Joern verified=True + Tier 2 verified=True → tier=1 (both agree)
        # 场景: process 未被调用 (Joern dead method) + return 后 dead code (Tier 2 dead stmt)
        # 两者一致 True → 保持 Joern tier=1
        print("\n  -- P8C-2: mock Joern True + Tier 2 True → tier=1 (agree) --")
        original_verify_dead_code_2 = None
        try:
            import joern_cpg as _jc2
            original_verify_dead_code_2 = _jc2.verify_dead_code
            _jc2.verify_dead_code = lambda rr, fp, ln: {
                "verified": True, "evidence": "mock: dead method",
                "tier": 1, "latency_ms": 10
            }
        except ImportError:
            pass

        try:
            # alive_method_dead_stmt.py: process 被调用, return 后有 dead code
            # mock Joern=True (dead method), Tier 2=True (dead stmt after return)
            # 两者一致 True → 保持 Joern tier=1
            result_p8b = verify_findings.verify_l4_structural(
                lines_p8, 4, "dead code after return statement",
                ["dead_code"],
                repo_root=str(root_p8),
                file_path="alive_method_dead_stmt.py"
            )
            dc_check_b = result_p8b.get("checks", {}).get("dead_code", {})
            # 两者一致 True → verified=True
            check("P8C-2a mock Joern True + Tier 2 True → verified=True",
                  result_p8b.get("verified") is True,
                  f"got verified={result_p8b.get('verified')}")
            # 两者一致 → 保持 Joern tier=1
            check("P8C-2b tier=1 (both agree True)",
                  dc_check_b.get("tier") == 1,
                  f"got tier={dc_check_b.get('tier')} (expected 1 if both agree)")
        finally:
            if original_verify_dead_code_2 is not None:
                _jc2.verify_dead_code = original_verify_dead_code_2

        # P8C-3: mock Joern verified=True + Tier 2 verified=False → tier=2 (Tier 2 wins)
        # P1A 场景: Joern method-level dead, Tier 2 statement-level reachable
        print("\n  -- P8C-3: mock Joern True + Tier 2 False → tier=2 (Tier 2 wins) --")
        original_verify_dead_code_3 = None
        try:
            import joern_cpg as _jc3
            original_verify_dead_code_3 = _jc3.verify_dead_code
            _jc3.verify_dead_code = lambda rr, fp, ln: {
                "verified": True, "evidence": "mock: dead method",
                "tier": 1, "latency_ms": 10
            }
        except ImportError:
            pass

        try:
            # reach.py: x=2 在 if 分支外 (statement-level reachable)
            # mock Joern=True (dead method), Tier 2=False (stmt reachable)
            # 不一致 → Tier 2 wins → tier=2, verified=False
            reach_file = root_p8 / "reach.py"
            reach_file.write_text(textwrap.dedent("""\
                def foo():
                    if cond:
                        return 1
                    x = 2
            """), encoding="utf-8")
            lines_reach = reach_file.read_text().split("\n")
            result_p8c = verify_findings.verify_l4_structural(
                lines_reach, 4, "dead code after return in foo",
                ["dead_code"],
                repo_root=str(root_p8),
                file_path="reach.py"
            )
            dc_check_c = result_p8c.get("checks", {}).get("dead_code", {})
            # 不一致 → Tier 2 wins → verified=False
            check("P8C-3a mock Joern True + Tier 2 False → verified=False",
                  result_p8c.get("verified") is False,
                  f"got verified={result_p8c.get('verified')} (Tier 2 should win)")
            # 不一致 → tier=2 (Tier 2 wins, not stuck on Joern)
            check("P8C-3b tier=2 (Tier 2 wins over Joern True)",
                  dc_check_c.get("tier") == 2,
                  f"got tier={dc_check_c.get('tier')} (expected 2, Tier 2 wins)")
        finally:
            if original_verify_dead_code_3 is not None:
                _jc3.verify_dead_code = original_verify_dead_code_3

    finally:
        import shutil as _shutil
        _shutil.rmtree(tmpdir_p8, ignore_errors=True)
else:
    print("  SKIP P8C: verify_findings.py not importable")


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
