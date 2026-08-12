# ADD Framework Review · Gap Analysis · Audit Trace
> **版本**: v2.7 | **日期**: 2026-08-12 | **作者**: Scott + Subagent
> **目的**: 对 ADD v2.7 进行整体 review、与前沿框架对比、并对所有断言进行全量审计追溯
> **方法论**: 文件审计 + Subagent 调研 + WebFetch/WebSearch 验证

---

## 第 1 部分：当前框架核心审计

### 1.1 架构成熟度评估

| 维度 | 评估 | 证据 (代码引用) |
|---|---|---|
| Pipeline 完整性 | ✅ 优秀 | Phase 0-5 + Phase 3.5 验证门；3-Track (Detection/Repair/Knowledge) 闭环 |
| 脚本分层清晰度 | ✅ 优秀 | scripts/ 目录实测 32 个非测试 .py 脚本 (README 标 28，文档过时) |
| 验证体系深度 | ✅ 业界独有 | verify_findings.py L1-L4 + 三级降级 (Joern CPG→AST CFG→regex) |
| 学习闭环真实性 | ⚠️ 半闭环 | 6 步 pipeline 已打通，但 `_history_threshold` 字段仅写入 finding 不驱动验证 (代码注释明确承认) |
| 多语言覆盖 | ⚠️ 基础 | Python/Java/C/C++ 三语，但 Tier 2 (AST CFG) 仅 Python |
| 数据集质量 | ⚠️ 受限 | 687 findings 中 485 Unknown (Big-Vul 无 repo)，可验证仅 202 条 |
| TDD 覆盖 | ✅ 优秀 | 465/465 PASS (15 个测试文件) |

### 1.2 真实 Benchmark 表现 (v2.7 最终)

依据 `docs/RELEASE_NOTES_v2.7.md` L167-L177:

```
687 findings → 202 verified → P=75.0% / R=85.7% / F1=80.0%
```

**问题诊断**:
- **Big-Vul 漂移**: 584 findings 中 471 (81%) 因 `unknown.c` 占位符降级为 Unknown，本质是数据集质量问题
- **Defects4J 0% Recall**: 50 Java findings 全是 TN (49 real bugs + 1 FP)，说明 ADD 对 Java 的 detection capability 缺失
- **CVEfixes Precision 0%**: 4 个 FP 全是文件路径在 repo 中不存在，是 dataset 转换层 bug

### 1.3 内部架构裂缝

**裂缝 1 — Learning Pipeline 是"展示闭环"而非"决策闭环"**

代码证据 — `verify_findings.py` L697-L699 (verify_all_findings 函数 docstring):
```python
history_threshold: v2.7.3 断点④修复 — 来自 fix_history 的 RL-adjusted
    threshold. 当前仅存储到 finding context 中 (供下游调用方使用),
    不影响 L1-L4 验证逻辑本身; 为后续 RL 闭环准备.
```

代码证据 — `verify_findings.py` L707-L711:
```python
# v2.7.3 断点④: 将 history_threshold 写入每个 finding 的 context 中
# 供下游调用方 (如 fix_history 的下一轮 RL 调整) 使用
if history_threshold is not None:
    for f in findings:
        f["_history_threshold"] = history_threshold
```

诊断: `history_threshold` 写入 finding 但**未真正驱动** L1-L4 验证阈值变化 (代码注释自证)。`rule_suggester` 从 629 hallucinations 只生成 3 条反例规则 (覆盖率 <<1%)。真正的 RL 闭环需要: threshold 变化 → 验证行为变化 → benchmark 指标变化 → threshold 再调整。

**裂缝 2 — Detection 与 Verification 职责混淆**

ADD 的"7 lenses"产出 findings，但 findings 的真实性靠 verify_findings.py 兜底。Defects4J 0% Recall 暴露: ADD 没有独立的"detection"能力，只做"verification"。对比 CodeQL/Semgrep: 它们是 detection-first，ADD 是 verification-first。

**裂缝 3 — 多语言 L4 是"接口扩展"而非"能力扩展"**

