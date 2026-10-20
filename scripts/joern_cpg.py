"""Tier 1: Joern CPG verifier for Phase 3.5 Finding Verification.

Optional dependency (Joern CLI v4.0+ + JDK 21). When unavailable, returns
``verified=None, tier=0`` so verify_findings.py falls through to Tier 2 (ast CFG)
and Tier 3 (regex). The module NEVER raises from normal operation — all
exceptions are caught and converted to verified=None so callers can degrade.

P1-5 verified APIs (Joern v4.0.595, 2026-08-05):
  - cpg.method.lineNumber(N)             (NOT cpg.method.location.line(N))
  - target.flatMap(_.caller.l).isEmpty   (NOT reachableBy)
  - cpg.imports.l                        (correct)
  - imp.importedEntity                   (NOT imp.imported)
  - --language pythonsrc                 (NOT --language python)

Returns unified schema (P0-2):
  {"verified": True|False|None, "evidence": str, "tier": 1, "latency_ms": int}
  verified=None  -> cannot decide; trigger fallback to Tier 2
  tier=0         -> Joern unavailable (only set when verified=None)

Cache (§6.2):
  - Key: sha256(repo_path)[:8] + "_" + sha256(sorted .py mtimes)[:16]
  - Stored under /tmp/add_joern_cache/ (Linux/WSL2) or %TEMP%\\add_joern_cache (Windows)
  - TTL: invalidated when any .py file mtime changes
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from _script_utils import run_script

# ── Constants ────────────────────────────────────────────────────────────

JOERN_TIMEOUT_SEC = 30  # §6.3: Tier 1 budget; exceeded -> fallback to Tier 2
JOERN_VERSION_MIN = "4.0"  # v4.0 flatgraph migration; v3.x API incompatible
# 注意: 本常量是**最低兼容 floor**（≠ 实测版本）。实测环境（2026-10-20 实证）:
#   Joern 4.0.595，安装 2026-08-05 12:31 —— 证据与方法（发行包 lib/ 的 jar 文件名）
#   见 docs/audit-log/2026-10-20-T9prime-joern-api-validation.md §0 / M-10。
#   成功路径返回的 "joern_version" 字段即本 floor 值；MVP 不做运行时版本探测
#   （避免为每个 finding 增加 WSL 子进程，且 ADR-023 要求零新增依赖）—— 见验收报告 §10 L-7。

# v2.7.1: Internal language name → Joern --language flag mapping
JOERN_LANGUAGE_MAP = {
    "python": "pythonsrc",
    "java": "javasrc2cpg",
    "cpp": "c2cpg",
}

# ── v3.0 T9' Phase 1: taint reachability (D-T9'-3 / ADR-027) ──

# 宽来源集正则 (E-2 修正 + T0 实测定稿 M-1): 仅 call 形状的名字 —— 属性访问
# (os.environ / request.args) 不是 cpg.call 节点, 不能出现在此正则中; 属性型输入由
# cpg.method.parameter 覆盖。此处 ^get$ 因 pysrc2cpg 把点分调用渲染为【末段名】
# (os.getenv → "getenv"; request.args.get → "get") 而成立; 已删除 loads|load。
# 过近似说明: ^get$ 会匹配任意 .get() 调用 ⇒ 来源集偏大 ⇒ verified=False 更难出现 ⇒ 方向安全。
INPUT_API_REGEX = r"^(input|raw_input|getenv|getpass|get|getlist)$"

# Tier 1 查询结果 memo (§0.4 禁止重复计算)。有界, 防止内存泄漏 (不做 LRU, 避免复杂度)。
_TAINT_QUERY_MEMO = {}
_TAINT_QUERY_MEMO_MAX = 512

# Cache directory: Linux/WSL2 uses /tmp; Windows uses %TEMP%
_CACHE_DIR = None  # lazy-init (see _get_cache_dir())


def _get_cache_dir():
    """Lazy-init cache directory. Cross-platform: /tmp or %TEMP%."""
    global _CACHE_DIR
    if _CACHE_DIR is not None:
        return _CACHE_DIR
    # Prefer /tmp when on Linux/WSL2 (Joern itself only runs there)
    if os.name == "nt":
        base = os.environ.get("TEMP", tempfile.gettempdir())
    else:
        base = "/tmp"
    cache = Path(base) / "add_joern_cache"
    try:
        cache.mkdir(parents=True, exist_ok=True)
    except OSError:
        cache = Path(tempfile.gettempdir()) / "add_joern_cache"
        cache.mkdir(parents=True, exist_ok=True)
    _CACHE_DIR = cache
    return cache


# ── Availability Detection ──────────────────────────────────────────────

# WSL2 detection cache: None = not checked yet; (True, dict|None) = checked
_WSL_DETECT_CACHE = None


def _detect_wsl():
    """Detect if running INSIDE Windows WSL2 (Linux/WSL host).

    WSL2 exposes /proc/sys/kernel/osrelease containing "microsoft" or "WSL".
    This detects whether the current Python process is itself running inside
    WSL2 (not whether WSL2 is available from Windows).

    For Windows→WSL2 cross-environment detection, see _detect_wsl_from_windows().

    Returns:
        bool: True if inside WSL2, False otherwise (native Linux/Win/macOS).
    """
    # JOERN_FORCE_WSL env override for testing
    force = os.environ.get("JOERN_FORCE_WSL")
    if force is not None:
        return force == "1"
    if os.name == "nt":
        return False  # Windows host; not inside WSL2
    try:
        with open("/proc/sys/kernel/osrelease", "r") as f:
            release = f.read().lower()
        return "microsoft" in release or "wsl" in release
    except (OSError, IOError):
        return False


def _detect_wsl_from_windows():
    """Detect WSL2 + Joern availability FROM a Windows host.

    Phase 6: Fixes the Windows→WSL2 call chain break. On Windows, Joern CLI
    is installed inside WSL2 (not on Windows itself), so we must:
      1. Verify wsl.exe is available
      2. Probe WSL2 for joern-parse at known install paths
      3. Probe WSL2 for JDK 21 (required by Joern)
      4. Return paths for command construction

    Test overrides (avoid actual WSL2 calls in unit tests):
      - JOERN_FORCE_WSL=1 + JOERN_WSL_JOERN_PATH + JOERN_WSL_JAVA_HOME:
        Returns dict immediately without probing WSL2

    Returns:
        dict|None: {"joern_path": str, "java_home": str} or None if not found.
        None means: not on Windows, or WSL2 unavailable, or Joern not installed.
    """
    global _WSL_DETECT_CACHE
    if _WSL_DETECT_CACHE is not None:
        # Cache hit: (True, dict) for positive, (True, None) for negative
        return _WSL_DETECT_CACHE[1]

    # Test override: explicit paths without WSL2 probing
    if os.environ.get("JOERN_FORCE_WSL") == "1":
        joern_path = os.environ.get("JOERN_WSL_JOERN_PATH")
        java_home = os.environ.get("JOERN_WSL_JAVA_HOME")
        if joern_path and java_home:
            result = {"joern_path": joern_path, "java_home": java_home}
            _WSL_DETECT_CACHE = (True, result)
            return result
        # FORCE_WSL without explicit paths: fall through to actual probing

    # Only attempt WSL2 probing on Windows (or when forced)
    if os.name != "nt" and os.environ.get("JOERN_FORCE_WSL") != "1":
        _WSL_DETECT_CACHE = (True, None)
        return None

    # Check wsl.exe availability on Windows
    if os.name == "nt":
        try:
            wsl_check = subprocess.run(
                ["wsl.exe", "-l", "-v"], capture_output=True, text=True, timeout=5)
            if wsl_check.returncode != 0:
                _WSL_DETECT_CACHE = (True, None)
                return None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            _WSL_DETECT_CACHE = (True, None)
            return None

    # Source-level facts (verified 2026-08-05 via _check_wsl.py):
    #   - Joern: /home/pengliu2026/bin/joern/joern-cli/joern-parse
    #   - JDK:   /home/pengliu2026/jdk/bin/java (Temurin 21.0.12 LTS)
    candidate_joern = [
        "/home/pengliu2026/bin/joern/joern-cli/joern-parse",
    ]
    joern_home = os.environ.get("JOERN_HOME")
    if joern_home:
        candidate_joern.insert(0, f"{joern_home}/joern-cli/joern-parse")
        candidate_joern.insert(1, f"{joern_home}/joern-parse")

    candidate_java = [
        "/home/pengliu2026/jdk",
    ]

    found_joern = None
    found_java = None

    for jp in candidate_joern:
        try:
            cmd = ["wsl.exe", "-e", "bash", "-c", f"test -x '{jp}' && echo FOUND"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if "FOUND" in r.stdout:
                found_joern = jp
                break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    if found_joern is None:
        _WSL_DETECT_CACHE = (True, None)
        return None

    for jh in candidate_java:
        try:
            cmd = ["wsl.exe", "-e", "bash", "-c", f"test -x '{jh}/bin/java' && echo FOUND"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if "FOUND" in r.stdout:
                found_java = jh
                break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    if found_java is None:
        # Joern found but JDK missing — Joern won't run, treat as unavailable
        _WSL_DETECT_CACHE = (True, None)
        return None

    result = {"joern_path": found_joern, "java_home": found_java}
    _WSL_DETECT_CACHE = (True, result)
    return result


def _find_joern_binary():
    """Locate joern-parse binary. Returns absolute path str or None.

    Search order:
      1. $JOERN_HOME/joern-cli/joern-parse (explicit override, local)
      2. shutil.which("joern-parse")  (PATH lookup, local)
      3. Common install paths: ~/bin/joern/joern-cli/joern-parse (local)
      4. Phase 6: WSL2 detection via _detect_wsl_from_windows() (Windows→WSL2)
    """
    # 1. Explicit override (local filesystem)
    joern_home = os.environ.get("JOERN_HOME")
    if joern_home:
        candidate = Path(joern_home) / "joern-cli" / "joern-parse"
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
        candidate2 = Path(joern_home) / "joern-parse"
        if candidate2.exists() and os.access(candidate2, os.X_OK):
            return str(candidate2)

    # 2. PATH lookup (works on native Linux and inside WSL2)
    found = shutil.which("joern-parse")
    if found:
        return found

    # 3. Common install path (matches Plan §B.0.1 WSL2 install guide)
    home = Path.home()
    common = home / "bin" / "joern" / "joern-cli" / "joern-parse"
    if common.exists() and os.access(common, os.X_OK):
        return str(common)

    # 4. Phase 6: Windows→WSL2 cross-environment detection
    #    On Windows host, Joern is installed inside WSL2, not locally.
    #    Return the WSL2 path so command builders know to wrap with wsl.exe.
    wsl_info = _detect_wsl_from_windows()
    if wsl_info is not None:
        return wsl_info["joern_path"]

    return None


def is_available():
    """Detect whether Joern CLI is installed and usable. O(1).

    Honors JOERN_DISABLE=1 env var for test isolation and forced fallback.
    Does NOT honor JOERN_FORCE_RAISE (that is for runtime simulation).

    Returns:
        bool: True if joern-parse binary exists and Joern is not disabled.
    """
    # Test isolation: force-disable Joern for deterministic Tier 2/3 testing
    if os.environ.get("JOERN_DISABLE") == "1":
        return False
    return _find_joern_binary() is not None


# ── Cache Key Generation ────────────────────────────────────────────────


def _get_cache_key(repo_root, language="python"):
    """Generate deterministic cache key for a repo. O(F) where F=#source files.

    Uses mtime (not content) so non-git projects also benefit from caching.
    The key combines:
      - sha256(repo_root)[:8]   -> distinguishes different repos at same path
      - sha256(sorted mtimes)[:16] -> invalidates on any source file edit
      - language prefix -> v2.7.1: isolates Python/Java/C++ CPGs for same repo

    v2.7.1: language 参数控制扫描的文件扩展名:
      - python → *.py
      - java → *.java
      - cpp → *.c, *.cpp, *.h, *.hpp

    Args:
        repo_root: str path to repo root.
        language: str internal language name ("python"|"java"|"cpp").

    Returns:
        str: cache key like "py_a1b2c3d4_e5f6a7b8c9d0e1f2"
    """
    repo = Path(repo_root)

    # v2.7.1: 根据语言选择文件扩展名
    _LANG_EXTENSIONS = {
        "python": ["*.py"],
        "java": ["*.java"],
        "cpp": ["*.c", "*.cpp", "*.h", "*.hpp", "*.cc", "*.cxx"],
    }
    exts = _LANG_EXTENSIONS.get(language, _LANG_EXTENSIONS["python"])

    # Lazy generator: scan language-specific files, skip __pycache__ and .venv
    source_files = []
    try:
        for ext in exts:
            for f in repo.rglob(ext):
                if "__pycache__" not in f.parts and ".venv" not in f.parts:
                    source_files.append(f)
    except (OSError, ValueError):
        # repo_root doesn't exist or access denied -> stable fallback key
        pass

    mtimes = []
    for f in source_files:
        try:
            rel = str(f.relative_to(repo))
            mtime = f.stat().st_mtime
            mtimes.append((rel, mtime))
        except (OSError, ValueError):
            continue
    mtimes.sort()  # deterministic ordering

    path_hash = hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:8]
    content_hash = hashlib.sha256(str(mtimes).encode("utf-8")).hexdigest()[:16]
    lang_prefix = language[:2] if language else "py"
    return f"{lang_prefix}_{path_hash}_{content_hash}"


# ── Scala Script Generation (P1-5 verified APIs) ───────────────────────


def _gen_dead_code_script(line, language="python"):
    """Generate Scala DSL script for dead_code verification.

    Uses P1-5 verified API:
      - cpg.method.lineNumber(N)  (NOT cpg.method.location.line(N))
      - target.flatMap(_.caller.l) (NOT reachableBy)

    v2.7.1: cpg.method.lineNumber(N) 和 target.flatMap(_.caller.l) 是 Joern
    跨语言通用 API (METHOD 是 universal node type), Python/Java/C++ 共用同一脚本.
    language 参数仅用于注释标注, 供调试和审计追踪.

    Phase 7 fix (two hallucinations, E2E verified 2026-08-05):
      H1: @main annotation does NOT work in Joern v4.0.595 script mode.
          All @main scripts fail with "Error during compilation: ScalaReplPP.main".
          Fix: use bare statements (REPL semantics); cpg is auto-available via
          positional CPG arg (joern --script script.sc /path/to/cpg.bin).
      H2: <module> exclusion was wrong. A method called only from <module>
          (Python module-level code) is NOT dead — it's reachable.
          E2E proof: def foo(): ... foo() → dead=true (wrong, foo is called).
          Fix: remove .filter(_.name != "<module>"); any caller = not dead.

    A method is "dead" if NO caller exists at all (zero incoming call edges).

    Args:
        line: int target line number.
        language: v2.7.1 str internal language name ("python"|"java"|"cpp").

    Returns:
        str: Scala script (bare statements, no @main) for `joern --script`.
    """
    return f"""// Phase 7: bare script (REPL semantics), cpg auto-available via positional arg
