"""Tier 2: Python ast CFG verifier for Phase 3.5 Finding Verification.

Zero external dependencies (Python 3.8+ stdlib only). Provides:
  - CFGBuilder: builds Control Flow Graph from Python source via ast.NodeVisitor
  - verify_dead_code_in_source: checks if a line is unreachable in the CFG
  - ImportGraphBuilder + detect_cycle: builds import graph, detects cycles
  - verify_imports_in_repo: end-to-end import cycle verification

Returns unified schema (P0-2 fix):
  {"verified": True|False|None, "evidence": str, "tier": 2, ...}

Performance:
  - CFG build: O(N) single NodeVisitor traversal
  - Reachability: O(V+E) BFS with collections.deque
  - Cycle detection: O(V+E) iterative 3-color DFS (no recursion stack overflow)
  - Import graph: O(F*S) with pathlib.Path.rglob generator (lazy)
"""

import ast
import os
import sys
import time
from collections import deque
from pathlib import Path

from _script_utils import run_script


# ── CFG Builder ──────────────────────────────────────────────────────────


class CFGBuilder(ast.NodeVisitor):
    """Build a Control Flow Graph from Python AST. O(N) single traversal.

    Nodes are keyed by source line number. Edges represent possible control
    flow transitions. Uses _current_successors as a working list of pending
    predecessor lines that the next statement will connect from.
    """

    def __init__(self):
        self.nodes: dict = {}           # line -> {"line": int, "type": str}
        self.edges: list = []           # [(src_line, dst_line), ...]
        self._current_successors: list = []  # pending predecessor lines

    def _add_node(self, line, node_type):
        if line not in self.nodes:
            self.nodes[line] = {"line": line, "type": node_type}

    def _connect_predecessors(self, line):
        """Connect all _current_successors to the given line."""
        for src in self._current_successors:
            self.edges.append((src, line))

    def visit_FunctionDef(self, node):
        """Function entry -> body -> (function exit clears successors)."""
        self._add_node(node.lineno, "FunctionDef")
        self._current_successors = [node.lineno]
        for stmt in node.body:
            self.visit(stmt)
        self._current_successors = []  # function exit: no successors

    # async def has the same CFG structure as sync def
    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node):
        """Condition -> then branch + else branch -> merge."""
        cond_line = node.lineno
        self._add_node(cond_line, "If")
        self._connect_predecessors(cond_line)

        # then branch
        self._current_successors = [cond_line]
        for stmt in node.body:
            self.visit(stmt)
        then_successors = self._current_successors[:]

        # else branch
        if node.orelse:
            self._current_successors = [cond_line]
            for stmt in node.orelse:
                self.visit(stmt)
            else_successors = self._current_successors[:]
        else:
            else_successors = [cond_line]  # no else: cond falls through

        # merge
        self._current_successors = then_successors + else_successors

    def visit_For(self, node):
        """Loop head -> body -> back edge to head + loop exit."""
        loop_line = node.lineno
        self._add_node(loop_line, "For")
        self._connect_predecessors(loop_line)

        # body
        self._current_successors = [loop_line]
        for stmt in node.body:
            self.visit(stmt)
        body_successors = self._current_successors[:]

        # back edge: body end -> loop head
        for s in body_successors:
            self.edges.append((s, loop_line))

        # loop exit (condition false): loop head -> next statement
        self._current_successors = [loop_line]

    # While has the same CFG structure as For (loop head -> body -> back edge
    # + exit -> else). The else trigger differs (for: normal end; while: cond
    # False) but does not affect reachability analysis. P2-4: alias is correct.
    visit_While = visit_For

    def visit_Try(self, node):
        """try body + except handlers + else + finally.

        Key invariant (P1-2 fix): except branches connect from try_line (entry),
        NOT from try_successors (body exit). Rationale: any statement in try
        body can raise and jump to except, even if try body ends with return.
        return clears _current_successors, but must NOT affect except reachability.
        If we connected from try_successors, try body with return would yield
        try_successors=[] -> except has no in-edge -> except falsely flagged
        as dead code.
        """
        try_line = node.lineno
        self._add_node(try_line, "Try")
        self._connect_predecessors(try_line)

        # try body
        self._current_successors = [try_line]
        for stmt in node.body:
            self.visit(stmt)
        try_successors = self._current_successors[:]

        # except branches: connect from try_line (P1-2 fix), not try_successors
        all_branch_exits = try_successors[:]
        for handler in node.handlers:
            handler_line = handler.lineno
            self._add_node(handler_line, "ExceptHandler")
            self.edges.append((try_line, handler_line))  # P1-2: from try entry
            self._current_successors = [handler_line]
            for stmt in handler.body:
                self.visit(stmt)
            all_branch_exits.extend(self._current_successors[:])

        # else branch (if try has no exception): from try_successors
        # try body return -> try_successors=[] -> else unreachable (correct)
        if node.orelse:
            self._current_successors = try_successors[:]
            for stmt in node.orelse:
                self.visit(stmt)
            all_branch_exits.extend(self._current_successors[:])

        # finally: from all branch exits
        if node.finalbody:
            finally_line = node.finalbody[0].lineno
            self._add_node(finally_line, "Finally")
            for s in all_branch_exits:
                self.edges.append((s, finally_line))
            self._current_successors = [finally_line]
            for stmt in node.finalbody:
                self.visit(stmt)

        self._current_successors = all_branch_exits

    def visit_Return(self, node):
        """Terminal node: subsequent statements unreachable."""
        self._add_node(node.lineno, "Return")
        self._connect_predecessors(node.lineno)
        self._current_successors = []  # clear: following unreachable

    visit_Raise = visit_Return  # raise is also terminal

    # match/case (Python 3.10+)
    def visit_Match(self, node):
        """match -> N case branches -> merge."""
        match_line = node.lineno
        self._add_node(match_line, "Match")
        self._connect_predecessors(match_line)

        all_case_exits = []
        for case in node.cases:
            self._current_successors = [match_line]
            for stmt in case.body:
                self.visit(stmt)
            all_case_exits.extend(self._current_successors[:])

        self._current_successors = all_case_exits

    def generic_visit(self, node):
        """Other statements: sequential connection."""
        if hasattr(node, "lineno"):
            self._add_node(node.lineno, type(node).__name__)
            self._connect_predecessors(node.lineno)
            self._current_successors = [node.lineno]
        super().generic_visit(node)


