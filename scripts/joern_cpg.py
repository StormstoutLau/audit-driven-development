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


def _detect_wsl():
    """Detect if running inside Windows WSL2.

    WSL2 exposes /proc/sys/kernel/osrelease containing "microsoft" or "WSL".
    Used to decide whether to invoke joern via wsl.exe (Windows host) or
    directly (Linux/WSL inside).

    Returns:
        bool: True if inside WSL2, False otherwise (native Linux/Win/macOS).
    """
    # JOERN_FORCE_WSL env override for testing
    force = os.environ.get("JOERN_FORCE_WSL")
    if force is not None:
        return force == "1"
    if os.name == "nt":
        return False  # Windows host; Joern runs via wsl.exe if available
    try:
        with open("/proc/sys/kernel/osrelease", "r") as f:
            release = f.read().lower()
        return "microsoft" in release or "wsl" in release
    except (OSError, IOError):
        return False


def _find_joern_binary():
    """Locate joern-parse binary. Returns absolute path str or None.

    Search order:
      1. $JOERN_HOME/joern-cli/joern-parse (explicit override)
      2. shutil.which("joern-parse")  (PATH lookup)
      3. Common install paths: ~/bin/joern/joern-cli/joern-parse
    """
    # 1. Explicit override
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


def _get_cache_key(repo_root):
    """Generate deterministic cache key for a repo. O(F) where F=#.py files.

    Uses mtime (not content) so non-git projects also benefit from caching.
    The key combines:
      - sha256(repo_root)[:8]   -> distinguishes different repos at same path
      - sha256(sorted mtimes)[:16] -> invalidates on any .py file edit

    Args:
        repo_root: str path to repo root.

    Returns:
        str: 25-char cache key like "a1b2c3d4_e5f6a7b8c9d0e1f2"
    """
    repo = Path(repo_root)
    # Lazy generator: only .py files, skip __pycache__ and .venv
    try:
        py_files = [f for f in repo.rglob("*.py")
                    if "__pycache__" not in f.parts and ".venv" not in f.parts]
    except (OSError, ValueError):
        # repo_root doesn't exist or access denied -> stable fallback key
        py_files = []

    mtimes = []
    for f in py_files:
        try:
            rel = str(f.relative_to(repo))
            mtime = f.stat().st_mtime
            mtimes.append((rel, mtime))
        except (OSError, ValueError):
            continue
    mtimes.sort()  # deterministic ordering

    path_hash = hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:8]
    content_hash = hashlib.sha256(str(mtimes).encode("utf-8")).hexdigest()[:16]
    return f"{path_hash}_{content_hash}"


# ── Scala Script Generation (P1-5 verified APIs) ───────────────────────


def _gen_dead_code_script(line):
    """Generate Scala DSL script for dead_code verification.

    Uses P1-5 verified API:
      - cpg.method.lineNumber(N)  (NOT cpg.method.location.line(N))
      - target.flatMap(_.caller.l) (NOT reachableBy)

    A method is "dead" if no caller exists (excluding <module> entry point).

    Args:
        line: int target line number.

    Returns:
        str: Scala script ready for `joern --script`.
    """
    return f"""import io.joern.joerncli.*
import io.shiftleft.semanticcpg.*
import io.shiftleft.codepropertygraph.generated.Cpg

@main def checkDead(cpgFile: String): Unit =
  val cpg = loadCpg(cpgFile)
  // P1-5 verified API: cpg.method.lineNumber(N) for call-graph target lookup
  val target = cpg.method.lineNumber({line}).l
  // P1-5 verified API: caller.l (call graph edges), not data-flow APIs
  val callers = target.flatMap(_.caller.l)
  // <module> is the implicit entry; exclude it from "real" callers
  val isDead = callers.filter(_.name != "<module>").isEmpty
  println(s"dead=${{isDead}}")
  println(s"size=${{target.size}}")
"""


def _gen_import_script():
    """Generate Scala DSL script for import cycle detection.

    Uses P1-5 verified API:
      - cpg.imports.l               (correct)
      - imp.importedEntity          (NOT imp.imported)
      - imp.file.head.name          (file that contains the import)

    Builds a directed import graph and runs DFS cycle detection.

    Returns:
        str: Scala script ready for `joern --script`.
    """
    return """import io.joern.joerncli.*
import io.shiftleft.semanticcpg.*
import io.shiftleft.codepropertygraph.generated.Cpg
import scala.collection.mutable

@main def checkCyclic(cpgFile: String): Unit =
  val cpg = loadCpg(cpgFile)
  // P1-5 verified API: cpg.imports.l + imp.importedEntity (Option[String])
  val imports = cpg.imports.l
  val edges = imports.flatMap { imp =>
    imp.importedEntity.map(e => (imp.file.head.name, e))
  }
  // Build adjacency map
  val graph = mutable.Map.empty[String, Set[String]].withDefaultValue(Set.empty)
  edges.foreach { case (src, dst) =>
    graph(src) = graph(src) + dst
  }
  // DFS 3-color cycle detection
  val WHITE, GRAY, BLACK = 0, 1, 2
  val color = mutable.Map.empty[String, Int].withDefaultValue(WHITE)
  var hasCycle = false
  def dfs(node: String): Unit =
    if hasCycle then return
    color(node) = GRAY
    for (next <- graph(node)) {
      if (color(next) == GRAY) { hasCycle = true; return }
      if (color(next) == WHITE) dfs(next)
      if (hasCycle) return
    }
    color(node) = BLACK
  for (n <- graph.keys) {
    if (color(n) == WHITE) {
      dfs(n)
      if (hasCycle) return // early exit
    }
  }
  println(s"has_cycle=${hasCycle}")
  println(s"size=${graph.size}")
"""


