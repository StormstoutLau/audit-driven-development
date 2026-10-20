# v3.0+ 中期/远期改进路线重新评估与风险调研

> **版本**: v1.0 | **日期**: 2026-08-12 | **作者**: Scott + Subagent
> **前置文档**:
> - [ROADMAP.md v3.0+ Reassessment](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md)
> - [2026-08-12-convergence-analysis.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-convergence-analysis.md)
> - [2026-08-12-framework-review-and-gap-analysis.md](file:///f:/Coding/audit-driven-development/docs/audit/2026-08-12-framework-review-and-gap-analysis.md)
> **调研方法**: 4 个并行 subagent 深度调研 + 文件审计 + 外部引用追溯
> **目的**: 对 v2.8 完成后的中期/远期改进路线进行重新评估，并对关键风险项进行深度调研

---

## 0. 执行摘要

### 0.1 重新评估的触发条件

v2.8 完成后，10 个原始 Gap 中 4 个已解决（G1/G7/G10 + G3 部分解决），3 个部分缓解（G4/G5/G9），3 个仍存在（G2/G6/G8）。致命级 Gap 从 2 个降至 1 个（仅剩 G2 taint）。战略定位已确认：**ADD = "SAST Findings Validator"**（非 SAST Tool）。

基于此，原 v3.0+ 路线需要进行重新评估：
- **取消**: T7（AST pattern detection）— 违背战略定位
- **重新定位**: T9（检测 taint → 验证 taint）
- **重构**: T8（自建 import graph → 深化 Joern）
- **提升优先级**: T12（benchmark 规模是验证泛化能力的前提）
- **新增**: T17（Spec-driven Audit）+ T18（Lean4 形式化验证子集）

### 0.2 核心结论

经过 4 个并行 subagent 的深度调研，对 6 个关键任务（T9'/T12/T17/T18/T11/T8'）的风险评估如下：

| 任务 | 可行性 | 优先级 | 工作量 | 核心风险 | 建议 |
|------|--------|--------|--------|----------|------|
| **T9'** (Taint 验证) | ✅ 高 | 🔴 P0 | 2-3 天 (MVP) | Joern Python 前端 bug | **立即实施 Phase 1** |
| **T12** (Benchmark 5000+) | ✅ 高 | 🟠 P1 | 2-4 周 | 标签噪声 + 标注成本 | 采用半自动标注方案 |
| **T17** (Spec-driven Audit) | ✅ 高 | 🟠 P1 (L0-L1) | 1-3 月 | Spec 编写成本 | 从 OpenAPI 契约验证开始 |
| **T18** (Lean4 形式化) | ⚠️ 中 | 🟡 P2 (试点) | 6-12 月 | 学习曲线 + 翻译成功率 | Dafny 作为 fallback |
| **T11** (Java AST CFG) | ✅ 中 | 🟡 P2 | 8 天 | tree-sitter CFG 工作量 | T8' 完成后再实施 |
| **T8'** (Joern 深化) | ✅ 高 | 🟠 P1 | 6 天 | verify_imports 重构 | **优先于 T11 实施** |

### 0.3 推荐实施顺序

```
Phase 1 (立即, 0-1 周):
  └── T9' Phase 1 (Joern MVP) — 修复唯一致命 Gap G2

Phase 2 (短期, 1-4 周):
  ├── T8' (Joern 深化) — 修复 G4 残余
  └── T12 (Benchmark 扩展) — 数据基础

Phase 3 (中期, 1-3 月):
  ├── T17 L0-L1 (OpenAPI + EARS) — 条件性 1 收敛
  └── T11 (Java AST CFG) — 多语言验证精度

Phase 4 (长期, 3-12 月):
  ├── T17 L2-L3 (TLA+ + Hoare Triple)
  └── T18 (Lean4 试点 → 扩展) — 强收敛子集
```

### 0.4 关键决策记录

| ID | 决策 | 理由 |
|----|------|------|
| D1 | T9' 采用 L5 层架构，Joern 优先 + AST 兜底 | 复用现有降级机制，MVP 2-3 天可交付 |
| D2 | T12 弃用 Big-Vul，改用 CVEfixes + ICVul | Big-Vul 标签准确率仅 25-54% |
| D3 | T17 分层实施（L0-L4），从 OpenAPI 开始 | 渐进式采用，降低 spec 编写成本 |
| D4 | T18 以 Lean4 为主，Dafny 为 fallback | Lean4 学术价值最高，Dafny 学习曲线低 |
| D5 | T8' 优先于 T11 实施 | T8' 修复后 Java 可通过 Joern 获得 Tier 1 验证 |
| D6 | T11 采用 tree-sitter-java，非 javalang/Spoon | javalang 停更，Spoon 引入 JVM 依赖 |

---

## 1. 重新评估背景

### 1.1 v2.8 完成状态

v2.8 已完成 6 个短期改进任务（T1-T6）+ 3 个 P3 修复，TDD 491/491 PASS，Benchmark 无退化（P=75.0%, R=85.7%, F1=80.0%）。

**战略转向确认**: ADD = "SAST Findings Validator"（消费 SAST 输出，用 4-Level 验证门过滤虚假 findings），而非 SAST Tool。

### 1.2 Gap 闭合追踪（v2.8 后）

| Gap | 原状态 | v2.8 后 | v3.0 目标 | v3.5+ 目标 |
|-----|--------|---------|-----------|-----------|
| G1 无 Detection | 🔴 致命 | ✅ 解决 | — | — |
| G2 无 taint | 🔴 致命 | 🔴 仍存在 | T9' 解决 | — |
| G3 无 CWE/CVE | 🟠 严重 | 🟡 部分解决 | — | 完全解决 |
| G4 无跨文件 | 🟠 严重 | 🟡 部分缓解 | T8' 解决 | — |
| G5 语言窄 | 🟠 严重 | 🟡 部分缓解 | T11 提升 | — |
| G6 无 IDE | 🟡 中等 | 🟡 仍存在 | T10 解决 | — |
| G7 无 CI/CD | 🟡 中等 | ✅ 解决 | — | — |
| G8 规则生态 0 | 🟡 中等 | 🟡 仍存在 | — | T14 解决 |
| G9 Benchmark 小 | 🟡 中等 | 🟡 部分缓解 | T12 解决 | — |
| G10 Loop 展示非决策 | 🟡 中等 | ✅ 解决 | — | — |

### 1.3 重新评估的范围

本文档对以下 6 个任务进行深度风险评估：

- **T9'** — Taint 验证能力（修复 G2 致命 Gap）
- **T12** — Benchmark 扩展到 5000+ findings（修复 G9）
- **T17** — Spec-driven Audit（条件性 1 收敛）
- **T18** — Lean4 形式化验证子集（强收敛子集）
- **T11** — Tier 2 AST CFG 扩展到 Java（修复 G5）
- **T8'** — 深化 Joern 跨文件验证（修复 G4 残余）

每个任务的风险评估包括：技术可行性、业界方案对比、风险矩阵、实施建议。

---

## 2. T9' — Taint 验证能力风险评估

> **修复 Gap**: G2（无 taint）— 唯一仍处于 🔴 致命状态的 Gap
> **定位**: 验证 SAST 工具（Semgrep/CodeQL）报告的 taint finding 是否有真实 source→sink 可达路径
> **调研方法**: 业界方案对比 + 技术可行性分析 + 学术文献检索

### 2.1 业界 Taint 验证方案对比

| 工具 | 验证模式适配 | Python 支持 | 路径输出 | ADD 集成成本 | 推荐度 |
|------|------------|------------|---------|------------|--------|
| **CodeQL** | ⭐⭐⭐⭐⭐ (`flowPath`) | ⭐⭐⭐⭐ | 完整路径 | 高（需 database build） | 中（重型） |
| **Joern** | ⭐⭐⭐⭐ (`reachableByFlows`) | ⭐⭐⭐ (pythonsrc 弱) | 完整路径 | **低（ADD 已集成）** | **高** |
| **Semgrep Pro** | ⭐⭐⭐ (检测非验证) | ⭐⭐⭐⭐ | source/sink 对 | 低（已是上游） | 中 |
| **Infer Pulse** | ⭐⭐ (内存安全导向) | ⭐⭐ (Python 新前端) | 报告级 | 高（IR 不兼容） | 低 |

**关键决策**: 选择 **Joern** 作为首选验证引擎，因为 ADD 已集成 Joern CPG，`reachableByFlows` API 天然适合验证模式，扩展成本最低。

**CodeQL `flowPath` API 参考**:
```ql
// 新模块化 API (CodeQL 2.13.0+)
module MyConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) { ... }
  predicate isSink(DataFlow::Node sink) { ... }
  predicate isBarrier(DataFlow::Node barrier) { ... }
}
module MyFlow = TaintTracking::Global<MyConfig>;
from MyFlow::PathNode source, MyFlow::PathNode sink
where MyFlow::flowPath(source, sink)
select sink.getNode(), source, sink, "taint flow"
```
来源: [CodeQL TaintTracking](https://codeql.github.com/codeql-standard-libraries/java/semmle/code/java/dataflow/TaintTracking.qll/module.TaintTracking$TaintTracking.html)

**Joern `reachableByFlows` API 参考**:
```scala
val source = cpg.method.name("main").parameter
val sink = cpg.call.name("strcmp").argument
sink.reachableByFlows(source).p  // 返回表格化路径
```
来源: [Joern Data-Flow Steps](https://docs.joern.io/cpgql/data-flow-steps/)

### 2.2 技术可行性分析

#### 2.2.1 验证模式 vs 检测模式的关键差异

ADD 是**验证器**而非检测器，这一定位显著降低了 taint 分析的复杂度：

| 维度 | 检测模式（SAST Tool） | 验证模式（ADD T9'） |
|------|---------------------|-------------------|
| 输入 | 源代码 | SAST finding（含 source/sink 位置） |
| 任务 | 全程序 taint 分析 | 验证给定 source→sink 对 |
| 复杂度 | O(ED³) IFDS | Demand-Driven CFL-Reachability |
| 路径爆炸风险 | 高 | 低（有锚点） |

**推荐策略**: **Demand-Driven（按需）CFL-Reachability** — 给定 (source, sink) 对，按需计算可达性，避免全程序分析的爆炸。

#### 2.2.2 Python AST + CFG 实现 Taint 验证的难度

**难度评级**: 🟠 中高（过程内可行，跨过程困难）

| 能力 | 难度 | 说明 |
|------|------|------|
| Def-Use 链 | 中 | 到达定义分析，前向 worklist 算法 |
| Source/Sink 识别 | 低 | 模式匹配 |
| 过程内 taint 传播 | 中 | 赋值、返回值、字符串拼接 |
| Sanitizer 识别 | 低 | 白名单模式匹配 |
| 跨过程传播 | 🔴 高 | 需要调用图 + 过程摘要 |
| 别名分析 | 🔴 高 | Python pass-by-object-reference |
| 动态特性处理 | 🔴 极高 | getattr/setattr/猴子补丁/装饰器/eval |

**Python 特殊挑战**: 动态分发、一等函数、元编程、描述符协议、pass-by-object-reference、pervasive exceptions。

**实证参考**: PyFlow（ICSE 2026）基于 IFDS 框架为 Python 构建了完整的跨过程分析，在 8 个 SAST 工具对比中取得最佳 recall 和 F1，但实现复杂度极高。来源: [PyFlow 论文](https://arxiv.org/abs/2608.07026)

#### 2.2.3 路径爆炸缓解策略

| 策略 | 原理 | ADD 适用性 |
|------|------|-----------|
| Sparsification | 只在 source/sink 相关语句处计算 | ⭐⭐⭐⭐⭐ |
| CFL-Reachability | 路径问题转为 CFL 可达性 | ⭐⭐⭐⭐ |
| K-Limiting | 限制调用栈深度 | ⭐⭐⭐⭐⭐ |
| Summary-Based | 过程摘要复用 | ⭐⭐⭐⭐ |

**ADD 推荐组合**: **Sparsification + K-Limiting (k=3) + Demand-Driven**

### 2.3 ADD 定位适配

#### 2.3.1 Input/Output 契约

**Input 契约**（SAST finding 的 taint 子集）:
```json
{
  "finding_id": "semgrep-py-001",
  "tool": "semgrep",
  "rule_id": "python.django.security.injection.sql.sql-injection",
  "type": "taint",
  "source": {"file": "app/views.py", "line": 42, "code": "request.GET.get('q')"},
  "sink": {"file": "app/views.py", "line": 58, "code": "cursor.execute(query)"},
  "language": "python"
}
```

**Output 契约**（三态验证结果）:
```json
{
  "finding_id": "semgrep-py-001",
  "taint_verified": true,  // true | false | null
  "confidence": "high",
  "tier": 1,
  "path": [...],
  "sanitizer_found": false,
  "latency_ms": 342
}
```

**三态语义**:
- `taint_verified: true` — 路径确认可达，保留 finding
- `taint_verified: false` — 路径不可达（sanitizer 阻断/不可达代码），降级或移除 finding
- `taint_verified: null` — 无法确定，保留 finding（保守策略）

#### 2.3.2 与现有 4-Level 验证的关系

**推荐: L5 层（独立层级，taint finding 专属）**

```
L1 (文件存在) → L2 (行号有效) → L3 (关键词匹配) → L4 (结构验证) → L5 (taint 路径)
                                                                    ↑
                                                    仅 type == "taint" 的 finding 触发
```

**理由**:
1. 非破坏性：L1-L4 对所有 finding 保持不变
2. 按需触发：只有 taint 类型 finding 才进入 L5
3. 降级一致：L5 复用 Tier 1 (Joern) → Tier 2 (AST) → Tier 3 (保守通过) 降级机制

### 2.4 风险矩阵

| 风险项 | 概率 | 影响 | 严重度 | 缓解策略 |
|--------|------|------|--------|---------|
| Python 跨过程 taint 误报 | 高 | 中 | 🟠 | k-limiting + 仅验证不检测 |
| Joern Python 前端 bug | 高 | 高 | 🔴 | Tier 2 AST fallback + 已知 bug 规避 |
| 路径爆炸超时 | 中 | 高 | 🟠 | Sparsification + 30s 超时 + 降级 |
| Source/Sink 定义不一致 | 中 | 中 | 🟡 | 消费 SAST 输出的位置，不自定义 |
| 别名分析缺失导致漏报 | 高 | 低 | 🟡 | 接受 under-approx |
| 动态特性导致误判 | 高 | 中 | 🟠 | 保守策略：遇 getattr/eval 返回 None |
| 大项目性能问题 | 中 | 中 | 🟡 | 文件级 slice + 单文件内分析 |
| 与 Joern CPG 集成复杂度 | 低 | 低 | 🟢 | 已有 joern_cpg.py 集成基础 |

**关键风险详解 — Joern Python 前端 bug**:
- Issue [#5713](https://github.com/joernio/joern/issues/5713): Python 类属性 taint 传播失败（v4.0.325，2025-12-02 报告）
- Issue [#3761](https://github.com/joernio/joern/issues/3761): 跨过程间接调用误报
- **规避**: 在测试用例中排除类属性场景，或对类属性场景返回 `verified=None`

### 2.5 类似学术/工业工作

| 工作 | 定位 | 方法 | 结果 | ADD 启示 |
|------|------|------|------|---------|
| **Bond** (USENIX Security 2026) | Taint 验证器 | Constraint-Directed Fuzzing | 91.67% recall，发现 155 未知漏洞 | 动态验证静态结果 |
| **AdaTaint** (CISAI 2025) | 减少误报 | LLM 推断 source/sink | 减少 43.7% 误报 | LLM 补充 SAST 覆盖 |
| **Memoir** (arXiv 2026) | 误报记忆库 | LLM 标注 + 模式聚类 | CodeQL 误报减少 80% | ADD hallucination_log 已有类似机制 |
| **Frame** (2026) | 神经符号 SAST | separation-logic + Z3 + LLM | F1 0.58 | 神经符号架构与 ADD 同构 |

来源: [Bond Paper](https://www.usenix.org/system/files/conference/usenixsecurity26/sec26_prepub_peng-jiaqian.pdf), [AdaTaint](https://dl.acm.org/doi/pdf/10.1145/3773365.3773410), [Memoir](https://arxiv.org/html/2608.09181v1), [Frame](https://lambdasec.github.io/Frame-Grounding-LLM-Vulnerability-Detection-with-a-Sound-Separation-Logic-Core/)

### 2.6 实施建议

**Phase 1 (MVP, 2-3 天)**: Joern-based Taint 验证
1. 扩展 `joern_cpg.py`，新增 `verify_taint_path(source_loc, sink_loc, language)`
2. 调用 Joern `reachableByFlows` API
3. 在 `verify_findings.py` 中新增 L5 调度逻辑
4. 三态输出 + 路径

**Phase 2 (1-2 周)**: AST-based Taint 验证（Tier 2 fallback）
1. 扩展 `ast_cfg.py`，新增 `TaintVerifier` 类
2. 过程内 def-use 链 + source/sink 模式匹配
3. k=1 跨过程（直接调用）
4. Sanitizer 白名单识别

**Phase 3 (远期, v3.5+)**: 跨过程增强 + Java 支持
1. k-limited (k=3) 跨过程追踪
2. Java taint 验证（利用 Joern javasrc2cpg）
3. 与 `hallucination_log` 集成

**决策**: ✅ **立即实施 T9' Phase 1** — 修复唯一致命 Gap G2，MVP 2-3 天可交付。

---

## 3. T12 — Benchmark 扩展到 5000+ Findings 风险评估

> **修复 Gap**: G9（Benchmark 小）— 验证泛化能力的前提
> **当前状态**: 687 findings（v2.6），置信区间 ±2.6%
> **目标**: 5000+ findings，置信区间 ±1.0%
> **调研方法**: 现有数据集分析 + 标注成本估算 + 统计显著性计算

### 3.1 现有 SAST Benchmark 数据集分析

#### 3.1.1 本地数据现状校正（重要发现）

经核查 `docs/benchmark/` 下文件，发现任务描述中的若干数字与实际不符：

| 文件 | 实际条目数 | unknown.c 占比 | 任务描述 |
|---|---|---|---|
| `bigvul/findings.json` | **584** | **12.2%** (71/584) | "485, 81%" |
| `cvefixes/findings.json` | **26** | N/A | "4" |
| `defects4j/findings.json` | **50** | N/A | "50" ✓ |
| `v2.6-full-benchmark.json` | **687** (聚合) | — | "687" ✓ |

**关键发现**:
- Big-Vul 实际 584 条（非 485），unknown.c 占比 12.2%（非 81%）
- **CVEfixes 本地 26 条是合成占位数据**（commit_hash 为 `cve20200001fix0...` 格式），不是真实 CVEfixes 数据库内容
- 真正的 CVEfixes 数据集有 5,495 条 VFC

#### 3.1.2 数据集对比矩阵

| 数据集 | 规模 | 语言 | 真实性 | License | 标签质量 | SAST 适用性 |
|---|---|---|---|---|---|---|
| OWASP v1.2 | 2,740 | Java | 合成但可执行 | Apache 2.0 | 高 | ⭐⭐⭐⭐⭐ |
| Juliet C/C++ | 64,099 | C/C++ | 合成 | CC0 | 高 | ⭐⭐⭐⭐ |
| Juliet Java | 28,886 | Java | 合成 | CC0 | 高 | ⭐⭐⭐⭐ |
| **CVEfixes** | **5,495 VFC** | 多语言 | **真实** | 开源 | 中 | ⭐⭐⭐⭐ |
| Big-Vul | 188,636 函数 | C/C++ | **真实** | MIT | **低（25-54%）** | ⭐⭐ |
| **ICVul** | **15,396 函数** | 多语言 | **真实** | 开源 | **高（92%）** | ⭐⭐⭐⭐⭐ |
| Defects4J | 594 bugs | Java | 真实 | MIT | 高 | ⭐（非安全） |

**关键决策**: 弃用 Big-Vul（标签准确率仅 25-54%），改用 **CVEfixes + ICVul** 作为主干数据源。

来源: [Big-Vul 标签准确率](https://arxiv.org/html/2512.10485v2), [CVEfixes GitHub](https://github.com/jsamaze/CVEfixes), [OWASP Benchmark](https://owasp.org/www-project-benchmark/), [NIST SARD](https://samate.nist.gov/SARD/test-suites/112)

### 3.2 5000+ Findings 扩展路径

#### 3.2.1 推荐数据构成

| 类型 | 来源 | 占比 | 数量 | 用途 |
|---|---|---|---|---|
| 真实 CVE TP | CVEfixes + ICVul | 50% | 2500 | 主 recall 评估 |
| 真实 OSS FP | OSS 项目 SAST 扫描输出 | 30% | 1500 | precision 评估 |
| 合成 TP | Juliet / OWASP 子集 | 15% | 750 | CWE 覆盖补全 |
| 合成 FP | Juliet mixed 用例 | 5% | 250 | 边界案例测试 |

#### 3.2.2 多语言分配

| 语言 | 目标 findings 数 | 占比 | 数据来源 |
|---|---|---|---|
| C/C++ | 2,000 | 40% | CVEfixes + Juliet C/C++ 子集 |
| Java | 1,500 | 30% | OWASP v1.2 + Juliet Java + Defects4J（功能 bug 对照） |
| Python | 1,000 | 20% | CVEfixes Python 子集 + OWASP Python v0.1 |
| 其他（PHP/JS/C#） | 500 | 10% | SARD + CVEfixes |

### 3.3 标注成本分析

#### 3.3.1 全量人工标注成本

| 方案 | 每条时间 | 总工时 | 人力成本（$72/h） | 周期（2 人全职） |
|---|---|---|---|---|
| 保守（30 min/条） | 30 min | 2,500 h | **$180,000** | 31 周 |
| 中位（20 min/条） | 20 min | 1,667 h | **$120,000** | 21 周 |
| 乐观（15 min/条） | 15 min | 1,250 h | **$90,000** | 16 周 |

#### 3.3.2 半自动标注方案（推荐）

**方案**: 多工具 consensus 弱标注 + 抽样精标

| 阶段 | 工作量 | 工时 | 成本 |
|---|---|---|---|
| 4 工具批量运行 | 5000 findings × 4 工具 | 50 h（自动化） | $3,600 |
| Diff-based 自动过滤 | 脚本开发 + 运行 | 20 h | $1,440 |
| Uncertain 人工标注 | ~1250 findings × 20 min | 417 h | $30,000 |
| 抽样验证（20% of 3750） | 750 findings × 15 min | 188 h | $13,500 |
| **总计** | — | **675 h** | **$48,540** |

**节省**: 相比全量人工标注（$120K 中位），节省 **~60%**。

#### 3.3.3 多标注者一致性度量

| 指标 | 阈值 | 适用场景 |
|---|---|---|
| Cohen's Kappa（2 标注者） | >0.80 = 几乎完美 | 二分类 TP/FP |
| Krippendorff's Alpha（多标注者） | >0.80 = 高 | 多标注者 + 缺失值 |
| Fleiss' Kappa（>2 标注者） | >0.75 = 优秀 | 多标注者固定集合 |

**建议**: 至少 3 名标注者独立标注，目标 Krippendorff's Alpha ≥0.80。

### 3.4 统计显著性分析

#### 3.4.1 置信区间对比

使用 Wald 置信区间公式：`CI = p̂ ± z × √(p̂(1-p̂)/n)`，z=1.96（95%）：

| n | p̂=0.85 (precision) | 95% CI 宽度 | p̂=0.70 (recall) | 95% CI 宽度 |
|---|---|---|---|---|
| **687**（当前） | [0.824, 0.876] | **±2.6%** | [0.664, 0.736] | **±3.6%** |
| 1,000 | [0.828, 0.872] | ±2.2% | [0.671, 0.729] | ±2.9% |
| 2,000 | [0.833, 0.867] | ±1.7% | [0.678, 0.722] | ±2.2% |
| **5,000**（目标） | [0.840, 0.860] | **±1.0%** | [0.686, 0.714] | **±1.4%** |
| 10,000 | [0.843, 0.857] | ±0.7% | [0.690, 0.710] | ±1.0% |

**关键阈值**（Roth 2026 实证研究，2,047 数据集）:
- "**Seed inflation vanishes by n=5,000**" — 5000 是统计重要性拐点
- Cross-validation 95% 名义置信区间实际覆盖率仅 55%（严重欠覆盖）
- 推荐：n≥5000 + 独立 held-out test set（非 CV）

来源: [Roth 2026](https://arxiv.org/html/2604.04199v1), [Whittle et al. BMC Med Res Methodol 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12210805/)

#### 3.4.2 类别不平衡处理

| 指标 | 不平衡（1:4）下的偏差 | 缓解措施 |
|---|---|---|
| Accuracy | 虚高（多数类主导） | 不使用，改用 F1/MCC |
| F1 | 在 1:4 下仍稳健 | 主指标 |
| MCC（Matthews 相关系数） | 不平衡下最稳健 | 推荐补充指标 |

**建议**: 主基准保持 TP:FP = 1:1，额外构建 "realistic distribution" 子集（TP:FP = 1:4）用于操作效度评估。

### 3.5 数据质量保障

#### 3.5.1 标签泄露防范

| 类型 | SAST 场景表现 | 缓解 |
|---|---|---|
| Estimation leakage | 在全量数据上训练再测试 | 标准 train/test split |
| Selection leakage | 在 benchmark 上调参后再次测试 | n≥5000 + 独立 held-out |
| Memorization | LLM 类 SAST 记住训练时见过的漏洞 | 跨项目/跨 CVE-year split |
| Boundary leakage | 时间序列 split 错误 | 强制时间 split |

#### 3.5.2 Train/Validation/Test Split 策略

```
Train (60%, n=3000)
├─ 真实 CVE TP: 1500
├─ 真实 OSS FP: 900
├─ 合成 TP: 450
└─ 合成 FP: 150

Validation (20%, n=1000)
├─ 真实 CVE TP: 500
├─ 真实 OSS FP: 300
├─ 合成 TP: 150
└─ 合成 FP: 50

Test (20%, n=1000) — 冻结
├─ 真实 CVE TP: 500
├─ 真实 OSS FP: 300
├─ 合成 TP: 150
└─ 合成 FP: 50
```

**Split 方法**: `sklearn.model_selection.GroupShuffleSplit`，`group=project_id`，时间维度：test set CVE 日期 > train set。

### 3.6 风险矩阵

| # | 风险 | 概率 | 影响 | 严重度 | 缓解措施 |
|---|---|---|---|---|---|
| R1 | Big-Vul 标签噪声污染 | 高 | 高 | 🔴 | 弃用 Big-Vul，改用 ICVul（92% 准确率） |
| R2 | CVEfixes commit hash 错配 | 中 | 中 | 🟡 | 使用 Morefixes 置信度评分过滤 |
| R3 | 本地 cvefixes/findings.json 是合成占位数据 | 已确认 | 高 | 🔴 | 禁用当前数据，重新从 CVEfixes 数据库提取 |
| R4 | 全量标注成本超预算 | 高 | 中 | 🟡 | 采用半自动 consensus 弱标注（$48K vs $120K） |
| R5 | 合成数据虚高 SAST 性能 | 中 | 中 | 🟡 | 合成数据 ≤20%；报告 per-source-type 指标 |
| R6 | 时间维度数据泄露 | 中 | 高 | 🔴 | 强制时间 split；test set CVE 日期 > train |
| R7 | 类别不平衡扭曲指标 | 中 | 中 | 🟡 | 报告 MCC + per-class F1；构建平衡子集 |
| R8 | 同项目 findings 跨 train/test 泄露 | 中 | 高 | 🔴 | GroupShuffleSplit by project_id |
| R9 | 标注者一致性不足 | 中 | 中 | 🟡 | 3 标注者 + 仲裁流程；Alpha ≥0.80 |
| R10 | CWE 长尾分布 | 高 | 低 | 🟢 | Neyman 分层抽样；长尾 CWE oversample |

### 3.7 实施建议

**短期（2-4 周）**:
1. **数据源迁移**: CVEfixes 数据库重建（5,495 VFCs，8-10 小时）+ ICVul 数据集
2. **禁用当前 cvefixes/findings.json**（合成占位数据）
3. **修复 defects4j/ground_truth.json**（当前结构异常）

**中期（1-2 月）**:
1. 4 工具批量运行 → 自动弱标签
2. Diff-based + fixed-warnings 双重过滤
3. Uncertain 子集（~1250 条）3 标注者人工标注
4. 10% 抽样验证弱标签

**评估**:
- 主指标：F1 + MCC
- 报告：per-CWE × per-language × per-severity 三维 breakdown
- 置信区间：Wald 95% CI（n=5000 时 ±1.0%）

**决策**: ✅ **实施 T12** — 采用半自动标注方案（$48K），弃用 Big-Vul，以 CVEfixes + ICVul 为主干。

---

## 4. T17/T18 — Spec-driven Audit + Lean4 形式化验证风险评估

> **修复 Gap**: 无直接 Gap 修复，但提供"条件性 1 收敛"和"强收敛子集"的理论路径
> **理论依据**: [convergence-analysis.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-convergence-analysis.md)
> **调研方法**: 形式化验证工具对比 + 学术价值评估 + 算力无限假设分析

### 4.1 T17 Spec-driven Audit 可行性

#### 4.1.1 理论依据

当用户提供完整的规格说明(spec)时，在 spec 覆盖范围内实现 P=R=1, H=0 是理论上可行的，其依据来自**契约式设计(Design by Contract, DbC)** 理论（Bertrand Meyer, 1986）：

- **Precision=1**: 所有报告的 finding 都必须对应 spec 中的显式契约违反
- **Recall=1**: 在 spec 覆盖范围内，所有契约违反都必须被检测到
- **Hallucination=0**: 每个 finding 的判定依据来自 spec 的形式化条款

**关键约束**: 这一保证仅在 spec 覆盖范围内有效。Rice 定理 (1953) 证明了对于任意程序，所有非平凡的语义性质都是不可判定的。

来源: [Rice 定理](https://www.javacodegeeks.com/2026/04/the-halting-problem-rices-theoremand-the-walls-they-build.html), [Cousot 抽象解释](https://pcousot.github.io/talks/Cousot-slidesASIAN06_1-1.pdf)

#### 4.1.2 分层 Spec 格式建议

| Spec 层级 | 格式 | 适用场景 | 可验证性 | 自动化程度 |
|-----------|------|----------|----------|-----------|
| **L0: 接口级** | OpenAPI 3.1 / JSON Schema | API 契约验证 | 自动化（Schemathesis） | 高 |
| **L1: 行为级** | EARS (Easy Approach to Requirements Syntax) | 结构化需求声明 | 半自动（属性测试） | 中 |
| **L2: 状态机级** | TLA+ | 并发系统、状态转换 | 模型检验（TLC） | 中 |
| **L3: 契约级** | Hoare Triple / DbC annotations | 前置/后置条件、不变式 | 形式化验证（Dafny, F*, Lean4） | 中-高 |
| **L4: 全证明级** | Lean4 / Coq 定理 | 完整的函数正确性证明 | 交互式证明 | 低（需人工辅助） |

**推荐方案**: ADD 框架应支持 **L0-L3 的渐进式 spec 格式**，L0 作为最低门槛，L3 作为 T18 形式化验证的输入格式。

#### 4.1.3 业界类似工作对比

| 工具/方法 | Spec 格式 | 验证方式 | 自动化程度 | 局限性 |
|-----------|----------|----------|-----------|--------|
| **OpenAPI + Schemathesis** | OpenAPI 3.1 | 基于属性的契约测试 | 高 | 仅验证接口格式 |
| **Pact** | Consumer-driven contracts | 消费者驱动的契约测试 | 高 | 需要已知消费者 |
| **TLA+ + TLC** | TLA+ | 模型检验 | 中 | 状态空间爆炸 |
| **Dafny** | Hoare Triple annotations | SMT 求解（Z3） | 高 | 语言受限 |
| **F* (Project Everest)** | 依赖类型 + SMT | 类型系统 + Z3 | 中-高 | 学术性强 |
| **IcePick + Glacier** | TLA+ + 一阶逻辑契约 | 模型检验 + 可执行契约 | 中 | 研究阶段 |

来源: [OpenAPI 3.1 Contract Testing](https://qaskills.sh/blog/openapi-3-1-contract-testing-guide-2026), [IcePick](https://arxiv.org/html/2604.08633v1), [Dafny](https://dafny.org/latest/VerificationOptimization/VerificationOptimization), [F* Project Everest](https://project-everest.github.io/)

### 4.2 T18 Lean4 形式化验证子集可行性

#### 4.2.1 Lean4 CIC 类型检查可判定性

Lean4 基于**归纳构造演算 (Calculus of Inductive Constructions, CIC)**：
- **类型检查可判定**: 给定一个项和其声称的类型，可以在有限时间内机械地验证
- **证明项显式构造**: Lean4 构造显式的证明项传递给小型可信内核验证
- **多独立内核**: arena.lean-lang.org 托管了多个独立内核实现（C++ reference kernel、Rust nanoda、Lean lean4lean、Rust nanobruijn）

**重要技术差异**: Lean4 使用**定义证明无关性(definitional proof irrelevance)**作为默认公理，这导致 Lean4 失去了**主语归约(subject reduction)**和**定义相等可判定性**。

来源: [Lean4 FAQ](https://lean-lang.org/faq/), [Lean4 NFM 2026](https://leodemoura.github.io/static/nfm2026/)

#### 4.2.2 Lean4 vs 其他形式化验证工具对比

| 维度 | Lean4 | Coq (Rocq) | Isabelle/HOL | Dafny | F* |
|------|-------|-----------|--------------|-------|-----|
| **理论基础** | CIC (依赖类型) | CIC (依赖类型) | HOL (高阶逻辑) | 一阶逻辑 + SMT | 依赖类型 + SMT |
| **程序验证成熟度** | 中（快速增长） | 高（CompCert, 25年） | 高（seL4） | 高（auto-active） | 高（Project Everest） |
| **自动化程度** | 中（tactics + LLM） | 中（Ltac） | 高（Sledgehammer） | 高（Z3 自动） | 高（Z3 自动） |
| **代码提取** | ❌ 无（仅 eval） | ✅（OCaml/Haskell） | ✅（Haskell/Scala） | ✅（多语言） | ✅（C） |
| **学习曲线** | 中等（渐进式） | 陡峭 | 平缓 | 低（接近 Java） | 中等 |
| **LLM 辅助** | ⭐ 最强（AlphaProof） | 弱 | 弱 | 中 | 弱 |
| **生态规模** | 270K+ theorems (Mathlib) | 大（25年积累） | 大 | 中 | 中 |

**关键决策**: 以 **Lean4** 为主，**Dafny** 为 fallback。Dafny 在 miniF2F-Dafny 基准上展现了良好的 LLM 辅助验证能力（Claude Opus 4.6 达到 62.7% pass@4），且学习曲线显著低于 Lean4。

来源: [Lean4 NFM 2026](https://leodemoura.github.io/static/nfm2026/), [miniF2F-Dafny](https://arxiv.org/html/2512.10187v3), [形式化验证工具对比](https://blog.csdn.net/gitblog_01095/article/details/157412852)

#### 4.2.3 Python/Java 代码翻译为 Lean4 的难度

| 工具 | 输入 | 输出 | 成功率 | 方法 |
|------|------|------|--------|------|
| **Provepy** | Python 函数 + NL spec | Lean4 证明 | 实验性 | LLM + Lean 编译器反馈 |
| **code2lean** | Python 函数 | Lean4 完整文件 | 五重验证门控 | LLM proposer + 5 gates |
| **FVSpec** | Python PBT (Hypothesis) | Lean4 验证挑战 | **25%** | Agentic transpilation + LSP |
| **Goedel-Code-Prover** | Lean4 代码验证任务 | 证明 | **62%** (427 tasks) | 分层证明搜索 + RL |

**翻译难度评估**: 简单函数（纯函数）LLM 可自动翻译；复杂代码（可变状态、异常处理）需大量人工辅助。

来源: [Provepy](https://github.com/genie16/provepy), [code2lean](https://toooold.com/2026/05/07/code-to-lean.html), [FVSpec](https://www.themoonlight.io/es/review/fvspec-real-world-property-based-tests-as-lean-challenges), [Goedel-Code-Prover](https://arxiv.org/html/2603.19329v1)

#### 4.2.4 形式化子集占比估计

| 类别 | 估计占比 | 形式化可行性 |
|------|---------|-------------|
| 安全相关（taint, 注入, 越界, 空指针, 密码学） | ~20-30% | ✅ 高度可行 |
| 正确性相关（类型错误, 契约违反, 状态机违反） | ~15-25% | ✅ 可行 |
| 并发问题（竞争条件, 死锁） | ~5-10% | ⚠️ 部分可行 |
| 代码质量（风格, 复杂度, 可维护性） | ~30-40% | ❌ 不可行 |
| 性能问题 | ~10-15% | ❌ 不可行 |

**估计**: 形式化子集约占总 findings 的 **35-55%**（安全 + 正确性相关），远高于 5% 的阈值。

### 4.3 假设算力无限时的可解性

**结论**: 即使算力无限，Lean4 引入的增强任务也**不能保证**在有限时间内解决所有验证问题，但可以显著扩大可验证子集。

**理由**: Rice 定理证明了对于任意程序，所有非平凡的语义性质都是不可判定的——"throwing more hardware, more memory, or more model parameters at an undecidable problem doesn't help. The impossibility is mathematical, not technological."

**但是**，Cousot 的抽象解释理论提供了绕过不可判定性的路径：通过**正确近似**语义，如果近似是 sound 的且足够精确，则可以得到有效的验证结果。

#### 4.3.1 LLM 辅助证明的当前进展

| 系统 | 发布时间 | 成就 | 来源 |
|------|---------|------|------|
| **AlphaProof** | 2024.07 (Nature 2025.11) | IMO 2024 银牌（28/42） | [Nature](https://www.nature.com/articles/s41586-025-09833-y) |
| **DeepSeek-Prover-V2** | 2025.04 | miniF2F-test 88.9% | [arXiv:2504.21801](https://arxiv.org/abs/2504.21801) |
| **BFS-Prover-V2** | 2025.09 (NeurIPS 2025) | miniF2F 95.08% | [arXiv:2509.06493](https://arxiv.org/abs/2509.06493) |
| **Goedel-Code-Prover** | 2026.03 | **代码验证** 62%（427 tasks） | [arXiv:2603.19329](https://arxiv.org/html/2603.19329v1) |
| **LeanCopilot** | 2024.10 (ICML 2025) | 框架内 LLM 集成，74.2% Mathlib 自动化 | [arXiv:2404.12534](https://arxiv.org/abs/2404.12534) |

**关键趋势**: LLM 辅助证明在**数学竞赛**领域已接近金牌水平，但在**代码验证**领域仍处于早期阶段（Goedel-Code-Prover 62% 是当前 SOTA）。

### 4.4 学术价值评估

#### 4.4.1 "分层混合收敛"的新颖性

**核心贡献**: "分层混合收敛"——形式化子集强收敛 (P=R=1, H=0) + 非形式化子集有界收敛 (P,R<1, H≤ε)——是一个**新颖的学术贡献**。

**新颖性论证**:
1. 现有形式化验证工作（CompCert, seL4, Project Everest）都是**全验证或无验证**的二元模式
2. ADD 框架的独特视角：将形式化验证视为审计框架的一个**子集**
3. 收敛性度量：将 ML 评估指标 (P/R/H) 引入形式化验证领域

#### 4.4.2 完整推理链

**论文标题方向**: "From Rice's Theorem to Lean4: A Hierarchical Hybrid Convergence Framework for Code Audit"

1. **Rice 定理** (1953): 任意程序的非平凡语义性质不可判定 → 全自动验证不可能
2. **Cousot 抽象解释** (1977): 通过正确近似绕过不可判定性 → sound 但可能不精确
3. **Spec 限定范围**: 用户提供的 spec 将验证范围缩小 → 在 spec 范围内可判定
4. **Lean4 形式化验证**: 在 spec 范围内用 Lean4 实现强收敛 (P=R=1, H=0)
5. **分层混合收敛**: 形式化子集强收敛 + 非形式化子集有界收敛 → 统一的审计框架

#### 4.4.3 目标期刊/会议

| 会议/期刊 | 领域 | 匹配度 | 理由 |
|-----------|------|--------|------|
| **CAV** | 形式化验证 | ⭐⭐⭐⭐⭐ | 形式化验证的核心会议 |
| **TACAS** | 验证工具 | ⭐⭐⭐⭐⭐ | 验证工具和算法 |
| **OOPSLA** | PL 系统 | ⭐⭐⭐⭐⭐ | 面向实际应用的 PL 研究 |
| **POPL** | PL 理论 | ⭐⭐⭐⭐⭐ | 形式化验证 + PL 理论 |
| **ICFP** | 函数式编程 | ⭐⭐⭐⭐ | Lean4 是函数式语言 |
| **ICSE/FSE** | 软件工程 | ⭐⭐⭐⭐ | 代码审计的软件工程视角 |

**推荐**: 首选 **CAV** 或 **TACAS**（形式化验证核心会议），次选 **OOPSLA**（面向应用）。

### 4.5 风险矩阵

| 风险 | 概率 | 影响 | 风险等级 | 缓解措施 |
|------|------|------|---------|---------|
| **R1: Lean4 学习曲线过陡** | 中 | 高 | 🔴 | Fallback 到 Dafny（auto-active 验证） |
| **R2: Python→Lean4 翻译成功率低** | 高 | 高 | 🔴 | 限制形式化子集到简单纯函数；LLM 辅助翻译 |
| **R3: 证明维护成本过高** | 高 | 中 | 🟡 | 模块化证明结构；LLM 辅助证明修复 |
| **R4: 形式化子集占比 <5%** | 低 | 中 | 🟡 | 优先形式化安全关键 finding；学术价值不依赖占比 |
| **R5: spec 编写成本过高** | 中 | 高 | 🔴 | 提供 spec 模板和 LLM 辅助 spec 生成 |
| **R6: Lean4 生态变化快** | 中 | 中 | 🟡 | 锁定 Lean4 版本；关注 Lean FRO 路线图 |
| **R7: LLM 辅助证明不可靠** | 中 | 高 | 🔴 | 所有 LLM 生成的证明必须通过 Lean4 内核验证；禁止 `sorry` |
| **R8: T17 spec 格式标准化困难** | 中 | 高 | 🔴 | 采用现有标准（OpenAPI, EARS）；避免自定义 DSL |

### 4.6 T17 与 T18 的依赖关系

**T17 是 T18 的前置条件**:

```
T17 (Spec-driven Audit)
  ├── 提供 spec 格式定义 → T18 需要 spec 作为形式化验证的输入
  ├── 提供契约提取机制 → T18 需要契约作为 Lean4 定理的前提
  └── 提供 spec 覆盖范围界定 → T18 仅在覆盖范围内执行形式化验证

T18 (Lean4 形式化验证子集)
  └── 依赖 T17 的 spec 作为输入
```

**建议**: T17 必须先于 T18 实现，至少 T17 的 L0-L1 层级（OpenAPI + EARS）需要先就绪。

### 4.7 Fallback 方案

如果 Lean4 学习曲线过陡或翻译成功率过低：

| 方案 | 工具 | 自动化程度 | 学习曲线 | 表达力 | 适用场景 |
|------|------|-----------|---------|--------|----------|
| **Plan A (首选)** | Lean4 + LLM 辅助 | 中 | 中 | ⭐⭐⭐⭐⭐ | 全场景，学术价值最高 |
| **Plan B (fallback 1)** | Dafny + Z3 | 高 | 低 | ⭐⭐⭐ | auto-active 验证，工业友好 |
| **Plan C (fallback 2)** | F* + Z3 | 中-高 | 中 | ⭐⭐⭐⭐ | 密码学/安全验证 |
| **Plan D (fallback 3)** | TLA+ + 模型检验 | 中 | 中 | ⭐⭐⭐ | 并发/状态机验证 |
| **Plan E (最低)** | OpenAPI + Schemathesis | 高 | 极低 | ⭐⭐ | 接口契约验证 |

### 4.8 实施建议

**Phase 1 (0-3 个月): T17 L0-L1**
- 实现 OpenAPI 契约验证（基于 Schemathesis）
- 实现 EARS 属性测试生成
- 在 spec 覆盖范围内实现 P=R=1, H=0 的基础版本
- **预期成果**: 15-25% 的 finding 可达到强收敛

**Phase 2 (3-6 个月): T17 L2-L3 + T18 试点**
- 实现 TLA+ 模型检验集成
- 定义 Hoare Triple 契约格式
- T18 试点：选择 5-10 个安全关键函数，用 Lean4 + LLM 辅助验证
- **预期成果**: 30-40% 的 finding 可达到强收敛

**Phase 3 (6-12 个月): T18 扩展**
- 扩大 Lean4 形式化验证范围
- 开发自动化翻译流水线（Python → Lean4）
- 集成 LeanCopilot / LLMLean 辅助证明
- **预期成果**: 45-55% 的 finding 可达到强收敛

**Phase 4 (12+ 个月): 学术发表**
- 收集实验数据
- 撰写论文（目标 CAV/TACAS/OOPSLA）
- 开源工具链

**决策**: ✅ **实施 T17 L0-L1**（立即开始），✅ **T18 试点**（Phase 2 开始），始终保持 Dafny 作为 fallback。

---

## 5. T11/T8' — Java AST CFG + Joern 跨文件验证风险评估

> **修复 Gap**: G5（语言窄）+ G4（无跨文件）
> **完整调研文档**: [2026-08-12-T11-T8prime-feasibility-research.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-T11-T8prime-feasibility-research.md)
> **本章节为摘要 + 关键决策引用，详细技术分析见完整调研文档**

### 5.1 T11 — Java AST CFG 扩展

#### 5.1.1 方案对比与决策

| 方案 | 优势 | 劣势 | 决策 |
|------|------|------|------|
| **javalang** | 纯 Python | 2018 停更，Java 8+ 解析失败 | ❌ 弃用 |
| **tree-sitter-java** | 增量解析、错误恢复、跨语言统一 | 需自建 CFG | ✅ **推荐** |
| **Spoon** | 语义完整 | 引入 JVM 依赖 | ❌ 违反硬约束 |
| **JavaParser** | 有 Symbol Solver | 引入 JVM 依赖 | ❌ 违反硬约束 |
| **ANTLR Java grammar** | 灵活 | 需自己构建 CFG | ⚠️ 备选 |

**关键决策 D6**: T11 采用 **tree-sitter-java + 自建 CFG**，因为 javalang 自 2018 年停止维护，对 Java 8+ 语法（lambda、方法引用、record）解析失败率不可接受；Spoon/JavaParser 虽语义完整，但引入 JVM 依赖违反 ADD "Python ≥ 3.9，标准库优先" 的硬约束。

#### 5.1.2 Java CFG 构建的特殊挑战

| 挑战 | 难度 | 处理建议 |
|------|------|---------|
| 异常处理（try-catch-finally） | 中 | 按 Python 经验迁移，注意 finally 块的必执行语义 |
| 方法分派（virtual dispatch） | 🔴 高 | 属于 Tier 1 Joern 责任，T11 聚焦方法内部可达性 |
| 继承和多态 | 🔴 高 | 属于 Tier 1 Joern 责任 |
| Lambda 和 Stream | 中 | tree-sitter 可解析，CFG 构建需特殊处理 |
| Generics 类型擦除 | 低 | 不影响 CFG 结构 |

**工作量估算**: 约 8 天、1150 行代码，建议 "最小可行 CFG" 分阶段交付。

### 5.2 T8' — 深化 Joern 跨文件验证

#### 5.2.1 已识别的 5 个断裂

来自 `project_memory.md` 和 v2.7.3 审计：

| # | 断裂 | 位置 | 严重度 |
|---|------|------|--------|
| F1 | imp.file.head.name (带 .py) 和 imp.importedEntity (不带 .py) 节点名不匹配 | joern_cpg.py | 🔴 |
| F2 | verify_imports() 检测任意循环依赖而非特定模块对 | verify_findings.py | 🔴 |
| F3 | _find_joern_binary() 在 Windows 返回 None | joern_cpg.py | 🟠 |
| F4 | _build_joern_env() PATH override 是 dead code | joern_cpg.py | 🟠 |
| F5 | is_available() 在 Windows 短路为 False | joern_cpg.py | 🟠 |

#### 5.2.2 推荐修复路径

**双轨制**: 修复 + 重构

**Phase 1（1-2 天）**: 修复 5 个已识别断裂
- F1: 统一节点名（去除 .py 后缀）
- F3-F5: 修复 Windows 三链路断裂

**Phase 2（3-5 天）**: 重构 verify_imports()
- 从 "任意循环依赖检测" 改为 "特定模块对精确匹配"
- 使用 Joern 的 DEPTREE 或 CALLGRAPH 而非 IMPORTS

**工作量估算**: 约 6 天、330 行代码。

### 5.3 任务依赖关系

**T11 与 T8' 不存在硬依赖关系**，但建议 **T8' 优先于 T11 实施**：

```
T8' (Joern 深化) ──→ Java 通过 javasrc2cpg 获得 Tier 1 验证
                   │
                   └──→ T11 (Java AST CFG) 作为 Tier 2 fallback
```

**理由**: T8' 修复 Joern 跨文件能力后，Java 可通过 javasrc2cpg 获得 Tier 1 验证；T11 作为 Tier 2 fallback，可在 T8' 完成后再扩展，避免双重维护成本。

### 5.4 Joern CPG 稳定性评估

| 维度 | 评估 | 来源 |
|------|------|------|
| v4.0 flatgraph 架构 | ✅ 40% 内存节省 + 39% 性能提升 | Joern 官方 |
| TypeInferencePass Bug | ⚠️ 子类参数匹配 Bug (#5679) | [GitHub Issue](https://github.com/joernio/joern/issues/5679) |
| Python 前端 (pythonsrc) | ⚠️ 成熟度低于 C/Java | 实测 |
| Java 前端 (javasrc2cpg) | ✅ 成熟 | Joern 官方 |
| Windows/WSL2 稳定性 | ⚠️ v2.7.3 仍有残留断裂 | project_memory.md |

### 5.5 风险矩阵（摘要）

| 风险 | 概率 | 影响 | 严重度 | 缓解措施 |
|------|------|------|--------|---------|
| tree-sitter CFG 构建工作量被低估 | 中 | 高 | 🔴 | 分阶段交付，先 MVP 后增强 |
| verify_imports 重构引入新 Bug | 中 | 高 | 🔴 | TDD 覆盖 + 回归测试 |
| tree-sitter 依赖性质（build-time vs runtime） | 低 | 中 | 🟡 | 明确为 build-time 依赖 |
| Joern v4.x API 变化 | 中 | 中 | 🟡 | 锁定版本 + 兼容性测试 |
| Java 方法分派 CFG 合并复杂度 | 高 | 中 | 🟠 | 限定为方法内部可达性 |

**决策**: ✅ **T8' 优先于 T11 实施**。T8' 修复后 Java 可通过 Joern 获得 Tier 1 验证，T11 作为 Tier 2 fallback 后续扩展。

**详细技术分析**: 见 [2026-08-12-T11-T8prime-feasibility-research.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-T11-T8prime-feasibility-research.md)

---

## 6. 综合决策矩阵

### 6.1 任务优先级综合评估

| 任务 | 可行性 | 优先级 | 工作量 | Gap 修复 | 学术价值 | 综合 |
|------|--------|--------|--------|----------|----------|------|
| **T9'** Phase 1 | ✅ 高 | 🔴 P0 | 2-3 天 | G2 致命 | 中 | **立即** |
| **T8'** | ✅ 高 | 🟠 P1 | 6 天 | G4 严重 | 低 | **短期** |
| **T12** | ✅ 高 | 🟠 P1 | 2-4 周 | G9 中等 | 中 | **短期** |
| **T17** L0-L1 | ✅ 高 | 🟠 P1 | 1-3 月 | 无 | 中 | **中期** |
| **T11** | ✅ 中 | 🟡 P2 | 8 天 | G5 严重 | 低 | **中期** |
| **T17** L2-L3 | ✅ 中 | 🟡 P2 | 2-3 月 | 无 | 中-高 | **长期** |
| **T18** | ⚠️ 中 | 🟡 P2 | 6-12 月 | 无 | ⭐ 高 | **长期** |
| **T10** (IDE) | ✅ 中 | 🟢 P3 | 中 | G6 中等 | 低 | **远期** |
| **T14** (Rule Market) | ✅ 中 | 🟢 P3 | 中 | G8 中等 | 低 | **远期** |

### 6.2 推荐实施路线图

```
Phase 1 (立即, 0-1 周):
  └── T9' Phase 1 (Joern MVP) — 修复唯一致命 Gap G2
      └── 交付物: joern_cpg.py 扩展 + verify_findings.py L5 调度

Phase 2 (短期, 1-4 周):
  ├── T8' (Joern 深化) — 修复 G4 残余
  │   └── 交付物: 5 个断裂修复 + verify_imports 重构
  └── T12 (Benchmark 扩展) — 数据基础
      └── 交付物: CVEfixes 重建 + ICVul 集成 + 半自动标注流程

Phase 3 (中期, 1-3 月):
  ├── T17 L0-L1 (OpenAPI + EARS) — 条件性 1 收敛
  │   └── 交付物: spec 格式定义 + 契约提取 + 属性测试生成
  └── T11 (Java AST CFG) — 多语言验证精度
      └── 交付物: tree-sitter-java 集成 + Java CFGBuilder

Phase 4 (长期, 3-12 月):
  ├── T17 L2-L3 (TLA+ + Hoare Triple)
  │   └── 交付物: 模型检验集成 + 契约格式定义
  └── T18 (Lean4 试点 → 扩展) — 强收敛子集
      └── 交付物: 5-10 个安全关键函数形式化验证 + 论文草稿

Phase 5 (远期, 12+ 月):
  ├── T10 (VSCode 插件) — 体验提升
  ├── T14 (Rule Marketplace) — 生态建设
  └── T18 扩展 + 学术发表
```

### 6.3 资源分配建议

| Phase | 时间 | 核心任务 | 预期产出 |
|-------|------|---------|---------|
| Phase 1 | 0-1 周 | T9' Phase 1 | G2 致命 Gap 修复 |
| Phase 2 | 1-4 周 | T8' + T12 | G4 修复 + 5000+ benchmark |
| Phase 3 | 1-3 月 | T17 L0-L1 + T11 | 条件性 1 收敛 + Java 验证 |
| Phase 4 | 3-12 月 | T17 L2-L3 + T18 | 强收敛子集 + 论文 |
| Phase 5 | 12+ 月 | T10 + T14 + T18 扩展 | 生态 + 学术 |

### 6.4 关键里程碑

| 里程碑 | 时间 | 验收标准 |
|--------|------|---------|
| M1: G2 修复 | 1 周 | T9' Phase 1 交付，taint finding 三态验证 |
| M2: G4 修复 | 4 周 | T8' 完成，verify_imports 精确匹配 |
| M3: Benchmark 5000+ | 4 周 | T12 完成，置信区间 ±1.0% |
| M4: 条件性 1 收敛 | 3 月 | T17 L0-L1，spec 覆盖范围 P=R=1 |
| M5: Java 验证 | 3 月 | T11 完成，Java Tier 2 fallback |
| M6: 强收敛子集 | 12 月 | T18 试点，5-10 函数形式化验证 |
| M7: 论文发表 | 12+ 月 | CAV/TACAS/OOPSLA 投稿 |

---

## 7. 风险综合评估

### 7.1 跨任务风险依赖

```
T9' (taint 验证)
  ├── 依赖: T8' (Joern 修复) — T9' Phase 1 使用 Joern
  └── 风险传导: Joern Python 前端 bug → T9' 误报

T12 (benchmark 扩展)
  ├── 依赖: 无（独立）
  └── 风险传导: 标签噪声 → 所有依赖 benchmark 的任务受影响

T17 (spec-driven)
  ├── 依赖: 无（独立）
  └── 风险传导: spec 编写成本 → T18 缺少输入

T18 (Lean4)
  ├── 依赖: T17 (spec 格式)
  └── 风险传导: 翻译成功率 → 形式化子集占比

T11 (Java AST CFG)
  ├── 依赖: T8' (Joern 修复) — 建议 T8' 先完成
  └── 风险传导: tree-sitter CFG 工作量 → 延期
```

### 7.2 综合风险矩阵

| 风险类别 | 风险项 | 概率 | 影响 | 严重度 | 跨任务影响 |
|----------|--------|------|------|--------|-----------|
| **技术** | Joern Python 前端 bug | 高 | 高 | 🔴 | T9' + T8' |
| **技术** | Python→Lean4 翻译成功率 | 高 | 高 | 🔴 | T18 |
| **技术** | tree-sitter CFG 工作量 | 中 | 高 | 🔴 | T11 |
| **数据** | Big-Vul 标签噪声 | 已确认 | 高 | 🔴 | T12 |
| **数据** | 时间维度数据泄露 | 中 | 高 | 🔴 | T12 + 所有 benchmark 依赖任务 |
| **成本** | 全量标注成本超预算 | 高 | 中 | 🟡 | T12 |
| **成本** | Lean4 学习曲线 | 中 | 高 | 🔴 | T18 |
| **成本** | spec 编写成本 | 中 | 高 | 🔴 | T17 + T18 |
| **生态** | Lean4 生态变化快 | 中 | 中 | 🟡 | T18 |
| **集成** | verify_imports 重构 | 中 | 高 | 🔴 | T8' |

### 7.3 风险缓解策略汇总

1. **Joern Python 前端 bug**: Tier 2 AST fallback + 已知 bug 规避（类属性场景返回 None）
2. **Python→Lean4 翻译**: 限制形式化子集到简单纯函数 + LLM 辅助翻译 + Dafny fallback
3. **tree-sitter CFG 工作量**: 分阶段交付，先 MVP 后增强
4. **Big-Vul 标签噪声**: 弃用 Big-Vul，改用 ICVul（92% 准确率）
5. **时间维度数据泄露**: 强制时间 split + GroupShuffleSplit by project_id
6. **全量标注成本**: 半自动 consensus 弱标注（$48K vs $120K）
7. **Lean4 学习曲线**: Dafny fallback + LLM 辅助证明
8. **spec 编写成本**: spec 模板 + LLM 辅助生成 + 渐进式采用
9. **Lean4 生态变化**: 锁定版本 + 关注 Lean FRO 路线图
10. **verify_imports 重构**: TDD 覆盖 + 回归测试

---

## 8. 决策记录

### 8.1 关键决策汇总

| ID | 决策 | 理由 | 影响范围 |
|----|------|------|---------|
| **D1** | T9' 采用 L5 层架构，Joern 优先 + AST 兜底 | 复用现有降级机制，MVP 2-3 天可交付 | T9' |
| **D2** | T12 弃用 Big-Vul，改用 CVEfixes + ICVul | Big-Vul 标签准确率仅 25-54% | T12 |
| **D3** | T17 分层实施（L0-L4），从 OpenAPI 开始 | 渐进式采用，降低 spec 编写成本 | T17 |
| **D4** | T18 以 Lean4 为主，Dafny 为 fallback | Lean4 学术价值最高，Dafny 学习曲线低 | T18 |
| **D5** | T8' 优先于 T11 实施 | T8' 修复后 Java 可通过 Joern 获得 Tier 1 验证 | T8', T11 |
| **D6** | T11 采用 tree-sitter-java，非 javalang/Spoon | javalang 停更，Spoon 引入 JVM 依赖 | T11 |
| **D7** | T12 采用半自动标注方案（$48K） | 相比全量标注节省 60% 成本 | T12 |
| **D8** | T9' 三态验证结果（true/false/null） | 保守策略，verified=None 保守通过 | T9' |
| **D9** | T17 是 T18 的前置条件 | T18 需要 spec 作为形式化验证输入 | T17, T18 |
| **D10** | T18 目标会议: CAV/TACAS/OOPSLA | 形式化验证核心会议 | T18 |

### 8.2 待决策事项

| ID | 待决策 | 触发条件 | 选项 |
|----|--------|---------|------|
| **P1** | T18 是否升级为 Plan B (Dafny) | Lean4 翻译成功率 <20% | 继续 Lean4 / 切换 Dafny |
| **P2** | T12 是否公开 benchmark | T12 完成后 | Zenodo 发布 / 内部使用 |
| **P3** | T17 spec 格式标准化 | T17 L1 完成后 | 采用 EARS / 自定义 DSL |
| **P4** | T9' Phase 2 启动时机 | T9' Phase 1 benchmark 验证后 | 立即 / 等 T12 完成 |

---

## 9. 参考文档

### 9.1 内部文档

- [ROADMAP.md v3.0+ Reassessment](file:///f:/Coding/audit-driven-development/docs/ROADMAP.md)
- [2026-08-12-convergence-analysis.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-convergence-analysis.md) — 1 概率收敛研究
- [2026-08-12-T11-T8prime-feasibility-research.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-T11-T8prime-feasibility-research.md) — T11/T8' 完整调研
- [2026-08-12-framework-review-and-gap-analysis.md](file:///f:/Coding/audit-driven-development/docs/audit/2026-08-12-framework-review-and-gap-analysis.md) — 框架 review
- [2026-08-12-v2.8-short-term-improvements.md](file:///f:/Coding/audit-driven-development/docs/superpowers/specs/2026-08-12-v2.8-short-term-improvements.md) — v2.8 短期改进 spec
- [DEVLOG.md](file:///f:/Coding/audit-driven-development/docs/DEVLOG.md) — 开发日志

### 9.2 外部参考（关键来源）

**T9' Taint 验证**:
- [CodeQL TaintTracking](https://codeql.github.com/codeql-standard-libraries/java/semmle/code/java/dataflow/TaintTracking.qll/module.TaintTracking$TaintTracking.html)
- [Joern Data-Flow Steps](https://docs.joern.io/cpgql/data-flow-steps/)
- [Bond Paper (USENIX Security 2026)](https://www.usenix.org/system/files/conference/usenixsecurity26/sec26_prepub_peng-jiaqian.pdf)
- [PyFlow 论文](https://arxiv.org/abs/2608.07026)

**T12 Benchmark 扩展**:
- [CVEfixes GitHub](https://github.com/jsamaze/CVEfixes)
- [OWASP Benchmark](https://owasp.org/www-project-benchmark/)
- [NIST SARD](https://samate.nist.gov/SARD/test-suites/112)
- [Roth 2026 (Leakage types)](https://arxiv.org/html/2604.04199v1)
- [Big-Vul 标签准确率](https://arxiv.org/html/2512.10485v2)

**T17/T18 形式化验证**:
- [Lean4 NFM 2026](https://leodemoura.github.io/static/nfm2026/)
- [Lean4 FAQ](https://lean-lang.org/faq/)
- [Goedel-Code-Prover](https://arxiv.org/html/2603.19329v1)
- [miniF2F-Dafny](https://arxiv.org/html/2512.10187v3)
- [AlphaProof (Nature 2025)](https://www.nature.com/articles/s41586-025-09833-y)
- [OpenAPI 3.1 Contract Testing](https://qaskills.sh/blog/openapi-3-1-contract-testing-guide-2026)

**T11/T8' Java AST + Joern**:
- [2026-08-12-T11-T8prime-feasibility-research.md](file:///f:/Coding/audit-driven-development/docs/research/2026-08-12-T11-T8prime-feasibility-research.md) — 完整调研含 34 条 References

---

## 10. 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-08-12 | v1.0 | 初版创建。整合 4 个并行 subagent 调研结果（T9'/T12/T17/T18/T11/T8'），包含风险矩阵、决策记录、实施路线图。 |

---

**文档结束**

**核心建议**:
1. **立即**: T9' Phase 1（修复 G2 致命 Gap）
2. **短期**: T8'（修复 G4）+ T12（5000+ benchmark）
3. **中期**: T17 L0-L1（条件性 1 收敛）+ T11（Java 验证）
4. **长期**: T18（Lean4 强收敛子集）+ 学术发表（CAV/TACAS/OOPSLA）