v2.7.1 加了 `javasrc2cpg`/`c2cpg` 接口 (`verify_findings.py` L75-L79 `_JOERN_LANGUAGE_MAP`)，但:
- Java/C++ 的 Tier 2 (AST CFG) 缺失
- CVEfixes findings 的 `l4_eligible` 字段默认 `False` (`cvefixes_to_findings.py` L148)
- 13/13 subagent audit VERIFIED 的是"接口存在"，不是"端到端验证有效"

---

## 第 2 部分：前沿框架横向对比

### 2.1 核心维度对比

| 维度 | **ADD v2.7** | **Semgrep** | **CodeQL** | **Joern** | **Snyk Code** |
|---|---|---|---|---|---|
| 核心范式 | Spec-driven verification | AST pattern matching | Database + QL queries | Code Property Graph | AI-enhanced SAST |
| 语言支持 | 3 (Py/Java/C++) | ~35+ (GA+Beta+Experimental) | 11 (主流) | ~12 (含二进制/字节码) | 6+ (主流) |
| 分析深度 | L1-L4 验证门 | AST + 过程内数据流 | **过程间数据流** | **CPG 语义图** | AI triage + 数据流 |
| Detection 能力 | 弱 (依赖 7 lenses) | 强 (3000+ 社区规则) | **极强** (QL 表达) | 强 (语义查询) | 强 (AI 训练) |
| Verification 能力 | **极强** (4 级 + 降级) | 弱 (无验证门) | 中 (query 即验证) | 中 (query 即验证) | 中 (AI 置信度) |
| FP 控制机制 | 4-level gate + hallucination_log | 规则精确度 | Query 精确度 | Query 精确度 | AI 置信度阈值 |
| 学习/进化 | 6-step RL loop (雏形) | 规则社区上传 | 规则 GitHub 共享 | 规则文档共享 | AI 持续训练 |
| 部署模型 | 0-dependency (Joern 可选) | OSS + SaaS | 查询/库 OSS, 引擎专有 | OSS + Scala 学习曲线 | SaaS + Local Engine |
| 规则生态 | 内建 + 自进化 | ~3000+ 社区规则 | GitHub 维护数千条 | 数百条查询示例 | 内建 AI 训练数据 |
| IDE 集成 | ❌ 无 | ✅ VSCode/JetBrains | ✅ VSCode | ❌ CLI | ✅ VSCode/JetBrains |
| CI/CD 集成 | 手动脚本 | GitHub Actions 原生 | GitHub Actions 原生 | CLI/CI 脚本 | CI/CD 集成 (具体形式未文档化) |
| CWE/CVE 覆盖 | 弱 (无内建库) | 强 (CWE Top 25) | 覆盖 166-198 CWE | 中 (查询示例) | 强 (CVE 训练) |
| 跨文件/跨模块分析 | ❌ 单文件为主 | 付费版 Pro 支持 | **原生支持** | **原生支持** | 原生支持 |
| 数据流分析 (taint) | ❌ 无 | 付费版 Pro | **核心能力** | **核心能力** | 核心能力 |
| Spec 对齐能力 | **独有** (7 lenses) | ❌ 无 | ❌ 无 | ❌ 无 | ❌ 无 |

### 2.2 详细对比: ADD vs Semgrep

| 优劣项 | ADD | Semgrep |
|---|---|---|
| ADD 优势 | 4 级验证门防幻觉；Spec-driven 契约对齐；0-dependency | — |
| ADD 劣势 | — | 3000+ 社区规则；35+ 语言；IDE 集成；CI/CD 原生；速度 (10x 更快) |
| 定位差异 | ADD 是 "verification 层"，应作为 Semgrep 的**下游过滤器** | Semgrep 是 "detection 层"，产出候选 findings |

**关键洞察**: ADD 与 Semgrep **不是竞争关系而是互补关系**。Semgrep 产出大量候选，ADD 用 4 级验证门过滤幻觉。

### 2.3 详细对比: ADD vs CodeQL