// v2.7.1: language={language} — cpg.method.lineNumber is universal across frontends
// P1-5 verified API: cpg.method.lineNumber(N) for call-graph target lookup
val target = cpg.method.lineNumber({line}).l
// P1-5 verified API: caller.l (call graph edges), not data-flow APIs
val callers = target.flatMap(_.caller.l)
// Phase 7 fix: any caller (including module entry) means reachable
val isDead = callers.isEmpty
println(s"dead=" + isDead)
println(s"size=" + target.size)
println(s"callers=" + callers.map(_.name).mkString(","))
"""


def _gen_import_script(language="python"):
    """Generate Scala DSL script for import cycle detection.

    Uses P1-5 verified API:
      - cpg.imports.l               (correct)
      - imp.importedEntity          (NOT imp.imported)
      - imp.file.head.name          (file that contains the import)

    v2.7.1: language 参数控制文件后缀剥离逻辑:
      - python → strip ".py"
      - java → strip ".java"
      - cpp → strip ".c"/".cpp"/".h"/".hpp"
    cpg.imports.l 和 imp.importedEntity 是 Joern 跨语言通用 API.

    Phase 7 fix (H1 hallucination, E2E verified 2026-08-05):
      @main annotation does NOT work in Joern v4.0.595 script mode.
      Fix: use bare statements; cpg is auto-available via positional CPG arg.

    Phase 8 fix (B1 bug, source-level traced 2026-08-05):
      Node naming mismatch: imp.file.head.name = "mod_a.py" (with .py suffix)
      but imp.importedEntity = "mod_b" (without .py). DFS cannot find back-edge
      because "mod_b" is not a graph key (only "mod_b.py" is).
      E2E proof: mod_a<->mod_b cycle → has_cycle=false (wrong).
      ast_cfg.py L418 uses with_suffix("") to strip .py correctly.
      Fix: strip source file extension from src file name to unify node naming.

    Builds a directed import graph and runs DFS cycle detection.

    Args:
        language: v2.7.1 str internal language name ("python"|"java"|"cpp").

    Returns:
        str: Scala script (bare statements, no @main) for `joern --script`.
    """
    # v2.7.1: 根据语言生成后缀剥离逻辑
    if language == "java":
        suffix_strip = '// v2.7.1: strip .java suffix\n  val src = if (rawSrc.endsWith(".java")) rawSrc.substring(0, rawSrc.length - 5) else rawSrc'
    elif language == "cpp":
        suffix_strip = '''// v2.7.1: strip C/C++ source extensions
  val extensions = List(".cpp", ".hpp", ".cc", ".cxx", ".hxx", ".c", ".h")
  var src = rawSrc
  for (ext <- extensions) {
    if (src.endsWith(ext)) { src = src.substring(0, src.length - ext.length) }
  }'''
    else:
        # Python (default, Phase 8 behavior)
        suffix_strip = '// Phase 8: strip .py suffix from file name to unify node naming\n  val src = if (rawSrc.endsWith(".py")) rawSrc.substring(0, rawSrc.length - 3) else rawSrc'

    return f"""// Phase 7: bare script (REPL semantics), cpg auto-available via positional arg