# ── Subprocess Command Builders ─────────────────────────────────────────


def _build_joern_parse_command(repo_path, cpg_output_path, language="pythonsrc"):
    """Build the joern-parse command line for CPG generation.

    P1-5 verified:
      - --language pythonsrc  (NOT --language python, which invokes py2cpg.sh
        that does not exist in Joern v4.0.595)

    Args:
        repo_path: str path to repo root (input).
        cpg_output_path: str path to write CPG binary (output).
        language: str language frontend. Default "pythonsrc" for Python.

    Returns:
        list[str]: command tokens for subprocess.run.
    """
    joern_binary = _find_joern_binary() or "joern-parse"
    # WSL2 path translation: Windows repo path -> /mnt/<drive>/...
    # (handled by caller; here we trust the given path is already WSL2-native)
    return [
        joern_binary,
        "--language", language,
        "-o", cpg_output_path,
        repo_path,
    ]


def _build_joern_query_command(cpg_path, script_path):
    """Build the joern (interactive) command to run a Scala script on a CPG.

    Args:
        cpg_path: str path to CPG binary.
        script_path: str path to Scala script file.

    Returns:
        list[str]: command tokens for subprocess.run.
    """
    joern_binary = _find_joern_binary() or "joern"
    # Strip "-parse" suffix to get the interactive `joern` launcher
    if joern_binary.endswith("joern-parse"):
        joern_binary = joern_binary[:-len("-parse")]
    return [
        joern_binary,
        "--script", script_path,
        "--param", f"cpgFile={cpg_path}",
    ]


def _build_clean_env():
    """Build a clean env for Joern subprocess (avoid Windows PATH pollution).

    WSL2 default PATH includes Windows paths with parentheses (Program Files (x86))
    which cause bash syntax errors. We override PATH to include only:
      - $JAVA_HOME/bin (JDK 21 required by Joern)
      - $HOME/bin/joern/joern-cli (Joern itself)
      - /usr/bin, /bin (system utilities)
    """
    env = os.environ.copy()
    java_home = env.get("JAVA_HOME", str(Path.home() / "jdk"))
    joern_cli = str(Path.home() / "bin" / "joern" / "joern-cli")
    # Override PATH: keep JDK + Joern + system; drop Windows paths
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


def _generate_cpg(repo_root, cache_key):
    """Generate or load cached CPG for a repo. Returns CPG path or None.

    Cache strategy (§6.2):
      - Cache file: <cache_dir>/<cache_key>.bin
      - Hit: return cached path immediately
      - Miss: run joern-parse, store result, return path
      - Failure: return None (triggers Tier 2 fallback)

    Args:
        repo_root: str path to repo root.
        cache_key: str cache key from _get_cache_key().

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

    cmd = _build_joern_parse_command(wsl_repo, wsl_cpg, language="pythonsrc")
    env = _build_clean_env()

    try:
        proc = subprocess.run(
            cmd, env=env, capture_output=True, text=True,
            timeout=JOERN_TIMEOUT_SEC,
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
        )
        if proc.returncode != 0:
            return None
        return _parse_joern_output(proc.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


# ── Public API: verify_dead_code, verify_imports ────────────────────────


def verify_dead_code(repo_root, file_path, line_num):
    """Tier 1: Joern CPG-based dead_code verification.

    Args:
        repo_root: str path to repo root.
        file_path: str relative path to the claim target file.
        line_num: int target line number.

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

    # Generate / load cached CPG
    cache_key = _get_cache_key(repo_root)
    cpg_path = _generate_cpg(repo_root, cache_key)
    if cpg_path is None:
        return {"verified": None, "evidence": "cpg_generation_failed",
                "tier": 0, "latency_ms": latency()}

    # Run dead_code query
    script = _gen_dead_code_script(line_num)
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


def verify_imports(repo_root, claim):
    """Tier 1: Joern CPG-based import cycle detection.

    Args:
        repo_root: str path to repo root.
        claim: str original claim text (used for evidence, not parsing).

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

    # Generate / load cached CPG
    cache_key = _get_cache_key(repo_root)
    cpg_path = _generate_cpg(repo_root, cache_key)
    if cpg_path is None:
        return {"verified": None, "evidence": "cpg_generation_failed",
                "tier": 0, "latency_ms": latency()}

    # Run import cycle query
    script = _gen_import_script()
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
    parser.add_argument("--output", help="output JSON file (default: stdout)")
    args = parser.parse_args()

    if args.claim_type == "dead_code":
        if not args.file or not args.line:
            print(json.dumps({"error": "--file and --line required for dead_code"}))
            return 2
        result = verify_dead_code(args.repo, args.file, args.line)
    else:
        result = verify_imports(args.repo, args.claim)

    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    run_script(main)