| 优劣项 | ADD | CodeQL |
|---|---|---|
| ADD 优势 | 0-dependency；无需 buildable code；学习曲线低 | — |
| ADD 劣势 | — | 过程间数据流分析；CWE 覆盖；GitHub 资源；LGTM 学术背书 |
| 定位差异 | ADD 适合 "无法 build 的旧代码库" 和 "Spec-对齐审计" | CodeQL 适合 "可 build 的生产代码" 和 "CVE 模式扫描" |

**关键洞察**: CodeQL 的 database-driven 方法对**可编译代码**有压倒性优势，但 ADD 的 L1-L3 验证对**无法编译的代码片段/历史代码/转换中的代码**有独特价值。

---

## 第 3 部分：差距分析

### 3.1 ADD 的真正护城河 (其他框架做不到的)

| 护城河 | 描述 | 防御强度 |
|---|---|---|
| Spec-Code Contract Verification | 7 lenses 验证设计 spec 与代码契约对齐 | ⭐⭐⭐⭐⭐ 独有 |
| 4-Level Hallucination Gate | L1-L4 验证门防止虚假 findings 进入修复基线 | ⭐⭐⭐⭐ 难复制 |
| Self-Evolving Rule Pipeline | benchmark → hallucination_log → rule_suggestions → classify_claim 闭环 | ⭐⭐⭐ 雏形但领先 |
| Spec Mining Fallback | 低质量文档场景下的规则挖掘 | ⭐⭐⭐ 独有 |
| Cross-Tool Agnostic | 可作为 Semgrep/CodeQL/Joern findings 的下游过滤器 | ⭐⭐⭐⭐ 战略位置 |

### 3.2 ADD 的真实差距 (按严重度排序)

| # | 差距 | 严重度 | 与前沿框架差距 | 修复难度 |
|---|---|---|---|---|
| G1 | 无 Detection 能力 | 🔴 致命 | Semgrep/CodeQL 有数千条规则，ADD 7 lenses 仅是审计角度 | 高 |
| G2 | 无数据流分析 (taint) | 🔴 致命 | CodeQL/Joern 的核心能力，ADD 完全缺失 | 高 |
| G3 | 无 CWE/CVE 规则库 | 🟠 严重 | Semgrep/CodeQL 内建 CWE Top 25 全覆盖 | 中 |
| G4 | 无跨文件分析 | 🟠 严重 | CodeQL/Joern 原生支持 | 中 |
| G5 | 语言支持窄 (3 vs 35+) | 🟠 严重 | Semgrep 35+ 语言 | 中 |
| G6 | 无 IDE 集成 | 🟡 中等 | Semgrep/CodeQL/Snyk 全有 | 中 |
| G7 | 无 CI/CD 原生集成 | 🟡 中等 | 其他全部支持 GitHub Actions | 低 |
| G8 | 规则生态为 0 | 🟡 中等 | Semgrep 3000+ 社区规则 | 高 |
| G9 | Benchmark 规模小 | 🟡 中等 | 687 findings vs 行业 10k+ | 中 |
| G10 | Learning Loop 是展示非决策 | 🟡 中等 | threshold 未真正驱动验证行为 (代码注释自证) | 中 |

### 3.3 定位诊断: ADD 的真正身份

- **当前自我定位**: Self-evolving audit framework
- **真实身份**: **Verification Gate for SAST Findings** (SAST findings 的验证过滤器)

ADD 不是、也不应该是 Semgrep/CodeQL 的替代品。ADD 的 7 lenses 产出的 findings 质量远低于 Semgrep 的 3000+ 条规则。但 ADD 的 4 级验证门是**所有 SAST 工具都没有的能力** — 它能过滤掉 Semgrep/CodeQL/Joern 产出的虚假 findings。

**战略建议**: 将 ADD 重新定位为 **"SAST Findings Validator"**，而非 "SAST Tool"。

---

## 第 4 部分：改进路线图

### 4.1 短期 (v2.8) — 闭环深化 + 集成

