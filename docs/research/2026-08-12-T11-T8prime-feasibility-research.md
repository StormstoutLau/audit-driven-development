# T11 (Java AST CFG 扩展) 与 T8' (深化 Joern 跨文件验证) 技术可行性与稳定性调研报告

> **版本**: v1.0 | **日期**: 2026-08-12 | **作者**: Scott + Subagent
> **任务定位**: ADD Framework v3.0+ 中期任务技术调研
> **方法论**: 文件审计 + 多源 Web 调研 + 现有代码库逆向分析 + 业界案例对比
> **范围声明**: 本报告仅做研究，不写代码。所有外部引用均注明来源 URL。

---

## Abstract

本报告对 ADD Framework v3.0+ 路线图中的两个中期任务 — **T11 (Java AST CFG 扩展)** 与 **T8' (深化 Joern 跨文件验证)** — 进行系统性的技术可行性与稳定性评估。核心结论有三：

1. **T11 推荐采用 "tree-sitter-java + 自建 CFG" 路径**，而非 javalang 或引入 JVM 依赖 (Spoon/JavaParser)。javalang 自 2018 年停止维护，对 Java 8+ 语法（lambda、方法引用、record）解析失败率不可接受；Spoon/JavaParser 虽语义完整，但引入 JVM 依赖违反 ADD "Python ≥ 3.9，标准库优先" 的硬约束。tree-sitter-java 提供增量解析、错误恢复、跨语言统一架构，是当前最佳折中。

2. **T8' 应采用 "修复 + 重构" 双轨制**：先修复 joern_cpg.py 中 5 个已识别的跨环境断裂（节点名不匹配、verify_imports 误判、Windows 三链路断裂），再重构 verify_imports() 从 "任意循环依赖检测" 改为 "特定模块对精确匹配"。单纯修复无法解决 verify_imports 的根本性误判问题。

3. **T11 与 T8' 不存在硬依赖关系**，但建议 T8' 优先于 T11 实施。T8' 修复 Joern 跨文件能力后，Java 通过 javasrc2cpg 可获得 Tier 1 验证；T11 作为 Tier 2 fallback，可在 T8' 完成后再扩展，避免双重维护成本。

**核心风险矩阵**：tree-sitter CFG 构建工作量被低估（P0 风险），Joern v4.x flatgraph API 仍存在 TypeInferencePass 子类参数匹配 Bug（P1 风险），Windows/WSL2 跨环境调用链在 v2.7.3 仍有残留断裂（P1 风险）。详细风险矩阵见 §8。

---

## 1. Introduction

### 1.1 Background

ADD (Audit-Driven Development) Framework 当前的 Phase 3.5 Finding Verification 采用三层降级架构：

- **Tier 1**: Joern CPG (Apache-2.0) — 高精度验证后端，~95% 准确率
- **Tier 2**: Python ast CFG — 零依赖 fallback，~90% 准确率
- **Tier 3**: 正则启发式 — 最终 fallback，~42% 准确率

v2.7.3 审计（见 `docs/audit/2026-08-12-framework-review-and-gap-analysis.md`）识别出两大架构裂缝：

| 差距 | 严重度 | 现状 |
|---|---|---|
| **G4**: 无跨文件分析 | 🟠 严重 | Joern CPG 原生支持，但 ADD 集成存在 5 个已知断裂 |
| **G5**: 语言支持窄 | 🟠 严重 | Tier 2 仅支持 Python，Java/C/C++ 仅有 Tier 1/3 |

T11 与 T8' 正是为修复 G4 残余与 G5 而设计的中期任务（见 `docs/ROADMAP.md`）。

### 1.2 Research Objectives

1. 评估 T11 Java AST CFG 扩展的技术可行性，对比 5 种 Java AST 解析方案
2. 评估 T8' Joern 跨文件验证深化的修复路径，分析 5 个已知断裂的根因
3. 评估 Joern CPG 在 v4.0 flatgraph 架构下的稳定性与性能
4. 评估 4 类替代方案（Semgrep Pro / CodeQL / 商业工具 / 自建）的可行性
5. 给出 T11/T8' 与 ADD 现有架构的集成建议、依赖关系、工作量估算
6. 对比 4 类业界案例的跨文件分析实现

### 1.3 Methodology

- **代码审计**: 阅读 `scripts/joern_cpg.py`、`scripts/ast_cfg.py`、`docs/ROADMAP.md`、v2.4/v2.8 spec
- **多源 Web 调研**: Joern 官方文档、GitHub Issues、Semgrep/CodeQL 官方文档、学术论文
- **现有代码库逆向分析**: 从 project_memory 提取 v2.7.3 已识别的 5 个 Joern 断裂
- **业界案例对比**: Semgrep Pro Engine、CodeQL、Facebook Infer、Soot/WALA

---

## 2. T11 Java AST CFG 扩展可行性分析

### 2.1 Java AST 解析方案对比

当前 ADD 的 Tier 2 (AST CFG) 使用 Python 标准库 `ast` 模块，仅支持 Python。Java AST 解析存在 5 种主流方案：