// v2.7.1: language={language} — cpg.imports.l is universal across frontends
// P1-5 verified API: cpg.imports.l + imp.importedEntity (Option[String])
import scala.collection.mutable

val imports = cpg.imports.l
val edges = imports.flatMap {{ imp =>
  val rawSrc = imp.file.head.name
  {suffix_strip}
  imp.importedEntity.map(e => (src, e))
}}
// Build adjacency map
val graph = mutable.Map.empty[String, Set[String]].withDefaultValue(Set.empty)
edges.foreach {{ case (src, dst) =>
  graph(src) = graph(src) + dst
}}
// DFS 3-color cycle detection
val WHITE = 0
val GRAY = 1
val BLACK = 2
val color = mutable.Map.empty[String, Int].withDefaultValue(WHITE)
var hasCycle = false
def dfs(node: String): Unit =
  if hasCycle then return
  color(node) = GRAY
  for (next <- graph(node)) {{
    if (color(next) == GRAY) {{ hasCycle = true; return }}
    if (color(next) == WHITE) dfs(next)
    if (hasCycle) return
  }}
  color(node) = BLACK
for (n <- graph.keys) {{
  if (color(n) == WHITE) {{
    dfs(n)
  }}
}}
println(s"has_cycle=" + hasCycle)
println(s"size=" + graph.size)
"""


# ── Subprocess Command Builders ─────────────────────────────────────────


def _is_wsl2_mode():
    """Check if we're in Windows→WSL2 cross-environment mode.

    Returns True if Joern will be invoked via wsl.exe from a Windows host.
    """
    return _detect_wsl_from_windows() is not None


def _build_wsl_bash_command(linux_command, java_home=None):
    """Wrap a Linux command with wsl.exe invocation for Windows→WSL2 mode.

    Constructs: wsl.exe -e bash -c "export JAVA_HOME=... && export PATH=... && <cmd>"

    Args:
        linux_command: str the Linux command to run inside WSL2.
        java_home: str JAVA_HOME path in WSL2 (from _detect_wsl_from_windows).

    Returns:
        list[str]: command tokens ["wsl.exe", "-e", "bash", "-c", bash_script]
    """
    wsl_info = _detect_wsl_from_windows()
    if wsl_info is not None:
        jh = java_home or wsl_info.get("java_home", "")
        # Set JAVA_HOME and PATH inside bash to avoid Windows PATH pollution.
        # Source-level fact: WSL2 default PATH includes Windows paths with
        # parentheses (Program Files (x86)) causing bash syntax errors.
        bash_script = (
            f"export JAVA_HOME='{jh}' && "
            f"export PATH=\"$JAVA_HOME/bin:/usr/bin:/bin\" && "
            f"{linux_command}"
        )
    else:
        bash_script = linux_command
    return ["wsl.exe", "-e", "bash", "-c", bash_script]


def _build_joern_parse_command(repo_path, cpg_output_path, language="pythonsrc"):
    """Build the joern-parse command line for CPG generation.

    P1-5 verified:
      - --language pythonsrc  (NOT --language python, which invokes py2cpg.sh
        that does not exist in Joern v4.0.595)

    Phase 6: In WSL2 mode (Windows host), wraps command with wsl.exe.

    Args:
        repo_path: str path to repo root (input, already WSL2-translated).
        cpg_output_path: str path to write CPG binary (already WSL2-translated).
        language: str language frontend. Default "pythonsrc" for Python.

    Returns:
        list[str]: command tokens for subprocess.run.
    """
    joern_binary = _find_joern_binary() or "joern-parse"

    # Phase 6: WSL2 mode — wrap with wsl.exe -e bash -c
    if _is_wsl2_mode():
        # Quote paths for bash safety (paths may contain spaces in theory)
        linux_cmd = (
            f"'{joern_binary}' --language {language} "
            f"-o '{cpg_output_path}' '{repo_path}'"
        )
        return _build_wsl_bash_command(linux_cmd)

    # Native mode (Linux or inside WSL2)
    return [
        joern_binary,
        "--language", language,
        "-o", cpg_output_path,
        repo_path,
    ]


def _build_joern_query_command(cpg_path, script_path):
    """Build the joern (interactive) command to run a Scala script on a CPG.

    Phase 7 fix: pass CPG as positional arg (NOT --param cpgFile=...).
      Joern v4.0.595 script mode uses REPL semantics — @main annotations
      do NOT compile. Bare scripts access `cpg` auto-variable when CPG is
      passed as positional arg: `joern --script script.sc /path/to/cpg.bin`.

    Phase 6: In WSL2 mode (Windows host), wraps command with wsl.exe.

    Args:
        cpg_path: str path to CPG binary (already WSL2-translated).
        script_path: str path to Scala script file (already WSL2-translated).

    Returns:
        list[str]: command tokens for subprocess.run.
    """
    joern_binary = _find_joern_binary() or "joern"
    # Strip "-parse" suffix to get the interactive `joern` launcher
    if joern_binary.endswith("joern-parse"):
        joern_binary = joern_binary[:-len("-parse")]

    # Phase 6: WSL2 mode — wrap with wsl.exe -e bash -c
    if _is_wsl2_mode():
        # Phase 7: positional CPG arg (not --param)
        linux_cmd = (
            f"'{joern_binary}' --script '{script_path}' '{cpg_path}'"
        )
        return _build_wsl_bash_command(linux_cmd)

    # Native mode: positional CPG arg
    return [
        joern_binary,
        "--script", script_path,
        cpg_path,
    ]


def _build_clean_env():
    """Build a clean env for Joern subprocess (avoid Windows PATH pollution).

    Phase 6: In WSL2 mode, JAVA_HOME is the WSL2 path (not Windows path).
    The env dict is used for API consistency and testing; actual WSL2
    execution embeds env vars in the bash command string (see
    _build_wsl_bash_command).

    Native mode (Linux/WSL2-inside): override PATH to avoid Windows PATH
    pollution from WSL2's default PATH interop.
    """
    env = os.environ.copy()

    # Phase 6: WSL2 cross-environment mode
    wsl_info = _detect_wsl_from_windows()
    if wsl_info is not None:
        env["JAVA_HOME"] = wsl_info["java_home"]
        env["JOERN_WSL_MODE"] = "1"
        return env

    # Native mode (Linux or inside WSL2)
    java_home = env.get("JAVA_HOME", str(Path.home() / "jdk"))
    joern_cli = str(Path.home() / "bin" / "joern" / "joern-cli")
    # Override PATH: keep JDK + Joern + system; drop Windows paths
    # (applies when running inside WSL2 where Windows PATH is interop'd)
    if _detect_wsl() or os.name != "nt":
        env["PATH"] = f"{java_home}/bin:{joern_cli}:/usr/bin:/bin"
    env["JAVA_HOME"] = java_home
    return env


# ── Output Parsing ──────────────────────────────────────────────────────


def _parse_joern_output(output):
    """Parse Joern script output (key=value lines) into a dict.

    Robust to:
      - Extra log lines from Joern startup (skipped, not key=value)
      - Trailing whitespace / \r\n line endings
      - Multi-line values (only single-line key=value parsed)

    Args:
        output: str raw stdout from joern subprocess.

    Returns:
        dict: e.g. {"dead": "true", "size": "0", "has_cycle": "false"}
    """
    result = {}
    for line in output.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        # Split on first "=" only (value may contain "=")
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes if present
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if key:
            result[key] = value
    return result


# ── CPG Generation (with cache) ─────────────────────────────────────────


def _generate_cpg(repo_root, cache_key, language="pythonsrc"):
    """Generate or load cached CPG for a repo. Returns CPG path or None.

    Cache strategy (§6.2):
      - Cache file: <cache_dir>/<cache_key>.bin
      - Hit: return cached path immediately
      - Miss: run joern-parse, store result, return path
      - Failure: return None (triggers Tier 2 fallback)

    v2.7.1: language 参数选择 Joern 前端 (pythonsrc/javasrc2cpg/c2cpg).

    Args:
        repo_root: str path to repo root.
        cache_key: str cache key from _get_cache_key() (already language-scoped).
        language: str Joern frontend name (pythonsrc/javasrc2cpg/c2cpg).

    Returns:
        str|None: path to CPG binary, or None if generation failed.
    """
    cache_dir = _get_cache_dir()
    cpg_path = cache_dir / f"{cache_key}.bin"

    # Cache hit
    if cpg_path.exists() and cpg_path.stat().st_size > 0:
        return str(cpg_path)

    # Cache miss: generate CPG
    # Translate Windows path to WSL2 /mnt/<drive>/... if needed
    wsl_repo = _translate_path_to_wsl(repo_root)
    wsl_cpg = _translate_path_to_wsl(str(cpg_path))

    cmd = _build_joern_parse_command(wsl_repo, wsl_cpg, language=language)
    env = _build_clean_env()

    try:
        proc = subprocess.run(
            cmd, env=env, capture_output=True, text=True,
            timeout=JOERN_TIMEOUT_SEC,
            cwd=str(cache_dir),  # N-1 (T0 实测同源): 防 joern-parse 在调用者 CWD 生成 workspace/
        )
        if proc.returncode != 0 or not cpg_path.exists():
            return None
        return str(cpg_path)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _translate_path_to_wsl(path):
    """Translate a Windows path to WSL2 /mnt/<drive>/... form.

    On Linux/WSL2 hosts, returns the path unchanged.
    On Windows hosts, converts F:\foo\bar -> /mnt/f/foo/bar (lowercase drive).
    Joern itself runs in WSL2 (per Plan §B.0.1), so paths must be WSL2-native.

    Args:
        path: str path (Windows or Linux form).

    Returns:
        str: path in WSL2-native form (or unchanged if already Linux).
    """
    if os.name == "nt" and len(path) >= 2 and path[1] == ":":
        # Windows drive path: F:\foo\bar -> /mnt/f/foo/bar
        drive = path[0].lower()
        rest = path[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return path


# ── Joern Query Execution ───────────────────────────────────────────────


def _run_joern_query(cpg_path, script_text, script_name="query"):
    """Run a Scala script against a CPG. Returns parsed output dict or None.

    Writes the script to a temp file, invokes `joern --script`, parses output.
    All exceptions are caught — callers receive None on any failure.

    Args:
        cpg_path: str path to CPG binary.
        script_text: str Scala script source.
        script_name: str filename stem for the temp script file.

    Returns:
        dict|None: parsed key=value output, or None on failure.
    """
    cache_dir = _get_cache_dir()
    script_file = cache_dir / f"{script_name}.sc"
    try:
        script_file.write_text(script_text, encoding="utf-8")
    except OSError:
        return None

    wsl_cpg = _translate_path_to_wsl(cpg_path)
    wsl_script = _translate_path_to_wsl(str(script_file))

    cmd = _build_joern_query_command(wsl_cpg, wsl_script)
    env = _build_clean_env()

    try:
        proc = subprocess.run(
            cmd, env=env, capture_output=True, text=True,
            timeout=JOERN_TIMEOUT_SEC,
            cwd=str(cache_dir),  # N-1 (T0 实测): 防 joern --script 在调用者 CWD 生成 workspace/<cpg>/
        )
        if proc.returncode != 0:
            return None
        return _parse_joern_output(proc.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


# ── v3.0 T9' Phase 1: taint reachability script + API ───────────────────


def _gen_taint_flow_script(sink_line, sink_file, source_line=None,
                           source_file=None, language="python"):
    """Generate Scala DSL script for taint reachability (bare REPL style).

    遵守既有踩坑约定 (joern_cpg L338-L363):
      - bare REPL: 顶层语句, 禁止入口注解 (v4.0.595 script 模式 @main 失效)
      - 输出协议: 复用 _parse_joern_output 的 key=value 行解析

    E-1 (文件过滤, 阻断项 R1c): 必须按 sink_file 过滤 —— 否则行号 N 在多文件中命中,
      会把别的文件的调用当 sink, 导致 verified=False 不可靠。
    E-4 (step 形式): 用 cpg.call.lineNumber(N) 而非 filter(_.lineNumber == N)
      (lineNumber 是 Option[Integer]; step 形式与已实测的 cpg.method.lineNumber(N) 同构)

    G-2 (Step 6 审计发现): source_line 必须被脚本实际消费 —— 否则它是 dead parameter。
      source_line=None => broad 变体; source_line 给定 => exact 变体 (来源集限定为
      source_line 处的调用, 不含 cpg.method.parameter 兜底)。

    Args:
        sink_line: int sink 行号。
        sink_file: str sink 文件 basename。
        source_line: int|None 精确来源行号。
        source_file: str|None 精确来源文件 basename (缺省同 sink_file, 仅 exact 变体消费)。
        language: str 内部语言名 (仅用于注释标注)。

    Returns:
        str: Scala 脚本 (bare statements, 无入口注解)。
    """
    if source_line is None:
        return f"""// v3.0 T9' Phase 1: taint reachability (broad source) — bare REPL, no entry-point annotation