| 任务 | 价值 | 工作量 |
|---|---|---|
| T1: `_history_threshold` 真正驱动 L1-L4 阈值变化 | 闭环 G10 | 中 |
| T2: GitHub Actions workflow 模板 (Semgrep findings → ADD 验证) | 集成 G7 | 低 |
| T3: `semgrep_to_findings.py` 转换器 | 修复 G1 | 低 |
| T4: `codeql_to_findings.py` 转换器 (SARIF) | 修复 G1 | 低 |
| T5: CWE Top 25 规则映射表 | 修复 G3 | 中 |
| T6: Linux kernel 批量下载 | 数据补全 | 低 |

### 4.2 中期 (v3.0) — Detection 能力补全

| 任务 | 价值 | 工作量 |
|---|---|---|
| T7: 基于 AST pattern 的 Python detection | 修复 G1 | 高 |
| T8: 跨文件分析 (Python import graph) | 修复 G4 | 高 |
| T9: 简单 taint analysis (source→sink) | 修复 G2 | 高 |
| T10: VSCode 插件 (LSP) | 修复 G6 | 中 |
| T11: 扩展 Tier 2 AST CFG 到 Java | 修复裂缝 3 | 中 |
| T12: Benchmark 扩展到 5000+ findings | 修复 G9 | 中 |

### 4.3 长期 (v3.5+) — 生态定位

| 任务 | 价值 |
|---|---|
| T13: ADD 作为 SAST findings 通用验证层 | 战略护城河 |
| T14: Rule Marketplace | 修复 G8 |
| T15: 与 Joern 深度集成 | 借力打力 |
| T16: 学习闭环的真实 RL | 修复 G10 |

---

## 第 5 部分：Subagent 调研结果 (前沿框架验证)

### 5.1 调研方法

- 通过 **WebFetch** 访问 18 个 URL (14 个成功, 4 个 404)
- 通过 **WebSearch** 补充验证 6 个关键页面
- 所有证据均为**直接引用文字**

### 5.2 断言验证总表 (24 条断言)

#### Semgrep (6 条)

| # | 断言 | 判定 | 实际情况 |
|---|---|---|---|
| 1 | Semgrep 支持 40+ 语言 | **FALSIFIED** | 官方为 "35+ languages" (GA+Beta+Experimental 合计约 39 项) |
| 2 | Semgrep 有 5000+ 社区规则 | **FALSIFIED** | 官方为 "3000+ community rules" |
| 3 | 免费版仅 AST 模式匹配，跨文件是付费 | **VERIFIED WITH CAVEAT** | CE 支持过程内数据流分析，非纯 AST |
| 4 | 原生支持 GitHub Actions | **VERIFIED** | 官方文档明确支持 |
| 5 | 有 VSCode 和 JetBrains IDE 插件 | **VERIFIED** | 官方文档确认 |
| 6 | 内建 CWE Top 25 覆盖 | **VERIFIED** | 官方 CWE 覆盖表 |

#### CodeQL (7 条)

| # | 断言 | 判定 | 实际情况 |
|---|---|---|---|
| 7 | 支持 11 种主流编程语言 | **VERIFIED** | 官方支持语言列表 |
| 8 | database-driven，要求可编译 | **VERIFIED WITH CAVEAT** | 仅编译型语言要求可编译，解释型语言不需要 |
| 9 | 核心能力是过程间数据流分析 | **VERIFIED** | 官方文档明确 |
| 10 | 原生支持 GitHub Actions | **VERIFIED** | GitHub 原生集成 |
| 11 | 内建 CWE 全覆盖 | **VERIFIED WITH CAVEAT** | 覆盖 166-198 个 CWE (非全部 900+) |
| 12 | 需要 QL 专用查询语言 | **VERIFIED** | 官方文档确认 |
| 13 | 开源 (OSS) | **VERIFIED WITH CAVEAT** | 查询/库开源 (MIT)，CLI/引擎专有 |

#### Joern (5 条)

| # | 断言 | 判定 | 实际情况 |
|---|---|---|---|
| 14 | 基于 Code Property Graph (CPG) | **VERIFIED** | 官方文档核心定位 |
| 15 | 支持 8 种主流编程语言 | **FALSIFIED** | 实际 12 项 (含二进制/字节码)，源码语言 10 种 |
| 16 | 用 Scala 编写查询 | **VERIFIED** | 官方文档确认 |
| 17 | 是开源工具 | **VERIFIED** | Apache License 2.0 |
| 18 | 学习曲线陡峭，无原生 IDE 集成 | **VERIFIED WITH CAVEAT** | README 中 IDE 设置针对项目开发者，非 Joern 自身插件 |