| 方案 | 语言 | 依赖 | CFG 支持 | Java 版本 | 维护状态 | API 参考 |
|---|---|---|---|---|---|---|
| **javalang** | 纯 Python | `pip install javalang` | ❌ 无 | Java 8 | ⚠️ 2018 停更 | [c2nes/javalang](https://github.com/c2nes/javalang) |
| **tree-sitter-java** | C + Python binding | `tree-sitter` + `tree-sitter-java` | ❌ 需自建 | Java 17+ | ✅ 活跃 | [tree-sitter-java](https://github.com/tree-sitter/tree-sitter-java) |
| **Spoon** | Java | JVM + Maven | ✅ spoon-control-flow 模块 | Java 21 | ✅ 活跃 (INRIA) | [INRIA/spoon](https://github.com/INRIA/spoon) |
| **JavaParser** | Java | JVM + Jar | ⚠️ 需 Symbol Solver | Java 21 | ✅ 活跃 | [javaparser/javaparser](https://github.com/javaparser/javaparser) |
| **ANTLR Java grammar** | 多语言 | ANTLR runtime | ❌ 需自建 | 可定制 | ✅ 活跃 | [ANTLR grammars](https://github.com/antlr/grammars-v4) |

#### 2.1.1 javalang 的致命缺陷

javalang 是纯 Python 实现的 Java 8 解析器，是当前最易集成的方案，但存在三个致命缺陷：

1. **Java 8+ 语法支持不完整**：方法引用（`Type[]::new`）、record、sealed class、switch 表达式等新语法会触发 `JavaSyntaxError`，导致整个文件解析失败 ([elvezjp/code2map#9](https://github.com/elvezjp/code2map/issues/9))
2. **错误恢复能力缺失**：1 处未支持语法会导致整个文件 0 符号输出，无增量解析能力
3. **长期停止维护**：最后稳定版本为 2018 年，无社区响应

**结论**：javalang 不可用于 T11。即使在 ADD 的 Defects4J benchmark（50 Java findings）上也会因现代 Java 语法导致批量解析失败。

#### 2.1.2 tree-sitter-java 的优势

tree-sitter-java 是 tree-sitter 生态的 Java grammar，提供：

- **Java 17+ 语法全覆盖**：支持 record、sealed class、switch 表达式、模式匹配
- **增量解析**：源码小范围修改时仅更新变更部分，适合 ADD 的 `--changed-files` 模式
- **错误恢复**：部分损坏的代码仍能返回可解析部分的 AST，对 Defects4J 等真实 bug 数据集至关重要
- **跨语言统一架构**：未来扩展到 C/C++/TypeScript 可复用同一框架（与 ADD 的 G5 修复目标一致）
- **Python binding 稳定**：`tree-sitter~=0.22` + `tree-sitter-java>=0.23.5`，Python 3.9+ ([deepwiki](https://deepwiki.com/tree-sitter/tree-sitter-java/3.3-python-binding))

**关键 API**：

```python
import tree_sitter
import tree_sitter_java

parser = tree_sitter.Parser(tree_sitter_java.language())
tree = parser.parse(bytes(java_code, 'utf8'))
root_node = tree.root_node
print(root_node.sexp())  # S-expression AST
```

#### 2.1.3 Spoon 与 JavaParser 的 JVM 依赖问题

Spoon (INRIA) 与 JavaParser 都提供完整的 Java 语义分析能力：

- **Spoon** 的 `spoon-control-flow` 模块直接提供 `ControlFlowGraph` 类，基于 JGraphT 实现 ([INRIA/spoon spoon-control-flow README](https://github.com/INRIA/spoon/blob/master/spoon-control-flow/README.md))
- **JavaParser** 的 Symbol Solver 可解析方法调用、类型推断、跨文件引用 ([javaparser-symbol-solver-core](https://github.com/javaparser/javaparser))

但两者都引入 JVM 依赖，与 ADD 硬约束冲突：

> "Python ≥ 3.9，标准库优先，不引入新 runtime 依赖" — `project_memory.md` Hard Constraints

引入 JVM 依赖意味着：
- ADD CI 需要安装 JDK 21 + Maven/Gradle
- Windows 用户需配置 JAVA_HOME
- 与 ADD 的 "零依赖 fallback" 定位矛盾（Tier 2 应在 Joern 不可用时仍能工作）

**结论**：Spoon 与 JavaParser 不适合直接集成到 Tier 2，但其架构设计可作为 T11 自建 CFG 的参考实现。

#### 2.1.4 ANTLR Java grammar 的自建成本

ANTLR 提供 Java grammar，需要从零构建 CFG。其优势是可定制解析行为，劣势是：

- CFG 构建工作量等同 tree-sitter
- 缺少 tree-sitter 的增量解析与错误恢复
- 社区生态不如 tree-sitter 活跃

**结论**：ANTLR 仅在需要深度定制解析行为时考虑，非 T11 首选。

### 2.2 Java CFG 构建的特殊挑战

Java 与 Python 的控制流存在 5 大差异，这些是 T11 实施时必须处理的 Java-specific 特性：

| 挑战 | Python ast 处理方式 | Java tree-sitter 处理方式 | 难度 |
|---|---|---|---|
| **异常处理 (try-catch-finally)** | `visit_Try` 简化处理 | finally 块在所有路径执行，catch 块按异常类型分派 | 🟠 中 |
| **方法分派 (virtual/dynamic dispatch)** | 不存在 | `obj.method()` 需类型推断确定实际调用方法 | 🔴 高 |
| **继承与多态** | 不存在 | 子类可覆盖父类方法，CFG 需合并继承链 | 🔴 高 |
| **Lambda 与 Stream** | 简化处理 | Lambda 体的 CFG 需嵌入宿主方法，Stream 的 `map/filter/reduce` 是链式调用 | 🟠 中 |
| **Generics 类型擦除** | 不存在 | 类型擦除导致 `List<String>` 与 `List<Integer>` 在运行时无法区分 | 🟡 低（CFG 不依赖类型） |

#### 2.2.1 异常处理的 CFG 建模

Java 的 try-catch-finally 控制流比 Python 复杂：

- **finally 块**：在所有退出路径（return、throw、正常完成）都需执行
- **catch 块**：按异常类型分派，需为每个 catch 子句建立独立分支
- **try-with-resources**：自动调用 `close()`，隐含 finally 语义

**Spoon 的 NaiveExceptionControlFlowStrategy** ([INRIA/spoon ControlFlowGraph.java](https://github.com/INRIA/spoon/blob/master/spoon-control-flow/src/main/java/fr/inria/controlflow/ControlFlowGraph.java)) 提供参考实现，但有以下简化假设：
1. 任何语句都可能抛出任何异常
2. try 块内抛出的异常都被立即关联的 catch 捕获

ADD T11 可采用同样的简化策略，但需明确文档化这些限制。

#### 2.2.2 方法分派与继承链合并

这是 Java CFG 最困难的挑战。考虑：

```java
class Animal { void speak() { /* A */ } }
class Dog extends Animal { void speak() { /* B */ } }
Animal a = new Dog();
a.speak();  // 实际调用 B，但静态分析需考虑 A 与 B 都可能
```

**Joern javasrc2cpg 的 TypeInferencePass 存在已知 Bug**：当参数类型是声明参数类型的子类时，`doArgumentTypesMatch()` 仅做精确类型匹配，不考虑继承层次 ([joernio/joern#5679](https://github.com/joernio/joern/issues/5679))。这意味着 Joern 在跨文件调用图构建时存在系统性盲区。

**T11 的策略**：Tier 2 AST CFG 不应尝试解决方法分派问题（属于 Tier 1 Joern 的责任），而是：
- 对 `obj.method()` 调用，仅记录 `method` 名称，不解析 `obj` 的实际类型
- CFG 验证聚焦于方法内部的可达性，不跨方法边界
- 跨方法验证留给 Tier 1 Joern（即使有 Bug）或未来的 T9' taint 验证

### 2.3 与 Python CFG 的差异分析

基于 `scripts/ast_cfg.py` 的 `CFGBuilder` 类，分析 Python CFG 经验的可迁移性：

| Python CFG 概念 | 可迁移到 Java | 说明 |
|---|---|---|
| `ast.NodeVisitor` 模式 | ✅ | tree-sitter 提供类似的 cursor 遍历 API |
| `_current_successors` 工作列表 | ✅ | 通用 CFG 构建技巧 |
| `visit_FunctionDef` | ✅ | 对应 Java 的 MethodDeclaration |
| `visit_If` (条件分派) | ✅ | Java 的 if 语义相同 |
| `visit_For` / `visit_While` | ✅ | Java 的 for/while 语义相同 |
| `visit_Try` | ⚠️ | 需扩展处理 catch 与 finally |
| `visit_AsyncFunctionDef` | ❌ | Java 无 async/await（用 CompletableFuture） |
| `visit_Match` (Python 3.10+) | ⚠️ | Java 的 switch 表达式语义不同 |
| **不可迁移**: 装饰器 | ❌ | Java 的注解不影响控制流 |
| **不可迁移**: with 语句 | ❌ | Java 的 try-with-resources 语义不同 |

**关键洞察**：Python CFG 的核心算法（BFS 可达性、3-color DFS 环检测）完全可迁移，但 AST 节点访问器需要为 Java 重新实现。

### 2.4 T11 推荐方案

**推荐路径**：tree-sitter-java + 自建 CFG

**理由**：
1. 符合 ADD "标准库优先，不引入 runtime 依赖" 硬约束
2. tree-sitter 的错误恢复对 Defects4J 等真实 bug 数据集至关重要
3. 增量解析支持 ADD 未来的 `--changed-files` 模式
4. 跨语言统一架构为后续 C/C++/TypeScript 扩展铺路
5. Python CFG 的核心算法可迁移，工作量可控

**不推荐路径**：
- ❌ javalang（停止维护，Java 8+ 解析失败）
- ❌ Spoon/JavaParser（JVM 依赖违反硬约束）
- ❌ ANTLR（无增量解析，工作量等同 tree-sitter）

---

## 3. T8' Joern 跨文件验证深化分析

### 3.1 当前 ADD Joern 集成问题（来自 project_memory）

基于 `scripts/joern_cpg.py` 代码审计与 `project_memory.md` 的 v2.7.3 审计记录，识别出 5 个已知断裂：

| # | 断裂 | 根因 | 影响 | 修复难度 |
|---|---|---|---|---|
| **F1** | `imp.file.head.name` (带 .py) 与 `imp.importedEntity` (不带 .py) 节点名不匹配 | Joern CPG 的 IMPORTS 边两端节点命名约定不一致 | 跨文件 DFS 图遍历断裂，verify_imports 返回空结果 | 🟡 中 |
| **F2** | `verify_imports()` 检测任意循环依赖而非特定模块对 | 实现与 claim 语义不匹配 | import_related claim 的 FP/FN 率高 | 🟠 高（需重构） |
| **F3** | Windows 环境下 `_find_joern_binary()` 返回 None | Windows 注册表/PATH 查找逻辑缺失 | Windows 用户无法使用 Tier 1 | 🟡 中 |
| **F4** | `_build_joern_env()` PATH override 是 dead code | 函数签名存在但未被调用 | 环境变量配置失败 | 🟢 低 |
| **F5** | `is_available()` 在 Windows 上短路为 False | WSL2 检测逻辑在 Windows host 上错误返回 | Windows 用户被强制降级到 Tier 2 | 🟡 中 |

#### 3.1.1 F1 节点名不匹配的根因

Joern 的 pysrc2cpg frontend 在生成 IMPORTS 边时：
- `imp.file.head.name` 包含 `.py` 后缀（如 `foo.py`）
- `imp.importedEntity` 不包含后缀（如 `foo`）

这导致 DFS 遍历 IMPORTS 边时无法匹配目标节点。`project_memory.md` 记录的修复方案是"移除 `.py` 后缀"，但这是 pysrc2cpg 特有问题，javasrc2cpg 可能不存在（Java 文件以 `.java` 结尾，但 import 语句使用包名）。

**T8' 修复建议**：在 `verify_imports()` 中规范化节点名，移除所有文件扩展名（`.py`、`.java`、`.c`、`.cpp`）后再匹配。

#### 3.1.2 F2 verify_imports 误判的根本性问题

当前 `verify_imports()` 检测"是否存在任何循环依赖"，而 claim 语义是"特定的模块对 A↔B 是否构成循环依赖"。这是 **检测能力与验证能力的目标错位**：

- **检测能力**（Detection）：发现"项目存在循环依赖" → 任意循环检测正确
- **验证能力**（Verification）：验证"A 与 B 是否循环依赖" → 需精确匹配模块对

**修复方案对比**：

| 方案 | 实现复杂度 | 准确率提升 | 副作用 |
|---|---|---|---|
| **A: 精确匹配模块对** | 中 | 高 | 无 |
| **B: 使用 DEPTREE 替代 IMPORTS** | 高 | 高 | 需 Joern 支持 |
| **C: 结合 AST CFG 二次验证** | 高 | 中 | 增加复杂度 |

**推荐**：方案 A（精确匹配模块对）。在 `verify_imports()` 中：
1. 从 claim 提取模块对 (A, B)
2. 在 IMPORTS 图中查找 A→B 与 B→A 是否都存在
3. 若都存在则 confirmed=True，否则 confirmed=False

#### 3.1.3 F3-F5 Windows 跨环境断裂

`project_memory.md` 记录 v2.7.3 已修复部分 Windows 断裂，但 P3-2 测试失败根因是 "mock lambda 签名不匹配"。当前 `joern_cpg.py` 的 Windows 支持状态：

```python
# joern_cpg.py L60-71
if os.name == "nt":
    base = os.environ.get("TEMP", tempfile.gettempdir())
else:
    base = "/tmp"
```

**T8' 修复建议**：
- F3: 在 Windows 上优先检测 WSL2 可用性（`wsl.exe --list`），通过 WSL2 调用 Joern
- F4: 移除 `_build_joern_env()` 的 dead code，或修复调用链
- F5: `is_available()` 在 Windows 上应检测 WSL2 + Joern 双重可用性，而非直接返回 False

### 3.2 Joern 跨文件分析能力评估

#### 3.2.1 cpg.imports API 完整性与限制

Joern 提供 `cpg.imports` API 用于查询 IMPORTS 边：

```scala
cpg.imports.l                          // 所有 IMPORTS 边
cpg.imports.importedEntity("foo").l    // 按导入名过滤
cpg.imports.file.name("bar.py").l      // 按文件过滤
```

**限制**：
1. IMPORTS 边仅表示静态 import 语句，不表示运行时依赖
2. 动态导入（Python 的 `importlib.import_module`、Java 的反射）不被捕获
3. 节点命名约定不一致（F1 问题）

#### 3.2.2 跨文件调用图构建

Joern 通过 `CALLS` 边构建跨文件调用图：

```scala
cpg.method.name("foo").caller.l        // 调用 foo 的所有方法
cpg.method.name("foo").callee.l        // foo 调用的所有方法
```

**已知限制**：
- **Java 跨文件方法调用解析失败**：`service.doWork()` 模式（依赖注入）无法解析 `service` 的类型，导致 CALLS 边缺失 ([CodeGraphContext#823](https://github.com/CodeGraphContext/CodeGraphContext/issues/823))
- **Python 跨文件调用图不完整**：pysrc2cpg 对动态分派支持有限
- **TypeInferencePass 子类参数匹配 Bug** ([joernio/joern#5679](https://github.com/joernio/joern/issues/5679))：`doArgumentTypesMatch()` 仅做精确类型匹配，不考虑继承层次

#### 3.2.3 类型推断对跨文件分析的影响

Joern 的 TypeInferencePass 是跨文件调用图准确性的关键：

- **Python (pysrc2cpg)**：类型推断能力有限，大部分调用返回 `<unresolvedNamespace>`
- **Java (javasrc2cpg)**：基于 JavaParser 的类型推断，但存在子类参数匹配 Bug
- **C/C++ (c2cpg)**：基于 Eclipse CDT，对 C++ 模板支持有限

**对 ADD 的影响**：Tier 1 Joern 验证的准确率在不同语言上差异显著，需在 benchmark 中分别评估。

#### 3.2.4 Joern 对 Java/Python/C/C++ 的支持差异

| 能力 | Java (javasrc2cpg) | Python (pysrc2cpg) | C/C++ (c2cpg) |
|---|---|---|---|
| AST 完整度 | ✅ 高（JavaParser） | ⚠️ 中 | ✅ 高（Eclipse CDT） |
| CFG 完整度 | ✅ 高 | ⚠️ 中 | ✅ 高 |
| 跨文件 CALLS | ⚠️ 子类参数 Bug | ⚠️ 动态分派缺失 | ✅ 高 |
| IMPORTS 边 | ✅ 包导入 | ⚠️ 节点名不匹配 | ⚠️ #include 解析 |
| 类型推断 | ⚠️ 子类不匹配 | 🔴 弱 | ✅ 高 |

### 3.3 import_related 误判修复方案

基于 §3.1.2 分析，推荐 **方案 A: 精确匹配模块对**，辅以 **方案 C: AST CFG 二次验证** 作为降级路径：

```
verify_imports(claim):
    1. 从 claim 提取模块对 (A, B)
    2. Tier 1: Joern IMPORTS 图精确匹配
       - 查询 A→B 与 B→A 是否都存在
       - 若都存在: confirmed=True
       - 若都不存在: confirmed=False
       - 若仅一个方向存在: confirmed=None (降级 Tier 2)
    3. Tier 2: AST CFG 导入图二次验证
       - 用 ast_cfg.py 的 ImportGraphBuilder 构建导入图
       - 重复步骤 2
    4. Tier 3: 正则启发式（现有实现）
```

**为什么不用 DEPTREE/CALLGRAPH 替代 IMPORTS**：
- DEPTREE 表示依赖树，不直接表示循环
- CALLGRAPH 是方法级，不是文件级
- IMPORTS 是文件级依赖关系的最直接表示

### 3.4 T8' 推荐方案

**推荐路径**：修复 + 重构双轨制

**Phase 1 (修复，1-2 天)**：
- F1: 节点名规范化（移除文件扩展名）
- F3: Windows WSL2 检测逻辑修复
- F4: 移除 dead code
- F5: `is_available()` Windows 双重检测

**Phase 2 (重构，3-5 天)**：
- F2: 重构 `verify_imports()` 为精确模块对匹配
- 新增单元测试覆盖 6 种情况（A↔B、A→B、A↔C、无关系、自导入、外部库）

---

## 4. Joern CPG 稳定性分析

### 4.1 版本兼容性（v2.x vs v3.x vs v4.x）

Joern 版本兼容性是 ADD 集成的关键风险：

| 版本 | 架构 | API 变化 | 兼容性 |
|---|---|---|---|
| **v2.x** | overflowdb | `overflowdb.BatchedUpdate.applyDiff`、`io.shiftleft.passes.IntervalKeyPool`、`overflowdb.traversal.Traversal` | 旧 API |
| **v3.x** | 跳过 | "版本 3 是麻烦源"（官方说法） | N/A |
| **v4.x** | flatgraph | `flatgraph.DiffGraphApplier.applyDiff`、`io.joern.x2cpg.utils.IntervalKeyPool`、`scala.collection.Iterator` | 新 API |

**v4.0 flatgraph 迁移的核心变化** ([4.0.0-flatgraph.md](https://github.com/joernio/joern/blob/master/changelog/4.0.0-flatgraph.md))：

1. `overflowdb.BatchedUpdate.applyDiff` → `flatgraph.DiffGraphApplier.applyDiff`
2. `io.shiftleft.passes.IntervalKeyPool` → `io.joern.x2cpg.utils.IntervalKeyPool`
3. `StoredNode.propertyOption` 返回 `Option` 而非 `java.util.Optional`
4. 箭头语法 `v0 --- "CFG" --> v1` 不再支持
5. 边只能有零或一个属性
6. `Traversal` 类被移除，替换为 `type Traversal[+T] = scala.collection.Iterator[T]` ([traversal_removal.md](https://github.com/joernio/joern/blob/master/changelog/traversal_removal.md))

**性能改进**（Linux 4.1.16 基准测试）：

| 指标 | joern 2 (overflowdb) | joern 4 (flatgraph) | 改进 |
|---|---|---|---|
| heap after import | 33g | 20g | -40% |
| minimum Xmx for import | 80g | 30g | -62% |
| time for importCpg | 18 min | 11 min | -39% |
| file size on disk | 2600M | 400M | -85% |

**ADD 当前状态**：`joern_cpg.py` L41 已声明 `JOERN_VERSION_MIN = "4.0"`，但 API 调用仍使用 v2.x 兼容的查询语法（如 `cpg.method.lineNumber(N)`）。这是 v2.7.3 审计后的修正结果。

### 4.2 大项目性能表现

基于官方基准测试（Linux kernel 4.1.16，48M nodes + 431M edges）：

- **importCpg 耗时**：11 分钟（v4.0）
- **内存需求**：30g Xmx（v4.0）vs 80g Xmx（v2.x）
- **磁盘占用**：400M（v4.0）vs 2600M（v2.x）

**对 ADD 的影响**：
- ADD 的 benchmark（687 findings）远小于 Linux kernel，性能不是瓶颈
- CPG 生成已通过 mtime hash 缓存优化（24h TTL，`/tmp/add_joern_cache/`）
- 大型 Java 项目（如 Spring Boot）的 importCpg 可能在 5-10 分钟量级

### 4.3 Windows/WSL2 稳定性

`project_memory.md` 记录 v2.7.3 修复了三处跨环境调用链断裂，但 P3-2 测试仍失败。当前 `joern_cpg.py` 的 Windows 支持通过 WSL2 实现：

```python
# joern_cpg.py L80-100
def _detect_wsl():
    """Detect if running INSIDE Windows WSL2."""
    if os.name == "nt":
        return False  # Windows host; not inside WSL2
    try:
        with open("/proc/sys/kernel/osrelease", "r") as f:
            release = f.read().lower()
```

**已知问题**：
- Joern CLI 本身是 Scala/JVM 应用，Windows 原生支持有限
- WSL2 路径转换（`F:\foo` → `/mnt/f/foo`）需手动处理
- `JOERN_FORCE_WSL` 环境变量可用于测试覆盖

**T8' 建议**：
1. 文档化 Windows 用户必须安装 WSL2 + Joern CLI
2. 在 `is_available()` 中检测 WSL2 可用性，而非直接返回 False
3. 添加端到端测试覆盖 Windows → WSL2 → Joern 调用链

### 4.4 Server Mode vs CLI Mode

Joern 提供两种运行模式：

| 模式 | 启动 | 适用场景 | 限制 |
|---|---|---|---|
| **CLI Mode** | `joern --script query.sc` | 一次性查询，ADD 当前使用 | 每次启动 JVM，~5s 开销 |
| **Server Mode** | `joern --server --server-host localhost --server-port 8081` | 持久化查询服务 | 需管理 server 生命周期 |

**Server Mode API** ([docs.joern.io/server](https://docs.joern.io/server/))：

```
POST /query          {"query": "$query"} → {"uuid": "$uuid"}
GET  /result/$uuid   → {"success": "true/false", "stdout": "$stdout"}
WS   /connect        实时查询完成通知
```

**对 ADD 的建议**：
- 短期：维持 CLI Mode（简单，无状态管理）
- 长期：若 T11 + T8' 完成后性能成为瓶颈，考虑 Server Mode + 连接池
- Server Mode 不提供沙箱，需在 CI 中隔离

### 4.5 pysrc2cpg 与 javasrc2cpg 的已知限制

#### 4.5.1 pysrc2cpg 限制

- **动态导入不支持**：`importlib.import_module()` 不生成 IMPORTS 边
- **节点名不一致**：F1 问题（`.py` 后缀）
- **类型推断弱**：大部分调用返回 `<unresolvedNamespace>`

#### 4.5.2 javasrc2cpg 限制

- **TypeInferencePass 子类参数 Bug** ([joernio/joern#5679](https://github.com/joernio/joern/issues/5679))：`doArgumentTypesMatch()` 不考虑继承层次
- **增量更新缺失**：文件变更需 full rebuild（~10 min for large projects），但已有原型 ([joernio/joern#5865](https://github.com/joernio/joern/issues/5865))，性能提升 ~1700×
- **switch case CFG 断裂**：Spoon 的 ControlFlowGraph 曾存在 switch case 边缺失（PR #4004 修复）

---

## 5. 替代方案评估

### 5.1 Semgrep Pro Engine

**跨文件分析能力**：Semgrep Pro Engine（闭源，商业）支持跨函数与跨文件 taint 分析 ([Semgrep Pro Engine examples](https://semgrep.dev/docs/semgrep-code/semgrep-pro-engine-examples))。

**关键特性**：
- 30+ 语言支持
- 900+ 高置信度 Pro 规则
- 跨函数 + 跨文件数据流分析
- 减少误报 25%，增加真阳性 2.5×（Fortune 500 客户数据）

**对 ADD 的可行性**：
- ❌ **许可证冲突**：Semgrep Pro 是商业产品，与 ADD 的 Apache-2.0 兼容性存疑
- ❌ **定位冲突**：ADD 是 Validator（验证他人报告），Semgrep Pro 是 Detector（自己检测）
- ✅ **可作为 Detection 能力的参考实现**：未来若 ADD 扩展到 Detection（G1 修复），可借鉴 Semgrep 的跨文件 taint 模式

**最新动态**（2025-08）：
- Scala inter-file 分析首发 (code-9029)
- 改进 interfile 规则预过滤，提升性能 (code-8524)

### 5.2 CodeQL

**跨文件查询能力**：CodeQL 提供完整的跨文件数据流与 taint 追踪 ([CodeQL Java TaintTracking](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-java/))。

**关键 API**：

```ql
import semmle.code.java.dataflow.TaintTracking

module MyFlowConfiguration implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) { ... }
  predicate isSink(DataFlow::Node sink) { ... }
}

module MyFlow = TaintTracking::Global<MyFlowConfiguration>;
```

**对 ADD 的可行性**：
- ❌ **许可证冲突**：CodeQL 是 GitHub 专有许可证，禁止商业代码使用（v2.4 spec 已排除）
- ❌ **集成成本高**：需构建 CodeQL database，违反 "标准库优先" 原则
- ✅ **作为架构参考**：CodeQL 的 `isBarrier`（净化流）模式可启发 ADD 的 hallucination_pattern 规则设计

### 5.3 商业工具

| 工具 | 跨文件能力 | 价格 | 适用性 |
|---|---|---|---|
| **Understand (SciTools)** | ✅ Java 跨文件调用图 | 商业 | ❌ 闭源，与 ADD 定位冲突 |
| **Sourcerer** | ⚠️ Python only | 商业 | ❌ 语言覆盖窄 |
| **SonarQube** | ✅ 多语言 | 商业 | ❌ 重型，与 ADD 轻量定位冲突 |

**结论**：商业工具均不适用于 ADD，因其与 ADD 的 "开源、零依赖、Validator 定位" 核心价值观冲突。

### 5.4 自建轻量级方案

#### 5.4.1 自建 import graph

**成本估算**：
- Python: `ast` 模块解析 import 语句，~100 行代码
- Java: tree-sitter 解析 import 语句，~150 行代码
- 跨语言统一接口: ~50 行代码

**优势**：零依赖，完全可控，与 ADD 的 `ast_cfg.py` 现有架构一致

**劣势**：仅支持文件级依赖，不支持方法级 CALLS 边

#### 5.4.2 tree-sitter + 自定义图构建

**成本估算**：
- tree-sitter 解析: ~100 行代码
- CFG 构建: ~500-800 行代码（参考 `ast_cfg.py` 的 `CFGBuilder`）
- 调用图构建: ~300 行代码
- 跨文件边连接: ~200 行代码

**优势**：完整控制图结构，支持增量更新

**劣势**：方法分派解析需自建类型推断，工作量大

### 5.5 替代方案对比矩阵

| 方案 | 许可证 | 跨文件 | Java | Python | 集成成本 | ADD 适用性 |
|---|---|---|---|---|---|---|
| Semgrep Pro | 商业 | ✅ | ✅ | ✅ | 低 | ❌ 定位冲突 |
| CodeQL | 专有 | ✅ | ✅ | ✅ | 中 | ❌ 许可证冲突 |
| 商业工具 | 商业 | ✅ | ✅ | ✅ | 低 | ❌ 闭源 |
| 自建 import graph | 开源 | ⚠️ 文件级 | ✅ | ✅ | 低 | ✅ Tier 2 fallback |
| tree-sitter + 自定义 | 开源 | ✅ | ✅ | ✅ | 高 | ✅ T11 推荐 |
| Joern (现状) | Apache-2.0 | ✅ | ⚠️ | ⚠️ | 已集成 | ✅ Tier 1 (需 T8' 修复) |

---

## 6. ADD 架构集成建议

### 6.1 T11 集成方案：Tier 2 扩展 vs 独立 Tier 2.5

**方案 A: Tier 2 扩展**
- 在 `ast_cfg.py` 中新增 `JavaCFGBuilder` 类，复用 `CFGBuilder` 基类
- 优势：架构统一，`verify_findings.py` 无需修改
- 劣势：tree-sitter 与 Python ast 的 API 差异需适配层

**方案 B: 独立 Tier 2.5**
- 新建 `tree_sitter_cfg.py`，专门处理 tree-sitter 解析的语言
- 优势：tree-sitter 可同时支持 Java/C/C++/TypeScript
- 劣势：引入新的模块，增加维护成本

**推荐：方案 A (Tier 2 扩展)**

理由：
1. ADD 的 Tier 2 定位是 "零依赖 fallback"，tree-sitter 是唯一符合此定位的 Java 解析方案
2. `ast_cfg.py` 的 `CFGBuilder` 已抽象出 `_current_successors` 工作列表模式，可复用
3. 通过 `language` 参数分派到不同的 visitor，保持 `verify_findings.py` 的统一接口

**集成伪代码**：

```python
# ast_cfg.py 新增
class JavaCFGBuilder:
    """Build CFG from Java source via tree-sitter. O(N) single traversal."""
    
    def __init__(self):
        self.nodes: dict = {}
        self.edges: list = []
        self._current_successors: list = []
    
    def build(self, java_source: str) -> tuple:
        import tree_sitter
        import tree_sitter_java
        parser = tree_sitter.Parser(tree_sitter_java.language())
        tree = parser.parse(bytes(java_source, 'utf8'))
        self._visit(tree.root_node)
        return self.nodes, self.edges
```

### 6.2 T8' 集成方案：修复 vs 重构

基于 §3.4 的推荐，T8' 采用 **修复 + 重构双轨制**：

**Phase 1 (修复)**：
- 不改变 `verify_imports()` 的接口
- 仅修复 F1/F3/F4/F5 的环境与节点名问题
- 风险：低，可独立测试

**Phase 2 (重构)**：
- 重构 `verify_imports()` 的核心逻辑
- 新增 `extract_module_pair(claim)` 函数提取模块对
- 风险：中，需完整测试覆盖

### 6.3 任务依赖关系

**T11 与 T8' 的依赖分析**：

```
T8' (Joern 修复)
  ├── Phase 1: 环境修复 (独立)
  └── Phase 2: verify_imports 重构 (独立)

T11 (Java AST CFG)
  ├── tree-sitter 集成 (独立)
  └── Java CFGBuilder (可参考 T8' Phase 2 的模块对提取)
```

**结论**：T11 与 T8' **不存在硬依赖关系**，但建议 T8' 优先：

1. **T8' 优先的理由**：
   - T8' 修复后，Java 通过 javasrc2cpg 可获得 Tier 1 验证
   - T11 作为 Tier 2 fallback，可在 T8' 完成后再扩展
   - 避免 T11 完成后仍因 Joern 跨文件断裂而无法验证 Java findings

2. **T11 可并行准备**：
   - tree-sitter 依赖安装与 PoC 可与 T8' 并行
   - 正式集成建议在 T8' 完成后

### 6.4 工作量估算

| 任务 | 子任务 | 代码行数估算 | 工时估算 | 优先级 |
|---|---|---|---|---|
| **T8' Phase 1** | F1 节点名规范化 | ~30 行 | 0.5 天 | P0 |
| | F3 Windows WSL2 检测 | ~50 行 | 1 天 | P0 |
| | F4 dead code 移除 | ~10 行 | 0.5 天 | P0 |
| | F5 is_available() 修复 | ~40 行 | 0.5 天 | P0 |
| **T8' Phase 2** | verify_imports 重构 | ~100 行 | 2 天 | P1 |
| | 单元测试覆盖 | ~150 行 | 1.5 天 | P1 |
| **T8' 小计** | | ~330 行 | **6 天** | |
| **T11** | tree-sitter 集成 | ~100 行 | 1 天 | P1 |
| | JavaCFGBuilder 实现 | ~500 行 | 3 天 | P1 |
| | 异常处理 CFG | ~150 行 | 1 天 | P2 |
| | Lambda/Stream 处理 | ~100 行 | 1 天 | P2 |
| | 单元测试 | ~300 行 | 2 天 | P1 |
| **T11 小计** | | ~1150 行 | **8 天** | |
| **总计** | | ~1480 行 | **14 天** | |

**关键风险**：Java CFG 构建的 5 大挑战（§2.2）中，方法分派与继承链合并的复杂度可能超预期。建议 T11 采用 "最小可行 CFG" 策略：
- Phase 1: 仅处理 if/for/while/try-catch（不含 finally）
- Phase 2: 添加 finally 与 try-with-resources
- Phase 3: 添加 Lambda 与 Stream（可选）

---

## 7. 业界案例研究

### 7.1 Semgrep 跨文件分析实现

Semgrep Pro Engine 的跨文件分析（interfile analysis）于 2024 年 1 月正式发布 ([How we implemented inter-file analysis](https://semgrep.dev/events/the-birth-of-semgrep-pro))。

**核心设计**：
- 跨文件分析蕴含跨函数分析
- 通过 `options.interfile: true` 启用
- 支持 Java/JavaScript/TypeScript/Python/Scala 等

**Java 示例**（[Semgrep docs](https://semgrep.dev/docs/semgrep-code/semgrep-pro-engine-examples)）：

```yaml
rules:
  - id: dangerous-taint-pro-engine-example
    mode: taint
    options:
      interfile: true
    pattern-sources:
      - pattern: get_user_input(...)
    pattern-sinks:
      - pattern: dangerous(...)
```

**对 ADD 的启发**：
- Semgrep 的 `interfile: true` 选项设计简洁，ADD 可考虑在 `verify_findings.py` 中增加 `cross_file: true` 参数
- Semgrep Pro 的 5 个月开发周期表明跨文件分析是中等规模工程

### 7.2 CodeQL 数据流跨文件实现

CodeQL 的跨文件数据流通过 `TaintTracking::Global` 模块实现 ([CodeQL Java TaintTracking](https://codeql.github.com/codeql-standard-libraries/java/semmle/code/java/dataflow/TaintTracking.qll/module.TaintTracking.html))。

**核心 API**：

```ql
import semmle.code.java.dataflow.TaintTracking

module MyTaintConfig implements TaintTracking::ConfigSig {
  predicate isSource(DataFlow::Node source) { ... }
  predicate isSink(DataFlow::Node sink) { ... }
  predicate isBarrier(DataFlow::Node node) { ... }  // 净化点
  predicate isAdditionalTaintStep(DataFlow::Node src, DataFlow::Node sink) { ... }
}

module MyTaint = TaintTracking::Global<MyTaintConfig>;
```

**关键设计模式**：
- `isBarrier`：净化流，中断 taint 传播
- `isAdditionalTaintStep`：自定义 taint 步骤，支持框架特定传播
- `defaultTaintSanitizer`：默认净化点

**对 ADD 的启发**：
- CodeQL 的 `isBarrier` 模式可启发 ADD 的 `hallucination_pattern` 规则设计
- ADD 的 `verify_l4_structural()` 可引入类似的 "barrier" 概念，当遇到特定模式时中断验证降级

### 7.3 Facebook Infer 跨过程分析

Facebook Infer 是基于分离逻辑（Separation Logic）的跨过程分析工具，支持 C/C++/Java/ObjC。

**核心能力**：
- Bi-abduction 推理：自动推断函数的前置与后置条件
- 跨过程分析：追踪指针所有权跨函数传递
- 内存泄漏检测：基于分离逻辑的资源追踪

**对 ADD 的启发**：
- Infer 的跨过程分析是 "sound but imprecise"（可靠但不精确），与 ADD 的 "Validator" 定位一致
- Infer 不尝试解决所有问题，而是对特定类别（内存、并发）提供高置信度验证

### 7.4 学术界跨文件分析工具

#### 7.4.1 Soot

Soot 是麦吉尔大学的 Java 字节码分析框架，提供完整的调用图构建：

- **CHA (Class Hierarchy Analysis)**：基于继承层次的保守调用图
- **RTA (Rapid Type Analysis)**：基于已实例化类型的精确调用图
- **VTA (Variable Type Analysis)**：基于变量类型的精确调用图
- **Spark**：Soot 的指针分析框架，支持上下文敏感分析

**对 ADD 的启发**：Soot 的 CHA/RTA 调用图构建策略可启发 ADD 的 Joern 调用图验证。但 Soot 是字节码分析，需编译 Java 源码，与 ADD 的源码级验证定位不同。

#### 7.4.2 WALA

WALA 是 IBM 的静态分析框架，支持 Java/JavaScript/Python：

- **调用图构建**：支持 SSA-based 调用图
- **指针分析**：上下文敏感的堆抽象
- **数据流分析**：基于 IFDS/IDE 框架

**对 ADD 的启发**：WALA 的 IFDS/IDE 框架是数据流分析的经典算法，可用于 ADD 未来 T9' taint 验证的设计参考。

---

## 8. 风险矩阵

### 8.1 T11 风险矩阵

| 风险 ID | 风险描述 | 概率 | 影响 | 严重度 | 缓解措施 |
|---|---|---|---|---|---|
| **T11-R1** | tree-sitter CFG 构建工作量被低估 | 🟠 中 | 🔴 高 | 🔴 P0 | 采用 "最小可行 CFG" 策略，Phase 1 仅处理基本控制流 |
| **T11-R2** | Java 异常处理 CFG 建模复杂度超预期 | 🟠 中 | 🟠 中 | 🟠 P1 | 参考 Spoon 的 NaiveExceptionControlFlowStrategy 简化策略 |
| **T11-R3** | tree-sitter Python binding 版本兼容性 | 🟡 低 | 🟠 中 | 🟡 P2 | 固定 `tree-sitter~=0.22` + `tree-sitter-java>=0.23.5` |
| **T11-R4** | Lambda/Stream 的 CFG 嵌入语义不明确 | 🟠 中 | 🟡 低 | 🟡 P2 | Phase 3 可选实现，不阻塞主路径 |
| **T11-R5** | Defects4J benchmark Java 版本兼容性 | 🟡 低 | 🟠 中 | 🟡 P2 | tree-sitter 支持 Java 17+，应覆盖 Defects4J |

### 8.2 T8' 风险矩阵

| 风险 ID | 风险描述 | 概率 | 影响 | 严重度 | 缓解措施 |
|---|---|---|---|---|---|
| **T8'-R1** | verify_imports 重构引入新 Bug | 🟠 中 | 🔴 高 | 🔴 P0 | 完整测试覆盖 6 种模块对组合 |
| **T8'-R2** | Joern v4.x TypeInferencePass 子类参数 Bug 未修复 | 🔴 高 | 🟠 中 | 🟠 P1 | 文档化限制，Java 跨文件验证准确率下降 |
| **T8'-R3** | Windows WSL2 检测逻辑在 CI 环境失败 | 🟡 低 | 🟠 中 | 🟡 P2 | 添加 `JOERN_FORCE_WSL` 测试覆盖 |
| **T8'-R4** | Joern 版本升级引入 API 不兼容 | 🟡 低 | 🔴 高 | 🟠 P1 | 固定 Joern v4.0.595，升级前完整测试 |
| **T8'-R5** | 节点名规范化误处理 javasrc2cpg 的包名 | 🟠 中 | 🟠 中 | 🟠 P1 | 分语言处理：Python 移除 `.py`，Java 保留包名 |

### 8.3 整体架构风险

| 风险 ID | 风险描述 | 概率 | 影响 | 严重度 | 缓解措施 |
|---|---|---|---|---|---|
| **ARCH-R1** | T11 与 T8' 并行开发导致接口不一致 | 🟠 中 | 🟠 中 | 🟠 P1 | T8' 优先，T11 在 T8' 完成后启动 |
| **ARCH-R2** | tree-sitter 引入新的 runtime 依赖违反硬约束 | 🔴 高 | 🔴 高 | 🔴 P0 | tree-sitter 是 build-time 依赖，非 runtime 依赖；明确文档化 |
| **ARCH-R3** | Benchmark 无法验证 T11/T8' 的实际改进 | 🟠 中 | 🟠 中 | 🟠 P1 | 扩展 benchmark 到 Java findings，对比 T11 前后 F1 分数 |

---

## 9. Conclusion

### 9.1 核心结论

**T11 (Java AST CFG 扩展)** 的技术可行性已确认，推荐采用 **tree-sitter-java + 自建 CFG** 路径。该方案在符合 ADD "标准库优先，不引入 runtime 依赖" 硬约束的前提下，提供了 Java 17+ 语法全覆盖、增量解析、错误恢复能力。Java CFG 构建的 5 大挑战中，方法分派与继承链合并属于 Tier 1 Joern 的责任范围，T11 应聚焦于方法内部可达性验证，不跨方法边界。Python CFG 的核心算法（BFS 可达性、3-color DFS 环检测）完全可迁移，但 AST 节点访问器需为 Java 重新实现。预估工作量约 8 天、1150 行代码，建议采用 "最小可行 CFG" 策略分阶段交付。

**T8' (深化 Joern 跨文件验证)** 的修复路径已明确，推荐采用 **修复 + 重构双轨制**。Phase 1 修复 5 个已识别的跨环境断裂（节点名不匹配、Windows 三链路断裂、dead code），Phase 2 重构 `verify_imports()` 从 "任意循环依赖检测" 改为 "特定模块对精确匹配"。单纯修复无法解决 verify_imports 的根本性误判问题，重构是必要的。预估工作量约 6 天、330 行代码，风险主要集中在重构引入的新 Bug，需完整测试覆盖 6 种模块对组合。

**T11 与 T8' 的依赖关系**：两者不存在硬依赖，但建议 T8' 优先于 T11 实施。T8' 修复 Joern 跨文件能力后，Java 通过 javasrc2cpg 可获得 Tier 1 验证；T11 作为 Tier 2 fallback，可在 T8' 完成后再扩展，避免双重维护成本。

**Joern CPG 稳定性**：v4.0 flatgraph 架构带来 40% 内存节省与 39% 性能提升，API 变化已通过 `JOERN_VERSION_MIN = "4.0"` 与 v2.7.3 修正适配。剩余稳定性风险主要是 TypeInferencePass 子类参数匹配 Bug（joernio/joern#5679），该 Bug 影响 Java 跨文件调用图准确性，需在 T8' 文档化限制并考虑 workaround。

**替代方案评估**：Semgrep Pro Engine 与 CodeQL 虽提供成熟的跨文件分析，但分别因商业许可证与专有许可证而无法集成。商业工具（Understand、Sourcerer、SonarQube）与 ADD 的开源、零依赖、Validator 定位冲突。自建轻量级 import graph 是可行的 Tier 2 fallback，但仅支持文件级依赖。tree-sitter + 自定义图构建是 T11 的最佳路径。

### 9.2 战略判断

ADD 作为 "验证基础设施的建造者"，其核心能力不是发明新的跨文件分析算法，而是**判断现有工具（Joern、Semgrep、CodeQL）的跨文件分析结果是否可信**。T11 与 T8' 的本质都是 "扩展验证能力的覆盖范围"：T11 将 Tier 2 从 Python 扩展到 Java，T8' 将 Tier 1 从 "任意循环检测" 精确化为 "特定模块对验证"。

这一战略定位决定了 ADD 不应尝试复制 CodeQL 或 Semgrep Pro 的完整跨文件 taint 分析能力（那是 T9' 的责任），而应聚焦于 **验证** — 即给定一个跨文件 claim，判断其是否成立。这一聚焦使 T11/T8' 的工作量可控（合计 14 天 vs 完整 taint 分析的数月），同时保持 ADD 的 "Validator" 核心身份。

> **One-Liner Truth**: ADD 不应建造另一个 CodeQL，而应建造判断 CodeQL 报告是否可信的能力。T11 与 T8' 是这一能力的 Java 扩展与 Joern 深化，不是新工具的发明。

---

## 10. References

[1] joernio. Joern 4.0.x: Migration to flatgraph[EB/OL]. https://github.com/joernio/joern/blob/master/changelog/4.0.0-flatgraph.md, 2025.

[2] joernio. The great Traversal removal (v1.2.0)[EB/OL]. https://github.com/joernio/joern/blob/master/changelog/traversal_removal.md, 2023-06.

[3] joernio. Joern Server Mode documentation[EB/OL]. https://docs.joern.io/server/, 2026.

[4] joernio. Joern javasrc2cpg README[EB/OL]. https://github.com/joernio/joern/blob/master/joern-cli/frontends/javasrc2cpg/README.md, 2026.

[5] jjzdxmd. [Bug][javasrc2cpg] TypeInferencePass fails to match method calls when argument types are subclasses[EB/OL]. https://github.com/joernio/joern/issues/5679, 2025-10-15.

[6] CheolHoJung. [Feature] Incremental CPG update for javasrc2cpg[EB/OL]. https://github.com/joernio/joern/issues/5865, 2026-03-08.

[7] tree-sitter. tree-sitter-java Python Binding[EB/OL]. https://deepwiki.com/tree-sitter/tree-sitter-java/3.3-python-binding, 2025-04-30.

[8] Vinod Pahuja. Building Call Graphs for Code Exploration Using Tree-Sitter[EB/OL]. https://dzone.com/articles/call-graphs-code-exploration-tree-sitter, 2025-01-24.

[9] bstee615. tree-climber: CFG Builder using tree-sitter[EB/OL]. https://github.com/bstee615/tree-climber/, 2025-08-18.

[10] INRIA. Spoon Control-flow module README[EB/OL]. https://github.com/INRIA/spoon/blob/master/spoon-control-flow/README.md, 2026.

[11] INRIA. Spoon ControlFlowGraph.java source[EB/OL]. https://github.com/INRIA/spoon/blob/master/spoon-control-flow/src/main/java/fr/inria/controlflow/ControlFlowGraph.java, 2026.

[12] Pawlak R, Noguera C, Petitprez N. Spoon: Program Analysis and Transformation in Java[R]. INRIA Research Report RR-5901, 2006.

[13] javaparser. JavaParser SymbolResolver.java[EB/OL]. https://github.com/javaparser/javaparser/blob/master/javaparser-core/src/main/java/com/github/javaparser/resolution/SymbolResolver.java, 2026.

[14] javaparser. Type Resolution Fails for Lambda Expressions as Method Parameters[EB/OL]. https://github.com/javaparser/javaparser/issues/5040, 2026-06-16.

[15] javaparser. Ambiguity in method calls for overloaded functional parameters[EB/OL]. https://github.com/javaparser/javaparser/issues/4814, 2025-08-15.

[16] Semgrep. Cross-file analysis examples[EB/OL]. https://semgrep.dev/docs/semgrep-code/semgrep-pro-engine-examples, 2026.

[17] Semgrep. Semgrep AppSec vs. Semgrep Community Edition[EB/OL]. https://semgrep.dev/products/semgrep-vs-ce, 2026.

[18] Semgrep. How we implemented inter-file analysis[EB/OL]. https://semgrep.dev/events/the-birth-of-semgrep-pro, 2024-01-16.

[19] Semgrep. Semgrep CHANGELOG (Scala interfile, prefiltering)[EB/OL]. https://github.com/grupooruss/semgrep/blob/develop/CHANGELOG.md, 2025-08-27.

[20] GitHub. CodeQL Analyzing data flow in Java and Kotlin[EB/OL]. https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-java/, 2026.

[21] GitHub. CodeQL TaintTracking module documentation[EB/OL]. https://codeql.github.com/codeql-standard-libraries/java/semmle/code/java/dataflow/TaintTracking.qll/module.TaintTracking.html, 2026.

[22] awiskar acharya. Finding Vulnerabilities Before They Find You: A Guide to CodeQL for Java[EB/OL]. https://macronepal.com/finding-vulnerabilities-before-they-find-you-a-guide-to-codeql-for-java/, 2025-11-27.

[23] Yg. CodeQL中Java污点分析的净化流优化与API安全检测实践[EB/OL]. https://xz.aliyun.com/news/19067, 2025-09-28.

[24] CodeGraphContext. Java: CALLS graph does not resolve cross-file method invocations[EB/OL]. https://github.com/CodeGraphContext/CodeGraphContext/issues/823, 2026-04-12.

[25] elvezjp. Java 8+構文を含むファイルのパースに失敗する (javalang limitations)[EB/OL]. https://github.com/elvezjp/code2map/issues/9, 2026-03-11.

[26] c2nes. javalang: Java 8 parser in Python[EB/OL]. https://github.com/c2nes/javalang, 2018.

[27] ADD Framework. joern_cpg.py source code (v2.7.3)[Z]. f:\Coding\audit-driven-development\scripts\joern_cpg.py, 2026.

[28] ADD Framework. ast_cfg.py source code (v2.7.3)[Z]. f:\Coding\audit-driven-development\scripts\ast_cfg.py, 2026.

[29] ADD Framework. v2.4 Joern CPG Integration Spec[Z]. f:\Coding\audit-driven-development\docs\superpowers\specs\2026-07-17-v2.4-joern-cpg-integration.md, 2026-07-17.

[30] ADD Framework. v2.8 Short-term Improvements Spec[Z]. f:\Coding\audit-driven-development\docs\superpowers\specs\2026-08-12-v2.8-short-term-improvements.md, 2026-08-12.

[31] ADD Framework. Framework Review and Gap Analysis[Z]. f:\Coding\audit-driven-development\docs\audit\2026-08-12-framework-review-and-gap-analysis.md, 2026-08-12.

[32] ADD Framework. ROADMAP[Z]. f:\Coding\audit-driven-development\docs\ROADMAP.md, 2026.

[33] Cornell University. Restrictions on Java Generics (Type Erasure)[Z]. https://www.cs.cornell.edu/courses/JavaAndDS/files/genericRestrictions.pdf, 2018.

[34] chichoxian. Joern代码分析工具解析[EB/OL]. https://blog.csdn.net/chichoxian/article/details/146364206, 2026-06-26.