# ── Reachability BFS ────────────────────────────────────────────────────


def is_reachable(cfg_nodes, cfg_edges, entry_line, target_line):
    """BFS check: is target_line reachable from entry_line? O(V+E).

    Uses collections.deque for O(1) popleft (vs list.pop(0) which is O(N)).
    Complete traversal proves UNreachability (vs DFS which may miss paths).
    """
    if entry_line == target_line:
        return True
    if target_line not in cfg_nodes:
        return False

    # build adjacency list once: O(E)
    adjacency = {n: [] for n in cfg_nodes}
    for src, dst in cfg_edges:
        if src in adjacency:
            adjacency[src].append(dst)

    visited = {entry_line}
    queue = deque([entry_line])

    while queue:
        current = queue.popleft()  # O(1)
        for neighbor in adjacency.get(current, []):
            if neighbor == target_line:
                return True
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return False


# ── dead_code verification ──────────────────────────────────────────────


def _find_enclosing_function(tree, target_line):
    """Find the FunctionDef node whose body contains target_line. Returns None if module-level."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.lineno <= target_line and
                hasattr(node, "end_lineno") and
                node.end_lineno and node.end_lineno >= target_line):
                return node
    return None


def verify_dead_code_in_source(source_code, line):
    """Verify a dead_code claim at the given line. Returns unified schema.

    Returns:
        {"verified": True|False|None, "evidence": str, "tier": 2, "latency_ms": int}
        verified=True  -> line IS dead code (claim correct)
        verified=False -> line IS reachable (claim is hallucination)
        verified=None  -> cannot determine (parse error, etc.)
    """
    t0 = time.perf_counter()
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return {"verified": None, "evidence": f"SyntaxError: {e}",
                "tier": 2, "latency_ms": int((time.perf_counter() - t0) * 1000)}

    builder = CFGBuilder()

    # determine scope: function-level or module-level
    func_node = _find_enclosing_function(tree, line)
    if func_node is not None:
        builder.visit(func_node)
        entry_line = func_node.lineno
        scope = f"function '{func_node.name}'"
    else:
        builder.visit(tree)
        entry_line = 1  # module-level entry
        scope = "module"

    if line not in builder.nodes:
        return {"verified": None,
                "evidence": f"line {line} not a CFG node in {scope} (may be blank/comment)",
                "tier": 2, "latency_ms": int((time.perf_counter() - t0) * 1000)}

    reachable = is_reachable(builder.nodes, builder.edges, entry_line, line)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    if reachable:
        return {"verified": False,
                "evidence": f"ast CFG: line {line} reachable from {scope} entry (line {entry_line})",
                "tier": 2, "latency_ms": latency_ms}
    else:
        return {"verified": True,
                "evidence": f"ast CFG: line {line} unreachable from {scope} entry (line {entry_line})",
                "tier": 2, "latency_ms": latency_ms}


def verify_dead_code(repo_root, file_path, line_num):
    """Verify dead_code claim against a file on disk. Returns unified schema."""
    abs_path = Path(repo_root) / file_path
    if not abs_path.exists():
        return {"verified": None, "evidence": f"file not found: {file_path}",
                "tier": 2, "latency_ms": 0}
    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"verified": None, "evidence": f"read error: {e}",
                "tier": 2, "latency_ms": 0}
    return verify_dead_code_in_source(source, line_num)


# ── Import Graph + Cycle Detection ──────────────────────────────────────


def detect_cycle(graph):
    """Iterative 3-color DFS cycle detection. Returns cycle path or None.

    Three colors:
      White (0): unvisited
      Gray (1):  on current DFS path (being explored)
      Black (2): fully explored (all descendants visited)

    Iterative version avoids recursion stack overflow on deep import chains.
    Returns the cycle as a list like ["a", "b", "a"] if found.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    parent = {n: None for n in graph}

    for start_node in graph:
        if color[start_node] != WHITE:
            continue

        stack = [(start_node, 0)]  # (node, child_index)
        color[start_node] = GRAY

        while stack:
            node, idx = stack[-1]
            neighbors = graph.get(node, [])

            if idx < len(neighbors):
                # advance index: this is a list-element assignment (creates new
                # tuple, replaces old tuple in list). tuple itself is immutable.
                stack[-1] = (node, idx + 1)
                neighbor = neighbors[idx]

                if color.get(neighbor, WHITE) == GRAY:
                    # found cycle: backtrack via parent pointers
                    cycle = [neighbor]
                    current = node
                    while current != neighbor and current is not None:
                        cycle.append(current)
                        current = parent.get(current)
                    cycle.append(neighbor)
                    cycle.reverse()
                    return cycle

                if color.get(neighbor, WHITE) == WHITE:
                    color[neighbor] = GRAY
                    parent[neighbor] = node
                    stack.append((neighbor, 0))
            else:
                color[node] = BLACK
                stack.pop()

    return None