// language={language} — cpg.call / cpg.method are universal across frontends
import io.joern.dataflowengineoss.language._
val sinkLine = {sink_line}
val sinkFile = "{sink_file}"
val srcRe = "{INPUT_API_REGEX}"
val sinkList = cpg.call.lineNumber(sinkLine).filter(_.file.head.name == sinkFile).l
val sources = (cpg.call.name(srcRe) ++ cpg.method.parameter).l
val hasFlow = sinkList.exists(s => s.reachableBy(sources).size > 0)
println("sink_nodes=" + sinkList.size)
println("source_nodes=" + sources.size)
println("has_flow=" + hasFlow)
"""
    src_file = source_file or sink_file
    return f"""// v3.0 T9' Phase 1: taint reachability (exact source) — bare REPL, no entry-point annotation
// language={language} — source set restricted to the call at sourceLine
import io.joern.dataflowengineoss.language._
val sinkLine = {sink_line}
val sourceLine = {source_line}
val sinkFile = "{sink_file}"
val srcFile = "{src_file}"
val sinkList = cpg.call.lineNumber(sinkLine).filter(_.file.head.name == sinkFile).l
val srcList = cpg.call.lineNumber(sourceLine).filter(_.file.head.name == srcFile).l
val hasFlow = sinkList.exists(s => s.reachableBy(srcList).size > 0)
println("sink_nodes=" + sinkList.size)
println("source_nodes=" + srcList.size)
println("has_flow=" + hasFlow)
"""


def _to_int(value, default=0):
    """把 Joern 输出字符串转为 int; 缺键/非数字 => default (调用方视同 0 => verified=None)。"""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _store_taint_memo(memo_key, result):
    """写入 taint 查询 memo (G-5: 存副本; §0.4: 有界, 超出即清空)。"""
    if len(_TAINT_QUERY_MEMO) >= _TAINT_QUERY_MEMO_MAX:
        _TAINT_QUERY_MEMO.clear()
    _TAINT_QUERY_MEMO[memo_key] = dict(result)


def verify_taint_flow(repo_root, sink_file, sink_line, language="python",
                      source_file=None, source_line=None):
    """Tier 1: Joern CPG-based taint reachability verification (MVP: broad-source).

    三段来源策略 (设计 spec §2.3):
      S1 exact: source_line 可得 + sink 可达 source => taint_mode="exact"
      S2 broad: source 不可得 (MVP 默认)          => taint_mode="broad"
      S3 不可判定                                 => verified=None

    降级触发 (全部 => verified=None, tier=0):
      1. JOERN_DISABLE=1 或 is_available() is False  => evidence="joern_unavailable"
      2. _generate_cpg 返回 None                     => "cpg_generation_failed"
      3. _run_joern_query 返回 None                  => "joern_query_failed"
      4. sink_nodes == 0                             => "sink_not_located"  (D-T9'-3 关键保护)
      5. source_nodes == 0                           => "no_sources"

    Returns (统一 schema, 只增不删):
      {"verified": True|False|None, "evidence": str, "tier": 0|1, "latency_ms": int,
       "taint_mode": "exact"|"broad"|None, "sink_nodes": int, "source_nodes": int,
       "joern_version": str  # 仅成功查询时存在, 对齐 verify_dead_code
      }
    """
    t0 = time.perf_counter()
    latency = lambda: int((time.perf_counter() - t0) * 1000)  # noqa: E731
    base = {"taint_mode": None, "sink_nodes": 0, "source_nodes": 0}

    # Test hook: simulate runtime failure (caught by verify_findings.py)
    if os.environ.get("JOERN_FORCE_RAISE") == "1":
        raise RuntimeError("JOERN_FORCE_RAISE=1 (test simulation)")

    # Unavailable -> verified=None, tier=0 (triggers Tier 2 fallback)
    if not is_available():
        return dict(base, verified=None, evidence="joern_unavailable",
                    tier=0, latency_ms=latency())

    # v3.0: 映射内部语言名到 Joern --language flag
    joern_lang = JOERN_LANGUAGE_MAP.get(language, "pythonsrc")

    # 查询级 memo (§0.4 性能保护 2): 同一 (cache_key, sink, source, language) 只跑一次
    cache_key = _get_cache_key(repo_root, language=language)
    memo_key = (cache_key, sink_file, sink_line, source_line, language)
    hit = _TAINT_QUERY_MEMO.get(memo_key)
    if hit is not None:
        return dict(hit)  # G-5: 返回浅拷贝, 防调用方可变引用跨 finding 污染

    # Generate / load cached CPG (cache key is language-scoped; 与 dead_code 复用同一 CPG)
    cpg_path = _generate_cpg(repo_root, cache_key, language=joern_lang)
    if cpg_path is None:
        result = dict(base, verified=None, evidence="cpg_generation_failed",
                      tier=0, latency_ms=latency())
        _store_taint_memo(memo_key, result)
        return result

    mode = "exact" if source_line is not None else "broad"
    script = _gen_taint_flow_script(sink_line, sink_file, source_line=source_line,
                                    source_file=source_file, language=language)
    out = _run_joern_query(cpg_path, script, script_name="taint_flow")
    if out is None:
        result = dict(base, verified=None, evidence="joern_query_failed",
                      tier=0, latency_ms=latency())
        _store_taint_memo(memo_key, result)
        return result

    sink_nodes = _to_int(out.get("sink_nodes"))
    source_nodes = _to_int(out.get("source_nodes"))

    # D-T9'-3 关键保护: sink 未定位与"无路径"数值同形 (都是 0) => 必返回 None
    if sink_nodes == 0:
        result = dict(base, verified=None, evidence="sink_not_located", tier=0,
                      latency_ms=latency(), taint_mode=mode, sink_nodes=0,
                      source_nodes=source_nodes)
        _store_taint_memo(memo_key, result)
        return result
    if source_nodes == 0:
        result = dict(base, verified=None, evidence="no_sources", tier=0,
                      latency_ms=latency(), taint_mode=mode, sink_nodes=sink_nodes,
                      source_nodes=0)
        _store_taint_memo(memo_key, result)
        return result

    has_flow = out.get("has_flow", "").strip().lower() == "true"
    result = {"verified": has_flow,
              "evidence": (f"Joern CPG: taint {'reachable' if has_flow else 'NOT reachable'} "
                           f"from {'exact source' if mode == 'exact' else 'broad source set'} "
                           f"to {sink_file}:{sink_line} "
                           f"(sinks={sink_nodes}, sources={source_nodes})"),
              "tier": 1, "latency_ms": latency(),
              "taint_mode": mode, "sink_nodes": sink_nodes,
              "source_nodes": source_nodes, "joern_version": JOERN_VERSION_MIN}
    _store_taint_memo(memo_key, result)
    return result


# ── Public API: verify_dead_code, verify_imports ────────────────────────


def verify_dead_code(repo_root, file_path, line_num, language="python"):
    """Tier 1: Joern CPG-based dead_code verification.

    v2.7.1: language 参数选择 Joern 前端 (pythonsrc/javasrc2cpg/c2cpg).
    内部语言名 ("python"/"java"/"cpp") 映射为 Joern --language flag.

    Args:
        repo_root: str path to repo root.
        file_path: str relative path to the claim target file.
        line_num: int target line number.
        language: v2.7.1 str internal language name ("python"|"java"|"cpp").

    Returns:
        dict with unified schema (P0-2):
          {
            "verified": True|False|None,  # None = cannot decide -> fallback
            "evidence": str,
            "tier": 1,                    # 0 if Joern unavailable
            "latency_ms": int
          }
    """
    t0 = time.perf_counter()
    latency = lambda: int((time.perf_counter() - t0) * 1000)

    # Test hook: simulate runtime failure (caught by verify_findings.py)
    if os.environ.get("JOERN_FORCE_RAISE") == "1":
        raise RuntimeError("JOERN_FORCE_RAISE=1 (test simulation)")

    # Unavailable -> verified=None, tier=0 (triggers Tier 2 fallback)
    if not is_available():
        return {"verified": None, "evidence": "joern_unavailable",
                "tier": 0, "latency_ms": latency()}

    # v2.7.1: 映射内部语言名到 Joern --language flag
    joern_lang = JOERN_LANGUAGE_MAP.get(language, "pythonsrc")

    # Generate / load cached CPG (cache key is language-scoped)
    cache_key = _get_cache_key(repo_root, language=language)
    cpg_path = _generate_cpg(repo_root, cache_key, language=joern_lang)
    if cpg_path is None:
        return {"verified": None, "evidence": "cpg_generation_failed",
                "tier": 0, "latency_ms": latency()}

    # Run dead_code query (v2.7.1: pass language for script annotation)
    script = _gen_dead_code_script(line_num, language=language)
    result = _run_joern_query(cpg_path, script, script_name="dead_code")
    if result is None:
        return {"verified": None, "evidence": "joern_query_failed",
                "tier": 0, "latency_ms": latency()}

    # Interpret output
    is_dead = result.get("dead", "").lower() == "true"
    if is_dead:
        return {"verified": True,
                "evidence": f"Joern CPG: line {line_num} in {file_path} has no caller (dead)",
                "tier": 1, "latency_ms": latency(),
                "joern_version": JOERN_VERSION_MIN}
    else:
        return {"verified": False,
                "evidence": f"Joern CPG: line {line_num} in {file_path} is reachable (called)",
                "tier": 1, "latency_ms": latency(),
                "joern_version": JOERN_VERSION_MIN}


def verify_imports(repo_root, claim, language="python"):
    """Tier 1: Joern CPG-based import cycle detection.

    v2.7.1: language 参数选择 Joern 前端 (pythonsrc/javasrc2cpg/c2cpg)
    和 Scala 脚本中的文件后缀剥离逻辑.

    Args:
        repo_root: str path to repo root.
        claim: str original claim text (used for evidence, not parsing).
        language: v2.7.1 str internal language name ("python"|"java"|"cpp").

    Returns:
        dict with unified schema (P0-2):
          {
            "verified": True|False|None,
            "evidence": str,
            "tier": 1,
            "latency_ms": int
          }
    """
    t0 = time.perf_counter()
    latency = lambda: int((time.perf_counter() - t0) * 1000)

    # Test hook: simulate runtime failure
    if os.environ.get("JOERN_FORCE_RAISE") == "1":
        raise RuntimeError("JOERN_FORCE_RAISE=1 (test simulation)")

    # Unavailable -> verified=None, tier=0
    if not is_available():
        return {"verified": None, "evidence": "joern_unavailable",
                "tier": 0, "latency_ms": latency()}

    # v2.7.1: 映射内部语言名到 Joern --language flag
    joern_lang = JOERN_LANGUAGE_MAP.get(language, "pythonsrc")

    # Generate / load cached CPG (cache key is language-scoped)
    cache_key = _get_cache_key(repo_root, language=language)
    cpg_path = _generate_cpg(repo_root, cache_key, language=joern_lang)
    if cpg_path is None:
        return {"verified": None, "evidence": "cpg_generation_failed",
                "tier": 0, "latency_ms": latency()}

    # Run import cycle query (v2.7.1: pass language for suffix stripping)
    script = _gen_import_script(language=language)
    result = _run_joern_query(cpg_path, script, script_name="import_cycle")
    if result is None:
        return {"verified": None, "evidence": "joern_query_failed",
                "tier": 0, "latency_ms": latency()}

    # Interpret output
    has_cycle = result.get("has_cycle", "").lower() == "true"
    if has_cycle:
        return {"verified": True,
                "evidence": f"Joern CPG: import cycle detected (claim: {claim[:80]})",
                "tier": 1, "latency_ms": latency(),
                "joern_version": JOERN_VERSION_MIN}
    else:
        return {"verified": False,
                "evidence": f"Joern CPG: no import cycle (claim: {claim[:80]})",
                "tier": 1, "latency_ms": latency(),
                "joern_version": JOERN_VERSION_MIN}


# ── CLI entry point ─────────────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Tier 1: Joern CPG verifier for Phase 3.5 (optional)")
    parser.add_argument("--repo", required=True, help="repo root path")
    parser.add_argument("--file", help="claim target file (for dead_code)")
    parser.add_argument("--line", type=int, help="claim target line (for dead_code)")
    parser.add_argument("--claim-type", choices=["dead_code", "import_related"],
                        required=True)
    parser.add_argument("--claim", required=True, help="original claim text")
    parser.add_argument("--language", default="python",
                        choices=["python", "java", "cpp"],
                        help="v2.7.1: source language (default: python)")
    parser.add_argument("--output", help="output JSON file (default: stdout)")
    args = parser.parse_args()

    if args.claim_type == "dead_code":
        if not args.file or not args.line:
            print(json.dumps({"error": "--file and --line required for dead_code"}))
            return 2
        result = verify_dead_code(args.repo, args.file, args.line,
                                   language=args.language)
    else:
        result = verify_imports(args.repo, args.claim, language=args.language)

    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    run_script(main)
