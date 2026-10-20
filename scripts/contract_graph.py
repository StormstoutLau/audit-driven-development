"""v3.0 T19: 跨模块契约确定性验证 (Tier 2, 纯 stdlib)。

复用 ast_cfg.build_import_graph，不引入任何新 runtime 依赖 (ADR-023)。
import-linter 仅作语义范本 (layers 顺序语义 + 间接依赖检测)，不作为依赖引入。

三态语义 (设计 spec D-T19-4 / 实施规范 §2.2):
    True  = claim 断言成立 (被禁方向 + 存在路径 + 未命中 allow)
    False = 声明合法且图完整，但断言不成立 (允许方向 / 无路径 / allow 例外)
    None  = 无裁决 (调用方不写 check，回落 generic)

图完整性哨兵 (D-T19-4): 模块数 > 1 且内部边 == 0 ⇒ 判 graph_incomplete ⇒ None。
原因: 0 边图与"确实无依赖"数值同形，若不拦截将产生系统性假 False (F-1 实测)。
"""

import ast
import os
import re
from pathlib import Path

import ast_cfg  # 复用既有导入图构建能力

# ── Constants ────────────────────────────────────────────────────────────

# 声明文件探测顺序 (实施规范 §2 / D-T19-2)
_DEFAULT_DECL_PATHS = (
    "docs/audit/guards.yml",
    "docs/audit/guards.project.yml",
    "docs/audit/guards.common.yml",
)

# 图缓存: 有界，键 = abs(root)，值 = (mtime_sig, graph)
_GRAPH_CACHE = {}
_GRAPH_CACHE_MAX = 8

_SKIP_PARTS = {"__pycache__", ".venv", ".git"}

# 方向判据: 仅 "X imports Y" 形态有方向语义 (实施规范 §2.1)
_IMPORTS_RE = re.compile(r"([\w\.]+)\s+imports\s+([\w\.]+)", re.IGNORECASE)
_IMPORTS_ITSELF_RE = re.compile(r"imports?\s+itself", re.IGNORECASE)

_DYNAMIC_NAMES = ("__import__", "import_module")


# ── Helpers ──────────────────────────────────────────────────────────────


def _skip(path):
    """排除 __pycache__ / .venv / .git (G-7: 防仓库根递归遍历 benchmark 克隆)。"""
    return bool(_SKIP_PARTS & set(path.parts))


def _norm(name):
    """去掉 .py 后缀，保留点分路径。"""
    if name and name.lower().endswith(".py"):
        return name[:-3]
    return name


def _mtime_sig(root):
    """图缓存失效签名 = root 下 .py 的最大 mtime。异常/空 ⇒ None。"""
    try:
        mtimes = [f.stat().st_mtime for f in Path(root).rglob("*.py") if not _skip(f)]
    except OSError:
        return None
    return max(mtimes) if mtimes else None


def _build_graph(root):
    """取导入图 —— 带缓存 + 图完整性哨兵。返回 None 表示不可用/图不完整。"""
    try:
        key = str(Path(root).resolve())
    except OSError:
        return None
    sig = _mtime_sig(root)
    if sig is None:
        return None
    cached = _GRAPH_CACHE.get(key)
    if cached is not None and cached[0] == sig:  # G-3: 命中条件 = 键存在 且 sig 相等
        return cached[1]
    try:
        graph = ast_cfg.build_import_graph(str(root))
    except Exception:
        return None
    if not graph:
        return None
    edges = sum(len(v) for v in graph.values() if v)
    if len(graph) > 1 and edges == 0:
        return None  # 哨兵: 防假 False (D-T19-4 / F-1)
    if len(_GRAPH_CACHE) >= _GRAPH_CACHE_MAX:
        _GRAPH_CACHE.clear()
    _GRAPH_CACHE[key] = (sig, graph)
    return graph