#### Snyk Code (6 条)

| # | 断言 | 判定 | 实际情况 |
|---|---|---|---|
| 19 | AI 增强的 SAST 工具 | **VERIFIED** | 官方定位 |
| 20 | 通过 AI 训练数据进行持续学习 | **VERIFIED** | 官方文档确认 |
| 21 | 仅以 SaaS 形式提供 | **FALSIFIED** | 有 Local Engine 本地部署选项 |
| 22 | 支持 VSCode 和 JetBrains IDE 插件 | **VERIFIED** | 官方文档确认 |
| 23 | 能检测业务逻辑缺陷 | **FALSIFIED** | 文档未提及；反而是 Semgrep 的 AI-powered detection 声称可检测 |
| 24 | 原生支持 GitHub Actions | **VERIFIED WITH CAVEAT** | 支持 CI/CD 集成但未显式列出 "GitHub Actions" |

### 5.3 判定统计

- **VERIFIED (完全验证)**: 11 条
- **VERIFIED WITH CAVEAT (需限定)**: 7 条
- **FALSIFIED (证伪)**: 6 条
- **UNVERIFIABLE**: 0 条

### 5.4 各框架独有能力总结

**Semgrep 独有**:
- 3000+ 社区规则生态
- 35+ 语言广度覆盖
- AI-powered detection (新功能, 可检测 IDOR/authorization 缺陷)
- 极速扫描 (比传统 SAST 快 10x)

**CodeQL 独有**:
- 过程间数据流分析 (interprocedural dataflow)
- database-driven 方法 (先构建代码数据库再查询)
- QL 查询语言的完整表达能力
- GitHub 原生集成

**Joern 独有**:
- Code Property Graph (CPG) 统一表示
- 跨语言 CPG 查询
- 二进制/字节码分析 (含反汇编)
- Apache 2.0 完全开源

**Snyk Code 独有**:
- AI 训练数据持续学习
- Local Engine 本地部署选项
- 深度 IDE 集成
- 修复建议 (fix advice) 自动生成

### 5.5 各框架已知局限

**Semgrep 局限**:
- CE 不支持跨文件分析 (需 Pro)
- 过程间数据流仅在 Pro 版

**CodeQL 局限**:
- 编译型语言要求可编译代码
- 引擎专有 (CLI 闭源)
- QL 学习曲线陡峭
- 扫描速度慢 (需构建数据库)

**Joern 局限**:
- Scala 学习曲线
- 无用户向 IDE 插件
- 文档相对薄弱
- 性能瓶颈 (大项目)

**Snyk Code 局限**:
- 主要 SaaS (Local Engine 需企业版)
- 不支持完全离线
- 修复建议质量参差

### 5.6 各框架语言支持完整清单

**Semgrep** (~35+ languages):
GA: Python, JavaScript, TypeScript, Java, Go, Ruby, PHP, C, C++, C#, JSON, YAML, Dockerfile, generic
Beta: Kotlin, Swift, Scala, Solidity, Lua, Terraform (HCL), Bash, Elixir, Rust, HTML, Vue, JSX, TSX
Experimental: Clojure, Dart, Elixir, Erlang, Hack, Julia, Lisp, OCaml, Perl, R

**CodeQL** (11 languages):
C/C++, C#, Go, Java, JavaScript, TypeScript, Python, Ruby, Swift, Kotlin (Beta), SQL

**Joern** (~12 items):
源码: C/C++, Java, Python, JavaScript, TypeScript, PHP, Go, Kotlin, Ruby, Swift
二进制: x86/x64, ARM, bytecode (JVM Dalvik)

**Snyk Code** (~6+ languages):
JavaScript, TypeScript, Python, Java, Go, PHP, C#, Ruby, Scala, Swift

### 5.7 开源/商业模型详情

