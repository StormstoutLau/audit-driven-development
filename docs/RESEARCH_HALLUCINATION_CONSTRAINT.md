# 调研报告：ADD Skill 幻觉约束机制与形式化验证前景

> **版本**: v1.0 | **日期**: 2026-07-26 | **作者**: Scott (鹏)
> **关联版本**: ADD v3.5 (Phase 3.5 Finding Verification)

---

## 目录

1. [当前 Skill 的幻觉约束机制](#1-当前-skill-的幻觉约束机制)
2. [外部工具对比分析](#2-外部工具对比分析)
3. [Lean4 形式化验证前景](#3-lean4-形式化验证前景)
4. [阶段 1: 规则形式化详细调研](#4-阶段-1-规则形式化详细调研)
5. [结论与建议](#5-结论与建议)

---

## 1. 当前 Skill 的幻觉约束机制

### 1.1 架构概览

当前 ADD skill 采用 **后验验证（post-hoc verification）** 架构 — 不阻止 subagent 产生幻觉，而是在幻觉进入修复基线前拦截。

```
subagent 产生 findings (可能含幻觉)
        ↓
Phase 3 聚合 + 分级 (P0/P1/P2/P3)
        ↓
Phase 3.5 验证关卡 ← 幻觉拦截点
        ↓
Phase 4 修复基线 (幻觉已被移除)
```

### 1.2 四级验证机制

| Level | 验证手段 | 幻觉类型 | 拦截率 | 适用严重度 |
|---|---|---|---|---|
| **L1** | `Path.exists()` 文件存在性检查 | 文件名幻觉（编造不存在的文件） | ~100% | P0 + P1 |
| **L2** | 行号范围检查 `1 ≤ line ≤ len(lines)` | 行号幻觉（编造越界行号） | ~100% | P0 + P1 |
| **L3** | 关键词在 ±20 行窗口内匹配 | 证据不匹配（声称的代码模式不存在） | ~70-80% | P0 only |
| **L4** | 6 种 claim 类型的结构性验证 | 语义幻觉（claim 与代码语义矛盾） | ~50-60% | P0 only |

### 1.3 Action Matrix

| 验证结果 | 动作 | 严重度变化 | 后续处理 |
|---|---|---|---|
| **verified** (P0 L4) | 保留 | P0 不变 | 进入 Phase 4 修复基线 |
| **verified_l1l2** (P1 L1+L2) | 保留 | P1 不变 | 进入 Phase 4 修复基线 |
| **partial** (P0 L3 only, L4 fail) | 降级 | P0 → P1 | 标记 `_phase35_action: downgraded`，需人工审核 |
| **unverified** (L1/L2 fail) | 移出 | 从基线移除 | 记录到 `hallucination_log.json`（区分 P0/P1 幻觉） |

### 1.4 L4 保守回退策略 (v3.5 fix)

当 L4 结构性验证无法提取 claim 关键词时，默认 `confirmed=False`（保守策略），触发 `partial` → P0 降级 P1 人工审核。三处回退点：

- `_verify_missing`: 无法提取 missing_thing → `confirmed=False`
- `_verify_wrong`: 无法提取 wrong_thing → `confirmed=False`
- `_verify_violates`: 无法提取 violation_thing → `confirmed=False`

### 1.5 核心局限

1. **L4 依赖正则启发式**：6 种 claim 类型用正则匹配分类，对复杂多从句 claim 提取成功率未知。保守回退是正确策略，但意味着复杂 claim 全部降级为人工审核，人工成本高。

2. **单向验证**：只验证 "claim 描述的代码是否存在"，不验证 "claim 的结论是否正确"。例如 claim 说 "missing error handling"，L4 只验证 error handling 确实缺失，但不验证 "这里是否应该有 error handling"（后者的判断超出正则能力）。

3. **无 ground truth 对比**：当前机制不引入外部知识源（如 spec、ADR、API 文档）进行交叉验证。subagent 的 claim 是自 referential 的——用 claim 关键词去匹配 claim 指向的代码，没有独立信息源。

---

## 2. 外部工具对比分析

### 2.1 AnySearch

**产品定位**: 为 AI Agent 设计的搜索基础设施（2026年5月上线，登顶 Product Hunt 周榜），为 Agent 提供高质量外部信息检索，优化 Agent 的输入信息质量。属于 RAG（检索增强生成）生态的 Agent 专用层。

**对本项目的幻觉约束价值**:

| 幻觉类型 | AnySearch 能否约束 | 原因 |
|---|---|---|
| **事实幻觉**（编造库/API/文档） | ✅ 强 | 直接检索真实文档作为 ground truth |
| **引用幻觉**（编造论文/URL） | ✅ 强 | 搜索验证引用是否存在 |
| **代码审计幻觉**（编造文件/行号/模式） | ❌ 弱 | 代码审计的 ground truth 是本地源码，不是外部知识 |

**关键判断**: AnySearch 对本项目的价值有限。代码审计的幻觉是 "Agent 编造了不存在的本地代码模式"，ground truth 在本地文件系统，不在互联网。已有的等效机制（`mcp_lookup.py` v2.3 + `benchmark_syncer.py` v2.3）已实现从外部知识源检索最佳实践。

**潜在价值场景**: AnySearch 可以在 Phase 2（subagent 审计）时为 subagent 提供外部最佳实践上下文，减少因"不知道正确做法"而产生的误报。但这属于输入端增强，不是输出端验证，与 Phase 3.5 的定位不同。

### 2.2 其他工具对比

| 工具 | 类型 | 幻觉约束机制 | 对本项目的价值 |
|---|---|---|---|
| **AnySearch** | RAG 检索层 | 外部知识 ground truth | 低 — 场景不匹配（外部知识 vs 本地源码） |
| **Self-RAG / CRAG** | 自我评估 RAG | 检索结果自我评估 | 中 — 可用于 L4 的 claim 自我评估层 |
| **Knowledge Graph** | 结构化知识库 | 结构化对比 | 中 — 可为 L4 提供代码模式的结构化对比 |
| **Harness Engineering** | 运行环境约束 | 限制 Agent 行为边界 | 高 — 限制 Agent 行为，但不直接约束幻觉 |
| **verified-ledger** | Lean4 oracle | 形式化模型作为测试预言机 | 极高 — 直接先例，Lean4 作为 oracle 验证 claim |
| **neuro-symbolic proof** | LLM + 形式化 | LLM 生成命题 + 自动证明 | 极高 — claim → Lean4 命题翻译的理论基础 |
| **Aesop** | Lean4 自动证明搜索 | 自动化证明搜索 | 中 — 可自动化不可达性/无环性证明 |

### 2.3 工具分类总结

幻觉约束工具按作用环节分为三类：

```
输入端 (预防幻觉)
├── AnySearch (RAG 检索增强)
├── Knowledge Graph (结构化上下文)
└── Harness Engineering (行为约束)

处理端 (检测幻觉) ← 当前 Phase 3.5 所处位置
├── Self-RAG (自我评估)
├── 正则 L4 (当前实现, ~50-60% 准确率)
└── Lean4 形式化验证 (目标方案, 100% 准确率)

输出端 (纠正幻觉)
├── hallucination_log.json (幻觉记录)
├── partial 降级机制 (P0→P1)
└── human review (人工审核)
```

---

## 3. Lean4 形式化验证前景

### 3.1 为什么 Lean4 是最终答案

当前 L4 用正则启发式验证 claim 的结构性正确性，有两个根本缺陷：

1. **正则无法表达语义**：`re.search(r"\bmissing\b", claim)` 只能匹配 "missing" 这个词，不能判断 "missing" 的语义是否成立
2. **无法证明否定命题**：`_verify_missing()` 验证 "某元素确实缺失" 时，只能检查关键词是否出现，不能形式化证明 "该元素在所有可能的代码路径中都不存在"

Lean4 提供数学确定性的验证：

| 当前 L4 (正则) | Lean4 形式化验证 |
|---|---|
| `re.search(r"\bmissing\b", claim)` → 匹配到 "missing" | `theorem missing_error_handling : ¬ ∃ path, reaches(path, raise_call)` → 证明所有路径都不经过 raise |
| `re.search(r"\bdead\s+code\b", claim)` → 匹配到 "dead code" | `theorem unreachable : ∀ cfg, ¬ reachable(start, cfg)` → 形式化证明不可达 |
| `re.search(r"\bcircular\s+dep\b", claim)` → 匹配到 "circular dep" | `theorem acyclic_deps : ∀ n, ¬ path(n, n) in import_graph` → 证明导入图无环 |

形式化验证的结论是**数学确定性**的 — proved 就是 proved，disproved 就是 disproved，不存在 "~50-60% 准确率" 的问题。

### 3.2 三阶段应用路径

| 阶段 | 目标 | 时间 | 创新性 |
|---|---|---|---|
| **阶段 1: 规则形式化** | 将可形式化的审计规则转化为 Lean4 命题 | 短期可行 | 高 |
| **阶段 2: Claim 自动形式化** | subagent 的 NL claim 自动翻译为 Lean4 命题 | 中期研究 | 极高 |
| **阶段 3: 形式化 oracle** | Lean4 替代正则 L4 | 长期愿景 | 革命性 |

### 3.3 与 Research OS 的对齐

Phase 3.5 的 L4 正则验证是 "检测幻觉的方法"，而 Lean4 形式化验证是 **"形式化证明幻觉存在/不存在的方法"** — 这是从启发式到形式化的跃迁，与 "形式先行 → 数值证伪 → 回溯形式化" 的研究方法论完全一致。

---

## 4. 阶段 1: 规则形式化详细调研

### 4.1 当前 L4 正则验证逐函数解剖

#### 4.1.1 `_verify_dead_code` (L307-320)

```python
# 当前实现：只检查前一行是否是 return/raise/exit
for i in range(line_num - 2, -1, -1):
    stripped = all_lines[i].strip()
    if stripped and not stripped.startswith("#"):
        if re.match(r'^\s*(?:return|raise|sys\.exit|exit)\b', stripped):
            has_return_before = True
        break  # 只看最近一行非注释代码
```

| 缺陷 | 说明 | 幻觉风险 |
|---|---|---|
| 只看 1 行 | 不处理 `if/else` 分支、`try/except`、`for/while` 循环 | claim 说 "dead code" 但代码在另一分支可达 → 误报 |
| 无 CFG | 没有控制流图，无法判断跨函数可达性 | claim 说 "unreachable" 但通过函数调用可达 → 漏报 |
| 无数据流 | 不追踪变量赋值，无法判断条件分支是否恒真/恒假 | `if True: return` 后的代码是 dead code，但正则不识别 `True` |

**估计准确率**: ~40% — 只能捕获最简单的 "return 后紧跟代码" 模式

#### 4.1.2 `_verify_import` (L323-337)

```python
# 当前实现：正则匹配 import 语句是否存在
import_names = re.findall(r'(?:import|from)\s+(\S+)', claim)
pattern = re.compile(r'(?:import|from)\s+' + re.escape(name) + r'\b')
found = bool(pattern.search(context_text))
```

| 缺陷 | 说明 | 幻觉风险 |
|---|---|---|
| 只验证存在性 | 不检查循环依赖 | claim 说 "circular dependency" 但只验证 import 存在 |
| 无图结构 | 不构建导入图，无法检测环 | A→B→C→A 的环完全不可检测 |
| 无使用分析 | 不检查 import 是否被使用 | claim 说 "unused import" 但只验证 import 存在（反向） |

**估计准确率**: ~60% — 能验证 import 存在，但无法验证循环依赖

#### 4.1.3 `_verify_missing` (L192-223)

```python
# 当前实现：提取"缺失的元素"关键词，检查它在上下文中不存在
pattern_present = _check_pattern_present(missing_thing, context_text)
return {"confirmed": not pattern_present}  # 不存在 → confirmed=True
```

**根本局限**: 验证 "X 不在上下文中" ≠ 验证 "X 应该存在但不存在"。后者是设计判断，不是事实检查。**不可形式化** — "应该有 error handling" 需要外部规约定义。

#### 4.1.4 `_verify_wrong` (L258-280)

```python
# 当前实现：提取"错误的元素"关键词，检查它在上下文中存在
found = any(kw.lower() in context_lower for kw in keywords)
return {"confirmed": found}  # 存在 → confirmed=True
```

**根本局限**: 验证 "提到的模式存在" ≠ 验证 "这个模式是错误的"。需要 ground truth 对比。**不可形式化**。

#### 4.1.5 `_verify_violates` (L283-304)

```python
# 当前实现：提取"违反的规则"关键词，检查相关关键词存在
found = any(kw.lower() in context_lower for kw in keywords)
return {"confirmed": found}
```

**根本局限**: 与 `_verify_wrong` 相同。**不可形式化**（阶段 1 范围内）。

#### 4.1.6 `_verify_generic`

纯关键词匹配，无结构验证能力。**不可形式化**。

### 4.2 可形式化程度排序

| Claim 类型 | 可形式化程度 | 当前 L4 准确率 | Lean4 替代方案 | 技术难度 | 优先级 |
|---|---|---|---|---|---|
| `dead_code` | **高** | ~40% | CFG 不可达性证明 | 中 | **P0** |
| `import_related` | **高** | ~60% | 依赖图无环性证明 | 低 | **P0** |
| `violates` (contract) | 中 | ~30% | Hoare 逻辑前置/后置条件 | 高 | P2 |
| `missing` | 低 | ~50% | 需要设计判断 | - | 不做 |
| `wrong` | 低 | ~40% | 需要 ground truth | - | 不做 |
| `generic` | 不可 | ~30% | 无法形式化 | - | 不做 |

**结论**: 阶段 1 聚焦 `dead_code` 和 `import_related` 两类，覆盖率 ~25% 的 P0 claim，但这是正则 L4 准确率最低、形式化收益最高的 25%。

### 4.3 `dead_code` 的 Lean4 形式化

#### 当前正则 vs Lean4 方案

**当前正则**: 检查前一行是否是 return/raise → ~40% 准确率

**Lean4 方案**: 构建 CFG，证明不可达性

```lean4
-- Python AST → Lean4 CFG 表示
inductive PyStmt where
  | assign : String → PyExpr → PyStmt
  | return : PyExpr → PyStmt
  | raise : PyExpr → PyStmt
  | ifThen : PyExpr → List PyStmt → List PyStmt → PyStmt
  | forWhile : PyExpr → List PyStmt → PyStmt
  | pass : PyStmt

-- 控制流图
structure CFG where
  nodes : List (Nat × PyStmt)     -- (line_number, statement)
  edges : List (Nat × Nat)         -- (src_line, dst_line)
  entry : Nat                      -- 入口行号

-- 可达性：标准图的传递闭包
def reachable (cfg : CFG) (src dst : Nat) : Prop :=
  ∃ path : List Nat, path.head? = some src ∧ path.getLast? = some dst ∧
    ∀ i : Fin (path.length - 1),
      (path[i], path[i+1]) ∈ cfg.edges

-- dead_code claim 的形式化命题
-- "line N 是 dead code" ⟺ "entry 不可达 N"
theorem dead_code_at_line (cfg : CFG) (n : Nat) :
  ¬ reachable cfg cfg.entry n ↔ isDeadCode cfg n := by
  -- 通过 BFS/DFS 构造性证明：枚举所有路径，均不包含 n
  sorry
```

**技术路径**:
1. Python `ast` 模块解析源码 → AST JSON
2. Python 脚本将 AST JSON 转换为 Lean4 `CFG` 结构
3. Lean4 证明器检查可达性
4. 返回 `proved` (确实不可达) / `disproved` (可达，claim 是幻觉)

**关键优势**: CFG 可达性是**可判定问题**（有限图），Lean4 可以通过构造性证明（BFS/DFS 遍历）给出确定性答案。

### 4.4 `import_related` 的 Lean4 形式化

#### 当前正则 vs Lean4 方案

**当前正则**: 只检查 import 语句存在 → ~60% 准确率，无法检测循环依赖

**Lean4 方案**: 构建导入图，证明无环性

```lean4
-- 导入图
structure ImportGraph where
  modules : List String
  edges : List (String × String)  -- (importer, imported)

-- 路径定义
def importPath (g : ImportGraph) (src dst : String) : Prop :=
  ∃ path : List String, path.head? = some src ∧ path.getLast? = some dst ∧
    ∀ i : Fin (path.length - 1), (path[i], path[i+1]) ∈ g.edges

-- 循环依赖：存在模块自环
def hasCircularDep (g : ImportGraph) : Prop :=
  ∃ m : String, m ∈ g.modules ∧ importPath g m m

-- "无循环依赖" 的形式化命题
theorem acyclic_imports (g : ImportGraph) :
  ¬ hasCircularDep g := by
  -- 通过拓扑排序证明：存在拓扑序使得所有边正向
  sorry

-- "模块 A 循环依赖模块 B" 的形式化命题
theorem circular_dep_between (g : ImportGraph) (a b : String) :
  importPath g a b ∧ importPath g b a := by
  -- 找到 A→B 和 B→A 的路径
  sorry
```

**技术路径**:
1. Python 脚本扫描项目所有 `.py` 文件的 import 语句
2. 构建导入图 JSON
3. Lean4 验证器检查无环性
4. 返回 `proved` (确实无环，claim 是幻觉) / `disproved` (有环，claim 正确)

**关键优势**: 图无环性是**可判定问题**（拓扑排序），Lean4 可以确定性判定。

### 4.5 已有 Lean4 元编程经验

检查 `d:\Textbook` 目录发现，团队（Yuanhe Zhang 等）已实现 `UnusedHaveDetector.lean` — 一个 Lean4 元编程工具，用于检测 Lean4 证明中未使用的 `have` 语句。

**关键代码**:
```lean4
def checkLetEUsage (declName : Name) (type : Expr) (value : Expr)
    (body : Expr) (nondep : Bool) (st : TraverseState) : MetaM TraverseState := do
  if !nondep then return st
  withLetDecl declName type value fun fvar => do
    let fvarId := fvar.fvarId!
    let bodyInst := body.instantiate1 fvar
    if !bodyInst.containsFVar fvarId then
      return { st with unused := st.unused.push { ... } }
```

**意义**: 这个工具已实现：
- Lean4 `Expr` 树遍历（`traverseExpr`）
- 元编程命令（`#check_unused_have`）
- 批量声明分析（`analyzeAllWithPrefix`）

`traverseExpr` 的架构可以直接用于 CFG 构建——遍历 AST 节点，收集控制流边。从 "遍历 Lean4 Expr" 到 "遍历 Python AST" 的技术跳跃很小。

### 4.6 集成架构设计

#### 4.6.1 整体架构

```
Phase 3.5 L4 验证流程:
┌──────────────────────────────────────────────────────────┐
│  classify_claim(claim) → claim_types                     │
├──────────────────────────────────────────────────────────┤
│  对每个 claim_type:                                      │
│                                                          │
│  ┌─ dead_code ──→ Lean4 CFG 验证器 (新增) ──┐           │
│  │  import_related → Lean4 图论验证器 (新增) │→ 合并结果  │
│  └─ missing/wrong/violates/generic → 正则 (保留) ─┘     │
│                                                          │
│  Lean4 结果优先级 > 正则结果                              │
└──────────────────────────────────────────────────────────┘
```

#### 4.6.2 数据流

```
Python 源码
    ↓ ast.parse()
AST JSON
    ↓ extract_cfg.py (新增)
CFG JSON  +  Import Graph JSON
    ↓
Lean4 验证器 (lean4_verify.py 调用)
    ↓ lake build + lake eval
{ "dead_code": "proved" | "disproved" | "unknown",
  "import_cycle": "proved" | "disproved" | "unknown" }
    ↓
verify_findings.py L4 合并
    ↓ confirmed (Lean4 优先) / partial / unverified
```

#### 4.6.3 新增文件

| 文件 | 功能 | 语言 |
|---|---|---|
| `scripts/lean4_verify.py` | Lean4 验证器调用层（subprocess + JSON） | Python |
| `scripts/extract_cfg.py` | Python AST → CFG JSON | Python |
| `scripts/extract_imports.py` | Python 项目 → Import Graph JSON | Python |
| `lean4/` 目录 | Lean4 项目 | Lean4 |
| `lean4/DeadCode.lean` | CFG 不可达性证明器 | Lean4 |
| `lean4/ImportGraph.lean` | 导入图无环性证明器 | Lean4 |
| `lean4/lakefile.lean` | Lean4 项目配置 | Lean4 |

#### 4.6.4 `verify_findings.py` 修改

```python
def verify_l4_structural(lines, line_num, claim, claim_types, repo_root=None, file_path=None):
    """L4: Structural claim verification.
    
    For dead_code/import_related: attempt Lean4 formal verification first,
    fall back to regex heuristics if Lean4 unavailable.
    """
    checks = {}
    
    if "dead_code" in claim_types:
        # 新增：Lean4 CFG 验证（如果可用）
        lean4_result = None
        if repo_root and file_path:
            lean4_result = lean4_verify_dead_code(repo_root, file_path, line_num)
        if lean4_result:
            checks["dead_code"] = lean4_result  # 形式化验证结果
        else:
            checks["dead_code"] = _verify_dead_code(context_text, lines, line_num)  # 正则 fallback
    
    if "import_related" in claim_types:
        lean4_result = None
        if repo_root:
            lean4_result = lean4_verify_imports(repo_root, claim)
        if lean4_result:
            checks["import_related"] = lean4_result
        else:
            checks["import_related"] = _verify_import(claim, context_text, lines, line_num)
    
    # missing/wrong/violates/generic 保持正则验证不变
    ...
```

### 4.7 可行性评估

#### 4.7.1 技术可行性

| 维度 | 评估 | 依据 |
|---|---|---|
| Lean4 元编程能力 | **高** | 已有 UnusedHaveDetector.lean 证明团队具备 Expr 遍历能力 |
| Python AST 解析 | **高** | Python `ast` 模块是标准库，项目已广泛使用 Python |
| CFG 构建 | **中** | 需要处理 if/else/try/except/for/while 的分支合并，但算法成熟 |
| 图无环性 | **高** | 拓扑排序是教科书算法，Lean4 可直接实现 |
| Lean4 ↔ Python 通信 | **高** | `lake eval` + JSON stdin/stdout，无需复杂 IPC |

#### 4.7.2 性能评估

| 操作 | 预期耗时 | 频率 | 总增量 |
|---|---|---|---|
| Python AST 解析 | <50ms/文件 | 每审计 1 次 | ~50ms |
| CFG 构建 | <100ms/文件 | 每审计 1 次 | ~100ms |
| Import 图构建 | <200ms/项目 | 每审计 1 次 | ~200ms |
| Lean4 不可达性证明 | <2s/claim | ~2-3 个 dead_code P0 | ~6s |
| Lean4 无环性证明 | <500ms/项目 | 1 次 | ~500ms |
| **总增量** | | | **~7s/审计** |

对于一次完整审计（通常 5-15 分钟），增加 7 秒是可接受的。

#### 4.7.3 覆盖率评估

```
claim 类型分布 (P0 估计):
├── dead_code:        ~15%  → Lean4 验证 (100% 准确率)
├── import_related:   ~10%  → Lean4 验证 (100% 准确率)  
├── missing:          ~25%  → 正则验证 (保留, ~50% 准确率)
├── wrong:            ~20%  → 正则验证 (保留, ~40% 准确率)
├── violates:         ~15%  → 正则验证 (保留, ~30% 准确率)
└── generic:          ~15%  → 正则验证 (保留, ~30% 准确率)

Lean4 覆盖: 25% 的 P0 claim，但准确率从 ~50% 提升到 100%
整体 L4 准确率提升: 从 ~40% 提升到 ~55% (25%×100% + 75%×40%)
```

#### 4.7.4 成本评估

| 成本项 | 估算 | 说明 |
|---|---|---|
| 开发时间 | 中 | 2 个 Lean4 证明器 + 2 个 Python 提取器 + 集成 |
| 依赖引入 | 低 | Lean4 编译器 + lake，不与现有 Python 工具链冲突 |
| 维护成本 | 低 | Lean4 证明一旦写好，无需修改；CFG 提取器需适配 Python 语法变化 |
| 运行时依赖 | 中 | 需要安装 Lean4（~500MB），但只在 P0 dead_code/import_related claim 时调用 |

#### 4.7.5 风险

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| Lean4 未安装 | 高（用户环境） | 降级为正则 fallback | 检测 Lean4 可用性，不可用时自动降级 |
| CFG 构建不完整 | 中 | 证明结果不可靠 | 先在项目自身代码上验证，积累测试用例 |
| Python 动态特性 | 中 | AST 无法捕获 `eval()`/`getattr()` 动态调用 | 在文档中声明限制：只覆盖静态可分析的代码 |
| Lean4 编译慢 | 低 | 首次编译慢 | 预编译，后续增量编译 <1s |

### 4.8 `violates` (contract) 的形式化评估

**为什么排在 P2 而非 P0**:

Hoare 逻辑需要形式化规约（前置条件 `P`、后置条件 `Q`）：

```lean4
-- Hoare 三元组
-- {P} S {Q} ⟺ 如果执行前 P 成立，则执行后 Q 成立
theorem hoare_triple (P Q : Prop) (S : PyStmt) :
  hoareValid P S Q := sorry
```

**困难**: 当前审计不维护形式化规约。subagent 的 claim 是自然语言（"violates spec X"），但 "spec X" 本身没有被形式化定义。需要先建立规约库，这是阶段 2 的任务。

### 4.9 实施路径

#### 阶段 1a: `import_related` 无环性证明器（先做，难度低）

1. 编写 `extract_imports.py`：扫描项目 import 语句，输出 JSON 图
2. 编写 `lean4/ImportGraph.lean`：拓扑排序 + 无环性证明
3. 编写 `lean4_verify.py`：调用 Lean4 验证器
4. 集成到 `verify_findings.py` 的 `_verify_import`
5. TDD：测试用例覆盖有环/无环场景

#### 阶段 1b: `dead_code` 不可达性证明器（后做，难度中）

1. 编写 `extract_cfg.py`：Python AST → CFG JSON
2. 编写 `lean4/DeadCode.lean`：BFS 可达性证明
3. 集成到 `verify_findings.py` 的 `_verify_dead_code`
4. TDD：测试用例覆盖 return/raise/if-else/try-except/for 场景

#### 验收标准

- Lean4 验证器在 `dead_code` 和 `import_related` claim 上达到 100% 准确率
- 正则 L4 作为 fallback 保留，Lean4 不可用时不影响现有功能
- 全量 TDD 测试通过（250+ 现有 + 新增 Lean4 验证测试）

### 4.10 与前沿研究的对齐

| 前沿工作 | 关联 |
|---|---|
| **verified-ledger** (2026-01) | 直接先例 — Lean4 作为 oracle 验证实现逻辑，本项目用 Lean4 作为 oracle 验证审计 claim |
| **neuro-symbolic proof search** (2026-03, 南大/ETH) | 同源思路 — LLM 生成命题 + 形式化验证，本项目的 claim → Lean4 命题翻译是其具体应用 |
| **Aesop** (Lean4 自动证明搜索) | 可用于自动化不可达性/无环性证明的搜索过程 |
| **Formal Proof Bench** (2026-03) | 评估 LLM 生成形式化证明的能力，可用于评估 claim → Lean4 命题的自动翻译质量 |

---

## 5. 结论与建议

### 5.1 核心判断

| 方向 | 价值 | 成本 | 建议 |
|---|---|---|---|
| **AnySearch 集成** | 低 | 低 | 不推荐 — 场景不匹配 |
| **Self-RAG 评估** | 中 | 中 | 可选 — L4 的 LLM 自我评估层 |
| **Lean4 形式化 L4** | 极高 | 高 | **推荐** — 核心创新方向 |

### 5.2 阶段 1 规则形式化判断

**技术可行、收益明确、风险可控**：

1. **已有技术基础** — UnusedHaveDetector.lean 证明团队具备 Lean4 元编程能力
2. **先例存在** — verified-ledger 验证了 "Lean4 作为 oracle" 的架构模式
3. **问题可判定** — CFG 可达性和图无环性都是可判定问题，Lean4 可以给出 100% 确定性答案
4. **增量部署** — 正则 L4 作为 fallback，Lean4 作为升级路径，不影响现有功能
5. **覆盖 25% 但价值最高** — 这 25% 是正则准确率最低（~40-60%）的部分，提升到 100% 的边际收益最大

### 5.3 实施建议

**从 `import_related` 开始**（难度低、算法成熟），验证集成架构后再做 `dead_code`（难度中、需要 CFG 构建）。

当前 Phase 3.5 的正则 L4 是 **"足够好的工程方案"**，但不是 **"最终答案"**。Lean4 形式化验证才是作为方法论发明家应该追求的最终答案。

---

## 附录 A: 相关文件索引

| 文件 | 说明 |
|---|---|
| `scripts/verify_findings.py` | Phase 3.5 验证引擎，含 L1-L4 四级验证 |
| `scripts/test_v35_consistency.py` | Phase 3.5 TDD 测试（51 项） |
| `SKILL.md` §Phase 3.5 | Phase 3.5 规范文档 |
| `d:\Textbook\lean-stat-learning-theory\vibe-recipe\UnusedHaveDetector.lean` | 已有 Lean4 元编程经验 |
| `docs/RESEARCH_HALLUCINATION_CONSTRAINT.md` | 本文档 |

## 附录 B: 术语表

| 术语 | 定义 |
|---|---|
| **Hallucination (幻觉)** | LLM 编造不存在的代码模式/文件/行号/行为 |
| **Post-hoc verification** | 在 LLM 输出后进行验证，而非在生成时阻止 |
| **CFG (Control Flow Graph)** | 控制流图，表示程序所有可能执行路径的有向图 |
| **Reachability** | 图中从源节点到目标节点是否存在路径 |
| **DAG (Directed Acyclic Graph)** | 有向无环图，拓扑排序可判定 |
| **Hoare Logic** | 形式化验证程序正确性的逻辑系统，使用前置/后置条件 |
| **Oracle** | 在测试/验证中提供正确答案的权威来源 |
| **Lean4** | 交互式定理证明器，支持构造性数学和形式化验证 |
| **Aesop** | Lean4 的自动证明搜索工具 |