def _resolve_module(import_name, repo, current_file):
    """Resolve an import name to a project-internal module. External -> None."""
    # try: import_name -> import_name.py
    candidate = repo / (import_name.replace(".", os.sep) + ".py")
    if candidate.exists():
        return import_name
    # try: import_name -> import_name/__init__.py
    candidate_init = repo / import_name.replace(".", os.sep) / "__init__.py"
    if candidate_init.exists():
        return import_name
    return None  # external dependency (numpy, re, os, etc.)


def build_import_graph(repo_root):
    """Scan project .py files, build import graph. O(F*S).

    Uses pathlib.Path.rglob with generator for lazy traversal. Skips
    __pycache__ and .venv directories. External deps return None and are
    not added to the graph.
    """
    repo = Path(repo_root)
    graph = {}

    # lazy generator: doesn't load all files at once
    py_files = (f for f in repo.rglob("*.py")
                if "__pycache__" not in f.parts and ".venv" not in f.parts)

    for py_file in py_files:
        try:
            rel = py_file.relative_to(repo)
            module = str(rel.with_suffix("")).replace(os.sep, ".")
        except ValueError:
            continue  # file not under repo

        if module not in graph:
            graph[module] = []

        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(py_file))
        except SyntaxError:
            continue  # skip syntax-error files

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = _resolve_module(alias.name, repo, py_file)
                    if target and target not in graph[module]:
                        graph[module].append(target)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    target = _resolve_module(node.module, repo, py_file)
                    if target and target not in graph[module]:
                        graph[module].append(target)

    return graph


def verify_imports_in_repo(repo_root, claim):
    """Verify an import-related (circular dependency) claim. Returns unified schema.

    Returns:
        {"verified": True|False|None, "evidence": str, "tier": 2,
         "cycle": list|None, "latency_ms": int}
    """
    t0 = time.perf_counter()
    try:
        graph = build_import_graph(repo_root)
    except Exception as e:
        return {"verified": None, "evidence": f"build_import_graph error: {e}",
                "tier": 2, "cycle": None, "latency_ms": int((time.perf_counter() - t0) * 1000)}

    cycle = detect_cycle(graph)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    if cycle:
        return {"verified": True,
                "evidence": f"ast import graph: cycle detected: {' -> '.join(cycle)}",
                "tier": 2, "cycle": cycle, "latency_ms": latency_ms}
    else:
        return {"verified": False,
                "evidence": f"ast import graph: no cycle in {len(graph)} modules",
                "tier": 2, "cycle": None, "latency_ms": latency_ms}


def verify_imports(repo_root, claim):
    """Alias for verify_imports_in_repo (matches Plan §A.1 interface)."""
    return verify_imports_in_repo(repo_root, claim)


# ── CLI entry point ─────────────────────────────────────────────────────


def main():
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(
        description="Tier 2: Python ast CFG verifier for Phase 3.5")
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
            print(_json.dumps({"error": "--file and --line required for dead_code"}))
            return 2
        result = verify_dead_code(args.repo, args.file, args.line)
    else:
        result = verify_imports_in_repo(args.repo, args.claim)

    output = _json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    run_script(main)