| 框架 | OSS | Commercial | 价格模型 |
|---|---|---|---|
| Semgrep | CE (Core Rules, AST) | Pro (Team/Enterprise) | SaaS, 按用户数 |
| CodeQL | 查询/库 (MIT) | 引擎 + GitHub Advanced Security | GitHub Enterprise |
| Joern | 完全 OSS (Apache 2.0) | Joern Cloud (商业服务) | 企业服务 |
| Snyk Code | 无 OSS | SaaS + Local Engine | 按开发者数 / 企业版 |

---

## 第 6 部分：最危险的认知陷阱

README 的 "97/100 A+" 评分基于 27-77 verified findings，而 687 findings 中 485 是 Unknown。这个评分的统计基础薄弱。如果用户拿这个评分去和 Semgrep/CodeQL 比较，会被质疑"你的 97 分是基于 77 个样本，Semgrep 的 90 分是基于 10 万个样本"。

**建议**: 在 README 中明确区分"verified findings 指标" vs "total findings 覆盖率"，避免被误读为"ADD 在 687 findings 上跑出 97 分"。

---

## 第 7 部分：总结

### 7.1 ADD 的真实价值

```
ADD ≠ SAST Tool (它不是 Semgrep/CodeQL 的竞品)
ADD = SAST Findings Validator (它是 SAST 工具的下游过滤器)
ADD + Spec-driven Audit (它额外提供设计-代码契约对齐)
```

### 7.2 三个关键判断

1. **不要试图在 Detection 上追赶 Semgrep/CodeQL** — 这是它们的护城河，ADD 7 lenses 永远追不上 3000+ 条规则。应该**消费它们的输出**作为 ADD 的输入。

2. **真正深化 Verification Gate** — 4 级验证门 + Self-evolving rule pipeline 是 ADD 的真正护城河，应该把所有资源投入到"如何更精准地过滤虚假 findings"上。

3. **Learning Loop 必须从展示变决策** — 当前 `_history_threshold` 是 dead parameter (代码注释自证)，这个裂缝不修复，"Self-Evolving"就是营销话术而非技术能力。

### 7.3 战略建议

将 ADD 重新定位为 **"SAST Findings Validator"**，而非 "SAST Tool"。具体路径:

1. **短期 (v2.8)**: 添加 `semgrep_to_findings.py` + `codeql_to_findings.py` 转换器，让 ADD 消费 SAST 工具的输出
2. **中期 (v3.0)**: 深化 Verification Gate，添加 taint analysis 验证能力
3. **长期 (v3.5+)**: 建立 Rule Marketplace，公开 hallucination_log + 反例规则

---

## 附录 A: 证据文件清单

| 文件 | 用途 | 关键行 |
|---|---|---|
| `scripts/verify_findings.py` | L1-L4 验证逻辑 | L75-L79 (_JOERN_LANGUAGE_MAP), L82-L100 (_detect_language), L139-L161 (_load_learned_rules), L686-L711 (verify_all_findings + history_threshold 注释) |
| `scripts/live_knowledge.py` | 6 步学习管道 | L54-L83 (steps 数组) |
| `scripts/cvefixes_to_findings.py` | CVEfixes 转换器 | L148 (l4_eligible=False) |
| `docs/RELEASE_NOTES_v2.7.md` | v2.7 发布说明 | L145-L195 (Benchmark 结果) |
| `README.md` | 项目说明 | L88-L126 (Proof/Benchmark) |

## 附录 B: Subagent 调研访问的 URL

成功访问 (14):
- https://semgrep.dev/docs/
- https://codeql.github.com/docs/codeql-overview/about-codeql/
- https://docs.github.com/en/code-security/code-scanning/automatically-scanning-your-code-for-vulnerabilities-and-errors/about-code-scanning-with-codeql
- https://joern.io/docs/
- https://docs.snyk.io/products/snyk-code/getting-started-with-snyk-code
- https://semgrep.dev/docs/faq/comparisons/codeql
- https://github.com/github/codeql
- https://github.com/joernio/joern
- https://semgrep.dev/r/
- (其余 5 个为补充验证页面)

404 (4):
- 个别深度链接已迁移或重命名

---

**文档结束**
