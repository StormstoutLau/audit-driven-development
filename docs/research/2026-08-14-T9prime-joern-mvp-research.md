# T9' Phase 1 (Joern MVP) — Taint 验证能力调研报告

> **版本**: v1.0 | **日期**: 2026-08-14 | **作者**: Scott + Subagent
> **前置文档**:
> - [ROADMAP.md v3.0+ T9'](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md)
> - [DECISIONS.md ADR-005/012/016](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md)
> - [2026-08-12-v3-roadmap-reassessment.md §2](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-v3-roadmap-reassessment.md)
> **调研方法**: 代码库内 search subagent 调研 + WebSearch/WebFetch 外部文档追溯 + GitHub Issue 追踪
> **目的**: 为 T9' Phase 1 (Joern MVP taint 验证) 提供技术可行性依据，识别扩展点和风险

---

## 0. 执行摘要

### 0.1 调研结论

| 维度 | 结论 | 置信度 | 依据 |
|------|------|--------|------|
| Joern `reachableByFlows` API 存在性 | ✅ 确认存在 | 高 | [官方文档 reference-card](https://docs.joern.io/cpgql/reference-card/) 明确列出 |
| API 适用于 taint 验证场景 | ✅ 适用 | 高 | [arXiv:2512.12313v3](https://arxiv.org/html/2512.12313v3) 真实使用案例 |
| Joern v4.0 兼容性 | ✅ 兼容 | 高 | Issue #5713 在 v4.0.325 上使用该 API；ADD `JOERN_VERSION_MIN="4.0"` |
| Python 前端 (pysrc2cpg) 稳定性 | ⚠️ 有已知 bug | 中 | 4 个 GitHub Issue 证实（详见 §3） |
| ADD 现有架构可复用性 | ✅ 80% 基础设施可复用 | 高 | search subagent 代码库审计 |
| Tier 2 AST 兜底可行性 | ⚠️ 需新建数据流追踪 | 中 | ast_cfg.py 仅有控制流，无数据流 |

### 0.2 核心建议

1. **立即可实施**: T9' Phase 1 (Joern MVP) 技术可行，Joern `reachableByFlows` API 满足需求
2. **三层降级必须**: Python 前端有已知 bug，Tier 2 AST 兜底和 Tier 3 regex 兜底不可省略
3. **架构选择**: 在 `verify_l4_structural` 内新增 `taint` 分支（类比 dead_code 分支），不新建独立 L5 函数——最小侵入，复用现有 `checks` dict 模式
4. **最高风险**: Joern `reachableByFlows` 的 Scala 脚本生成——必须先做 P1-5 式 API 实测（参考现有 dead_code/import 脚本的踩坑记录）

### 0.3 补充核验（2026-10-20 回填，Step 3 前置）

Step 3 设计阶段核对转换器代码时，发现"source/sink 提取"机制在本报告中**未定义**，遂补充以下外部核验（均以一手文档为准）：

| 事实 | 结论 | 来源 |
|------|------|------|
| CodeQL SARIF 是否携带 taint 路径 | ✅ 携带，`codeFlows[].threadFlows[].locations[]`；**仅当规则为 `@kind path-problem` 时生成**；首位置=source，末位置=sink | [GitHub Docs · CodeQL CLI SARIF output](https://docs.github.com/en/code-security/reference/code-scanning/codeql/codeql-cli/sarif-output) |
| Semgrep 是否携带 taint 路径 | ✅ 存在 `dataflow_trace`（`taint_source`/`intermediate_vars`/`taint_sink`），但属 **Pro Engine** 能力；Semgrep CE 仅单函数 taint | [semgrep_output_v1.jsonschema](https://raw.githubusercontent.com/semgrep/semgrep-interfaces/main/semgrep_output_v1.jsonschema) · [Semgrep CE vs Platform](https://docs.semgrep.dev/faq/comparisons/opengrep) |
| ADD 当前转换器是否保留上述路径信息 | ❌ 不保留 | [codeql_to_findings.py L104](file:///f:/Coding/audit-driven-development/scripts/codeql_to_findings.py#L104) 只取 `locations[0]`；[semgrep_to_findings.py L79](file:///f:/Coding/audit-driven-development/scripts/semgrep_to_findings.py#L79) 的 `evidence` 无路径字段 |

**结论修正**: §0.1 中"从 Semgrep/CodeQL finding 提取 source/sink"（§7.1）在 MVP 中**不可无条件成立** —— 精确 source 依赖上游分析模式与转换器保留原始 payload。此项已在 [Step 3 设计 spec](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T9prime-taint-design.md) 中作为 GAP-1 处理，并据此引入 broad-source 退化语义。

---

## 1. 背景

### 1.1 T9' 定位

T9' 是 v3.0 路线的 P0 优先级任务，目标是修复唯一致命 Gap G2 (taint 验证)。

**关键定位转变** (ADR-016): T9 从"检测 taint"重新定位为"验证 taint"——验证 SAST 工具 (Semgrep/CodeQL) 报告的 taint finding 的 source→sink 可达性是否真实，而非自行检测 taint。

### 1.2 设计约束

| ADR | 约束 | 来源 |
|-----|------|------|
| ADR-005 | T9' 采用 L5 层架构，Joern 优先 + AST 兜底 | [DECISIONS.md](file:///f:/Coding/audit-driven-development/docs/DECISIONS.md) |
| ADR-012 | T9' 三态验证结果 (true/false/null) | 同上 |
| ADR-016 | T9 重新定位: 检测→验证 | 同上 |
| ADR-019 | Joern CPG 三层降级架构 | 同上 |
| ADR-023 | Python ≥ 3.9，标准库优先，不引入新 runtime 依赖 | 同上 |

---

## 2. Joern reachableByFlows API 调研

### 2.1 API 确认

**来源**: [Joern 官方文档 CPGQL Reference Card](https://docs.joern.io/cpgql/reference-card/)

官方文档的 "Complex Steps" 表格明确列出以下数据流相关 step：

| Step | Description |
|------|-------------|
| `reachableBy` | Find if a given source node is reachable by a sink via a dataflow |
| `reachableByFlows` | Find paths for flows of data from sinks to sources |
| `source` | List of all nodes identified as sensitive/attacker-controlled |
| `sink` | List of all nodes identified as potential sensitive sinks |
| `controlledBy` | Returns only those dataflows that are wrapped by a given AST control condition |
| `notControlledBy` | Returns only those flows that are NOT wrapped by a given AST control condition |
| `locations` | List of all locations nodes traversed in a given dataflow |

**关键区别**:
- `reachableBy`: 返回布尔型可达性判断（source 是否被 sink 可达）
- `reachableByFlows`: 返回完整路径（flows of data from sinks to sources）

**ADD 用途**: T9' 需要验证 "source→sink 是否可达"，使用 `reachableBy` 即可（MVP 不需要完整路径）。`reachableByFlows` 可作为 Phase 2 增强（提供 evidence 路径）。

### 2.2 Scala 脚本用法

**来源**: [GitHub Issue #5713](https://github.com/joernio/joern/issues/5713)（Joern v4.0.325，2025-12-02）

Issue #5713 是一个 bug report，但其复现脚本提供了 `reachableByFlows` 的真实用法：

```scala
import io.joern.dataflowengineoss.language._
import io.shiftleft.codepropertygraph.generated.nodes._

@main def main(): Unit = {
  val source = cpg.method.nameExact("simple_object_003_T").parameter.nameExact("taint_src").l
  val sink = cpg.call.nameExact("system").where(_.argument.code("os")).l
  println(s"Source count: ${source.size}")
  println(s"Sink count: ${sink.size}")
  val flows = sink.reachableByFlows(source).l
  if (flows.nonEmpty) {
    println(s"Found ${flows.size} flows.")
    flows.foreach(println)
  } else {
    println("No flows found.")
  }
}
```

**注意**: ADD 现有 `joern_cpg.py` 的 `_gen_dead_code_script` (L327) 和 `_gen_import_script` (L371) 使用 **bare REPL** 风格（无 `@main`），因为 ADD 代码注释记录了 `@main` 在 joern --script 模式下失效的坑（[L338-L340](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py#L338-L340)）。T9' 的 `_gen_taint_flow_script` 应沿用 bare REPL 风格。

### 2.3 Custom Data-Flow Semantics

**来源**: [Joern 官方文档 Custom Data-Flow Semantics](https://docs.joern.io/dataflow-semantics/)

Joern 的数据流引擎需要语义定义来精确建模方法行为：

- **无语义定义时**: Joern 将 taint 从所有参数传播到所有参数 + 返回值（sound but imprecise，导致 `reachableBy` 返回额外无关路径）
- **有语义定义时**: 可以指定 `1->-1`（参数 1 → 返回值）、`PASSTHROUGH`（参数不杀流）等

**语法示例**:
```
"foo" 1->-1 2->3   // 参数1→返回值, 参数2→参数3
"foo" PASSTHROUGH 0 -> 0  // 参数不杀流
```

**ADD 影响**: MVP 阶段可使用 Joern 默认语义（`DefaultSemantics`），接受 imprecision 换取简单性。Phase 2 可考虑为常见 Python sanitizer（如 `html.escape`、`markupsafe.escape`）添加自定义语义。

### 2.4 学术使用案例

**来源**: [arXiv:2512.12313v3](https://arxiv.org/html/2512.12313v3) "Taint-Based Code Slicing for LLMs-based Malicious NPM Package Detection" (2026-06-13)

该论文使用 Joern 的 `ReachableByFlows` API 进行 taint-based slicing，追踪 untrusted sources 到 critical sinks 的数据流路径。这确认了：
1. `reachableByFlows` API 在学术研究中被真实使用
2. API 适用于 source→sink 可达性验证场景
3. 该论文引用编号 [54] 指向 Joern 工具

---

## 3. Joern Python 前端 (pysrc2cpg) Bug 调研

### 3.1 已知 Bug 清单

| Issue | 标题 | 版本 | 日期 | 状态 | 影响 |
|-------|------|------|------|------|------|
| [#5713](https://github.com/joernio/joern/issues/5713) | Taint flow not tracked when assigning to class attribute and accessing via instance | v4.0.325 | 2025-12-02 | Open | 类属性 taint 不追踪 |
| [#4594](https://github.com/joernio/joern/issues/4594) | Type inference of class attributes does not propagate from nested field accesses | v2.0.359 | 2024-05-23 | Open | 嵌套字段访问类型推断失败 |
| [#2886](https://github.com/joernio/joern/issues/2886) | pysrc2cpg exceptions and slow parsing with black repo | v1.2.19 | 2023-06-15 | Open | 大型 repo 崩溃/慢 |
| [#4577](https://github.com/joernio/joern/issues/4577) | Invalid Code parsing issues (whitespace) | v2.0.375 | 2024-05-21 | Closed | tab/空格解析问题 |

### 3.2 风险评估

**Issue #5713 (最高风险)**: Python 类属性赋值后通过实例访问时，taint flow 不追踪。这意味着：
```python
Person.name = taint_src    # taint 赋值到类属性
person = Person()
taint_sink(person.name)    # 通过实例访问 → Joern 不追踪
```
**ADD 影响**: 如果 SAST 报告的 taint finding 涉及类属性传播，Joern 可能返回 false negative（verified=False）。这正是 ADR-012 三态 `null` 的适用场景——Joern 无法判定时返回 `null`，保守保留 finding 供人工审查。

**Issue #4594 (中等风险)**: 嵌套字段访问（`self.classA.name = name`）的类型推断不传播。影响 taint 精度但不影响基本可达性。

**Issue #2886 (低风险)**: 大型 repo（如 black）解析崩溃。ADD benchmark 数据集（itsdangerous, fastapi, flask）规模较小，风险低。

**Issue #4577 (已解决)**: whitespace 解析问题，workaround 是用 `black` formatter 格式化。已 closed。

### 3.3 对 T9' 的设计影响

1. **三态返回是必须的**: `verified=null` 用于 Joern Python 前端 bug 导致的无法判定场景（ADR-012 已预见）
2. **Tier 2 AST 兜底不可省略**: 当 Joern 返回 false negative 时，AST def-use 链追踪作为第二道防线
3. **MVP 限定场景**: Phase 1 聚焦函数内 taint（local data flow），避免类属性/跨函数的已知 bug 区

---

## 4. 业界 Taint 验证方案对比

### 4.1 方案对比矩阵

| 维度 | Joern reachableByFlows | CodeQL TaintTracking | Semgrep Pro taint |
|------|------------------------|----------------------|-------------------|
| **API 类型** | CPGQL (Scala DSL) | QL (Datalog 方言) | YAML rule + Pro Engine |
| **source/sink 定义** | `cpg.method.parameter` / `cpg.call` 遍历 | `sourceModel`/`sinkModel` extensible predicates | `pattern-sources`/`pattern-sinks` YAML |
| **sanitizer 支持** | Custom Data-Flow Semantics (`FlowSemantic`) | `barrierModel` (替代 deprecated `isSanitizer`) | `pattern-sanitizers` YAML |
| **Python 支持** | pysrc2cpg (有已知 bug) | 原生支持 | 原生支持 |
| **API 重构** | 稳定 (v4.0 flatgraph 迁移) | 2023-2024 大重构 ([新数据流 API](https://github.blog/changelog/2023-08-13-new-dataflow-api-for-writing-custom-codeql-queries/)) | 稳定 |
| **部署成本** | JVM + joern-cli | CLI + database build | SaaS (Pro) / CLI (CE) |
| **ADD 集成现状** | ✅ 已集成 (Tier 1) | ❌ 仅消费 SARIF 输出 (T4) | ❌ 仅消费 JSON 输出 (T3) |

**来源**:
- Joern: [官方文档](https://docs.joern.io/cpgql/reference-card/) + [dataflow-semantics](https://docs.joern.io/dataflow-semantics/)
- CodeQL: [官方文档 Analyzing data flow](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-java/) + [Customizing library models](https://codeql.github.com/docs/codeql-language-guides/customizing-library-models-for-java-and-kotlin/) + [TaintTracking module](https://codeql.github.com/codeql-standard-libraries/java/semmle/code/java/dataflow/TaintTracking.qll/module.TaintTracking.html)
- Semgrep: T3 转换器已实现，Semgrep CE 不含 taint engine（Pro 才有）

### 4.2 ADD 战略选择

**ADD 不自建 taint detection，而是验证 SAST 报告的 taint finding**。因此：
- **Joern `reachableByFlows`**: 作为验证引擎（检查 Semgrep/CodeQL 报告的 source→sink 是否可达）✅ 选定
- **CodeQL TaintTracking**: 作为上游 SAST 工具（报告 taint finding），ADD 消费其 SARIF 输出
- **Semgrep Pro taint**: 作为上游 SAST 工具（如有 Pro 许可），ADD 消费其 JSON 输出

**理由**: ADD 已集成 Joern (Tier 1)，复用现有 CPG 基础设施成本最低。CodeQL 和 Semgrep 作为 detection 层已通过 T3/T4 转换器接入。

### 4.3 CodeQL 2023-2024 API 重构

**来源**: [GitHub Blog Changelog](https://github.blog/changelog/2023-08-13-new-dataflow-api-for-writing-custom-codeql-queries/) + [CSDN 技术博客](https://blog.csdn.net/2301_80951345/article/details/149700135)

CodeQL 在 2023-2024 年对数据流/污点跟踪 API 做了彻底重构：
- `isSanitizer` 已被 `isBarrier` 替代
- 新增 `sourceModel`/`sinkModel`/`summaryModel`/`barrierModel` extensible predicates
- 旧版 `TaintTracking::Configuration` 在 CodeQL 2.13.0 后被 modular API 替代
- 旧版库 deprecated，2024 年 12 月移除

**ADD 影响**: ADD 消费 CodeQL 的 SARIF 输出（通过 T4 `codeql_to_findings.py`），不直接调用 CodeQL API，因此 API 重构不影响 ADD。但需注意 CodeQL taint finding 的 SARIF 格式可能随 API 重构变化。

---

## 5. ADD 现有架构扩展点分析

> **来源**: search subagent 代码库审计（joern_cpg.py / verify_findings.py / ast_cfg.py / test_v24_consistency.py / test_v27_consistency.py / _e2e_joern_test.py）

### 5.1 现有 joern_cpg.py API

| 函数 | 行号 | 用途 | T9' 可复用 |
|------|------|------|-----------|
| `_get_cache_dir()` | L54 | 缓存目录 | ✅ 直接复用 |
| `_detect_wsl()` / `_detect_wsl_from_windows()` | L80/L106 | WSL2 检测 | ✅ 直接复用 |
| `_find_joern_binary()` | L208 | 定位 joern-cli | ✅ 直接复用 |
| `is_available()` | L248 | O(1) 可用性检测 | ✅ 直接复用 |
| `_get_cache_key(repo_root, language)` | L266 | CPG 缓存 key | ✅ 直接复用（taint 共用同一 CPG） |
| `_gen_dead_code_script(line, language)` | L327 | dead_code Scala 脚本生成 | 📋 模板参考 |
| `_gen_import_script(language)` | L371 | import 环检测 Scala 脚本 | 📋 模板参考 |
| `_generate_cpg(repo_root, cache_key, language)` | L642 | CPG 生成/缓存 | ✅ 直接复用 |
| `_translate_path_to_wsl(path)` | L688 | Windows→WSL2 路径 | ✅ 直接复用 |
| `_run_joern_query(cpg_path, script_text, script_name)` | L712 | 执行 Scala 脚本 | ✅ 直接复用 |
| `_parse_joern_output(output)` | L608 | 解析 key=value 输出 | ✅ 直接复用 |
| `_build_joern_query_command(cpg_path, script_path)` | L536 | 构建 joern --script 命令 | ✅ 直接复用 |
| `_build_clean_env()` | L574 | 干净 env | ✅ 直接复用 |
| `verify_dead_code(repo_root, file_path, line_num, language)` | L754 | dead_code 验证 API | 📋 模板参考 |
| `verify_imports(repo_root, claim, language)` | L818 | import 验证 API | 📋 模板参考 |

**结论**: 80% 基础设施可直接复用。需新增 `_gen_taint_flow_script(source, sink, language)` 和 `verify_taint_flow(repo_root, source, sink, language)`。

### 5.2 现有 verify_findings.py claim 调度

**claim 类型分类** (`classify_claim`, L103-132):

| 类型 | 模式常量 | 行号 | T9' 需新增 |
|------|---------|------|-----------|
| `missing` | `MISSING_PATTERNS` | L26-34 | — |
| `wrong` | `WRONG_PATTERNS` | L36-42 | — |
| `violates` | `VIOLATES_PATTERNS` | L44-50 | — |
| `dead_code` | `DEAD_CODE_PATTERNS` | L52-59 | — |
| `import_related` | `IMPORT_PATTERNS` | L61-69 | — |
| `taint` | (不存在) | — | ✅ 需新增 `TAINT_PATTERNS` |

**L4 调度** (`verify_l4_structural`, L316-474):

当前有 `dead_code` 分支 (L339-385) 和 `import_related` 分支 (L387-418)，采用 Tier 1→2→3 三层降级。T9' 需新增 `taint` 分支，类比 `dead_code` 分支结构。

### 5.3 现有 ast_cfg.py Tier 2 局限

**关键发现**: `ast_cfg.py` 的 `CFGBuilder` (L33) 是**控制流图**（CFG），不是**数据流图**（DFG）。它追踪"语句是否可达"（`is_reachable`, L202, BFS），不追踪"变量值如何传播"。

**T9' Tier 2 需新建**: 基于 `ast` 模块的 def-use 链追踪（变量赋值链、参数传递、return 值回流），这是 `ast_cfg.py` 完全没有的能力。

**可部分复用**:
- `_find_enclosing_function` (L237): 限定 source/sink 是否在同一函数内
- `is_reachable` (L202): 限定 source/sink 是否在同一可达控制流路径上

### 5.4 现有测试覆盖

| 测试文件 | Joern/CPG 覆盖 | T9' 需新增 |
|---------|---------------|-----------|
| `test_v24_consistency.py` J1-J10 | Tier 1 is_available/disabled/schema/降级 | T9' taint API 测试 |
| `test_v27_consistency.py` L7.1.2 | 多语言 language 参数 | taint 多语言测试 |
| `_e2e_joern_test.py` | WSL2 冒烟测试 (dead_code/imports) | `_e2e_taint_test.py` |
| 所有 test_*.py | **0 处 taint 测试** | 全新测试套件 |

---

## 6. 风险矩阵

| 风险 | 概率 | 影响 | 严重度 | 缓解措施 |
|------|------|------|--------|---------|
| Joern `reachableByFlows` Scala API 幻觉（脚本不工作） | 高 | 高 | 🔴 P0 | P1-5 式 API 实测（参考 dead_code 踩坑记录 L338-356） |
| pysrc2cpg 类属性 taint bug (#5713) | 中 | 中 | 🟠 P1 | 三态 `null` 返回 + Tier 2 AST 兜底 |
| Tier 2 AST def-use 链实现复杂度 | 中 | 中 | 🟠 P1 | MVP 限定函数内 local data flow |
| source/sink 从 finding 提取困难 | 中 | 中 | 🟠 P1 | MVP 从 Semgrep/CodeQL finding 的 metadata 提取 |
| Joern 大型 repo 解析崩溃 (#2886) | 低 | 低 | 🟡 P2 | benchmark 数据集规模小 |
| CodeQL SARIF taint 格式变化 | 低 | 低 | 🟡 P2 | T4 转换器已兼容 SARIF 2.0/2.1/2.2 |

---

## 7. 实施建议

### 7.1 MVP 范围限定

**Phase 1 (Joern MVP) 范围**:
- ✅ 函数内 taint (local data flow) 验证
- ✅ 从 Semgrep/CodeQL finding 提取 source/sink 【⚠️ 2026-10-20 修正：MVP 阶段**精确 source 不可得**，见 §0.3；改为 sink 定位 + broad-source 退化语义】
- ✅ Joern `reachableBy` (布尔可达性，非完整路径)
- ✅ Tier 1→2→3 三层降级
- ❌ 跨函数 taint (inter-procedural) — Phase 2
- ❌ 完整 flow 路径输出 — Phase 2
- ❌ Custom Data-Flow Semantics — Phase 2

### 7.2 架构选择

**在 `verify_l4_structural` 内新增 `taint` 分支**（非新建独立 L5 函数）：

```python
# verify_findings.py verify_l4_structural 内
if "taint" in claim_types:
    # Tier 1: Joern reachableBy
    joern_result = joern_cpg.verify_taint_flow(repo_root, source, sink, language=language)
    if joern_result["verified"] is True:
        checks["taint_t1"] = (True, joern_result["evidence"], 1)
    elif joern_result["verified"] is False:
        # Tier 2: AST def-use 链兜底
        ast_result = ast_cfg.verify_taint_flow(repo_root, source, sink)
        checks["taint_t2"] = (ast_result["verified"], ast_result["evidence"], 2)
    else:  # None (Joern 不可用或无法判定)
        # Tier 3: regex 兜底
        checks["taint_t3"] = _verify_taint_regex(claim, file_path, line_num)
```

**理由**: 复用现有 `checks` dict 模式 (L337)，最小侵入，保持聚合策略 (L448-470) 一致性。

### 7.3 新增 API 清单

| 文件 | 新增 API | 对标现有 |
|------|---------|---------|
| `joern_cpg.py` | `verify_taint_flow(repo_root, source, sink, language="python")` | `verify_dead_code` (L754) |
| `joern_cpg.py` | `_gen_taint_flow_script(source, sink, language)` | `_gen_dead_code_script` (L327) |
| `verify_findings.py` | `TAINT_PATTERNS` 正则常量 | `DEAD_CODE_PATTERNS` (L52) |
| `verify_findings.py` | `classify_claim` 增加 `taint` 类型 | L103-132 |
| `verify_findings.py` | `verify_l4_structural` 增加 `taint` 分支 | dead_code 分支 (L339-385) |
| `ast_cfg.py` | `verify_taint_flow_in_source(source_code, source_pattern, sink_pattern)` | `verify_dead_code_in_source` (L263) |
| `ast_cfg.py` | `verify_taint_flow(repo_root, source, sink)` | `verify_dead_code` (L317) |

### 7.4 可直接复用的基础设施（无需修改）

- CPG 缓存: `_get_cache_key` / `_generate_cpg` / `_get_cache_dir`（taint 共用同一 CPG）
- WSL2 路径转换: `_translate_path_to_wsl` / `_build_wsl_bash_command` / `_detect_wsl_from_windows`
- 子进程封装: `_build_joern_query_command` / `_build_clean_env` / `_run_joern_query` / `_parse_joern_output`
- 不抛异常约定与 `JOERN_FORCE_RAISE` / `JOERN_DISABLE` 测试钩子
- 统一三态返回 schema（已与 ADR-012 对齐）

---

## 8. 外部引用清单

### 8.1 官方文档

| # | 引用 | URL | 用途 |
|---|------|-----|------|
| R1 | Joern CPGQL Reference Card | https://docs.joern.io/cpgql/reference-card/ | 确认 reachableBy/reachableByFlows/source/sink API 存在 |
| R2 | Joern Custom Data-Flow Semantics | https://docs.joern.io/dataflow-semantics/ | 语义定义语法 (FlowSemantic, PASSTHROUGH) |
| R3 | CodeQL Analyzing Data Flow | https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-java/ | CodeQL taint tracking API |
| R4 | CodeQL Customizing Library Models | https://codeql.github.com/docs/codeql-language-guides/customizing-library-models-for-java-and-kotlin/ | sourceModel/sinkModel/barrierModel |
| R5 | CodeQL TaintTracking Module | https://codeql.github.com/codeql-standard-libraries/java/semmle/code/java/dataflow/TaintTracking.qll/module.TaintTracking.html | TaintTracking API 参考 |
| R6 | CodeQL New Dataflow API (2023) | https://github.blog/changelog/2023-08-13-new-dataflow-api-for-writing-custom-codeql-queries/ | API 重构确认 |

### 8.2 GitHub Issues

| # | 引用 | URL | 用途 |
|---|------|-----|------|
| R7 | Issue #5713 — Python class attribute taint bug | https://github.com/joernio/joern/issues/5713 | pysrc2cpg 已知 bug + reachableByFlows 真实用法 |
| R8 | Issue #4594 — Nested field access type inference bug | https://github.com/joernio/joern/issues/4594 | pysrc2cpg 类型推断 bug |
| R9 | Issue #2886 — black repo crash/slow | https://github.com/joernio/joern/issues/2886 | 大型 repo 解析风险 |
| R10 | Issue #4577 — Whitespace parsing (closed) | https://github.com/joernio/joern/issues/4577 | 已解决的解析问题 |

### 8.3 学术论文

| # | 引用 | URL | 用途 |
|---|------|-----|------|
| R11 | arXiv:2512.12313v3 — Taint-Based Code Slicing for LLMs-based Malicious NPM Package Detection | https://arxiv.org/html/2512.12313v3 | reachableByFlows 真实学术使用案例 |

### 8.4 技术博客

| # | 引用 | URL | 用途 |
|---|------|-----|------|
| R12 | 使用 Joern 进行漏洞挖掘 (evilpan) | https://evilpan.com/2024/09/16/using-joern/ | reachableByFlows 实战示例 |
| R13 | codeql 从入门到入土 (CSDN) | https://blog.csdn.net/2301_80951345/article/details/149700135 | CodeQL API 重构 (isBarrier 替代 isSanitizer) |
| R14 | Joern 代码分析工具解析 (CSDN) | https://blog.csdn.net/chichoxian/article/details/146364206 | Joern CPG 架构概述 |

### 8.5 内部代码引用

| # | 引用 | 路径 | 用途 |
|---|------|------|------|
| R15 | `joern_cpg.py verify_dead_code` | [L754](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py#L754) | T9' API 模板 |
| R16 | joern_cpg.py _gen_dead_code_script | [L327](file:///f:/Coding/audit-driven-development/scripts/joern_cpg.py#L327) | Scala 脚本生成模板 |
| R17 | verify_findings.py verify_l4_structural | [L316](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L316) | L4 调度扩展点 |
| R18 | verify_findings.py classify_claim | [L103](file:///f:/Coding/audit-driven-development/scripts/verify_findings.py#L103) | claim 类型分类扩展点 |
| R19 | ast_cfg.py CFGBuilder | [L33](file:///f:/Coding/audit-driven-development/scripts/ast_cfg.py#L33) | Tier 2 局限确认 |
| R20 | test_v24_consistency.py J1-J10 | [L397](file:///f:/Coding/audit-driven-development/scripts/test_v24_consistency.py#L397) | 测试模板 |

---

## 9. 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-08-14 | v1.0 | 初始调研: Joern reachableByFlows API 确认 + pysrc2cpg bug 清单 + CodeQL 对比 + ADD 扩展点分析 |
| 2026-08-14 | v1.1 | 审计校验: 修正 1 处事实幻觉 (arXiv 论文标题) + 8 处代码行号偏差 (统一为精确 def 行号) |
| 2026-10-20 | v1.2 | **第二轮审计（Step 3 前置）**: 撤回 v1.1 的 8 处行号"修正"（该轮按 `Read` 标签改错方向），改以 `Grep` 为权威值恢复；确立"行号以 Grep 为准"纪律；新增 §0.4 外部事实核验回填（CodeQL codeFlows / Semgrep dataflow_trace） |

---

## 10. 审计校验记录 (v1.2)

### 10.1 审计方法

- **外部引用**: 逐条 WebFetch 验证 URL 可访问性 + 内容匹配
- **代码行号**: 逐条核验 def/常量起始行；**权威来源为 `Grep`(ripgrep)**，不以 `Read` 显示标签为准（见 §10.2 根因）
- **GitHub Issues**: 验证 Issue 编号、标题、版本、日期、状态
- **学术论文**: 验证 arXiv 编号、标题、作者、日期

### 10.2 审计发现

#### 幻觉 (1 处，已修正)

| ID | 位置 | 错误 | 修正 | 来源 |
|----|------|------|------|------|
| H1 | §2.4, §8.3 R11 | arXiv 论文标题写成 "Leveraging Code Slicing..." | 修正为 "Taint-Based Code Slicing..." | [arXiv:2512.12313](https://arxiv.org/abs/2512.12313) 官网 |

#### 行号偏差 (8 处，第二轮审计已修正回权威值)

> ⚠️ **第一轮审计自身引入了偏差（已记录为教训）**：第一轮曾按 `Read` 显示标签把这 8 处行号"修正"为 `-1/-2` 的值，方向与事实相反。第二轮改用 `Grep`(ripgrep) 交叉复核后确认：**第一轮被"修正"前的原始值才是正确的**。下表"最终值"列即为权威值，验证方法为 `Grep`。

| ID | 位置 | 原值 | 第一轮误改为 | **最终权威值（Grep）** |
|----|------|------|------------|---------------------|
| H2 | §5.1, §7.3, §8.5 R15 | L754 | L753 ✗ | **L754** |
| H3 | §5.1, §7.3, §8.5 R16 | L327 | L325 ✗ | **L327** |
| H4 | §5.1 | L818 | L816 ✗ | **L818** |
| H5 | §5.1, §2.2 注意 | L371 | L369 ✗ | **L371** |
| H6 | §5.3 | L202 | L200 ✗ | **L202** |
| H7 | §5.3, §7.3 | L263 | L261 ✗ | **L263** |
| H8 | §7.3 | L317 | L315 ✗ | **L317** |

**根因**: `Read` 工具显示的行号标签对**不同文件存在不一致偏移**（`joern_cpg.py` 偏 -1~-2，`verify_findings.py` 与 `Grep` 一致）。故行号必须以 `Grep` 为唯一权威来源。该纪律已写入 [Step 3 设计 spec §12](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-10-20-v3.0-T9prime-taint-design.md)。

**残余偏差说明**: §5.3 原写 `CFGBuilder (L33-196)` 的范围末值 196 属 `Read` 推定，已改为只保留已验证的 `L33`；其余区间型引用（如 `L339-385`/`L387-418`）的端点均为 `Grep` 已确认的 def/分支起始行。

### 10.3 验证通过的断言

| 引用 | 验证结果 | 证据 |
|------|---------|------|
| R1 Joern CPGQL Reference Card | ✅ 通过 | reachableBy/reachableByFlows/source/sink 均在 Complex Steps 表格 |
| R2 Custom Data-Flow Semantics | ✅ 通过 | PASSTHROUGH 语法、FlowSemantic、DefaultSemantics 全部匹配 |
| R7 Issue #5713 | ✅ 通过 | 标题/版本 v4.0.325/日期 2025-12-02/状态 Open/复现脚本全部一致 |
| R8 Issue #4594 | ✅ 通过 | 标题/版本 v2.0.359/日期 2024-05-23/状态 Open 全部一致 |
| R9 Issue #2886 | ✅ 通过 | 标题/日期 2023-06-15/版本 v1.2.19/black repo 崩溃一致 |
| R10 Issue #4577 | ✅ 通过 | 标题/状态 Closed/日期 2024-05-21/版本 v2.0.375/workaround (black formatter) 一致 |
| R11 arXiv:2512.12313v3 | ✅ 通过 (标题已修正) | 编号/日期 2025-12-13/v3 版本 2026-06-13 一致 |
| R6 CodeQL New Dataflow API | ✅ 通过 | 2023-08-14 发布，isSanitizer→isBarrier，December 2024 deprecation 一致 |
| R3 CodeQL Analyzing Data Flow | ✅ 通过 | 文档存在，Java/Kotlin 数据流分析 |
| R5 CodeQL TaintTracking Module | ✅ 通过 | 文档存在，模块定义一致 |
| 代码行号 (Grep 权威) | ✅ 通过 | L316 verify_l4_structural / L103 classify_claim / L52 DEAD_CODE_PATTERNS / L61 IMPORT_PATTERNS / L44 VIOLATES_PATTERNS / L337 checks dict / L339 dead_code 分支 / L33 CFGBuilder / L202 is_reachable / L263 verify_dead_code_in_source / L317 verify_dead_code / L754 verify_dead_code / L327 _gen_dead_code_script / L818 verify_imports / L371 _gen_import_script / L5 NEVER raises / L40 JOERN_TIMEOUT_SEC / L41 JOERN_VERSION_MIN / L779+L842 JOERN_FORCE_RAISE 全部为 def/常量起始行 |
| DECISIONS.md ADR 行号 (Grep 权威) | ✅ 通过 | ADR-001 L41 / ADR-005 L143 / ADR-012 L316 / ADR-016 L394 / ADR-018 L426 / ADR-019 L442 / ADR-023 L525 |
| JOERN_VERSION_MIN = "4.0" | ✅ 通过 | joern_cpg.py L41 |
| JOERN_LANGUAGE_MAP | ✅ 通过 | joern_cpg.py L44-48 |