def _module_file(root, module):
    """模块名 → 文件路径 (G-4)。不存在 ⇒ None。"""
    base = Path(root)
    for cand in (base / (module.replace(".", os.sep) + ".py"),
                 base / module.replace(".", os.sep) / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def _has_dynamic_import_at(root, module):
    """该模块是否含动态 import (__import__ / importlib.import_module)。"""
    f = _module_file(root, module)
    if f is None:
        return False
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"), filename=str(f))
    except (SyntaxError, OSError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in _DYNAMIC_NAMES:
                return True
            if isinstance(fn, ast.Attribute) and fn.attr in _DYNAMIC_NAMES:
                return True
    return False


def layer_of(module, layers):
    """层↔模块前缀映射 (最长匹配)。未命中 ⇒ None。"""
    best = None
    for name in layers:
        if module == name or module.startswith(name + "."):
            if best is None or len(name) > len(best):
                best = name
    return best


def find_path(graph, src, dst):
    """模块图可达性 + 路径证据 (G-2)。BFS + 前驱回溯；含环安全。无路径 ⇒ None。"""
    if src not in graph or dst not in graph:
        return None
    if src == dst:
        return [src, src] if src in graph.get(src, []) else None
    prev = {src: None}
    queue = [src]
    head = 0
    while head < len(queue):
        cur = queue[head]
        head += 1
        for nxt in graph.get(cur, []):
            if nxt in prev:
                continue
            prev[nxt] = cur
            if nxt == dst:
                path = [dst]
                while path[-1] != src:
                    path.append(prev[path[-1]])
                path.reverse()
                return path
            queue.append(nxt)
    return None


# ── Declaration loading ──────────────────────────────────────────────────


def _load_yaml(path):
    """可选 YAML 解析。无 PyYAML / 解析失败 / 顶层非 dict ⇒ None (不抛异常)。"""
    try:
        import yaml
    except ImportError:
        return None
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _validate_layers(contract):
    """声明合法性 (实施规范 §2)。"""
    if not isinstance(contract, dict):
        return False
    if contract.get("kind") != "layers":
        return False
    layers = contract.get("layers")
    if not isinstance(layers, list) or len(layers) < 2:
        return False
    if not all(isinstance(x, str) and x for x in layers):
        return False
    if len(set(layers)) != len(layers):
        return False
    allow = contract.get("allow") or []
    if not isinstance(allow, list):
        return False
    for pair in allow:
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2
                and all(isinstance(x, str) for x in pair)):
            return False
    return True


def load_contract_declarations(repo_root, guards_path=None):
    """按优先级探测 + 解析 + 校验。无有效声明 ⇒ None。"""
    for rel in ((guards_path,) if guards_path else _DEFAULT_DECL_PATHS):
        p = Path(rel) if guards_path else Path(repo_root) / rel
        if not p.is_file():
            continue
        data = _load_yaml(p)
        if data is None:
            return None
        decls = []
        for g in (data.get("guards") or []):
            if not isinstance(g, dict):
                continue
            c = g.get("contract")
            if c and _validate_layers(c):
                decls.append({
                    "rule_id": g.get("id"),
                    "severity": g.get("severity"),
                    "root": c.get("root", "."),
                    "kind": c.get("kind"),
                    "layers": list(c.get("layers")),
                    "allow": [list(x) for x in (c.get("allow") or [])],
                })
        return decls or None
    return None


# ── Direction & evaluation ───────────────────────────────────────────────


def _parse_direction(claim):
    """claim → (src, dst)。自环 / between / among / 无方向 ⇒ None (H4)。"""
    if not claim:
        return None
    if _IMPORTS_ITSELF_RE.search(claim):
        return None
    m = _IMPORTS_RE.search(claim)
    if not m:
        return None
    src = _norm(m.group(1))
    dst = _norm(m.group(2))
    if not src or not dst or src == dst:
        return None
    return (src, dst)


def evaluate_contract(graph, decl, src, dst, incomplete=False):
    """三态求值 (实施规范 §2.2)。layers[0] = 最高层。

    incomplete: 图可能不完整（src 含动态 import）。
        **仅影响「被禁方向 + 无路径」这一支** —— 此时不可判 False（边可能被隐藏），
        改判 None。「允许方向的 False」与图完整性无关，不受影响。
        (Step 9 实施期细化: v1.0 曾在 verify_contract 里无条件跳过含动态导入的模块，
         导致 ADD 自身的真实用例永久不可求值 —— 见实施规范 §2.2 注。)
    """
    layers = decl["layers"]
    a = layer_of(src, layers)
    b = layer_of(dst, layers)
    if a is None or b is None:
        return None
    ia, ib = layers.index(a), layers.index(b)
    if ia == ib:
        return None  # 同层 ⇒ 层次语义不适用
    if ia < ib:
        return False  # src 更高 ⇒ 允许方向 ⇒ 断言不成立（与图完整性无关）
    # ia > ib: src 更低 ⇒ 被禁方向
    if find_path(graph, src, dst) is None:
        return None if incomplete else False
    if [src, dst] in decl["allow"]:
        return False  # 反向例外 ⇒ 断言不成立
    return True


# ── Public entry ─────────────────────────────────────────────────────────


def verify_contract(repo_root, claim, evidence=None, guards_path=None, language="python"):
    """对外唯一入口。返回统一 schema dict，或 None 表示无裁决。

    None 的触发见设计 spec §2.3 十条清单。
    """
    if language != "python":
        return None  # AC-15: Tier 2 仅 python

    decls = load_contract_declarations(repo_root, guards_path)
    if not decls:
        return None

    direction = _parse_direction(claim)
    if direction is None:
        return None
    src, dst = direction

    for decl in sorted(decls, key=lambda d: str(d.get("rule_id") or "")):
        root = Path(repo_root) / decl["root"]
        graph = _build_graph(root)
        if graph is None:
            continue  # 含图完整性哨兵
        if src not in graph or dst not in graph:
            continue
        if layer_of(src, decl["layers"]) is None or layer_of(dst, decl["layers"]) is None:
            continue
        # 动态 import ⇒ 图可能不完整 ⇒ 只影响「被禁方向 + 无路径」这一支（见 evaluate_contract）
        incomplete = _has_dynamic_import_at(root, src)
        verdict = evaluate_contract(graph, decl, src, dst, incomplete=incomplete)
        if verdict is None:
            continue
        return {
            "verified": verdict,
            "confirmed": verdict,
            "tier": 2,
            "reason": ("layer_violation_confirmed" if verdict
                       else "layer_assertion_refuted"),
            "kind": decl["kind"],
            "rule_id": decl.get("rule_id"),
            "modules": {"src": src, "dst": dst},
            "path": find_path(graph, src, dst),
            "claim_types": ["contract_related"],
        }
    return None
